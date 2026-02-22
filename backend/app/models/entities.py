from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    filename: Mapped[str] = mapped_column(String(255))
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps_sampled: Mapped[int | None] = mapped_column(Integer, nullable=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    storage_key: Mapped[str] = mapped_column(String(512))
    logs_summary: Mapped[str] = mapped_column(Text, default="")

    tracks: Mapped[list["Track"]] = relationship(back_populates="job")
    events: Mapped[list["Event"]] = relationship(back_populates="job")


class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    class_name: Mapped[str] = mapped_column(String(32))
    start_t: Mapped[float] = mapped_column(Float)
    end_t: Mapped[float] = mapped_column(Float)
    bbox_stats_json: Mapped[dict] = mapped_column(JSON, default=dict)
    motion_stats_json: Mapped[dict] = mapped_column(JSON, default=dict)

    job: Mapped[Job] = relationship(back_populates="tracks")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    track_id: Mapped[int | None] = mapped_column(ForeignKey("tracks.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[str] = mapped_column(String(16), default="pending")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    clip_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    job: Mapped[Job] = relationship(back_populates="events")


class AnalyticsWindow(Base):
    __tablename__ = "analytics_windows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    t_start: Mapped[float] = mapped_column(Float)
    t_end: Mapped[float] = mapped_column(Float)
    congestion_score: Mapped[float] = mapped_column(Float)
    counts_json: Mapped[dict] = mapped_column(JSON, default=dict)
    motion_json: Mapped[dict] = mapped_column(JSON, default=dict)
