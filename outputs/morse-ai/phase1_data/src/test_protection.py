"""Create-once baseline; later calls only verify. No test WAV is ever written."""
from pathlib import Path
from .common import ROOT, sha256, read_csv, write_csv, write_json, digest
from .dataset_audit import active


def snapshot(rows):
    return sorted([{'filename':r['filename'], 'path':r['path'], 'label':r['label'],
        'original_label':r['original_label'], 'source_id':r['source_id'], 'active':int(active(r)),
        'sha256':r['sha256'], 'sample_rate':r['sample_rate'], 'duration':r['duration']}
        for r in rows if r['split']=='test'], key=lambda r:r['path'])


def freeze_or_verify(rows, cfg, root=ROOT):
    root = Path(root); target = root / 'reports/test_manifest.csv'
    test_rows = [r for r in rows if r['split']=='test']
    if not test_rows or any(r['status']!='ok' for r in test_rows):
        raise ValueError('Missing or invalid test inventory; baseline not accepted')
    current = snapshot(rows)
    if target.exists():
        stored = read_csv(target)
        def normalize(items): return [{k:str(v) for k,v in r.items()} for r in items]
        if normalize(current) != normalize(stored):
            raise ValueError('TEST BASELINE CHANGED: content, label, selection or inventory mismatch')
    else:
        write_csv(target, current, exclusive=True)
        write_json(root / 'reports/test_lock.json', {'manifest_sha256':sha256(target),
            'sources':cfg['existing_sources'], 'labels':cfg['labels'], 'count':len(current)}, exclusive=True)
    verify_lock(root)
    return len(current)


def verify_lock(root=ROOT, read_audio=True):
    import json
    root = Path(root); target = root / 'reports/test_manifest.csv'
    lock = json.loads((root / 'reports/test_lock.json').read_text(encoding='utf-8'))
    if sha256(target) != lock['manifest_sha256']: raise ValueError('Test manifest was changed')
    rows = read_csv(target)
    if read_audio:
        for row in rows:
            if not Path(row['path']).is_file() or sha256(row['path']) != row['sha256']:
                raise ValueError(f'TEST CHANGED OR MISSING: {row["path"]}')
        # Detect additions as well as changed/deleted files in all frozen test folders.
        expected = {Path(r['path']).resolve() for r in rows}
        actual = set()
        for source in lock['sources']:
            directory = (root / source['path']).resolve() / 'test'
            actual.update(p.resolve() for p in directory.rglob('*.wav'))
        if actual != expected: raise ValueError('Test inventory added/removed')
    return rows
