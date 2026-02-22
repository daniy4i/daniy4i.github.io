from collections import Counter, defaultdict
from pathlib import Path
import json
import tempfile

import cv2
import numpy as np
from sqlalchemy import select

from app.core.logging import logger
from app.db.session import SessionLocal
from app.ml.heuristics import bike_proximity_confidence, build_windows, close_following_confidence, congestion_score, cut_in_confidence
from app.models.entities import AnalyticsWindow, Event, Job, Track
from app.services.data_product import build_marketplace_payload, hash_payload
from app.services.storage import download_file, upload_bytes
from app.workers.celery_app import celery_app

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None

TARGET_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}


def _blur_privacy(frame: np.ndarray) -> np.ndarray:
    h, _ = frame.shape[:2]
    roi = frame[int(h * 0.2): int(h * 0.8), :]
    frame[int(h * 0.2): int(h * 0.8), :] = cv2.GaussianBlur(roi, (21, 21), 20)
    return frame


def _safe_conf(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 3)))


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
def process_job(self, job_id: int):
    db = SessionLocal()
    job = db.get(Job, job_id)
    if not job:
        return

    job.status = "running"
    db.commit()

    with tempfile.TemporaryDirectory() as td:
        src = str(Path(td) / "src.mp4")
        annotated_path = str(Path(td) / "annotated.mp4")
        download_file(job.storage_key, src)

        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            raise RuntimeError("Unable to open uploaded video")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        sample_every = max(1, int(fps / max(job.settings_json.get("fps_sampled", 5), 1)))
        job.fps_sampled = int(round(fps / sample_every))
        job.duration_s = total_frames / max(fps, 1)

        model = YOLO("yolov8n.pt") if YOLO else None

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(annotated_path, fourcc, fps, (frame_width, frame_height))

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
                annotated_frame = result.plot()
                if result.boxes is not None:
                    boxes = result.boxes
                    ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
                    xys = boxes.xywh.cpu().numpy() if len(boxes) else []

                    for i, box in enumerate(boxes):
                        cls_name = result.names[int(box.cls[0])]
                        if cls_name not in TARGET_CLASSES:
                            continue

                        tid = ids[i] if i < len(ids) else None
                        x, y, w, h = xys[i]
                        area = float(max(1.0, w * h))
                        area_ratio = area / float(max(1, frame_width * frame_height))
                        track_id = int(tid) if tid is not None else -1

                        detections.append({
                            "class": cls_name,
                            "track_id": track_id,
                            "t": t,
                            "xc": float(x),
                            "yc": float(y),
                            "w": float(w),
                            "h": float(h),
                            "area": area,
                            "area_ratio": area_ratio,
                        })

                        if track_id >= 0:
                            per_track_points[track_id].append(detections[-1])
                            history = track_history[track_id]
                            history.append((float(x), float(y)))
                            if len(history) > 30:
                                history.pop(0)
                            pts = np.array(history, dtype=np.int32).reshape((-1, 1, 2))
                            cv2.polylines(annotated_frame, [pts], isClosed=False, color=(220, 220, 220), thickness=2)

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

        db.query(Event).filter(Event.job_id == job_id).delete()
        db.query(Track).filter(Track.job_id == job_id).delete()

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
            analytics_rows.append({
                "t_start": w["t_start"],
                "t_end": w["t_end"],
                "active_tracks": w["active_tracks"],
                "avg_motion": round(w["avg_motion"], 2),
                "congestion_score": score,
            })
            db.add(AnalyticsWindow(
                job_id=job_id,
                t_start=w["t_start"],
                t_end=w["t_end"],
                congestion_score=score,
                counts_json={"active_tracks": w["active_tracks"]},
                motion_json={"avg_motion": round(w["avg_motion"], 2)},
            ))

        clip_key = f"jobs/{job_id}/clips/annotated_preview.mp4"
        with open(annotated_path, "rb") as f:
            upload_bytes(clip_key, f.read(), "video/mp4")

        events = db.scalars(select(Event).where(Event.job_id == job_id)).all()
        for event in events:
            event.clip_key = clip_key

        class_counts = Counter(track.class_name for track in db.scalars(select(Track).where(Track.job_id == job_id)).all())
        event_counts = Counter(event.type for event in events)

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
            "marketplace_product_key": product_key,
            "marketplace_product_sha256": payload_hash,
        }

        job.status = "succeeded"
        job.logs_summary = (
            f"Processed with YOLOv8 tracking ({'enabled' if model else 'fallback mode'}), "
            f"tracks={sum(class_counts.values())}, events={sum(event_counts.values())}, data_hash={payload_hash[:12]}..."
        )
        db.commit()
        logger.info("job.completed", job_id=job_id, events=sum(event_counts.values()), hash=payload_hash)
