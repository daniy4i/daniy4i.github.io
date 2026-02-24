from __future__ import annotations

import re
from typing import Any

DATAPACK_VERSION = "v1"
_PLATE_KEY_RE = re.compile(r"plate|license", re.IGNORECASE)


def compute_window_metrics(active_tracks: int, avg_compensated_speed: float) -> dict[str, float]:
    density_index = min(1.0, active_tracks / 20.0)
    speed_norm = min(1.0, max(0.0, avg_compensated_speed / 8.0))
    stopped_ratio = max(0.0, min(1.0, 1.0 - speed_norm))
    avg_speed_proxy = round(avg_compensated_speed, 3)
    return {
        "stopped_ratio": round(stopped_ratio, 3),
        "density_index": round(density_index, 3),
        "avg_speed_proxy": avg_speed_proxy,
    }


def contains_plate_like_keys(value: Any) -> bool:
    if isinstance(value, dict):
        for k, v in value.items():
            if _PLATE_KEY_RE.search(str(k)):
                return True
            if contains_plate_like_keys(v):
                return True
        return False
    if isinstance(value, list):
        return any(contains_plate_like_keys(v) for v in value)
    return False
