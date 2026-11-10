from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import io
import json
import os
import platform
import numpy as np
import scipy
import soundfile as sf
from .common import ROOT, read_csv, write_csv, write_json, sha256, digest, contained
from .metadata_manager import FIELDS, rebuild_indices
from .morse_table import TABLE
from .augmentation import sample_seed, synthesize, synthesis_config
from .test_protection import verify_lock
from . import VERSION


def safe_output(path, root):
    root=Path(root).absolute(); path=Path(path).absolute()
    if not path.is_relative_to(root/'data/generated'): raise ValueError('Output must be inside data/generated')
    for part in [path, *path.parents]:
        if part.is_relative_to(root) and part.exists() and (part.is_symlink() or part.resolve()!=part.absolute()):
            raise ValueError('Symlink/junction output refused')
    contained(path,root/'data/generated')
    if 'test' in [p.lower() for p in path.relative_to(root).parts]: raise ValueError('Cannot generate Test data')
    return path


def plan_generation(cfg, root=ROOT):
    root=Path(root)
    verify_lock(root,read_audio=False)  # hashes only; generator never reads test waveforms
    if json.loads((root/'metadata/label_mapping.json').read_text()) != {l:i for i,l in enumerate(cfg['labels'])}:
        raise ValueError('Class mapping differs from fixed experiment')
    targets={'train':cfg['samples_per_class'],'validation':cfg['validation_samples_per_class']}
    jobs=[];summary={}; signature=digest(synthesis_config(cfg))
    for split,target in targets.items():
        rows=read_csv(root/f'metadata/{split}.csv')
        if any(r['split']!=split for r in rows): raise ValueError('Contaminated split index')
        counts=Counter(r['label'] for r in rows)
        for label in cfg['labels']:
            # Index includes already generated samples. Ordinals remain stable on an idempotent rerun.
            used={int(r['sample_id'].rsplit(':',1)[-1]) for r in rows if r['source_id']=='generated'
                  and r['label']==label and r['config_hash']==signature}
            cursor=0
            for _ in range(max(0,target-counts[label])):
                while cursor in used: cursor+=1
                jobs.append({'split':split,'label':label,'ordinal':cursor,
                             'random_seed':sample_seed(cfg,split,label,cursor),'config_hash':signature})
                used.add(cursor);cursor+=1
        summary[split]={'existing':len(rows),'target_per_class':target,'to_generate':sum(j['split']==split for j in jobs)}
    return jobs,summary


@contextmanager
def generation_lock(root):
    path=Path(root)/'.generation.lock'
    with path.open('x') as f: f.write(str(os.getpid()))
    try: yield
    finally: path.unlink()  # only this run's lock, never a data directory


def generate(cfg, root=ROOT, dry_run=False, limit=None):
    root=Path(root)
    jobs,summary=plan_generation(cfg,root)
    print(json.dumps({'dry_run':dry_run,'planned':len(jobs),'splits':summary},indent=2),flush=True)
    if dry_run: return summary
    if limit is not None and limit<1: raise ValueError('limit must be positive')
    with generation_lock(root):
        jobs,summary=plan_generation(cfg,root)
        if limit is not None: jobs=jobs[:limit]
        if not jobs: return summary
        # Reserve all known inventory hashes; test hashes need not expose its WAVs to synthesis.
        inventory=read_csv(root/'reports/dataset_audit.csv')
        existing=read_csv(root/'metadata/metadata.csv')
        forbidden={r['sha256'] for r in inventory+existing if r.get('sha256')}
        batch=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        soft={'generator':VERSION,'python':platform.python_version(),'numpy':np.__version__,
              'scipy':scipy.__version__,'soundfile':sf.__version__,'libsndfile':sf.__libsndfile_version__}
        source_hashes={p.name:sha256(p) for p in (ROOT/'src').glob('*.py')}
        source_hashes['legacy_augment_audio.py']=sha256(ROOT.parent/'augment_audio.py')
        write_json(root/f'metadata/runs/{batch}.json',{'config':cfg,'software':soft,'source_hashes':source_hashes},exclusive=True)
        streams={};writers={}
        try:
            for split in ('train','validation'):
                if not any(j['split']==split for j in jobs): continue
                file=root/f'metadata/generated/{split}_{batch}.csv';file.parent.mkdir(parents=True,exist_ok=True)
                streams[split]=file.open('x',encoding='utf-8-sig',newline='')
                import csv
                writers[split]=csv.DictWriter(streams[split],fieldnames=FIELDS);writers[split].writeheader()
            for number,job in enumerate(jobs):
                audio,clean,details=synthesize(job['label'],cfg,job['random_seed'])
                buffer=io.BytesIO();sf.write(buffer,audio,cfg['sample_rate'],format='WAV',subtype='PCM_16')
                import hashlib
                payload=buffer.getvalue();hashed=hashlib.sha256(payload).hexdigest()
                if hashed in forbidden: raise ValueError('Duplicate synthesized WAV: change conditions/seed; no file written')
                filename=f"{job['label']}_{job['ordinal']+1:06d}_{job['config_hash'][:12]}.wav"
                path=safe_output(root/f"data/generated/{job['split']}/{job['label']}/{filename}",root)
                path.parent.mkdir(parents=True,exist_ok=True)
                suffix=0
                while True:
                    candidate=path if suffix==0 else path.with_stem(path.stem+f'_extra{suffix}')
                    try:
                        with candidate.open('xb') as stream: stream.write(payload)
                        path=candidate;break
                    except FileExistsError: suffix+=1
                decoded,_=sf.read(io.BytesIO(payload))
                residual=decoded-clean
                measured=None if details['snr_db'] is None else float(10*np.log10(np.mean(clean**2)/np.mean(residual**2)))
                row={k:'' for k in FIELDS}
                row.update(sample_id=f"generated:{job['config_hash']}:{job['split']}:{job['label']}:{job['ordinal']}",
                    filename=path.relative_to(root).as_posix(),label=job['label'],morse_code=TABLE[job['label']],split=job['split'],
                    sample_rate=cfg['sample_rate'],frequency=details['frequency'],amplitude=details['amplitude'],
                    dot_duration=details['dot_duration'],timing_jitter=json.dumps(details['timing_jitter']),
                    noise_type=details['noise_type'],snr_db=details['snr_db'],random_seed=job['random_seed'],
                    generated_at=datetime.now(timezone.utc).isoformat(),sha256=hashed,duration=len(audio)/cfg['sample_rate'],
                    original_label=job['label'],source_id='generated',mapping_policy='identity',provenance=f'metadata/runs/{batch}.json',
                    software_version=json.dumps(soft,sort_keys=True),config_hash=job['config_hash'],mix_gain=details['mix_gain'],
                    measured_snr_db=details['measured_snr_db'],saved_snr_db=measured,timing_samples=json.dumps(details['timing_samples']))
                writers[job['split']].writerow(row);streams[job['split']].flush();forbidden.add(hashed)
                if (number+1)%500==0: print(f'Generated {number+1}/{len(jobs)}',flush=True)
        finally:
            for stream in streams.values(): stream.close()
            rebuild_indices(root)
    return summary
