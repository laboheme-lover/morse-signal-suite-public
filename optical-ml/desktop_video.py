"""Local video limits; inspect metadata without reading file bytes into RAM."""
import math
from pathlib import Path

MAX_BYTES = 5 * 1024**3
MAX_SECONDS = 20 * 60

def validate_metadata(size, meta):
    if not 0 < size <= MAX_BYTES:
        raise ValueError('PC版は5 GB（5 GiB）以内の動画に対応します。')
    duration = float(meta['duration'])
    if not math.isfinite(duration) or not 0 < duration <= MAX_SECONDS:
        raise ValueError('PC版は20分以内の動画に対応します。')
    return meta

def inspect_local(path):
    from predict import splitter
    path = Path(path).expanduser()
    if not path.is_file():
        raise ValueError('動画ファイルが見つかりません。')
    size = path.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise ValueError('PC版は5 GB（5 GiB）以内の動画に対応します。')
    return validate_metadata(size, splitter.info(path))
