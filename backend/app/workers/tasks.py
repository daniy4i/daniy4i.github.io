from collections import Counter, defaultdict
from pathlib import Path
import json
import subprocess
import tempfile
import zipfile

import cv2
import numpy as np
import pandas as pd
from sqlalchemy import select

from app.core.logging import logger
from app.db.session import SessionLocal
from app.ml.heuristics import bike_proximity_confidence, build_windows, close_following_confidence, congestion_score, cut_in_confidence
from app.models.entities import AnalyticsWindow, Event, Job, Track
from app.services.data_product import build_marketplace_payload, hash_payload
from app.services.storage import download_file, upload_bytes
from app.workers.artifacts import ARTIFACT_NAMES, artifact_entry, artifact_key
from app.workers.datapack import DATAPACK_VERSION, compute_window_metrics, contains_plate_like_keys
from app.workers.celery_app import celery_app

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None

TARGET_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}
TRAIL_LENGTH = 20
def _blur_privacy(frame: np.ndarray) -> np.ndarray:
    h, _ = frame.shape[:2]
    roi = frame[int(h * 0.2): int(h * 0.8), :]
    frame[int(h * 0.2): int(h * 0.8), :] = cv2.GaussianBlur(roi, (21, 21), 20)
    return frame


def _safe_conf(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 3)))


def _draw_detection(frame: np.ndarray, det: dict, trail: list[tuple[float, float]]) -> None:
    x1 = int(det["xc"] - det["w"] / 2)
    y1 = int(det["yc"] - det["h"] / 2)
    x2 = int(det["xc"] + det["w"] / 2)
    y2 = int(det["yc"] + det["h"] / 2)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (77, 255, 196), 2)
    label = f"ID {det['track_id']} {det['class']} {det['conf']:.2f}"
    cv2.putText(frame, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (77, 255, 196), 2)
    if len(trail) >= 2:
        pts = np.array(trail[-TRAIL_LENGTH:], dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], isClosed=False, color=(230, 230, 230), thickness=2)


def _encode_preview_h264(src_path: str, out_path: str) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        src_path,
        "-vf",
        "scale=-2:720,fps=15",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        "2200k",
        "-movflags",
        "+faststart",
        "-an",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_job",
    queue="video",
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_kwargs={"max_retries": 3},
)
def process_job(self, job_id: int):
    db = SessionLocal()
    job = db.get(Job, job_id)
    if not job:
        return

    job.status = "running"
    db.commit()

    with tempfile.TemporaryDirectory() as td:
        src = str(Path(td) / "src.mp4")
        preview_raw_path = str(Path(td) / "preview_raw.mp4")
        preview_path = str(Path(td) / ARTIFACT_NAMES["preview"])
        summary_path = str(Path(td) / ARTIFACT_NAMES["summary"])
        events_path = str(Path(td) / ARTIFACT_NAMES["events"])
        events_csv_path = str(Path(td) / ARTIFACT_NAMES["events_csv"])
        tracks_path = str(Path(td) / ARTIFACT_NAMES["tracks"])
        tracks_csv_path = str(Path(td) / ARTIFACT_NAMES["tracks_csv"])
        windows_parquet_path = str(Path(td) / ARTIFACT_NAMES["windows_parquet"])
        windows_csv_path = str(Path(td) / ARTIFACT_NAMES["windows_csv"])
        datapack_zip_path = str(Path(td) / ARTIFACT_NAMES["data_pack_zip"])

        download_file(job.storage_key, src)

        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            raise RuntimeError("Unable to open uploaded video")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        sample_every = max(1, int(fps / max((job.settings_json or {}).get("fps_sampled", 5), 1)))
        job.fps_sampled = int(round(fps / sample_every))
        job.duration_s = total_frames / max(fps, 1)

        model = YOLO("yolov8n.pt") if YOLO else None

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(preview_raw_path, fourcc, max(1, job.fps_sampled), (frame_width, frame_height))

        samples: list[dict] = []
        track_history: dict[int, list[tuple[float, float]]] = defaultdict(list)
        per_track_points: dict[int, list[dict]] = defaultdict(list)

        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_idx % sample_every != 0:
                frame_idx += 1
                continue

            t = frame_idx / max(fps, 1)
            detections: list[dict] = []
            annotated_frame = frame.copy()

            if model:
                result = model.track(frame, persist=True, verbose=False)[0]
                if result.boxes is not None and len(result.boxes):
                    boxes = result.boxes
                    ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
                    xys = boxes.xywh.cpu().numpy()
                    confs = boxes.conf.cpu().tolist() if boxes.conf is not None else [0.0] * len(boxes)

                    for i, box in enumerate(boxes):
                        cls_name = result.names[int(box.cls[0])]
                        if cls_name not in TARGET_CLASSES:
                            continue

                        tid = ids[i] if i < len(ids) else None
                        x, y, w, h = xys[i]
                        area = float(max(1.0, w * h))
                        area_ratio = area / float(max(1, frame_width * frame_height))
                        track_id = int(tid) if tid is not None else -1

                        det = {
                            "class": cls_name,
                            "track_id": track_id,
                            "t": t,
                            "xc": float(x),
                            "yc": float(y),
                            "w": float(w),
                            "h": float(h),
                            "conf": float(confs[i]),
                            "area": area,
                            "area_ratio": area_ratio,
                        }
                        detections.append(det)

                        if track_id >= 0:
                            per_track_points[track_id].append(det)
                            history = track_history[track_id]
                            history.append((float(x), float(y)))
                            _draw_detection(annotated_frame, det, history)

            motions = []
            for points in per_track_points.values():
                if len(points) >= 2 and abs(points[-1]["t"] - t) < (2 * sample_every / max(fps, 1)):
                    dx = points[-1]["xc"] - points[-2]["xc"]
                    dy = points[-1]["yc"] - points[-2]["yc"]
                    motions.append(float(np.hypot(dx, dy)))
            avg_motion = float(np.mean(motions)) if motions else 0.0

            samples.append({
                "t": t,
                "active_tracks": len({d["track_id"] for d in detections if d["track_id"] >= 0}),
                "motion": avg_motion,
            })

            annotated_frame = _blur_privacy(annotated_frame)
            writer.write(annotated_frame)
            frame_idx += 1

        cap.release()
        writer.release()

        _encode_preview_h264(preview_raw_path, preview_path)

        db.query(Event).filter(Event.job_id == job_id).delete()
        db.query(Track).filter(Track.job_id == job_id).delete()

        track_rows_points: dict[int, list[dict]] = {}
        for _, pts in per_track_points.items():
            if not pts:
                continue
            class_name = pts[0]["class"]
            track = Track(
                job_id=job_id,
                class_name=class_name,
                start_t=pts[0]["t"],
                end_t=pts[-1]["t"],
                bbox_stats_json={"max_area": max(p["area"] for p in pts), "mean_area": float(np.mean([p["area"] for p in pts]))},
                motion_stats_json={"points": len(pts)},
            )
            db.add(track)
            db.flush()
            track_rows_points[track.id] = pts

            if class_name in VEHICLE_CLASSES:
                cut_conf = _safe_conf(cut_in_confidence(pts, frame_width))
                if cut_conf > 0.2:
                    db.add(Event(job_id=job_id, track_id=track.id, type="cut_in", timestamp=pts[-1]["t"], confidence=cut_conf, details_json={"definition": "central zone crossing + fast area growth"}))

                close_conf = _safe_conf(close_following_confidence(pts, frame_width))
                if close_conf > 0.2:
                    db.add(Event(job_id=job_id, track_id=track.id, type="close_following_proxy", timestamp=pts[-1]["t"], confidence=close_conf, details_json={"definition": "large centered bbox sustained"}))

            if class_name == "bicycle":
                bike_conf = _safe_conf(bike_proximity_confidence(pts, frame_width))
                if bike_conf > 0.2:
                    db.add(Event(job_id=job_id, track_id=track.id, type="bike_proximity_lane_share_proxy", timestamp=pts[-1]["t"], confidence=bike_conf, details_json={"definition": "bicycle near ego-forward center"}))

        db.query(AnalyticsWindow).filter(AnalyticsWindow.job_id == job_id).delete()
        analytics_rows = []
        for w in build_windows(samples, window_s=5):
            score = congestion_score(w["active_tracks"], w["avg_motion"])
            metrics = compute_window_metrics(w["active_tracks"], w["avg_motion"])
            analytics_rows.append({
                "datapack_version": DATAPACK_VERSION,
                "t_start": w["t_start"],
                "t_end": w["t_end"],
                "active_tracks": w["active_tracks"],
                "avg_motion": round(w["avg_motion"], 2),
                "congestion_score": score,
                **metrics,
            })
            db.add(AnalyticsWindow(
                job_id=job_id,
                t_start=w["t_start"],
                t_end=w["t_end"],
                congestion_score=score,
                counts_json={"active_tracks": w["active_tracks"]},
                motion_json={"avg_motion": round(w["avg_motion"], 2)},
            ))

        events = db.scalars(select(Event).where(Event.job_id == job_id)).all()
        tracks = db.scalars(select(Track).where(Track.job_id == job_id)).all()
        for event in events:
            event.clip_key = artifact_key(job_id, ARTIFACT_NAMES["preview"])

        class_counts = Counter(track.class_name for track in tracks)
        event_counts = Counter(event.type for event in events)

        with open(events_path, "w", encoding="utf-8") as f:
            for event in events:
                row = {
                    "datapack_version": DATAPACK_VERSION,
                    "id": event.id,
                    "track_id": event.track_id,
                    "type": event.type,
                    "timestamp": event.timestamp,
                    "confidence": event.confidence,
                    "details": event.details_json,
                    "clip_key": event.clip_key,
                    "review_status": event.review_status,
                }
                if contains_plate_like_keys(row):
                    raise RuntimeError("Data pack event export contains plate-like keys")
                f.write(json.dumps(row) + "\n")

        events_df = pd.DataFrame([
            {
                "datapack_version": DATAPACK_VERSION,
                "event_id": event.id,
                "type": event.type,
                "timestamp": event.timestamp,
                "confidence": event.confidence,
                "track_id": event.track_id,
                "details_json": json.dumps(event.details_json),
                "clip_key": event.clip_key,
                "review_status": event.review_status,
            }
            for event in events
        ])
        events_df.to_csv(events_csv_path, index=False)

        with open(tracks_path, "w", encoding="utf-8") as f:
            for track in tracks:
                points = track_rows_points.get(track.id) or []
                sampled_traj = [{"t": p["t"], "x": p["xc"], "y": p["yc"]} for p in points[:: max(1, len(points) // 20 or 1)]]
                row = {
                    "datapack_version": DATAPACK_VERSION,
                    "id": track.id,
                    "class": track.class_name,
                    "start_t": track.start_t,
                    "end_t": track.end_t,
                    "bbox_stats": track.bbox_stats_json,
                    "motion_stats": track.motion_stats_json,
                    "trajectory_sampled": sampled_traj,
                }
                if contains_plate_like_keys(row):
                    raise RuntimeError("Data pack track export contains plate-like keys")
                f.write(json.dumps(row) + "\n")

        tracks_df = pd.DataFrame([
            {
                "datapack_version": DATAPACK_VERSION,
                "track_id": track.id,
                "class": track.class_name,
                "start_t": track.start_t,
                "end_t": track.end_t,
                "bbox_stats_json": json.dumps(track.bbox_stats_json),
                "motion_stats_json": json.dumps(track.motion_stats_json),
                "trajectory_sampled": json.dumps([
                    {"t": p["t"], "x": p["xc"], "y": p["yc"]}
                    for p in (track_rows_points.get(track.id) or [])[:: max(1, (len(track_rows_points.get(track.id) or []) // 20) or 1)]
                ]),
            }
            for track in tracks
        ])
        tracks_df.to_csv(tracks_csv_path, index=False)

        windows_df = pd.DataFrame(analytics_rows)
        windows_df.to_parquet(windows_parquet_path, index=False)
        windows_df.to_csv(windows_csv_path, index=False)

        summary_payload = {
            "datapack_version": DATAPACK_VERSION,
            "job_id": job_id,
            "status": "succeeded",
            "duration_s": job.duration_s,
            "fps_sampled": job.fps_sampled,
            "settings": job.settings_json or {},
            "privacy": {"contains_identifiers": False, "contains_raw_plates": False},
            "tracks_total": int(sum(class_counts.values())),
            "events_total": int(sum(event_counts.values())),
            "class_counts": dict(class_counts),
            "event_counts": dict(event_counts),
            "windows_total": int(len(analytics_rows)),
        }

        if contains_plate_like_keys(analytics_rows):
            raise RuntimeError("Data pack windows export contains plate-like keys")

        if contains_plate_like_keys(summary_payload):
            raise RuntimeError("Data pack contains plate-like keys")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)

        with zipfile.ZipFile(datapack_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(summary_path, arcname=ARTIFACT_NAMES["summary"])
            zf.write(windows_parquet_path, arcname=ARTIFACT_NAMES["windows_parquet"])
            zf.write(windows_csv_path, arcname=ARTIFACT_NAMES["windows_csv"])
            zf.write(events_path, arcname=ARTIFACT_NAMES["events"])
            zf.write(events_csv_path, arcname=ARTIFACT_NAMES["events_csv"])
            zf.write(tracks_path, arcname=ARTIFACT_NAMES["tracks"])
            zf.write(tracks_csv_path, arcname=ARTIFACT_NAMES["tracks_csv"])

        artifacts = [
            (ARTIFACT_NAMES["summary"], summary_path, "application/json"),
            (ARTIFACT_NAMES["preview"], preview_path, "video/mp4"),
            (ARTIFACT_NAMES["events"], events_path, "application/x-ndjson"),
            (ARTIFACT_NAMES["events_csv"], events_csv_path, "text/csv"),
            (ARTIFACT_NAMES["tracks"], tracks_path, "application/x-ndjson"),
            (ARTIFACT_NAMES["tracks_csv"], tracks_csv_path, "text/csv"),
            (ARTIFACT_NAMES["windows_parquet"], windows_parquet_path, "application/octet-stream"),
            (ARTIFACT_NAMES["windows_csv"], windows_csv_path, "text/csv"),
            (ARTIFACT_NAMES["data_pack_zip"], datapack_zip_path, "application/zip"),
        ]
        artifact_manifest = []
        for name, path, mime_type in artifacts:
            key = artifact_key(job_id, name)
            with open(path, "rb") as f:
                upload_bytes(key, f.read(), mime_type)
            artifact_manifest.append(artifact_entry(name=name, key=key, path=path, mime_type=mime_type))

        marketplace_payload = build_marketplace_payload(
            job_id=job_id,
            filename=job.filename,
            duration_s=job.duration_s or 0.0,
            analytics_windows=analytics_rows,
            event_counts=dict(event_counts),
            class_counts=dict(class_counts),
        )
        payload_hash = hash_payload(marketplace_payload)
        marketplace_payload["sha256"] = payload_hash

        product_key = f"jobs/{job_id}/marketplace/product.json"
        upload_bytes(product_key, json.dumps(marketplace_payload, separators=(",", ":")).encode("utf-8"), "application/json")

        job.settings_json = {
            **(job.settings_json or {}),
            "preview_clip_key": artifact_key(job_id, ARTIFACT_NAMES["preview"]),
            "marketplace_product_key": product_key,
            "marketplace_product_sha256": payload_hash,
        }
        job.artifacts_json = {"artifacts": artifact_manifest}

        job.status = "succeeded"
        job.logs_summary = (
            f"Processed with YOLOv8 tracking ({'enabled' if model else 'fallback mode'}), "
            f"tracks={sum(class_counts.values())}, events={sum(event_counts.values())}, artifacts={len(artifact_manifest)}"
        )
        db.commit()
        logger.info("job.completed", job_id=job_id, events=sum(event_counts.values()), artifacts=len(artifact_manifest))
