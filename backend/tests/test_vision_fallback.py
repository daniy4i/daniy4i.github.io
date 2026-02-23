import pytest

pytest.importorskip("numpy")


def test_load_yolo_model_returns_none_when_constructor_fails(monkeypatch):
    import app.workers.vision.tracking as tracking

    class _BrokenYOLO:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("weights missing")

    monkeypatch.setattr(tracking, "YOLO", _BrokenYOLO)
    model = tracking.load_yolo_model("yolov8n.pt")
    assert model is None
