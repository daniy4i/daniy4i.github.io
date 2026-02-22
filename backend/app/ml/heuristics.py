from collections import defaultdict


def in_center(xc: float, frame_w: int) -> bool:
    return frame_w * 0.33 <= xc <= frame_w * 0.67


def cut_in_confidence(track_points: list[dict], frame_w: int) -> float:
    if len(track_points) < 3:
        return 0.0
    start, end = track_points[0], track_points[-1]
    start_region = "center" if in_center(start["xc"], frame_w) else ("left" if start["xc"] < frame_w * 0.33 else "right")
    end_center = in_center(end["xc"], frame_w)
    area_growth = (end["area"] - start["area"]) / max(start["area"], 1)
    if start_region in {"left", "right"} and end_center and area_growth > 0.35:
        return min(1.0, 0.5 + area_growth / 2)
    return 0.0


def close_following_confidence(track_points: list[dict], frame_w: int, min_seconds: float = 2.0) -> float:
    centered = [p for p in track_points if in_center(p["xc"], frame_w) and p["area_ratio"] > 0.08]
    if not centered:
        return 0.0
    dur = centered[-1]["t"] - centered[0]["t"]
    if dur < min_seconds:
        return 0.0
    return min(1.0, dur / 6.0)


def bike_proximity_confidence(bike_points: list[dict], frame_w: int) -> float:
    close = [p for p in bike_points if in_center(p["xc"], frame_w) and p["area_ratio"] > 0.01]
    if not close:
        return 0.0
    return min(1.0, 0.4 + len(close) * 0.1)


def congestion_score(active_tracks: int, avg_motion: float) -> float:
    density = min(1.0, active_tracks / 20)
    low_motion = 1 - min(1.0, avg_motion / 25)
    return round(100 * (0.6 * density + 0.4 * low_motion), 2)


def build_windows(samples: list[dict], window_s: int = 5) -> list[dict]:
    buckets = defaultdict(list)
    for s in samples:
        buckets[int(s["t"] // window_s)].append(s)
    out = []
    for idx, vals in sorted(buckets.items()):
        motions = [v.get("motion", 0.0) for v in vals]
        out.append({
            "t_start": idx * window_s,
            "t_end": (idx + 1) * window_s,
            "active_tracks": max(v.get("active_tracks", 0) for v in vals),
            "avg_motion": sum(motions) / max(1, len(motions)),
        })
    return out
