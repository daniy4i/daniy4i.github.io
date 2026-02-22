# NYC Traffic Intelligence

NYC Traffic Intelligence is a web app that lets you upload dashcam videos and review traffic analytics.

## If you don’t code (recommended)


### 0) Make sure you are on the updated repo
From this project folder run:
```bash
git pull
git log -1 --oneline
```
You should see the latest commit at the top.

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
2. Upload either a single video (`.mp4`, `.mov`, `.mkv`) or a ZIP of multiple clips
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
curl -X GET http://localhost:8000/api/org/usage -H "Authorization: Bearer <token>"
curl -X GET http://localhost:8000/api/org/data_catalog -H "Authorization: Bearer <token>"
```


### Processing engine
- Uses YOLOv8 `model.track(..., persist=True)` for tracked detections (vehicle, bicycle, person classes).
- Writes a privacy-blurred annotated preview video and links it to detected events.
- Standardizes job artifacts under `jobs/{job_id}/artifacts/*`:
  `job_summary.json`, `preview_tracking.mp4`, `events.jsonl`, `tracks.jsonl`, `windows.parquet` (and `windows.csv`).
- Batch mode: one ZIP upload creates one job, processes each clip, and merges into unified events/tracks/windows with `clip_id`.
- Original input clips are stored as artifacts under `jobs/{job_id}/inputs/{clip_id}.mp4`.
- Data Pack v1 exports include CSV/JSONL/Parquet variants plus `data_pack_v1.zip`, each with SHA-256 in the artifact manifest.
- Computes congestion windows and behavior proxy events from tracked trajectories.
- Uses ego-motion compensation (global frame motion subtraction) so speed/stopped proxies are less biased by dashcam movement.
- Produces a marketplace-ready anonymized aggregate JSON package and SHA-256 hash for integrity verification.

## Privacy model
- Preview outputs use blur transforms for privacy.
- No identity labeling or violation claims.
- Events are probabilistic behavior proxies with confidence scores.

## Troubleshooting
- Ensure Docker daemon is running.
- If you see `open .../infra/docker-compose.yml: no such file or directory`, you are in the wrong folder. Run `cd /Users/<you>/Documents/GitHub/daniy4i.github.io` first, then retry commands.
- If you get `make: *** No rule to make target \`do-it-all\``:
  1. Run `git pull` to get the latest `Makefile` and `scripts/` folder.
  2. Retry with either `make do-it-all` or `make do_it_all`.
  3. Fallback (no Make required): `./scripts/do_it_all.sh`.
- Apple Silicon note: YOLO/Ultralytics is installed only on `x86_64` containers to avoid PyTorch wheel issues on ARM; ARM builds still run with fallback analytics mode.
- Dependency note: NumPy is pinned to `1.26.4` to stay compatible with both `opencv-python-headless` and `ultralytics` during image builds.
- If YOLO weights cannot download, worker still emits congestion windows using fallback motion stats.
- If worker logs show `Received unregistered task of type 'app.workers.tasks.process_job'`, rebuild and restart backend+worker so Celery reloads task discovery:
  ```bash
  docker compose -f infra/docker-compose.yml down
  docker compose -f infra/docker-compose.yml build --no-cache backend worker
  docker compose -f infra/docker-compose.yml up -d
  docker compose -f infra/docker-compose.yml logs -f worker
  ```
- Verify MinIO endpoint and credentials in `.env`/compose.


Data product retrieval:
```bash
# After a job succeeds
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/jobs/<job_id>/data_product

# Artifact manifest + direct artifact URL
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/jobs/<job_id>/artifacts
curl -H "Authorization: Bearer <token>" -L http://localhost:8000/api/jobs/<job_id>/artifacts/preview_tracking.mp4 -o preview_tracking.mp4
curl -H "Authorization: Bearer <token>" -L "http://localhost:8000/api/jobs/<job_id>/data_pack?format=zip" -o data_pack_v1.zip
```
