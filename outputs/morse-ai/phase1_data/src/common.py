import csv
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ('train', 'validation', 'test')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields=None, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    if exclusive:
        stream = path.open('x', encoding='utf-8-sig', newline='')
    else:
        stream = path.with_suffix(path.suffix + '.tmp').open('w', encoding='utf-8-sig', newline='')
    with stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    if not exclusive:
        os.replace(stream.name, path)


def write_json(path, value, exclusive=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def contained(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Path outside allowed root: {path}')
    return path


def load_config(path=None):
    # JSON is a YAML 1.2 subset: no additional YAML runtime dependency needed.
    cfg = json.loads(Path(path or ROOT / 'config/config.yaml').read_text(encoding='utf-8-sig'))
    from .morse_table import TABLE
    import math
    if cfg['sample_rate'] < 2000 or not isinstance(cfg['sample_rate'], int):
        raise ValueError('sample_rate must be integer >= 2000')
    if not cfg['labels'] or len(set(cfg['labels'])) != len(cfg['labels']) or not set(cfg['labels']) <= TABLE.keys():
        raise ValueError('Unknown/duplicate/empty labels')
    for key in ('frequency', 'dot_duration_ms', 'amplitude', 'timing_jitter'):
        low, high = cfg[key]['min'], cfg[key]['max']
        if not all(math.isfinite(v) for v in (low, high)) or low > high:
            raise ValueError(f'Invalid range: {key}')
    if not 0 < cfg['frequency']['min'] <= cfg['frequency']['max'] < cfg['sample_rate']/2:
        raise ValueError('Frequency must be below Nyquist')
    if not 0 < cfg['amplitude']['min'] <= cfg['amplitude']['max'] <= 1:
        raise ValueError('Amplitude outside (0,1]')
    if cfg['dot_duration_ms']['min'] < 1 or not -1 < cfg['timing_jitter']['min'] <= cfg['timing_jitter']['max'] < 1:
        raise ValueError('Invalid duration/jitter')
    if any(not isinstance(cfg[k], int) or cfg[k] < 0 for k in ('samples_per_class', 'validation_samples_per_class', 'random_seed')):
        raise ValueError('Counts/seed must be nonnegative integers')
    if not cfg['noise_types'] or not set(cfg['noise_types']) <= {'none', 'gaussian', 'white'}:
        raise ValueError('Unsupported noise_types')
    if not cfg['snr_db'] or any(not math.isfinite(s) or not -100 <= s <= 100 for s in cfg['snr_db']):
        raise ValueError('Invalid SNR')
    for k in ('padding_seconds', 'edge_ramp_ms'):
        if not math.isfinite(cfg[k]) or cfg[k] < 0: raise ValueError(f'Invalid {k}')
    return cfg
