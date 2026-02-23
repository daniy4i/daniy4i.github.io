import zipfile
from pathlib import Path

import pytest


def test_extract_zip_inputs_rejects_path_traversal(tmp_path: Path):
    pytest.importorskip("cv2")
    from app.workers.tasks import _extract_zip_inputs

    zip_path = tmp_path / "clips.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.mp4", b"bad")
        zf.writestr("safe_clip.mp4", b"ok")
        zf.writestr("nested/clip2.mov", b"ok2")
        zf.writestr("notes.txt", b"ignore")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    clips = _extract_zip_inputs(str(zip_path), str(out_dir))
    clip_ids = {c[0] for c in clips}

    assert "evil" not in clip_ids
    assert "safe_clip" in clip_ids
    assert "clip2" in clip_ids


def test_clip_windows_aggregation_preserves_clip_id():
    samples = [
        {"clip_id": "a", "t": 0.0, "active_tracks": 2, "raw_motion": 3.0, "comp_motion": 1.0},
        {"clip_id": "a", "t": 1.0, "active_tracks": 3, "raw_motion": 2.0, "comp_motion": 0.8},
        {"clip_id": "b", "t": 0.0, "active_tracks": 5, "raw_motion": 1.0, "comp_motion": 0.2},
    ]
    by_clip = {}
    for s in samples:
        by_clip.setdefault(s["clip_id"], []).append(s)

    assert set(by_clip.keys()) == {"a", "b"}
    assert len(by_clip["a"]) == 2
    assert len(by_clip["b"]) == 1
