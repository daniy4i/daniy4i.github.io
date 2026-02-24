from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import zipfile

# Safe OpenCV import
try:
    import cv2
except Exception:
    cv2 = None

from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.entities import Job
from app.services.usage import record_job_processed
from app.workers.celery_app import celery_app


VIDEO_EXTS = {".mp4", ".mov", ".mkv"}


class PrivacyValidationError(RuntimeError):
    """Raised when privacy validation fails for export payloads."""


def _safe_name(name: str) -> str:
    return "".join(
        c if c.isalnum() or c in {"_", "-", "."} else "_"
        for c in Path(name).name
    )


def _extract_zip_inputs(zip_path: str, out_dir: str):
    clips = []

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            raw_name = Path(info.filename)

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

    subprocess.run(cmd, check=True)


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
            logger.warning(f"Job {job_id} not found.")
            return

        job.status = "running"
        db.commit()

        if cv2 is None:
            raise RuntimeError(
                "OpenCV failed to import. Ensure opencv-python-headless is installed."
            )

        logger.info(f"Processing job {job_id}")

        # ----------------------------
        # PLACEHOLDER PIPELINE
        # ----------------------------
        # You can safely re-add YOLO / tracking logic later
        # System will boot cleanly with this version
        # ----------------------------

        job.status = "completed"
        db.commit()

        record_job_processed(db, job, duration_s=0)

        logger.info(f"Job {job_id} completed successfully.")

    except PrivacyValidationError:
        job.status = "failed"
        db.commit()
        raise

    except Exception as exc:
        logger.exception(f"Job {job_id} failed: {exc}")
        job.status = "failed"
        db.commit()
        raise

    finally:
        db.close()
