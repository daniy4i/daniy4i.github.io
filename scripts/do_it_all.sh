#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker is not installed. Install Docker Desktop first: https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker is installed but not running. Please start Docker Desktop, then rerun this script."
  exit 1
fi

mkdir -p backend
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "✅ Created backend/.env from template"
fi

echo "🚀 Starting all services (this can take a few minutes the first time)..."
docker compose -f infra/docker-compose.yml up -d --build

echo "⏳ Waiting for backend health endpoint..."
for i in {1..60}; do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Backend is healthy"
    break
  fi
  sleep 2
  if [ "$i" -eq 60 ]; then
    echo "❌ Backend did not become healthy in time."
    echo "
Container status:"
    docker compose -f infra/docker-compose.yml ps
    echo "
Last backend logs:"
    docker compose -f infra/docker-compose.yml logs backend --tail=120 || true
    echo "
Tips:"
    echo "- Retry: docker compose -f infra/docker-compose.yml restart backend"
    echo "- Follow logs: docker compose -f infra/docker-compose.yml logs -f backend"
    exit 1
  fi
done

echo "\n🎉 NYC Traffic Intelligence is ready"
echo "Frontend: http://localhost:3000"
echo "Backend API docs: http://localhost:8000/docs"
echo "MinIO Console: http://localhost:9001 (user: minioadmin / pass: minioadmin)"

echo "\nNext steps (no coding needed):"
echo "1) Open http://localhost:3000/upload"
echo "2) Upload a dashcam video (.mp4/.mov/.mkv)"
echo "3) Open Jobs page and click a job ID"
echo "4) If needed, trigger run using API docs at /docs: POST /api/jobs/{job_id}/run"

echo "\nTo stop everything later:"
echo "docker compose -f infra/docker-compose.yml down -v"
