from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import OrgUsageMonthly


def current_year_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_or_create_usage(db: Session, org_id: int) -> OrgUsageMonthly:
    ym = current_year_month()

    row = db.scalars(
        select(OrgUsageMonthly).where(
            OrgUsageMonthly.org_id == org_id,
            OrgUsageMonthly.year_month == ym,
        )
    ).first()

    if row:
        return row

    row = OrgUsageMonthly(
        org_id=org_id,
        year_month=ym,
        processed_minutes=0.0,
        jobs_total=0,
        exports_total=0,
    )
    db.add(row)
    db.flush()
    return row


def ensure_within_limits(db: Session, org_id: int) -> None:
    u = get_or_create_usage(db, org_id)

    if u.processed_minutes >= settings.usage_limit_minutes_per_month:
        raise HTTPException(
            status_code=429,
            detail="Monthly processed-minutes limit reached",
        )

    if u.jobs_total >= settings.usage_limit_jobs_per_month:
        raise HTTPException(
            status_code=429,
            detail="Monthly jobs limit reached",
        )


def record_job_processed(db: Session, org_id: int, duration_s: float) -> None:
    u = get_or_create_usage(db, org_id)

    u.jobs_total += 1
    u.processed_minutes += max(0.0, duration_s / 60.0)

    db.flush()


def record_export(db: Session, org_id: int) -> None:
    u = get_or_create_usage(db, org_id)

    u.exports_total += 1

    if u.exports_total > settings.usage_limit_exports_per_month:
        raise HTTPException(
            status_code=429,
            detail="Monthly exports limit reached",
        )

    db.flush()
