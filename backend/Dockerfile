FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/backend && python - <<'PY'
from pathlib import Path
from urllib.request import urlopen
url = 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt'
out = Path('/app/backend/yolov8n.pt')
out.write_bytes(urlopen(url, timeout=120).read())
print(f'downloaded {out} ({out.stat().st_size} bytes)')
PY
RUN useradd --create-home --shell /bin/bash appuser
COPY --chown=appuser:appuser app ./app
RUN chown -R appuser:appuser /app/backend
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
