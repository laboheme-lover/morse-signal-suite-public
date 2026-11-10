from pathlib import Path
import sys,json,hashlib
import soundfile as sf
from new_recording_preparation import P,D,entries,selection,transform,digest,save
from audio_preprocessing import load_audio
from policy import normalize_reference
out=D/'selection_inputs';out.mkdir(exist_ok=False)
plan=json.loads((D/'augmentation_plan.json').read_text(encoding='utf-8'));assert digest(D/'augmentation_plan.json')==(D/'augmentation_plan.sha256.txt').read_text().strip()
records=[];audit=[];mapping=str.maketrans('〇一二三四五六七八九','0123456789')
for original in entries():
 if original['role']!='selection':continue
 e=selection(original['number']);n=e['number'];source=Path(e['reference']);assert digest(source)==e['reference_sha256']
 text=source.read_text(encoding='utf-8-sig');lines=text.splitlines();body='\n'.join(lines[2:]);converted=body.translate(mapping);normalized=normalize_reference(converted)
 ref=out/f'no{n:02d}_body.txt';ref.write_text(converted,encoding='utf-8')
 audit.append(dict(number=n,original_reference=str(source),original_sha256=e['reference_sha256'],excluded_lines=lines[:2],body_original=body,body_converted=converted,normalized_reference=normalized,units=len(normalized),reference_sha256=digest(ref)))
 x=load_audio(e['audio'])
 for i,c in enumerate(plan['conditions']):
  seed=plan['seed_base']+n*100+i
  if c['id']=='clean':audio=Path(e['audio']);detail={'original_audio':True}
  else:
   y,detail=transform(x,c,seed);audio=out/f"no{n:02d}_{c['id']}.wav";sf.write(audio,y,16000,subtype='FLOAT')
  records.append(dict(id=f"no{n:02d}_{c['id']}",audio=str(audio.resolve()),reference=str(ref.resolve()),body={'mode':'protocol'},original_number=n,role='selection',condition=c['id'],seed=seed,audio_sha256=digest(audio),augmentation_details=detail))
 print('Prepared selection',n,flush=True)
records.sort(key=lambda x:(x['condition']!='clean',x['original_number'],x['condition']))
save(D/'selection_manifest.json',dict(scope='MODEL_SELECTION_NOT_FINAL_CONFIRMATION',recordings=records))
save(D/'reference_preparation.json',dict(user_instruction='Treat provided numeric and kana codes as correct; no transcription corrections',policy='first two lines are telegram header and addressee, body begins at line 3; kanji digits mapped individually to ASCII 0-9; apply unchanged content_v2 normalization',audio_framing='existing protocol detection, not reference-driven time windows; missing/ambiguous framing is a failure',records=audit))
save(D/'selection_preparation_lock.json',dict(manifest_sha256=digest(D/'selection_manifest.json'),reference_preparation_sha256=digest(D/'reference_preparation.json'),augmentation_plan_sha256=digest(D/'augmentation_plan.json'),split_sha256=digest(D/'split_plan.json'),scripts={str(p.relative_to(P)):digest(p) for p in [Path(__file__),P/'phase8_quality/new_recording_preparation.py']}))
assert len(records)==77 and all(r['original_number']<=11 for r in records)
print('77 cases, 11 originals, final confirmation untouched',flush=True)
