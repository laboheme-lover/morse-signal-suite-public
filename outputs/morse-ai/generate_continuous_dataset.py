"""Train/validation-only extension with continuous timing; original test is not read."""
import csv
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
import soundfile as sf
from generate_morse_audio import generate_morse_audio,save_wav
from augment_audio import mix_at_snr
from morse_table import MORSE_TABLE


def generate(source,output,seed=20260915):
    source,output=Path(source),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    mapping=json.loads((source/'label_mapping.json').read_text(encoding='utf-8'))
    with (source/'metadata.csv').open(encoding='utf-8-sig',newline='') as f:
        originals=[r for r in csv.DictReader(f) if r['split'] in ('train','validation')]
    rows=[];hash_splits={}
    for r in originals:
        dest=output/r['filepath'];dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/r['filepath'],dest)
        rows.append(r)
    for label,index in mapping.items():
        for split,count in [('train',100),('validation',20)]:
            for j in range(count):
                sample_seed=int(np.random.SeedSequence([seed,index,int(split=='validation'),j]).generate_state(1)[0])
                rng=np.random.default_rng(sample_seed)
                dot=float(rng.uniform(.05,.17));freq=float(rng.uniform(550,850))
                amp=float(rng.uniform(.2,.9));padding=float(rng.uniform(.07,.13))
                jitter=float(rng.uniform(0,.1))
                audio=generate_morse_audio(label,dot,freq,amp,padding=padding,timing_jitter=jitter,rng=rng)
                noise='clean' if j%2==0 else 'white';snr='' if noise=='clean' else int(rng.choice([0,5,10,20]))
                if noise=='white':audio=mix_at_snr(audio,rng.standard_normal(len(audio)),snr)[0]
                path=save_wav(output/split/f'{index:03d}'/f'continuous_{j:03d}.wav',audio)
                rows.append(dict(filepath=path.relative_to(output).as_posix(),split=split,label=label,
                                 class_index=index,morse_code=MORSE_TABLE[label],samples=len(audio),
                                 dot_duration=dot,frequency_hz=freq,amplitude=amp,padding_seconds=padding,
                                 timing_jitter=jitter,noise_type=noise,snr_db=snr,speed='continuous',seed=sample_seed,
                                 wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),generator_version='continuous-v1'))
        print(f'Generated class {index+1}/{len(mapping)}',flush=True)
    max_frames=0
    for r in rows:
        path=output/r['filepath'];digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=r['wav_sha256']:raise ValueError('Hash mismatch')
        if hash_splits.setdefault(digest,r['split'])!=r['split']:raise ValueError('Split leakage')
        audio,sr=sf.read(path);info=sf.info(path)
        if sr!=16000 or audio.ndim!=1 or not np.isfinite(audio).all() or max(abs(audio))>=1 or len(audio)!=int(r['samples']) or info.subtype!='PCM_16':
            raise ValueError('Invalid WAV')
        max_frames=max(max_frames,1+len(audio)//128)
    if max_frames>512:raise ValueError('Input too long')
    fields=sorted(set().union(*(r.keys() for r in rows)))
    with (output/'metadata.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    (output/'label_mapping.json').write_text(json.dumps(mapping,ensure_ascii=False),encoding='utf-8')
    config=dict(status='complete',labels=list(mapping),samples_per_class=len(rows)//len(mapping),
                version='continuous-v1',seed=seed,original_source=str(source.resolve()),
                original_metadata_sha256=hashlib.sha256((source/'metadata.csv').read_bytes()).hexdigest(),
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                original_test_audio_used=False,real_audio_used=False,max_frames=max_frames,
                added_per_class={'train':100,'validation':20},dot_range=[.05,.17],
                frequency_range=[550,850],amplitude_range=[.2,.9],padding_range=[.07,.13])
    (output/'dataset_config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(config,ensure_ascii=False),flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='data/dataset/m4_300')
    p.add_argument('--output',default='data/dataset/continuous_v1')
    a=p.parse_args();generate(a.source,a.output)
