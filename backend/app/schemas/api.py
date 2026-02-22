from datetime import datetime
from pydantic import BaseModel, Field


class JobOut(BaseModel):
    id: int
    created_at: datetime
    status: str
    filename: str
    duration_s: float | None = None
    fps_sampled: int | None = None
    logs_summary: str = ""

    class Config:
        from_attributes = True


class EventOut(BaseModel):
    id: int
    job_id: int
    track_id: int | None
    type: str
    timestamp: float
    confidence: float
    details_json: dict
    review_status: str
    review_notes: str

    class Config:
        from_attributes = True


class AnalyticsWindowOut(BaseModel):
    t_start: float
    t_end: float
    congestion_score: float
    counts_json: dict
    motion_json: dict

    class Config:
        from_attributes = True


class ReviewIn(BaseModel):
    review_status: str = Field(pattern="^(confirm|reject)$")
    review_notes: str = ""


class AuthIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DataProductOut(BaseModel):
    job_id: int
    sha256: str
    url: str


class ArtifactOut(BaseModel):
    name: str
    key: str
    mime_type: str
    size_bytes: int
    sha256: str


class ArtifactManifestOut(BaseModel):
    job_id: int
    artifacts: list[ArtifactOut]
