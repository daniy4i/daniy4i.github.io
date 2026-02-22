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


def congestion_score(active_tracks: int, avg_compensated_speed: float, stopped_ratio: float, density_index: float) -> float:
    """
    Congestion score (0..100):
      45% density pressure + 35% stopped-pressure + 20% low compensated speed pressure.
    """
    density = max(0.0, min(1.0, density_index if density_index is not None else (active_tracks / 20.0)))
    stopped = max(0.0, min(1.0, stopped_ratio))
    low_speed = 1.0 - min(1.0, max(0.0, avg_compensated_speed) / 8.0)
    score = 100.0 * (0.45 * density + 0.35 * stopped + 0.20 * low_speed)
    return round(max(0.0, min(100.0, score)), 2)


def build_windows(samples: list[dict], window_s: int = 5) -> list[dict]:
    buckets = defaultdict(list)
    for s in samples:
        buckets[int(s["t"] // window_s)].append(s)
    out = []
    for idx, vals in sorted(buckets.items()):
        raw_motions = [v.get("raw_motion", 0.0) for v in vals]
        comp_motions = [v.get("comp_motion", 0.0) for v in vals]
        active_tracks = max(v.get("active_tracks", 0) for v in vals)
        density_index = min(1.0, active_tracks / 20.0)
        stopped_ratio = sum(1 for m in comp_motions if m < 1.0) / max(1, len(comp_motions))
        out.append({
            "t_start": idx * window_s,
            "t_end": (idx + 1) * window_s,
            "active_tracks": active_tracks,
            "avg_raw_speed": sum(raw_motions) / max(1, len(raw_motions)),
            "avg_compensated_speed": sum(comp_motions) / max(1, len(comp_motions)),
            "stopped_ratio": stopped_ratio,
            "density_index": density_index,
            "avg_speed_proxy": sum(comp_motions) / max(1, len(comp_motions)),
        })
    return out
