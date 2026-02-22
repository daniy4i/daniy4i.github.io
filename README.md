# NYC Traffic Intelligence

NYC Traffic Intelligence is a web app that lets you upload dashcam videos and review traffic analytics.

## If you don’t code (recommended)

### 1) Install Docker Desktop
- Download: https://www.docker.com/products/docker-desktop/
- Open Docker Desktop and wait until it says it is running.

### 2) Start everything with one command
From this project folder:
```bash
make do-it-all
```

### 3) Open the app
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (`minioadmin` / `minioadmin`)

### 4) Use it
1. Open `http://localhost:3000/upload`
2. Upload your dashcam video (`.mp4`, `.mov`, `.mkv`)
3. Go to `Jobs`
4. Open a job
5. If processing does not start automatically, open API docs and call `POST /api/jobs/{job_id}/run`

### 5) Verify everything is healthy
```bash
make check
```

### 6) Stop everything
```bash
make down
```

---

## For developers

### Stack
- FastAPI + Celery + Redis + PostgreSQL + MinIO
- Ultralytics YOLO + ByteTrack (`model.track`) + OpenCV + FFmpeg stubs
- Next.js dashboard for uploads, jobs, analytics charts, and event review

### Local setup
```bash
cp backend/.env.example backend/.env
make up
```

### Run services separately
```bash
make backend
make worker
make frontend
```

### Run tests
```bash
make test
```

### cURL examples
```bash
curl -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}'
curl -X GET http://localhost:8000/api/jobs -H "Authorization: Bearer <token>"
curl -X POST http://localhost:8000/api/events/1/review -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' -d '{"review_status":"confirm","review_notes":"looks valid"}'
```

## Privacy model
- Preview outputs use blur transforms for privacy.
- No identity labeling or violation claims.
- Events are probabilistic behavior proxies with confidence scores.

## Troubleshooting
- Ensure Docker daemon is running.
- If you get `make: *** No rule to make target \`do-it-all\``:
  1. Run `git pull` to get the latest `Makefile` and `scripts/` folder.
  2. Retry with either `make do-it-all` or `make do_it_all`.
  3. Fallback (no Make required): `./scripts/do_it_all.sh`.
- If YOLO weights cannot download, worker still emits congestion windows using fallback motion stats.
- Verify MinIO endpoint and credentials in `.env`/compose.
