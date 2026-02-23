import cv2
import numpy as np


def estimate_global_motion(prev_frame: np.ndarray | None, curr_frame: np.ndarray | None) -> tuple[float, float]:
    """Estimate camera/global motion between two frames as (dx, dy) in pixels."""
    if prev_frame is None or curr_frame is None:
        return 0.0, 0.0

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY) if prev_frame.ndim == 3 else prev_frame
    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY) if curr_frame.ndim == 3 else curr_frame

    prev_pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=300, qualityLevel=0.01, minDistance=8)
    if prev_pts is None or len(prev_pts) == 0:
        return 0.0, 0.0

    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None)
    if curr_pts is None or status is None:
        return 0.0, 0.0

    valid = status.reshape(-1) == 1
    if valid.sum() < 8:
        return 0.0, 0.0

    deltas = curr_pts[valid] - prev_pts[valid]
    dx = float(np.median(deltas[:, 0, 0]))
    dy = float(np.median(deltas[:, 0, 1]))
    return dx, dy
