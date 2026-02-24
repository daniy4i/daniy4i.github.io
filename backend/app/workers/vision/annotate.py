from __future__ import annotations

from typing import Any

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None
import numpy as np


def blur_privacy(frame: np.ndarray) -> np.ndarray:
    h, _ = frame.shape[:2]
    roi = frame[int(h * 0.2): int(h * 0.8), :]
    frame[int(h * 0.2): int(h * 0.8), :] = cv2.GaussianBlur(roi, (21, 21), 20)
    return frame


def annotate_frame(
    frame: np.ndarray,
    detections: list[dict[str, Any]],
    track_history: dict[int, list[tuple[float, float]]],
    *,
    trail_length: int = 20,
) -> np.ndarray:
    if cv2 is None:
        return frame.copy()

    annotated = frame.copy()
    for det in detections:
        x1 = int(det["xc"] - det["w"] / 2)
        y1 = int(det["yc"] - det["h"] / 2)
        x2 = int(det["xc"] + det["w"] / 2)
        y2 = int(det["yc"] + det["h"] / 2)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (77, 255, 196), 2)
        label = f"ID {det['track_id']} {det['class']} {det['conf']:.2f}"
        cv2.putText(annotated, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (77, 255, 196), 2)

        track_id = int(det.get("track_id", -1))
        if track_id >= 0:
            history = track_history.setdefault(track_id, [])
            history.append((float(det["xc"]), float(det["yc"])))
            if len(history) >= 2:
                pts = np.array(history[-trail_length:], dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(annotated, [pts], isClosed=False, color=(230, 230, 230), thickness=2)

    return blur_privacy(annotated)
