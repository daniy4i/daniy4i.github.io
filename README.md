# NYC Traffic Intelligence

Production-grade MVP for ingesting dashcam video and producing congestion + detected behavior event analytics.

## Stack
- FastAPI + Celery + Redis + PostgreSQL + MinIO
- Ultralytics YOLO + ByteTrack (`model.track`) + OpenCV + FFmpeg stubs
- Next.js dashboard for uploads, jobs, analytics charts, and event review

## Local setup
```bash
cp backend/.env.example backend/.env
make up
```

## Run services separately
```bash
make backend
make worker
make frontend
```

## Run tests
```bash
make test
```

## Process sample video
1. Open `http://localhost:3000/upload`
2. Upload user-provided dashcam `.mp4/.mov/.mkv`
3. Trigger processing via API:
```bash
curl -X POST http://localhost:8000/api/jobs/{job_id}/run -H "Authorization: Bearer <token>"
```
4. Open job details page for analytics and review actions.

## cURL examples
```bash
curl -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}'
curl -X GET http://localhost:8000/api/jobs -H "Authorization: Bearer <token>"
curl -X POST http://localhost:8000/api/events/1/review -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' -d '{"review_status":"confirm","review_notes":"looks valid"}'
```

## Privacy model
- Preview outputs use blur transforms for privacy.
- No identity labeling or violation claims.
- Events are surfaced as probabilistic behavior proxies with confidence.

## Troubleshooting
- Ensure Docker daemon is running.
- If YOLO weights cannot download, worker still runs and emits congestion windows using fallback motion stats.
- Verify MinIO endpoint and credentials in `.env`/compose.
