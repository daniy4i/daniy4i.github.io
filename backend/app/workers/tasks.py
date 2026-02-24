from collections import Counter, defaultdict
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import zipfile

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None
import numpy as np
import pandas as pd
from sqlalchemy import select

from app.core.logging import logger
from app.db.session import SessionLocal
from app.ml.ego_motion import estimate_global_motion
from app.ml.heuristics import bike_proximity_confidence, build_windows, close_following_confidence, congestion_score, cut_in_confidence
from app.models.entities import AnalyticsWindow, Event, Job, Track
from app.services.data_product import build_marketplace_payload, hash_payload
from app.services.storage import download_file, upload_bytes
from app.services.usage import record_job_processed
from app.workers.artifacts import ARTIFACT_NAMES, artifact_entry, artifact_key
from app.workers.datapack import DATAPACK_VERSION, contains_plate_like_keys
from app.workers.celery_app import celery_app
from app.workers.vision.annotate import annotate_frame
from app.workers.vision.tracking import load_yolo_model, track_frame

TARGET_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv"}
TRAIL_LENGTH = 20


class PrivacyValidationError(RuntimeError):
    """Raised when privacy validation fails for export payloads."""



def _safe_conf(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 3)))


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in {"_", "-", "."} else "_" for c in Path(name).name)


def _extract_zip_inputs(zip_path: str, out_dir: str) -> list[tuple[str, str]]:
    clips: list[tuple[str, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            raw_name = Path(info.filename)
            if raw_name.is_absolute() or ".." in raw_name.parts:
                continue
            if raw_name.suffix.lower() not in VIDEO_EXTS:
                continue
            clip_id = _safe_name(raw_name.stem)[:48] or f"clip_{len(clips)+1}"
            ext = raw_name.suffix.lower()
            dst = Path(out_dir) / f"{clip_id}{ext}"
            with zf.open(info) as src, open(dst, "wb") as out:
                shutil.copyfileobj(src, out)
            clips.append((clip_id, str(dst)))
    return clips



def _encode_preview_h264(src_path: str, out_path: str) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-vf", "scale=-2:720,fps=15",
        "-c:v", "libx264", "-preset", "veryfast", "-b:v", "2200k",
        "-movflags", "+faststart", "-an", out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_job",
    queue="video",
    autoretry_for=(Exception,),
    dont_autoretry_for=(PrivacyValidationError,),
    retry_backoff=5,
    retry_kwargs={"max_retries": 3},
)
def process_job(self, job_id: int):
    if cv2 is None:
        raise RuntimeError("OpenCV failed to import. Ensure opencv-python-headless runtime libs are available in worker image.")

    db = SessionLocal()
    job = db.get(Job, job_id)
    if not job:
        return

    job.status = "running"
    db.commit()

    with tempfile.TemporaryDirectory() as td:
        src = str(Path(td) / "input")
        Path(src).mkdir(parents=True, exist_ok=True)
        raw_path = str(Path(td) / "source.bin")
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

        download_file(job.storage_key, raw_path)

        ext = Path(job.filename).suffix.lower()
        clip_sources: list[tuple[str, str]]
        if ext == ".zip":
            clip_sources = _extract_zip_inputs(raw_path, src)
            if not clip_sources:
                raise RuntimeError("ZIP contains no supported video clips")
        elif ext in VIDEO_EXTS:
            clip_id = _safe_name(Path(job.filename).stem)[:48] or "clip_1"
            single = str(Path(src) / f"{clip_id}{ext}")
            shutil.copy2(raw_path, single)
            clip_sources = [(clip_id, single)]
        else:
            raise RuntimeError("Unsupported source format")

        # persist original clip inputs as artifacts
        clip_manifest = []
        for clip_id, clip_path in clip_sources:
            clip_artifact_key = f"jobs/{job_id}/inputs/{clip_id}.mp4"
            with open(clip_path, "rb") as f:
                payload = f.read()
            upload_bytes(clip_artifact_key, payload, "video/mp4")
            clip_manifest.append({"clip_id": clip_id, "key": clip_artifact_key, "size_bytes": len(payload)})

        model = load_yolo_model("/app/backend/yolov8n.pt")
        if model is None:
            raise RuntimeError("YOLO model failed to load. Ensure ultralytics is installed AND /app/backend/yolov8n.pt exists in the worker image.")

        samples: list[dict] = []
        per_track_points: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
        clip_offset = 0.0
        total_duration = 0.0
        job_fps_sampled = max((job.settings_json or {}).get("fps_sampled", 5), 1)

        writer = None
        output_size = None

        for clip_id, clip_path in clip_sources:
            cap = cv2.VideoCapture(clip_path)
            if not cap.isOpened():
                continue

            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            total_duration += total_frames / max(fps, 1)
            sample_every = max(1, int(fps / job_fps_sampled))

            if writer is None:
                output_size = (frame_width, frame_height)
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(preview_raw_path, fourcc, job_fps_sampled, output_size)

            frame_idx = 0
            prev_sampled_frame = None
            track_history: dict[int, list[tuple[float, float]]] = defaultdict(list)

            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_idx % sample_every != 0:
                    frame_idx += 1
                    continue

                t_local = frame_idx / max(fps, 1)
                t = clip_offset + t_local
                global_dx, global_dy = estimate_global_motion(prev_sampled_frame, frame)
                detections: list[dict] = track_frame(
                    model,
                    frame,
                    clip_id=clip_id,
                    timestamp_s=t,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    target_classes=TARGET_CLASSES,
                )
                for det in detections:
                    track_id = det["track_id"]
                    if track_id >= 0:
                        per_track_points[clip_id][track_id].append(det)

                raw_motions = []
                comp_motions = []
                for points in per_track_points[clip_id].values():
                    if len(points) >= 2 and abs(points[-1]["t"] - t) < (2 * sample_every / max(fps, 1)):
                        raw_dx = points[-1]["xc"] - points[-2]["xc"]
                        raw_dy = points[-1]["yc"] - points[-2]["yc"]
                        comp_dx = raw_dx - global_dx
                        comp_dy = raw_dy - global_dy
                        points[-1]["raw_dx"] = float(raw_dx)
                        points[-1]["raw_dy"] = float(raw_dy)
                        points[-1]["comp_dx"] = float(comp_dx)
                        points[-1]["comp_dy"] = float(comp_dy)
                        raw_motions.append(float(np.hypot(raw_dx, raw_dy)))
                        comp_motions.append(float(np.hypot(comp_dx, comp_dy)))

                samples.append({
                    "clip_id": clip_id,
                    "t": t,
                    "active_tracks": len({d["track_id"] for d in detections if d["track_id"] >= 0}),
                    "raw_motion": float(np.mean(raw_motions)) if raw_motions else 0.0,
                    "comp_motion": float(np.mean(comp_motions)) if comp_motions else 0.0,
                    "global_dx": float(global_dx),
                    "global_dy": float(global_dy),
                })

                annotated = annotate_frame(frame, detections, track_history, trail_length=TRAIL_LENGTH)
                if output_size and (annotated.shape[1], annotated.shape[0]) != output_size:
                    annotated = cv2.resize(annotated, output_size)
                writer.write(annotated)
                prev_sampled_frame = frame.copy()
                frame_idx += 1

            cap.release()
            clip_offset += total_frames / max(fps, 1)

        if writer is None:
            raise RuntimeError("No readable clips found")
        writer.release()

        _encode_preview_h264(preview_raw_path, preview_path)

        db.query(Event).filter(Event.job_id == job_id).delete()
        db.query(Track).filter(Track.job_id == job_id).delete()
        db.query(AnalyticsWindow).filter(AnalyticsWindow.job_id == job_id).delete()

        track_rows_points: dict[int, list[dict]] = {}
        for clip_id, tracks_map in per_track_points.items():
            for _, pts in tracks_map.items():
                if not pts:
                    continue
                class_name = pts[0]["class"]
                track = Track(
                    job_id=job_id,
                    clip_id=clip_id,
                    class_name=class_name,
                    start_t=pts[0]["t"],
                    end_t=pts[-1]["t"],
                    bbox_stats_json={"max_area": max(p["area"] for p in pts), "mean_area": float(np.mean([p["area"] for p in pts]))},
                    motion_stats_json={
                        "points": len(pts),
                        "avg_raw_speed": float(np.mean([np.hypot(p.get("raw_dx", 0.0), p.get("raw_dy", 0.0)) for p in pts])),
                        "avg_compensated_speed": float(np.mean([np.hypot(p.get("comp_dx", 0.0), p.get("comp_dy", 0.0)) for p in pts])),
                    },
                )
                db.add(track)
                db.flush()
                track_rows_points[track.id] = pts

                if class_name in VEHICLE_CLASSES:
                    cut_conf = _safe_conf(cut_in_confidence(pts, output_size[0] if output_size else 1280))
                    if cut_conf > 0.2:
                        db.add(Event(job_id=job_id, clip_id=clip_id, track_id=track.id, type="cut_in", timestamp=pts[-1]["t"], confidence=cut_conf, details_json={"definition": "central zone crossing + fast area growth"}))

                    close_conf = _safe_conf(close_following_confidence(pts, output_size[0] if output_size else 1280))
                    if close_conf > 0.2:
                        db.add(Event(job_id=job_id, clip_id=clip_id, track_id=track.id, type="close_following_proxy", timestamp=pts[-1]["t"], confidence=close_conf, details_json={"definition": "large centered bbox sustained"}))

                if class_name == "bicycle":
                    bike_conf = _safe_conf(bike_proximity_confidence(pts, output_size[0] if output_size else 1280))
                    if bike_conf > 0.2:
                        db.add(Event(job_id=job_id, clip_id=clip_id, track_id=track.id, type="bike_proximity_lane_share_proxy", timestamp=pts[-1]["t"], confidence=bike_conf, details_json={"definition": "bicycle near ego-forward center"}))

        analytics_rows = []
        samples_by_clip: dict[str, list[dict]] = defaultdict(list)
        for s in samples:
            samples_by_clip[s["clip_id"]].append(s)

        for clip_id, clip_samples in samples_by_clip.items():
            for w in build_windows(clip_samples, window_s=5):
                score = congestion_score(w["active_tracks"], w["avg_compensated_speed"], w["stopped_ratio"], w["density_index"])
                row = {
                    "datapack_version": DATAPACK_VERSION,
                    "clip_id": clip_id,
                    "t_start": w["t_start"],
                    "t_end": w["t_end"],
                    "active_tracks": w["active_tracks"],
                    "avg_raw_speed": round(w["avg_raw_speed"], 3),
                    "avg_compensated_speed": round(w["avg_compensated_speed"], 3),
                    "avg_speed_proxy": round(w["avg_speed_proxy"], 3),
                    "stopped_ratio": round(w["stopped_ratio"], 3),
                    "density_index": round(w["density_index"], 3),
                    "congestion_score": score,
                }
                analytics_rows.append(row)
                db.add(AnalyticsWindow(
                    job_id=job_id,
                    clip_id=clip_id,
                    t_start=w["t_start"],
                    t_end=w["t_end"],
                    congestion_score=score,
                    counts_json={"active_tracks": w["active_tracks"]},
                    motion_json={k: row[k] for k in ["avg_raw_speed", "avg_compensated_speed", "avg_speed_proxy", "stopped_ratio", "density_index"]},
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
                    "clip_id": event.clip_id,
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
                    msg = "Data pack event export contains plate-like keys"
                    job.status = "failed"
                    job.logs_summary = f"Privacy validation failed: {msg}"
                    db.commit()
                    logger.error("job.failed.privacy_validation", job_id=job_id, error=msg)
                    raise PrivacyValidationError(msg)
                f.write(json.dumps(row) + "\n")

        pd.DataFrame([{
            "datapack_version": DATAPACK_VERSION,
            "clip_id": e.clip_id,
            "event_id": e.id,
            "type": e.type,
            "timestamp": e.timestamp,
            "confidence": e.confidence,
            "track_id": e.track_id,
            "details_json": json.dumps(e.details_json),
            "clip_key": e.clip_key,
            "review_status": e.review_status,
        } for e in events]).to_csv(events_csv_path, index=False)

        with open(tracks_path, "w", encoding="utf-8") as f:
            for track in tracks:
                points = track_rows_points.get(track.id) or []
                sampled = [{"t": p["t"], "x": p["xc"], "y": p["yc"]} for p in points[:: max(1, len(points) // 20 or 1)]]
                row = {
                    "datapack_version": DATAPACK_VERSION,
                    "clip_id": track.clip_id,
                    "id": track.id,
                    "class": track.class_name,
                    "start_t": track.start_t,
                    "end_t": track.end_t,
                    "bbox_stats": track.bbox_stats_json,
                    "motion_stats": track.motion_stats_json,
                    "trajectory_sampled": sampled,
                }
                if contains_plate_like_keys(row):
                    msg = "Data pack track export contains plate-like keys"
                    job.status = "failed"
                    job.logs_summary = f"Privacy validation failed: {msg}"
                    db.commit()
                    logger.error("job.failed.privacy_validation", job_id=job_id, error=msg)
                    raise PrivacyValidationError(msg)
                f.write(json.dumps(row) + "\n")

        pd.DataFrame([{
            "datapack_version": DATAPACK_VERSION,
            "clip_id": t.clip_id,
            "track_id": t.id,
            "class": t.class_name,
            "start_t": t.start_t,
            "end_t": t.end_t,
            "bbox_stats_json": json.dumps(t.bbox_stats_json),
            "motion_stats_json": json.dumps(t.motion_stats_json),
        } for t in tracks]).to_csv(tracks_csv_path, index=False)

        windows_df = pd.DataFrame(analytics_rows)
        windows_df.to_parquet(windows_parquet_path, index=False)
        windows_df.to_csv(windows_csv_path, index=False)

        summary_payload = {
            "datapack_version": DATAPACK_VERSION,
            "job_id": job_id,
            "status": "succeeded",
            "duration_s": total_duration,
            "fps_sampled": job_fps_sampled,
            "clips": [c[0] for c in clip_sources],
            "settings": job.settings_json or {},
            "privacy": {"contains_identifiers": False, "contains_raw_plates": False},
            "tracks_total": int(sum(class_counts.values())),
            "events_total": int(sum(event_counts.values())),
            "class_counts": dict(class_counts),
            "event_counts": dict(event_counts),
            "windows_total": int(len(analytics_rows)),
        }
        if contains_plate_like_keys(summary_payload):
            msg = "Data pack contains plate-like keys"
            job.status = "failed"
            job.logs_summary = f"Privacy validation failed: {msg}"
            db.commit()
            logger.error("job.failed.privacy_validation", job_id=job_id, error=msg)
            raise PrivacyValidationError(msg)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)

        with zipfile.ZipFile(datapack_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in [summary_path, windows_parquet_path, windows_csv_path, events_path, events_csv_path, tracks_path, tracks_csv_path]:
                zf.write(p, arcname=Path(p).name)

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
            duration_s=total_duration,
            analytics_windows=analytics_rows,
            event_counts=dict(event_counts),
            class_counts=dict(class_counts),
        )
        payload_hash = hash_payload(marketplace_payload)
        marketplace_payload["sha256"] = payload_hash
        product_key = f"jobs/{job_id}/marketplace/product.json"
        upload_bytes(product_key, json.dumps(marketplace_payload, separators=(",", ":")).encode("utf-8"), "application/json")

        job.duration_s = total_duration
        job.fps_sampled = job_fps_sampled
        job.settings_json = {
            **(job.settings_json or {}),
            "preview_clip_key": artifact_key(job_id, ARTIFACT_NAMES["preview"]),
            "marketplace_product_key": product_key,
            "marketplace_product_sha256": payload_hash,
            "clips": [c[0] for c in clip_sources],
        }
        job.artifacts_json = {"artifacts": artifact_manifest, "clips": clip_manifest}
        job.status = "succeeded"
        job.logs_summary = (
            f"Processed {len(clip_sources)} clip(s) with YOLO tracking ({'enabled' if model else 'fallback mode'}), "
            f"tracks={sum(class_counts.values())}, events={sum(event_counts.values())}, artifacts={len(artifact_manifest)}"
        )
        if job.org_id:
            record_job_processed(db, job.org_id, total_duration)
        db.commit()
        logger.info("job.completed", job_id=job_id, events=sum(event_counts.values()), artifacts=len(artifact_manifest), clips=len(clip_sources))
