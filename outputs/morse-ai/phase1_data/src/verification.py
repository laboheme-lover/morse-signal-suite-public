from collections import Counter,defaultdict
from pathlib import Path
import io,json,hashlib
import soundfile as sf
from .common import ROOT,read_csv,sha256,write_json
from .test_protection import verify_lock
from .dataset_audit import leakage,inspect_record
from .dataset_manager import WaveformDataset
from .augmentation import synthesize


def verify(cfg,root=ROOT):
    root=Path(root); protected=verify_lock(root)
    rows=[];counts={};replayed=0
    for split in ('train','validation','test'):
        dataset=WaveformDataset(split,root,purpose='evaluation' if split=='test' else 'training')
        counts[split]=dict(Counter(r['label'] for r in dataset.rows))
        if set(counts[split]) != set(cfg['labels']): raise ValueError(f'Missing classes in {split}')
        for old in dataset.rows:
            path=(root/old['filename']).resolve()
            item=inspect_record(path,{'source_id':old['source_id'],'split':split,'label':old['label'],
                'original_label':old['original_label'],'active':1,'expected_sha256':old['sha256'],
                'morse_code':old['morse_code'],'source_group':old['source_group']},cfg['sample_rate'])
            if item['status']!='ok': raise ValueError(f'Invalid {path}: {item["issues"]}')
            rows.append(item)
            if old['source_id']=='generated':
                saved=json.loads((root/old['provenance']).read_text(encoding='utf-8'))
                audio,clean,details=synthesize(old['label'],saved['config'],int(old['random_seed']))
                buf=io.BytesIO();sf.write(buf,audio,details['sample_rate'],format='WAV',subtype='PCM_16')
                if hashlib.sha256(buf.getvalue()).hexdigest()!=old['sha256']:raise ValueError(f'Replay differs: {path}')
                replayed+=1
            if len(rows)%5000==0: print(f'Verified {len(rows)} active files',flush=True)
    findings=leakage(rows)
    if any(f['severity']=='ERROR' for f in findings):raise ValueError('Cross-split leakage')
    targets={'train':cfg['samples_per_class'],'validation':cfg['validation_samples_per_class']}
    target_met=all(min(counts[sp].values())>=n for sp,n in targets.items())
    summary={'status':'PASS' if target_met else 'VALID_BUT_TARGET_INCOMPLETE','active_files':len(rows),
        'counts':counts,'frozen_test_files':len(protected),'active_test_files':sum(counts['test'].values()),
        'generated_exact_replays':replayed,'leakage_errors':0,'leakage_warnings':len(findings),
        'targets_met':target_met}
    verify_lock(root)
    write_json(root/'reports/verification.json',summary)
    return summary
