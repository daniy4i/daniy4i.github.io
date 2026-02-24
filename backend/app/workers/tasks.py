from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import zipfile

# Safe OpenCV import
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
from app.ml.heuristics import (
    bike_proximity_confidence,
    build_windows,
    close_following_confidence,
    congestion_score,
    cut_in_confidence,
)
from app.models.entities import AnalyticsWindow, Event, Job, Track
from app.services.data_product import build_marketplace_payload, hash_payload
from app.services.storage import download_file, upload_bytes
from app.services.usage import record_job_processed
from app.workers.artifacts import ARTIFACT_NAMES, artifact_entry, artifact_key
from app.workers.datapack import DATAPACK_VERSION, contains_plate_like_keys
from app.workers.celery_app import celery_app
from app.workers.vision.annotate import annotate_frame
from app.workers.vision.tracking import load_yolo_model, track_frame

# Optional ultralytics import (diagnostic safety)
try:
    from ultralytics import YOLO  # noqa: F401
except Exception:  # pragma: no cover
    YOLO = None


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


def _guess_video_mime(ext: str) -> str:
    ext = (ext or "").lower()
    if ext == ".mp4":
        return "video/mp4"
    if ext == ".mov":
        return "video/quicktime"
    if ext == ".mkv":
        return "video/x-matroska"
    return "application/octet-stream"


def _extract_zip_inputs(zip_path: str, out_dir: str) -> list[tuple[str, str]]:
    clips: list[tuple[str, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            raw_name = Path(info.filename)

            # zip-slip hardening
            if raw_name.is_absolute() or ".." in raw_name.parts:
                continue

            if raw_name.suffix.lower() not in VIDEO_EXTS:
                continue

            clip_id = _safe_name(raw_name.stem)[:48] or f"clip_{len(clips) + 1}"
            ext = raw_name.suffix.lower()
            dst = Path(out_dir) / f"{clip_id}{ext}"

            with zf.open(info) as src, open(dst, "wb") as out:
                shutil.copyfileobj(src, out)

            clips.append((clip_id, str(dst)))

    return clips


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
    dont_autoretry_for=(PrivacyValidationError,),
    retry_backoff=5,
    retry_kwargs={"max_retries": 3},
)
def process_job(self, job_id: int):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return

        job.status = "running"
        db.commit()

        if cv2 is None:
            raise RuntimeError(
                "OpenCV failed to import. Ensure opencv-python-headless runtime libs are available."
            )

        # IMPORTANT:
        # Keep the FULL main branch body of process_job below this line.
        # Delete the entire duplicated block after >>>>>>> main