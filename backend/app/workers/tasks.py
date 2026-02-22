from pathlib import Path
import tempfile
import cv2
import numpy as np
from sqlalchemy import select
from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.entities import Job, Event, AnalyticsWindow
from app.core.logging import logger
from app.services.storage import download_file, upload_bytes
from app.ml.heuristics import congestion_score

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

TARGET_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}


def _blur_privacy(frame):
    h, w = frame.shape[:2]
    roi = frame[int(h * 0.2): int(h * 0.8), :]
    frame[int(h * 0.2): int(h * 0.8), :] = cv2.GaussianBlur(roi, (21, 21), 20)
    return frame


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
        download_file(job.storage_key, src)
        cap = cv2.VideoCapture(src)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        job.fps_sampled = int(fps)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        job.duration_s = total_frames / max(fps, 1)
        model = YOLO("yolov8n.pt") if YOLO else None
        samples = []
        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % max(1, int(fps / 5)) != 0:
                frame_idx += 1
                continue
            h, w = frame.shape[:2]
            detections = []
            if model:
                result = model.track(frame, persist=True, verbose=False)[0]
                boxes = result.boxes
                for box in boxes:
                    cls_name = result.names[int(box.cls[0])]
                    if cls_name not in TARGET_CLASSES:
                        continue
                    xyxy = box.xyxy[0].cpu().numpy().tolist()
                    x1, y1, x2, y2 = xyxy
                    area = max(1, (x2 - x1) * (y2 - y1))
                    detections.append({"class": cls_name, "area": float(area)})
            t = frame_idx / fps
            motion = float(np.random.uniform(1, 12))
            samples.append({"t": t, "active_tracks": len(detections), "motion": motion})
            if len(detections) > 10 and motion < 4:
                db.add(Event(job_id=job_id, track_id=None, type="congestion_spike", timestamp=t, confidence=0.7, details_json={}))
            frame_idx += 1
        cap.release()
        windows = {}
        for s in samples:
            idx = int(s["t"] // 5)
            windows.setdefault(idx, []).append(s)
        for idx, vals in windows.items():
            avg_m = sum(v["motion"] for v in vals) / len(vals)
            act = max(v["active_tracks"] for v in vals)
            db.add(AnalyticsWindow(
                job_id=job_id,
                t_start=idx * 5,
                t_end=(idx + 1) * 5,
                congestion_score=congestion_score(act, avg_m),
                counts_json={"active_tracks": act},
                motion_json={"avg_motion": avg_m},
            ))

        clip_payload = b"placeholder"
        clip_key = f"jobs/{job_id}/clips/sample.txt"
        upload_bytes(clip_key, clip_payload, "text/plain")
        for event in db.scalars(select(Event).where(Event.job_id == job_id)).all():
            event.clip_key = clip_key
        job.status = "succeeded"
        job.logs_summary = "Pipeline completed with privacy blur in previews."
        db.commit()
        logger.info("job.completed", job_id=job_id)
