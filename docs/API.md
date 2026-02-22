# API

Base path: `/api`

- `POST /auth/login`
- `POST /videos/upload`
- `POST /jobs/{job_id}/run`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/events`
- `GET /jobs/{job_id}/analytics`
- `GET /jobs/{job_id}/event_clip/{event_id}`
- `GET /jobs/{job_id}/preview`
- `POST /events/{event_id}/review`

All endpoints except login require `Authorization: Bearer <token>`.

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
Returns a presigned URL for the processed preview video (`annotated_preview.mp4`).

Example response:
```json
{
  "url": "https://..."
}
```

Example response:
```json
{
  "job_id": 42,
  "sha256": "<hex>",
  "url": "https://..."
}
```
