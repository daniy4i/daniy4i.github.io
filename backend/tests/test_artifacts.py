from pathlib import Path

from app.workers.artifacts import ARTIFACT_NAMES, artifact_entry


def test_artifact_entry_collects_metadata(tmp_path: Path):
    p = tmp_path / "preview_tracking.mp4"
    payload = b"1234567890"
    p.write_bytes(payload)

    out = artifact_entry(name=p.name, key="jobs/1/artifacts/preview_tracking.mp4", path=str(p), mime_type="video/mp4")

    assert out["name"] == "preview_tracking.mp4"
    assert out["key"].endswith("preview_tracking.mp4")
    assert out["mime_type"] == "video/mp4"
    assert out["size_bytes"] == len(payload)


def test_required_artifact_names_present():
    required = {"job_summary.json", "preview_tracking.mp4", "events.jsonl", "tracks.jsonl", "windows.parquet"}
    assert required.issubset(set(ARTIFACT_NAMES.values()))
