# API

Base path: `/api`

- `POST /auth/login`
- `POST /videos/upload`
- `POST /jobs/{job_id}/run`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/clips`
- `GET /jobs/{job_id}/events`
- `GET /jobs/{job_id}/analytics`
- `GET /jobs/{job_id}/event_clip/{event_id}`
- `GET /jobs/{job_id}/preview`
- `GET /jobs/{job_id}/artifacts`
- `GET /jobs/{job_id}/artifacts/{name}`
- `GET /jobs/{job_id}/data_pack?format=zip|parquet|csv|jsonl`
- `POST /events/{event_id}/review`

All endpoints except login require `Authorization: Bearer <token>`.

Upload supports either a single video (`mp4/mov/mkv`) or a ZIP containing multiple clips.

Review payload:
```json
{
  "review_status": "confirm",
  "review_notes": "optional"
}
```


## GET /api/jobs/{job_id}/data_product
Returns a presigned URL for an anonymized aggregated data product plus its SHA-256 hash.

## GET /api/jobs/{job_id}/preview
Returns a presigned URL for the processed preview video (`preview_tracking.mp4`).

Example response:
```json
{
  "url": "https://..."
}
```

## GET /api/jobs/{job_id}/artifacts
Returns the artifact manifest for the job.

Example response:
```json
{
  "job_id": 1,
  "artifacts": [
    {"name":"preview_tracking.mp4","key":"jobs/1/artifacts/preview_tracking.mp4","mime_type":"video/mp4","size_bytes":12345}
  ]
}
```

## GET /api/jobs/{job_id}/artifacts/{name}
Returns a presigned URL for the requested artifact name.

## GET /api/jobs/{job_id}/clips
Returns clip list for a batch job.

## GET /api/jobs/{job_id}/events?clip_id=<clip_id>
Filters events by clip.

## GET /api/jobs/{job_id}/analytics?clip_id=<clip_id>
Filters analytics windows by clip.

## GET /api/jobs/{job_id}/data_pack?format=zip|parquet|csv|jsonl
Returns a presigned URL for Data Pack v1 exports:
- `zip` -> `data_pack_v1.zip`
- `parquet` -> `windows.parquet`
- `csv` -> `windows.csv`
- `jsonl` -> `events.jsonl`

Example response:
```json
{
  "job_id": 42,
  "sha256": "<hex>",
  "url": "https://..."
}
```
