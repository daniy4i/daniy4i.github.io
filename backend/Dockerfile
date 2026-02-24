FROM python:3.11-slim
WORKDIR /app
# System deps: ffmpeg for encoding + libs needed by OpenCV/Ultralytics in slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Ensure Ultralytics exists in the container (this is what your logs are missing)
RUN pip install --no-cache-dir ultralytics==8.3.0
RUN useradd --create-home --shell /bin/bash appuser
COPY --chown=appuser:appuser app ./app
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
