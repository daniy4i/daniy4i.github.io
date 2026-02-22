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
- `POST /events/{event_id}/review`

All endpoints except login require `Authorization: Bearer <token>`.

Review payload:
```json
{
  "review_status": "confirm",
  "review_notes": "optional"
}
```
