from pathlib import Path
import csv
import json
from .common import ROOT, read_csv, write_csv, write_json, sha256, digest
from .dataset_audit import active, leakage
from .test_protection import verify_lock

FIELDS = ['sample_id','filename','label','morse_code','split','sample_rate','frequency','amplitude',
          'dot_duration','timing_jitter','noise_type','snr_db','random_seed','generated_at','sha256',
          'duration','original_label','source_id','mapping_policy','source_group','provenance',
          'software_version','config_hash','mix_gain','measured_snr_db','saved_snr_db','timing_samples']


def prepare_existing(rows, cfg, root=ROOT):
    root = Path(root)
    if any(active(r) and r['status'] != 'ok' for r in rows): raise ValueError('Invalid active input; audit must pass')
    if any(r['severity']=='ERROR' for r in leakage(rows)): raise ValueError('Leakage ERROR; index publication blocked')
    verify_lock(root)
    original_metadata = {}
    for source in cfg['existing_sources']:
        for old in read_csv((root/source['path']).resolve()/'metadata.csv'):
            original_metadata[source['id']+':'+old['sample_id']] = old
    table_path = root / 'metadata/label_mapping.json'
    labels = {label:i for i,label in enumerate(cfg['labels'])}
    if table_path.exists():
        if json.loads(table_path.read_text()) != labels: raise ValueError('Fixed label mapping changed')
    else: write_json(table_path,labels,exclusive=True)
    for split in ('train','validation','test'):
        selected = []; seen = set()
        for row in rows:
            if row['source_id']=='generated' or not active(row) or row['split'] != split: continue
            if row['sha256'] in seen: continue
            seen.add(row['sha256'])
            item = {k:'' for k in FIELDS}
            item.update(sample_id=row['sample_id'],filename=row['path'],label=row['label'],
                morse_code=row['morse_code'],split=split,sample_rate=row['sample_rate'],frequency=row['frequency'],
                noise_type=row['noise_type'],snr_db=row['snr_db'],sha256=row['sha256'],duration=row['duration'],
                original_label=row['original_label'],source_id=row['source_id'],mapping_policy=row['mapping_policy'],
                source_group=row['source_group'],provenance='existing: original files unchanged; unknown metadata left blank')
            old = original_metadata[row['sample_id']]
            for key in ('amplitude','dot_duration','timing_jitter','mix_gain','measured_snr_db','timing_samples'):
                item[key] = old.get(key,'')
            item['random_seed'] = old.get('seed','')
            item['software_version'] = old.get('generator_version','')
            selected.append(item)
        path = root / f'metadata/existing_{split}.csv'
        if path.exists():
            if digest(read_csv(path)) != digest([{k:str(v) for k,v in row.items()} for row in selected]):
                raise ValueError(f'Frozen existing index changed: {split}; use separate experiment directory')
        else: write_csv(path,selected,FIELDS,exclusive=True)
    rebuild_indices(root)


def rebuild_indices(root=ROOT):
    root = Path(root); all_rows=[]
    for split in ('train','validation','test'):
        base = read_csv(root / f'metadata/existing_{split}.csv')
        if split != 'test':
            for path in sorted((root / 'metadata/generated').glob(f'{split}_*.csv')):
                base.extend(read_csv(path))
        if any(r['split'] != split for r in base): raise ValueError('Index contains mixed splits')
        dest = root / f'metadata/{split}.csv'
        if split == 'test' and dest.exists():
            if read_csv(dest) != base: raise ValueError('Frozen evaluation index changed')
        else: write_csv(dest,base,FIELDS,exclusive=(split=='test'))
        all_rows.extend(base)
    write_csv(root / 'metadata/metadata.csv',all_rows,FIELDS)
    stamp = root / 'reports/evaluation_index_lock.json'
    current = {'test_index_sha256':sha256(root / 'metadata/test.csv'),
               'labels_sha256':sha256(root / 'metadata/label_mapping.json')}
    if stamp.exists():
        if json.loads(stamp.read_text()) != current: raise ValueError('Fixed test index / labels modified')
    else: write_json(stamp,current,exclusive=True)
