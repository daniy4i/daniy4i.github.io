import hashlib
import json
from datetime import datetime, timezone


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_payload(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def build_marketplace_payload(job_id: int, filename: str, duration_s: float, analytics_windows: list[dict], event_counts: dict, class_counts: dict) -> dict:
    return {
        "version": "1.0",
        "job_id": job_id,
        "source_file": filename,
        "duration_s": round(duration_s, 2),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "contains_raw_video": False,
            "contains_identifiers": False,
            "notes": "Aggregated traffic statistics only. No plate or face identifiers."
        },
        "aggregates": {
            "event_counts": event_counts,
            "class_counts": class_counts,
            "analytics_windows": analytics_windows,
        },
    }
