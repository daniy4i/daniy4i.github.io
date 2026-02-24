from __future__ import annotations

from typing import Any

import numpy as np

from app.core.logging import logger

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None


DEFAULT_TARGET_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}


def load_yolo_model(weights: str = "/app/backend/yolov8n.pt") -> Any | None:
    if YOLO is None:
        logger.warning("yolo.unavailable", reason="ultralytics import failed")
        return None
    try:
        return YOLO(weights)
    except Exception as exc:  # pragma: no cover
        logger.warning("yolo.unavailable", reason=str(exc))
        return None


def track_frame(
    model: Any | None,
    frame: np.ndarray,
    *,
    clip_id: str,
    timestamp_s: float,
    frame_width: int,
    frame_height: int,
    target_classes: set[str] | None = None,
) -> list[dict[str, Any]]:
    if model is None:
        return []

    classes = target_classes or DEFAULT_TARGET_CLASSES
    result = model.track(frame, persist=True, verbose=False)[0]
    if result.boxes is None or len(result.boxes) == 0:
        return []

    boxes = result.boxes
    ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
    xys = boxes.xywh.cpu().numpy()
    confs = boxes.conf.cpu().tolist() if boxes.conf is not None else [0.0] * len(boxes)

    detections: list[dict[str, Any]] = []
    for i, box in enumerate(boxes):
        cls_name = result.names[int(box.cls[0])]
        if cls_name not in classes:
            continue
        tid = ids[i] if i < len(ids) else None
        x, y, w, h = xys[i]
        area = float(max(1.0, w * h))
        detections.append(
            {
                "clip_id": clip_id,
                "class": cls_name,
                "track_id": int(tid) if tid is not None else -1,
                "t": float(timestamp_s),
                "xc": float(x),
                "yc": float(y),
                "w": float(w),
                "h": float(h),
                "conf": float(confs[i]),
                "area": area,
                "area_ratio": area / float(max(1, frame_width * frame_height)),
            }
        )
    return detections
