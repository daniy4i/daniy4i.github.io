from pathlib import Path
import hashlib
import mimetypes

ARTIFACT_NAMES = {
    "summary": "job_summary.json",
    "preview": "preview_tracking.mp4",
    "events": "events.jsonl",
    "events_csv": "events.csv",
    "tracks": "tracks.jsonl",
    "tracks_csv": "tracks.csv",
    "windows_parquet": "windows.parquet",
    "windows_csv": "windows.csv",
    "data_pack_zip": "data_pack_v1.zip",
}


def artifact_key(job_id: int, name: str) -> str:
    return f"jobs/{job_id}/artifacts/{name}"


def artifact_entry(name: str, key: str, path: str, mime_type: str | None = None) -> dict:
    guessed = mime_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    return {
        "name": name,
        "key": key,
        "mime_type": guessed,
        "size_bytes": int(Path(path).stat().st_size),
        "sha256": hash_file(path),
    }


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
