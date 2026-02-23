from __future__ import annotations

from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from app.workers.vision.annotate import annotate_frame
from app.workers.vision.tracking import track_frame


class _FakeTensor:
    def __init__(self, values):
        self._values = values

    def int(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return np.array(self._values)

    def tolist(self):
        return list(self._values)


class _FakeBoxes:
    def __init__(self):
        self.id = _FakeTensor([1, 2])
        self.xywh = _FakeTensor([[100.0, 80.0, 40.0, 30.0], [180.0, 90.0, 42.0, 32.0]])
        self.conf = _FakeTensor([0.9, 0.85])
        self._classes = [2, 2]

    def __len__(self):
        return 2

    def __iter__(self):
        for cls in self._classes:
            yield type("FakeBox", (), {"cls": np.array([cls])})()


class _FakeResult:
    def __init__(self):
        self.boxes = _FakeBoxes()
        self.names = {2: "car"}


class _FakeModel:
    def track(self, *_args, **_kwargs):
        return [_FakeResult()]


def test_tracking_returns_stable_track_ids_across_frames():
    model = _FakeModel()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    first = track_frame(model, frame, clip_id="clipA", timestamp_s=0.0, frame_width=320, frame_height=240)
    second = track_frame(model, frame, clip_id="clipA", timestamp_s=0.2, frame_width=320, frame_height=240)

    assert [d["track_id"] for d in first] == [1, 2]
    assert [d["track_id"] for d in second] == [1, 2]


def test_preview_tracking_mp4_generated(tmp_path: Path):
    cv2 = pytest.importorskip("cv2")

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detections = [{"track_id": 7, "class": "car", "conf": 0.9, "xc": 120.0, "yc": 100.0, "w": 60.0, "h": 40.0}]
    history: dict[int, list[tuple[float, float]]] = {}
    frames = [annotate_frame(frame, detections, history, trail_length=5) for _ in range(3)]

    out_path = tmp_path / "preview_tracking.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, 15, (320, 240))
    try:
        for f in frames:
            writer.write(f)
    finally:
        writer.release()

    assert out_path.exists()
    assert out_path.stat().st_size > 0
