"""Milestone 4: stratified single-character WAV dataset with reproducible conditions."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import soundfile as sf
from augment_audio import generate_sample, mix_at_snr, SPEED_RANGES, SNR_LEVELS
from add_esc50_noise import generate_esc50_sample
from esc50_manager import ESC50Manager, SPLIT_FOLDS
from generate_morse_audio import save_wav
from morse_table import MORSE_TABLE

VERSION = 'm4-v1'
SPLITS = tuple(SPLIT_FOLDS)
NOISE_TYPES = ('clean', 'white', 'esc50')


def split_counts(count, label_index=0):
    """Largest remainder; rotate equal val/test remainders to avoid systematic bias."""
    if not isinstance(count, int) or count < 10:
        raise ValueError('samples_per_class must be an integer >= 10')
    raw = np.array([0.7, 0.15, 0.15])*count
    counts = np.floor(raw).astype(int)
    tie_order = [0, 1, 2] if label_index % 2 == 0 else [0, 2, 1]
    order = sorted(tie_order, key=lambda i: -(raw[i]-counts[i]))
    for i in order[:count-int(counts.sum())]:
        counts[i] += 1
    return dict(zip(SPLITS, (int(c) for c in counts)))


def build_plan(samples_per_class=10, seed=20260914, labels=None):
    labels = list(MORSE_TABLE) if labels is None else list(labels)
    if not labels or len(set(labels)) != len(labels) or any(label not in MORSE_TABLE for label in labels):
        raise ValueError('labels must be unique canonical Morse classes')
    split_counts(samples_per_class)
    master = np.random.SeedSequence(seed)
    children = master.spawn(len(labels)*samples_per_class)
    rows=[]
    cursor=0
    # Condition schedules are balanced across each split; no noise/SNR determined by label.
    positions=Counter()
    for label_index, label in enumerate(labels):
        for split, count in split_counts(samples_per_class, label_index).items():
            rng=np.random.default_rng(np.random.SeedSequence([seed, label_index, SPLITS.index(split), 41]))
            conditions=[]
            for _ in range(count):
                position=positions[split]
                noise=NOISE_TYPES[position % 3]
                noise_index=position//3
                speed=list(SPEED_RANGES)[noise_index % 3]
                snr=None if noise=='clean' else SNR_LEVELS[(noise_index//3) % 5]
                conditions.append((noise,speed,snr))
                positions[split]+=1
            rng.shuffle(conditions)
            for noise,speed,snr in conditions:
                state=children[cursor].generate_state(2, dtype=np.uint64)
                sample_id=f'{label_index:03d}_{cursor:06d}'
                rows.append(dict(label=label, class_index=label_index, split=split,
                                 noise_type=noise,speed=speed,snr_db=snr,
                                 seed=int(state[0]),noise_seed=int(state[1]),sample_id=sample_id))
                cursor+=1
    return rows


def generate_dataset(output_dir, samples_per_class=10, seed=20260914,
                     esc50_root='data/ESC-50-master', available_only=False, labels=None):
    plan=build_plan(samples_per_class,seed,labels)
    manager=ESC50Manager(esc50_root, cache_audio=True)
    for split in SPLITS:
        manager.candidates(split, available_only)
    root=Path(output_dir)
    root.mkdir(parents=True,exist_ok=False)
    labels=list(dict.fromkeys(r['label'] for r in plan))
    config=dict(version=VERSION,status='generating',samples_per_class=samples_per_class,
                master_seed=seed,labels=labels,split_ratio=[0.7,0.15,0.15],
                esc50_available_only=available_only,esc50_catalog=manager.summary(),
                esc50_catalog_sha256=manager.catalog_sha256,
                excluded_esc50=[r.__dict__ for r in manager.excluded_records],
                python=platform.python_version(),numpy=np.__version__,
                condition_policy='balanced split-level clean/white/esc50, speeds and SNR',
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')})
    config_path=root/'dataset_config.json'
    config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'label_mapping.json').write_text(json.dumps({v:k for k,v in enumerate(labels)},ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    for index,item in enumerate(plan):
        if item['noise_type']=='esc50':
            audio,metadata=generate_esc50_sample(manager,item['label'],item['speed'],item['split'],
                        item['snr_db'],item['seed'],item['noise_seed'],available_only)
        else:
            audio,metadata=generate_sample(item['label'],item['speed'],item['noise_type'],item['snr_db'],item['seed'])
        path=save_wav(root/item['split']/f"{item['class_index']:03d}"/f"{item['sample_id']}.wav",audio)
        metadata.update(item)
        metadata.update(filepath=path.relative_to(root).as_posix(),base_sample_id=item['sample_id'],
                        dataset_version=VERSION,wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        metadata['timing_samples']=json.dumps(metadata['timing_samples'],separators=(',',':'))
        rows.append(metadata)
        if (index+1)%500==0:
            print(f'Generated {index+1}/{len(plan)}',flush=True)
    fields=['filepath','split','label','morse_code','speed','dot_duration','frequency_hz','amplitude',
            'noise_type','snr_db','esc50_filename','esc50_category','esc50_fold','esc50_src_file']
    fields+=sorted(set().union(*(r.keys() for r in rows))-set(fields))
    with (root/'metadata.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    # A dataset is complete only after all files and metadata have been audited.
    report=validate_dataset(root,manager)
    config['status']='complete'
    config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report


def validate_dataset(root, manager=None):
    root=Path(root).resolve()
    config=json.loads((root/'dataset_config.json').read_text(encoding='utf-8'))
    mapping=json.loads((root/'label_mapping.json').read_text(encoding='utf-8'))
    with (root/'metadata.csv').open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    def check(condition,message):
        if not condition:
            raise ValueError(message)
    check(mapping=={label:i for i,label in enumerate(config['labels'])},'Label mapping mismatch')
    check(len(rows)==len(mapping)*config['samples_per_class'],'Sample count mismatch')
    counts=Counter(); paths=set(); base_splits={}; source_splits={}; hashes={}
    max_frames=0; max_snr_error=0.; bytes_total=0
    catalog={r.filename:r for r in manager.records} if manager else {}
    for row_index,row in enumerate(rows):
        label=row['label']; split=row['split']; noise=row['noise_type']
        check(label in mapping and split in SPLITS and noise in NOISE_TYPES,'Unknown label/split/noise')
        check(int(row['class_index'])==mapping[label] and row['morse_code']==MORSE_TABLE[label],'Label/code mismatch')
        path=(root/row['filepath']).resolve()
        check(path.is_relative_to(root) and path not in paths,'Unsafe or duplicate WAV path')
        paths.add(path)
        payload=path.read_bytes(); bytes_total+=len(payload)
        digest=hashlib.sha256(payload).hexdigest()
        check(digest==row['wav_sha256'],'WAV hash mismatch')
        check(hashes.setdefault(digest,split)==split,'Duplicate WAV across splits')
        audio,sr=sf.read(path)
        info=sf.info(path)
        check(sr==16000 and audio.ndim==1 and info.subtype=='PCM_16','Invalid audio format')
        check(len(audio)==int(row['samples']) and np.isfinite(audio).all(),'Invalid audio samples')
        check(abs(len(audio)/16000-float(row['duration_seconds']))<1e-10,'Duration mismatch')
        check(np.max(abs(audio))<1,'Clipped audio')
        check(base_splits.setdefault(row['base_sample_id'],split)==split,'Base sample leakage')
        check(row['sample_id']==row['base_sample_id'],'Sample ID mismatch')
        check(row['speed'] in SPEED_RANGES,'Unknown speed')
        lo,hi=SPEED_RANGES[row['speed']]
        check(lo<=float(row['dot_duration'])<=hi and 600<=float(row['frequency_hz'])<=800
              and 0.4<=float(row['amplitude'])<=0.9,'Generation parameter outside specification')
        # Reconstruct the clean component for each row; checks timing/parameters and post-PCM SNR.
        clean, regenerated=generate_sample(label,row['speed'],seed=int(row['seed']))
        for key in ('dot_duration','frequency_hz','amplitude'):
            check(float(row[key])==regenerated[key],f'Seed/metadata mismatch: {key}')
        check(json.loads(row['timing_samples'])==regenerated['timing_samples'],'Timing mismatch')
        check(len(clean)==len(audio),'Timing/length mismatch')
        if noise=='clean':
            check(row['snr_db']=='','Clean SNR should be blank')
            check(np.max(abs(audio-clean))<=1/32768+1e-10,'Clean reconstruction mismatch')
        else:
            snr=float(row['snr_db'])
            check(snr in SNR_LEVELS,'Unknown SNR')
            signal=clean.astype(float)*float(row['mix_gain'])
            measured=10*np.log10(np.mean(signal**2)/np.mean((audio-signal)**2))
            error=abs(measured-snr); max_snr_error=max(max_snr_error,error)
            check(error<0.01,f'SNR error: {error}')
        if noise=='white':
            expected,_=generate_sample(label,row['speed'],'white',float(row['snr_db']),int(row['seed']))
            check(np.max(abs(audio-expected))<=1/32768+1e-10,'White reconstruction mismatch')
        if noise=='esc50':
            check(int(row['esc50_fold']) in SPLIT_FOLDS[split],'ESC-50 fold leakage')
            check(bool(row['esc50_src_file']),'Missing ESC-50 source')
            check(source_splits.setdefault(row['esc50_src_file'],split)==split,'ESC-50 source leakage')
            if manager:
                check(row['esc50_filename'] in catalog,'Unknown/excluded ESC-50 file')
                record=catalog[row['esc50_filename']]
                check(record.src_file==row['esc50_src_file'] and record.fold==int(row['esc50_fold'])
                      and record.category==row['esc50_category'],'ESC-50 provenance mismatch')
                check(row['esc50_catalog_sha256']==manager.catalog_sha256,'ESC-50 catalog changed')
                source,original_sr,source_hash=manager._load_audio(manager.audio_path(record),16000)
                check(source_hash==row['esc50_audio_sha256'],'ESC-50 audio changed')
                offset=int(row['esc50_offset_samples'])
                check(0<=offset<len(source) and len(source)==int(row['esc50_resampled_samples'])
                      and original_sr==int(row['esc50_original_sample_rate']),'ESC-50 crop metadata mismatch')
                segment=source[(np.arange(len(clean))+offset)%len(source)].astype(float)
                expected,_,_,gain=mix_at_snr(clean,segment,float(row['snr_db']))
                check(abs(gain-float(row['mix_gain']))<1e-12,'ESC-50 gain mismatch')
                check(np.max(abs(audio-expected))<=1/32768+1e-10,'ESC-50 reconstruction mismatch')
        else:
            check(all(row[k]=='' for k in ('esc50_filename','esc50_category','esc50_fold','esc50_src_file')),
                  'Unexpected ESC-50 provenance')
        counts[(label,split)]+=1
        max_frames=max(max_frames,1+len(audio)//128)
        if (row_index+1)%2000==0:
            print(f'Validated {row_index+1}/{len(rows)}',flush=True)
    for label,index in mapping.items():
        for split,count in split_counts(config['samples_per_class'],index).items():
            check(counts[label,split]==count,'Class/split count mismatch')
    check(len(list(root.glob('*/*/*.wav')))==len(rows),'Unlisted WAV files')
    report=dict(samples=len(rows),classes=len(mapping),samples_per_class=config['samples_per_class'],
                split_counts=dict(Counter(r['split'] for r in rows)),
                noise_counts=dict(Counter(r['noise_type'] for r in rows)),
                speed_counts=dict(Counter(r['speed'] for r in rows)),
                noisy_snr_counts=dict(Counter(r['snr_db'] for r in rows if r['noise_type']!='clean')),
                max_frames=max_frames,max_saved_snr_error_db=max_snr_error,wav_bytes=bytes_total,
                unique_esc50_sources=len(source_splits),esc50_source_overlap=0,
                verified='all WAVs: format/hash/parameters/timing/SNR/label/split/provenance')
    (root/'validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('data/dataset/m4_smoke'))
    parser.add_argument('--samples-per-class',type=int,default=10)
    parser.add_argument('--seed',type=int,default=20260914)
    parser.add_argument('--esc50-root',type=Path,default=Path('data/ESC-50-master'))
    parser.add_argument('--available-only',action='store_true')
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    if args.validate_only:
        print(json.dumps(validate_dataset(args.output_dir,ESC50Manager(args.esc50_root,cache_audio=True)),indent=2))
    else:
        generate_dataset(args.output_dir,args.samples_per_class,args.seed,args.esc50_root,args.available_only)


if __name__=='__main__':
    main()
