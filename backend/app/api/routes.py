from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.entities import AnalyticsWindow, ApiToken, Event, Job, Organization
from app.schemas.api import AnalyticsWindowOut, ArtifactManifestOut, AuthIn, DataProductOut, EventOut, JobOut, ReviewIn, TokenOut
from app.services.auth import AuthContext, authenticate_user, issue_api_token, issue_token, require_user, token_hash
from app.services.storage import signed_url, upload_bytes
from app.services.usage import ensure_within_limits, get_or_create_usage, record_export
from app.workers.tasks import process_job

router = APIRouter(prefix="/api")


def enqueue_job(job_id: int) -> None:
    process_job.apply_async(args=[job_id], queue="video")


@router.post("/auth/login", response_model=TokenOut)
def login(payload: AuthIn):
    auth = authenticate_user(payload.username, payload.password)
    if not auth:
        raise HTTPException(status_code=401, detail="Bad credentials")
    user, _org = auth
    return TokenOut(access_token=issue_token(payload.username, user.id, user.org_id))


@router.post("/videos/upload", response_model=JobOut)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_user),
):
    ensure_within_limits(db, auth.org_id)
    ext = Path(file.filename).suffix.lower().replace(".", "")
    allowed = {e.strip() for e in settings.allowed_extensions.split(",") if e.strip()} | {"zip"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported format")
    payload = await file.read()
    if len(payload) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")
    key = f"jobs/raw/{file.filename}"
    upload_bytes(key, payload, file.content_type or "video/mp4")
    job = Job(org_id=auth.org_id, filename=file.filename, status="queued", storage_key=key, settings_json={"fps_sampled": settings.fps_sampled})
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_job(job.id)
    return job


@router.post("/jobs/{job_id}/run", response_model=JobOut)
def run_job(job_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    ensure_within_limits(db, auth.org_id)
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    enqueue_job(job_id)
    job.status = "queued"
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobOut])
def jobs(db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    return db.scalars(select(Job).where(Job.org_id == auth.org_id).order_by(Job.id.desc())).all()


@router.get("/jobs/{job_id}", response_model=JobOut)
def job_detail(job_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    return job


@router.get("/jobs/{job_id}/events", response_model=list[EventOut])
def events(job_id: int, clip_id: str | None = Query(default=None), db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    stmt = select(Event).where(Event.job_id == job_id)
    if clip_id:
        stmt = stmt.where(Event.clip_id == clip_id)
    return db.scalars(stmt.order_by(Event.timestamp)).all()


@router.get("/jobs/{job_id}/analytics", response_model=list[AnalyticsWindowOut])
def analytics(job_id: int, clip_id: str | None = Query(default=None), db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    stmt = select(AnalyticsWindow).where(AnalyticsWindow.job_id == job_id)
    if clip_id:
        stmt = stmt.where(AnalyticsWindow.clip_id == clip_id)
    return db.scalars(stmt.order_by(AnalyticsWindow.t_start)).all()


@router.get("/jobs/{job_id}/clips")
def job_clips(job_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    clips = (job.artifacts_json or {}).get("clips", [])
    if not clips:
        clips = [{"clip_id": c} for c in ((job.settings_json or {}).get("clips") or [])]
    return {"job_id": job_id, "clips": clips}


@router.get("/jobs/{job_id}/event_clip/{event_id}")
def event_clip(job_id: int, event_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    event = db.get(Event, event_id)
    if not job or job.org_id != auth.org_id or not event or event.job_id != job_id or not event.clip_key:
        raise HTTPException(status_code=404, detail="Clip missing")
    return {"url": signed_url(event.clip_key)}


@router.get("/jobs/{job_id}/preview")
def job_preview(job_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    preview_key = (job.settings_json or {}).get("preview_clip_key") or f"jobs/{job_id}/artifacts/preview_tracking.mp4"
    return {"url": signed_url(preview_key)}


@router.get("/jobs/{job_id}/artifacts", response_model=ArtifactManifestOut)
def job_artifacts(job_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    return ArtifactManifestOut(job_id=job_id, artifacts=(job.artifacts_json or {}).get("artifacts", []))


@router.get("/jobs/{job_id}/artifacts/{name}")
def job_artifact_url(job_id: int, name: str, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    artifacts = (job.artifacts_json or {}).get("artifacts", [])
    match = next((a for a in artifacts if a.get("name") == name), None)
    if not match:
        raise HTTPException(status_code=404, detail="Artifact not found")
    record_export(db, auth.org_id)
    db.commit()
    return RedirectResponse(url=signed_url(match["key"]))


@router.get("/jobs/{job_id}/data_pack")
def job_data_pack(
    job_id: int,
    format: str = Query(default="zip", pattern="^(zip|parquet|csv|jsonl)$"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_user),
):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    format_to_name = {"zip": "data_pack_v1.zip", "parquet": "windows.parquet", "csv": "windows.csv", "jsonl": "events.jsonl"}
    target_name = format_to_name[format]
    artifacts = (job.artifacts_json or {}).get("artifacts", [])
    match = next((a for a in artifacts if a.get("name") == target_name), None)
    if not match:
        raise HTTPException(status_code=404, detail="Data pack artifact not ready")
    record_export(db, auth.org_id)
    db.commit()
    return RedirectResponse(url=signed_url(match["key"]))


@router.post("/events/{event_id}/review", response_model=EventOut)
def review(event_id: int, payload: ReviewIn, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Not found")
    job = db.get(Job, event.job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    event.review_status = payload.review_status
    event.review_notes = payload.review_notes
    db.commit()
    db.refresh(event)
    return event


@router.get("/jobs/{job_id}/data_product", response_model=DataProductOut)
def data_product(job_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    job = db.get(Job, job_id)
    if not job or job.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    payload_key = (job.settings_json or {}).get("marketplace_product_key")
    payload_hash = (job.settings_json or {}).get("marketplace_product_sha256")
    if not payload_key or not payload_hash:
        raise HTTPException(status_code=404, detail="Data product not ready")
    return DataProductOut(job_id=job_id, sha256=payload_hash, url=signed_url(payload_key))


@router.get("/org/usage")
def org_usage(db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    usage = get_or_create_usage(db, auth.org_id)
    db.commit()
    return {
        "org_id": auth.org_id,
        "year_month": usage.year_month,
        "processed_minutes": usage.processed_minutes,
        "jobs_total": usage.jobs_total,
        "exports_total": usage.exports_total,
        "limits": {
            "processed_minutes": settings.usage_limit_minutes_per_month,
            "jobs": settings.usage_limit_jobs_per_month,
            "exports": settings.usage_limit_exports_per_month,
        },
    }


@router.post("/org/tokens")
def create_org_token(name: str = Query(default="default"), db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    if auth.user_id == 0:
        raise HTTPException(status_code=403, detail="Token creation requires user session")
    raw = issue_api_token()
    row = ApiToken(org_id=auth.org_id, name=name, token_hash=token_hash(raw))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "token": raw, "created_at": row.created_at.isoformat()}


@router.get("/org/tokens")
def list_org_tokens(db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    tokens = db.scalars(select(ApiToken).where(ApiToken.org_id == auth.org_id).order_by(ApiToken.id.desc())).all()
    return [{"id": t.id, "name": t.name, "created_at": t.created_at, "revoked_at": t.revoked_at} for t in tokens]


@router.delete("/org/tokens/{token_id}")
def revoke_org_token(token_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    token = db.get(ApiToken, token_id)
    if not token or token.org_id != auth.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    token.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.get("/org/data_catalog")
def org_data_catalog(db: Session = Depends(get_db), auth: AuthContext = Depends(require_user)):
    jobs = db.scalars(select(Job).where(Job.org_id == auth.org_id).order_by(Job.id.desc())).all()
    catalog = []
    for job in jobs:
        artifacts = (job.artifacts_json or {}).get("artifacts", [])
        dp = next((a for a in artifacts if a.get("name") == "data_pack_v1.zip"), None)
        if not dp:
            continue
        catalog.append({
            "job_id": job.id,
            "filename": job.filename,
            "status": job.status,
            "datapack_version": "v1",
            "hash": dp.get("sha256"),
            "schema": {
                "windows": ["t_start", "t_end", "congestion_score", "counts_json", "motion_json", "stopped_ratio", "density_index", "avg_speed_proxy"],
                "events": ["event_id", "type", "timestamp", "confidence", "track_id", "details_json", "clip_key", "review_status", "clip_id"],
                "tracks": ["track_id", "class", "start_t", "end_t", "bbox_stats_json", "motion_stats_json", "trajectory_sampled", "clip_id"],
            },
            "download": f"/api/jobs/{job.id}/data_pack?format=zip",
            "artifacts": artifacts,
        })
    return {"org_id": auth.org_id, "items": catalog}
