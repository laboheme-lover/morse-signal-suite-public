"""Single authoritative international table; exported from the existing project."""
import json
from pathlib import Path

_document = json.loads((Path(__file__).resolve().parents[1] / 'config/morse_table.json').read_text(encoding='utf-8'))
TABLE = _document['entries']
REVERSE = {v: k for k, v in TABLE.items()}


def morse_code(label):
    if label not in TABLE:
        raise ValueError(f'Expected canonical A-Z / 0-9, got {label!r}')
    return TABLE[label]
