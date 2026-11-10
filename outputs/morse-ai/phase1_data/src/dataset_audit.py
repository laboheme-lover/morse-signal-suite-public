"""Inventory and actual waveform audit. Never writes into input datasets."""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import numpy as np
import soundfile as sf
from .common import ROOT, read_csv, write_csv, write_json, contained, sha256
from .legacy import legacy_tables
from .morse_table import TABLE, REVERSE

AUDIT_FIELDS = ['source_id', 'filename', 'path', 'split', 'original_label', 'label', 'morse_code',
    'mapping_policy', 'active', 'status', 'issues', 'sha256', 'pcm_sha256', 'expected_sha256',
    'sample_rate', 'channels', 'format', 'subtype', 'duration', 'frames', 'peak', 'rms',
    'frequency', 'snr_db', 'noise_type', 'sample_id', 'source_group']


def inspect_record(path, record, sample_rate):
    import hashlib
    row = {key: '' for key in AUDIT_FIELDS} | record | {'path': str(path), 'filename': path.name}
    problems = []
    try:
        row['sha256'] = sha256(path)
        info = sf.info(path)
        audio, sr = sf.read(path, dtype='float64', always_2d=True)
        row.update(sample_rate=sr, channels=info.channels, format=info.format, subtype=info.subtype,
                   duration=info.duration, frames=info.frames)
        row['pcm_sha256'] = hashlib.sha256(str((sr, audio.shape)).encode() + audio.tobytes()).hexdigest()
        if not len(audio) or not np.isfinite(audio).all(): problems.append('empty_or_nonfinite')
        else:
            row['peak'] = float(np.max(np.abs(audio))); row['rms'] = float(np.sqrt(np.mean(audio**2)))
            if row['rms'] == 0: problems.append('silent')
            if row['peak'] >= 1: problems.append('clipped')
        if sr != sample_rate or info.channels != 1 or info.format != 'WAV' or not info.subtype.startswith('PCM_'):
            problems.append('incompatible_format')
        if row['expected_sha256'] and row['expected_sha256'] != row['sha256']: problems.append('metadata_hash_mismatch')
    except FileNotFoundError: problems.append('missing')
    except Exception as error: problems.append('unreadable:' + type(error).__name__)
    if row.get('issues'): problems.append(row['issues'])
    row['status'] = 'error' if problems else 'ok'
    row['issues'] = ';'.join(problems)
    return row


def scan_sources(cfg, root=ROOT, include_generated=True):
    root = Path(root)
    wabun, _ = legacy_tables()
    rows = []
    for source in cfg['existing_sources']:
        base = (root / source['path']).resolve()
        meta = base / 'metadata.csv'
        if not meta.exists(): raise ValueError(f'Missing source metadata: {meta}')
        expected = set()
        for old in read_csv(meta):
            raw_path = base / old['filepath']; path = contained(raw_path, base)
            if any(p.is_symlink() for p in [raw_path, *raw_path.parents] if p.is_relative_to(base)):
                raise ValueError(f'Symlink input not accepted: {raw_path}')
            expected.add(path)
            label, code, split = old['label'], old.get('morse_code', ''), old['split']
            if source['label_system'] == 'wabun':
                valid = wabun.get(label) == code
                canonical = REVERSE.get(code, '') if valid else ''
                policy = 'single_symbol_same_code' if canonical else 'not_in_target_36'
            else:
                valid = TABLE.get(label) == code
                canonical = label if valid else ''; policy = 'identity'
            record = {'source_id': source['id'], 'split': split, 'original_label': label,
                'label': canonical, 'morse_code': code, 'mapping_policy': policy,
                'active': int(split in source['active_splits'] and canonical in cfg['labels']),
                'issues': '' if valid and split in ('train', 'validation', 'test') else 'label_code_or_split_mismatch',
                'expected_sha256': old.get('wav_sha256', ''), 'frequency': old.get('frequency_hz', ''),
                'snr_db': old.get('snr_db', ''), 'noise_type': old.get('noise_type', ''),
                'sample_id': source['id'] + ':' + old['sample_id'], 'source_group': old.get('esc50_src_file', '')}
            rows.append(inspect_record(path, record, cfg['sample_rate']))
            if len(rows) % 5000 == 0: print(f'Audited {len(rows)} WAVs', flush=True)
        for path in sorted(base.rglob('*.wav')):
            if path.resolve() not in expected:
                split = next((p for p in path.relative_to(base).parts if p in ('train','validation','test')), 'unknown')
                rows.append(inspect_record(path.resolve(), {'source_id':source['id'], 'split':split,
                    'active':0, 'issues':'unlisted_file'}, cfg['sample_rate']))
    if include_generated:
        for split in ('train', 'validation'):
            for meta in sorted((root / 'metadata/generated').glob(f'{split}_*.csv')):
                for old in read_csv(meta):
                    path = contained(root / old['filename'], root / 'data/generated')
                    rows.append(inspect_record(path, {'source_id':'generated', 'split':old['split'],
                        'original_label':old['label'], 'label':old['label'], 'morse_code':old['morse_code'],
                        'mapping_policy':'identity', 'active':1, 'expected_sha256':old['sha256'],
                        'frequency':old['frequency'], 'snr_db':old['snr_db'], 'noise_type':old['noise_type'],
                        'sample_id':old['sample_id']}, cfg['sample_rate']))
        known = {r['path'] for r in rows if r['source_id'] == 'generated'}
        for path in (root / 'data/generated').rglob('*.wav'):
            if str(path.resolve()) not in known:
                rows.append(inspect_record(path, {'source_id':'generated','active':0,'split':'unknown','issues':'orphan_generated'},cfg['sample_rate']))
    return rows


def active(row):
    return str(row.get('active')) == '1'


def leakage(rows):
    findings = []
    for key in ('sha256', 'pcm_sha256', 'filename', 'source_group'):
        groups = defaultdict(list)
        for row in rows:
            if row.get(key): groups[row[key]].append(row)
        for value, group in groups.items():
            splits = {r['split'] for r in group}
            if len(splits) < 2: continue
            is_audio = key in ('sha256', 'pcm_sha256')
            severity = 'WARNING'
            selected = [r for r in group if active(r)]
            selected_splits = {r['split'] for r in selected}
            if is_audio and ('test' in splits and any(active(r) and r['split'] == 'train' for r in group)):
                severity = 'ERROR'
            elif is_audio and len(selected_splits) > 1: severity = 'ERROR'
            elif key == 'source_group' and len(selected_splits) > 1: severity = 'ERROR'
            findings.append({'severity':severity, 'kind':key, 'value':value,
                'splits':','.join(sorted(splits)), 'labels':','.join(sorted({r.get('label','') for r in group})),
                'paths':json.dumps([r['path'] for r in group], ensure_ascii=False)})
    # Same decoded data must not have contradictory canonical labels even within one split.
    groups = defaultdict(list)
    for row in rows:
        if active(row) and row.get('pcm_sha256'): groups[row['pcm_sha256']].append(row)
    for value, group in groups.items():
        if len({r['label'] for r in group}) > 1:
            findings.append({'severity':'ERROR','kind':'label_conflict','value':value,
                'splits':','.join(sorted({r['split'] for r in group})), 'labels':','.join(sorted({r['label'] for r in group})),
                'paths':json.dumps([r['path'] for r in group],ensure_ascii=False)})
    return findings


def audit(cfg, root=ROOT):
    root = Path(root); rows = scan_sources(cfg, root); findings = leakage(rows)
    reports = root / 'reports'
    write_csv(reports / 'dataset_audit.csv', rows, AUDIT_FIELDS)
    write_csv(reports / 'leakage.csv', findings, ['severity','kind','value','splits','labels','paths'])
    counts = Counter((r['source_id'],r['split'],r['original_label'],r['label']) for r in rows)
    write_csv(reports / 'class_counts.csv', [{'source_id':s,'split':sp,'original_label':o,'label':l,'count':n}
        for (s,sp,o,l),n in sorted(counts.items())])
    summary = {'inventory_rows':len(rows), 'unique_files':len({r['path'] for r in rows}),
        'source_counts':dict(Counter(r['source_id'] for r in rows)),
        'active_counts':dict(Counter(r['split'] for r in rows if active(r) and r['status']=='ok')),
        'active_classes':{sp:len({r['label'] for r in rows if active(r) and r['split']==sp and r['status']=='ok'}) for sp in ('train','validation','test')},
        'errors':sum(r['status']!='ok' for r in rows),
        'leakage_errors':sum(f['severity']=='ERROR' for f in findings),
        'leakage_warnings':sum(f['severity']=='WARNING' for f in findings)}
    write_json(reports / 'dataset_audit_summary.json', summary)
    (reports / 'dataset_audit_summary.txt').write_text(json.dumps(summary,ensure_ascii=False,indent=2) +
        '\nRead-only inventory. Original labels retained. Active mapping uses confirmed single-symbol code equivalence.\n',encoding='utf-8')
    return rows, summary
