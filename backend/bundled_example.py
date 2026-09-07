"""Versioned public media and the immutable, sanitized recorded analysis."""
import hashlib
import json
from pathlib import Path


MARA_REFERENCE = "sample:mara-v1"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "samples" / "recorded_mara.json"


def resolve_video_path(reference: str, samples_dir: Path) -> Path:
    if reference == MARA_REFERENCE:
        return samples_dir / "sample_short.mp4"
    if reference.startswith("sample:"):
        raise FileNotFoundError("This bundled media version is unavailable.")
    # Old uploads keep their original identity. Never substitute a different film.
    return Path(reference)


def load_recorded_example(samples_dir: Path) -> dict:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    for filename, key in (("sample_short.mp4", "video_sha256"), ("sample_ad.srt", "srt_sha256")):
        if hashlib.sha256((samples_dir / filename).read_bytes()).hexdigest() != snapshot[key]:
            raise ValueError("Recorded example assets do not match the verified analysis.")
    return snapshot
