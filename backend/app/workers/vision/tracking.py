from __future__ import annotations

from typing import Any

import numpy as np

from app.core.logging import logger

# Optional import: lets the app run even if ultralytics isn't installed in some envs
try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None


DEFAULT_TARGET_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}


def load_yolo_model(weights: str = "yolov8n.pt") -> Any | None:
    """
    Load a YOLO model. Returns None if ultralytics isn't available or the model fails to load.
    """
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
    """
    Run tracking on a frame and return normalized detections with track ids (if available).
    """
    if model is None:
        return []

    classes = target_classes or DEFAULT_TARGET_CLASSES

    try:
        results = model.track(frame, persist=True, verbose=False)
        if not results:
            return []
        result = results[0]
    except Exception as exc:  # pragma: no cover
        logger.warning("yolo.track_failed", reason=str(exc))
        return []

    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    # Ultralytics Boxes store tensors on device; move to CPU numpy/lists safely
    try:
        n = len(boxes)
    except Exception:
        return []

    if n == 0:
        return []

    # xywh: (n, 4) => x_center, y_center, width, height (in pixels)
    try:
        xys = boxes.xywh.cpu().numpy()
    except Exception:
        return []

    # conf: (n,) floats
    try:
        confs = boxes.conf.cpu().tolist() if getattr(boxes, "conf", None) is not None else [0.0] * n
    except Exception:
        confs = [0.0] * n

    # cls: (n,) ints
    try:
        clses = boxes.cls.cpu().numpy().astype(int)
    except Exception:
        return []

    # ids: (n,) ints or None
    ids_tensor = getattr(boxes, "id", None)
    if ids_tensor is not None:
        try:
            ids = ids_tensor.int().cpu().tolist()
        except Exception:
            ids = [None] * n
    else:
        ids = [None] * n

    names = getattr(result, "names", {}) or {}

    detections: list[dict[str, Any]] = []
    img_area = float(max(1, frame_width * frame_height))

    for i in range(n):
        cls_idx = int(clses[i])
        cls_name = names.get(cls_idx, str(cls_idx))

        if cls_name not in classes:
            continue

        tid = ids[i] if i < len(ids) else None
        x, y, w, h = xys[i]

        area = float(max(1.0, float(w) * float(h)))

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
                "conf": float(confs[i]) if i < len(confs) else 0.0,
                "area": area,
                "area_ratio": area / img_area,
            }
        )

    return detections