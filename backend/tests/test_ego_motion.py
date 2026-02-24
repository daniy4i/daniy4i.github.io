import pytest

cv2 = pytest.importorskip("cv2")
import numpy as np

from app.ml.ego_motion import estimate_global_motion


def test_estimate_global_motion_on_synthetic_shift():
    base = np.zeros((180, 240), dtype=np.uint8)
    cv2.rectangle(base, (40, 50), (80, 90), 255, -1)
    cv2.circle(base, (160, 120), 20, 255, -1)

    dx, dy = 6, -4
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    shifted = cv2.warpAffine(base, M, (base.shape[1], base.shape[0]))

    est_dx, est_dy = estimate_global_motion(base, shifted)
    assert abs(est_dx - dx) < 1.5
    assert abs(est_dy - dy) < 1.5
