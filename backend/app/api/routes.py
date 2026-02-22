from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import AnalyticsWindow, Event, Job
from app.schemas.api import AnalyticsWindowOut, ArtifactManifestOut, AuthIn, DataProductOut, EventOut, JobOut, ReviewIn, TokenOut
from app.services.auth import issue_token, require_user
from app.services.storage import signed_url, upload_bytes
from app.core.config import settings
from app.workers.tasks import process_job

router = APIRouter(prefix="/api")


def enqueue_job(job_id: int) -> None:
    # Force the queue name explicitly so jobs are consumed by the worker started with `-Q video`.
    process_job.apply_async(args=[job_id], queue="video")


@router.post("/auth/login", response_model=TokenOut)
def login(payload: AuthIn):
    if payload.username != "admin" or payload.password != "admin":
        raise HTTPException(status_code=401, detail="Bad credentials")
    return TokenOut(access_token=issue_token(payload.username))


@router.post("/videos/upload", response_model=JobOut)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: str = Depends(require_user),
):
    ext = Path(file.filename).suffix.lower().replace(".", "")
    if ext not in settings.allowed_extensions.split(","):
        raise HTTPException(status_code=400, detail="Unsupported format")
    payload = await file.read()
    if len(payload) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")
    key = f"jobs/raw/{file.filename}"
    upload_bytes(key, payload, file.content_type or "video/mp4")
    job = Job(filename=file.filename, status="queued", storage_key=key, settings_json={"fps_sampled": settings.fps_sampled})
    db.add(job)
    db.commit()
    db.refresh(job)

    # Auto-enqueue right after upload so non-technical users see processing start immediately.
    enqueue_job(job.id)
    return job


@router.post("/jobs/{job_id}/run", response_model=JobOut)
def run_job(job_id: int, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    enqueue_job(job_id)
    job.status = "queued"
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobOut])
def jobs(db: Session = Depends(get_db), _user: str = Depends(require_user)):
    return db.scalars(select(Job).order_by(Job.id.desc())).all()


@router.get("/jobs/{job_id}", response_model=JobOut)
def job_detail(job_id: int, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job


@router.get("/jobs/{job_id}/events", response_model=list[EventOut])
def events(job_id: int, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    return db.scalars(select(Event).where(Event.job_id == job_id).order_by(Event.timestamp)).all()


@router.get("/jobs/{job_id}/analytics", response_model=list[AnalyticsWindowOut])
def analytics(job_id: int, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    return db.scalars(select(AnalyticsWindow).where(AnalyticsWindow.job_id == job_id).order_by(AnalyticsWindow.t_start)).all()


@router.get("/jobs/{job_id}/event_clip/{event_id}")
def event_clip(job_id: int, event_id: int, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    event = db.get(Event, event_id)
    if not event or event.job_id != job_id or not event.clip_key:
        raise HTTPException(status_code=404, detail="Clip missing")
    return {"url": signed_url(event.clip_key)}


@router.get("/jobs/{job_id}/preview")
def job_preview(job_id: int, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")

    preview_key = (job.settings_json or {}).get("preview_clip_key")
    if not preview_key:
        preview_key = f"jobs/{job_id}/artifacts/preview_tracking.mp4"

    return {"url": signed_url(preview_key)}


@router.get("/jobs/{job_id}/artifacts", response_model=ArtifactManifestOut)
def job_artifacts(job_id: int, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    artifacts = (job.artifacts_json or {}).get("artifacts", [])
    return ArtifactManifestOut(job_id=job_id, artifacts=artifacts)


@router.get("/jobs/{job_id}/artifacts/{name}")
def job_artifact_url(job_id: int, name: str, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")

    artifacts = (job.artifacts_json or {}).get("artifacts", [])
    match = next((a for a in artifacts if a.get("name") == name), None)
    if not match:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return RedirectResponse(url=signed_url(match["key"]))


@router.post("/events/{event_id}/review", response_model=EventOut)
def review(event_id: int, payload: ReviewIn, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Not found")
    event.review_status = payload.review_status
    event.review_notes = payload.review_notes
    db.commit()
    db.refresh(event)
    return event


@router.get("/jobs/{job_id}/data_product", response_model=DataProductOut)
def data_product(job_id: int, db: Session = Depends(get_db), _user: str = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    payload_key = (job.settings_json or {}).get("marketplace_product_key")
    payload_hash = (job.settings_json or {}).get("marketplace_product_sha256")
    if not payload_key or not payload_hash:
        raise HTTPException(status_code=404, detail="Data product not ready")
    return DataProductOut(job_id=job_id, sha256=payload_hash, url=signed_url(payload_key))
