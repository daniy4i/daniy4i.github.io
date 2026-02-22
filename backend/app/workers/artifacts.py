from pathlib import Path
import mimetypes

ARTIFACT_NAMES = {
    "summary": "job_summary.json",
    "preview": "preview_tracking.mp4",
    "events": "events.jsonl",
    "tracks": "tracks.jsonl",
    "windows_parquet": "windows.parquet",
    "windows_csv": "windows.csv",
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
    }
