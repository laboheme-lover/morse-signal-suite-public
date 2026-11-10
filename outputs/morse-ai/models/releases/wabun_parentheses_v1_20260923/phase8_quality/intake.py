"""Read-only acceptance audit for future recordings; never trains or infers."""
from policy import PROJECT,normalize_reference
from pathlib import Path
import json,csv,hashlib,argparse
import soundfile as sf
import numpy as np

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def historical():
    audio=set();references=set()
    for p in (PROJECT/'evaluation/real_collection_baseline').glob('*/recording_metrics.json'):
        audio.add(json.loads(p.read_text(encoding='utf-8'))['audio_sha256'])
        ref=p.parent/'reference_original.txt'
        if ref.exists():references.add(normalize_reference(ref.read_text(encoding='utf-8')))
    with (PROJECT/'data/dataset/m4_300/metadata.csv').open(encoding='utf-8-sig') as f:
        audio.update(r['wav_sha256'] for r in csv.DictReader(f))
    return audio,references

def validate(manifest,base,known_audio,known_references):
    errors=[];accepted=[];seen_ids=set();seen_audio=set();seen_ref=set()
    rows=manifest.get('recordings',[])
    if not rows:errors.append('No recordings supplied; template is not a completed evaluation.')
    for i,row in enumerate(rows):
        try:
            for field in ('id','audio','reference','group_id','declared_unseen'):
                if field not in row:raise ValueError(f'Missing {field}')
            if not row['id'] or row['id'] in seen_ids:raise ValueError('Empty or duplicate recording id')
            if not row['group_id']:raise ValueError('group_id required to keep related recordings together')
            if row['declared_unseen'] is not True:raise ValueError('Exposure must be reviewed before claiming unseen data')
            audio=(base/row['audio']).resolve();ref=(base/row['reference']).resolve()
            if not audio.is_file() or not ref.is_file():raise ValueError('Audio/reference file missing')
            if audio.suffix.lower() not in ('.wav','.mp3'):raise ValueError('Expected WAV or MP3')
            with sf.SoundFile(audio) as stream:
                if stream.frames<=0 or stream.samplerate<=0:raise ValueError('Empty audio')
                info={'sample_rate':stream.samplerate,'channels':stream.channels,'frames':stream.frames,'duration_seconds':stream.frames/stream.samplerate}
                frames=0
                for block in stream.blocks(blocksize=65536,dtype='float32',always_2d=True):
                    if not np.isfinite(block).all():raise ValueError('Non-finite audio samples')
                    frames+=len(block)
                if frames!=info['frames']:raise ValueError('Incomplete audio decoding')
            h=digest(audio);text=normalize_reference(ref.read_text(encoding='utf-8-sig'))
            if not text:raise ValueError('Empty normalized reference')
            if h in known_audio or h in seen_audio:raise ValueError('Audio bytes duplicate known or submitted data')
            if text in known_references or text in seen_ref:raise ValueError('Reference repeats known or submitted text; keep outside independent set')
            seen_ids.add(row['id']);seen_audio.add(h);seen_ref.add(text)
            accepted.append({**row,'audio':str(audio),'reference':str(ref),'audio_sha256':h,'reference_sha256':digest(ref),
                'normalized_reference':text,'reference_units':len(text),'audio_info':info})
        except (ValueError,OSError,UnicodeError,TypeError,RuntimeError) as exc:errors.append(f'row {i+1}: {exc}')
    return {'status':'PASS' if not errors else 'NEEDS_REVIEW','errors':errors,'recordings':accepted,
        'limitations':'Audio decoding checked. Duplicate checks use byte hashes and normalized text, not perceptual similarity. Unseen status also relies on submitter disclosure.',
        'inference_executed':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    known_audio,known_ref=historical()
    result=validate(json.loads(a.manifest.read_text(encoding='utf-8-sig')),a.manifest.parent,known_audio,known_ref)
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(result['status']);print('\n'.join(result['errors']))
    if result['errors']:raise SystemExit(2)

if __name__=='__main__':main()
