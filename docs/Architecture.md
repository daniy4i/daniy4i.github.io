# Architecture

## Components
- **Frontend (Next.js)**: upload flow, jobs list, analytics dashboard, event review actions.
- **Backend API (FastAPI)**: auth, upload validation, job orchestration, analytics/event retrieval.
- **Worker (Celery)**: async video processing with YOLO+ByteTrack, heuristic event extraction, analytics windows, clip artifact outputs.
- **Storage**:
  - PostgreSQL: jobs, tracks, events, analytics windows.
  - MinIO/S3: raw uploads, clips, artifacts.

## Pipeline
1. Upload endpoint stores video in object storage and creates job row.
2. Run endpoint enqueues Celery task.
3. Worker downloads video, samples frames, estimates ego/global motion between sampled frames, runs tracking, computes behavior proxies + compensated-motion congestion score.
4. Event records and analytics windows are stored in PostgreSQL.
5. Dashboard reads APIs for visualization and reviewer workflow.

## Reliability
- Celery retries with exponential backoff.
- Structured JSON logging via structlog.
- Persistent job states and logs summary.

## Privacy
- Blur is applied to preview artifacts.
- No storage/display of readable plates or identifiable faces in dashboard previews.

## Ego-motion compensation
- We estimate frame-to-frame global motion using lightweight optical-flow feature tracking.
- Track center motion is split into raw displacement and ego-motion-compensated displacement.
- Congestion windows are scored from active tracks, compensated speed, stopped ratio, and density index for more credible dashcam analytics.
