# Data Pack Spec (v1)

## Version
- `datapack_version`: `v1`

## Files
- `job_summary.json`
- `windows.parquet`, `windows.csv`
- `events.jsonl`, `events.csv`
- `tracks.jsonl`, `tracks.csv`
- `data_pack_v1.zip` (bundle)

## windows schema
- `clip_id`
- `t_start`, `t_end`
- `congestion_score` (0-100)
- `active_tracks`
- `avg_raw_speed`
- `avg_compensated_speed`
- `avg_speed_proxy`
- `stopped_ratio`
- `density_index`

## events schema
- `clip_id`
- `event_id`
- `type`
- `timestamp`
- `confidence`
- `track_id`
- `details_json`
- `clip_key`
- `review_status`

## tracks schema
- `clip_id`
- `track_id`
- `class`
- `start_t`, `end_t`
- `bbox_stats_json`
- `motion_stats_json`
- `trajectory_sampled`

## Privacy posture
- No raw plate strings exported.
- No face identity labels.
- Artifacts are aggregate/trajectory based and include SHA-256 hashes in manifest.
