"""Selection-only preparation; no training, reference rewriting or final inference."""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np
import soundfile as sf
from scipy.signal import hilbert,resample_poly
P=Path(__file__).resolve().parent.parent;D=P/'phase8_quality/new_recordings_selection_v1'
sys.path[:0]=[str(P),str(P/'phase8_quality')]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def entries():
 assert digest(D/'split_plan.json')==(D/'split_plan.sha256.txt').read_text().split()[0]
 return json.loads((D/'split_plan.json').read_text(encoding='utf-8'))['recordings']
def selection(number):
 e=next(e for e in entries() if e['number']==number)
 if e['role']!='selection':raise ValueError('Final confirmation is locked; selection recordings only')
 if digest(e['audio'])!=e['audio_sha256']:raise ValueError('Source changed')
 return e
def transform(x,condition,seed,sr=16000):
 y=np.asarray(x,dtype=np.float64).copy();detail={}
 if 'frequency_deviation_hz' in condition:
  t=np.arange(len(y))/sr;f=condition['modulation_hz'];dev=condition['frequency_deviation_hz']
  phase=dev/f*(1-np.cos(2*np.pi*f*t));y=np.real(hilbert(y)*np.exp(1j*phase))
 if 'playback_rate' in condition:
  rate=condition['playback_rate'];assert rate==.9;y=resample_poly(y,10,9)
 if 'snr_db' in condition:
  rng=np.random.default_rng(seed);noise=rng.normal(size=len(y));power=np.mean(y*y)
  if power<=0:raise ValueError('Silent input')
  noise*=np.sqrt(power/(np.mean(noise*noise)*10**(condition['snr_db']/10)))
  detail['measured_snr_db']=float(10*np.log10(power/np.mean(noise*noise)));y=y+noise
 gain=min(1.,.99/max(float(np.max(np.abs(y))),1e-12));y*=gain
 assert np.isfinite(y).all();detail.update(gain=gain,peak=float(np.max(np.abs(y))),seconds=len(y)/sr)
 return y.astype(np.float32),detail
def pilot():
 from audio_preprocessing import load_audio
 assert digest(D/'augmentation_plan.json')==(D/'augmentation_plan.sha256.txt').read_text().strip()
 plan=json.loads((D/'augmentation_plan.json').read_text(encoding='utf-8'));e=selection(1);out=D/'pilot_no01';out.mkdir(exist_ok=False)
 x=load_audio(e['audio']);rows=[]
 for i,c in enumerate(plan['conditions']):
  seed=plan['seed_base']+100+i;y,info=transform(x,c,seed);path=out/(c['id']+'.wav');sf.write(path,y,16000,subtype='FLOAT')
  reread,sr=sf.read(path,dtype='float32');assert sr==16000 and np.array_equal(y,reread)
  rows.append(dict(condition=c,seed=seed,audio=str(path),sha256=digest(path),**info))
 save(out/'manifest.json',dict(original_number=1,role='selection',source_sha256=e['audio_sha256'],plan_sha256=digest(D/'augmentation_plan.json'),records=rows,no_inference=True))
 print('Pilot: 7 waveforms saved and read back',flush=True)
def probe():
 import evaluate_new as runner
 from morse_table import REVERSE_TABLE
 runner.verify_frozen();models,cfg,labels=runner.load_models();out=D/'clean_unscored_probe';out.mkdir(exist_ok=False);summary=[]
 for item in entries():
  if item['role']!='selection':continue
  e=selection(item['number']);t=time.perf_counter();x=runner.load_audio(e['audio']);rows,meta=runner.segment_morse(x)
  for i,r in enumerate(rows):r.update(index=i,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
  results={}
  for name,model in models.items():
   try:
    text,segments,warnings=runner.infer(rows,x,model,cfg,labels);results[name]=dict(status='OK',text=text,warnings=warnings,segments=segments)
   except (ValueError,RuntimeError) as exc:results[name]=dict(status='FAILED',error=str(exc))
  record=dict(number=e['number'],source_sha256=e['audio_sha256'],body_mode='full_unscored',detector=meta,detected_segments=rows,models=results,seconds=time.perf_counter()-t)
  save(out/f"no{e['number']:02d}.json",record)
  summary.append(dict(number=e['number'],segments=len(rows),seconds=record['seconds'],statuses={k:v['status'] for k,v in results.items()},framing_patterns=[dict(index=i,pattern=r['pattern'],seconds=r['start_seconds']) for i,r in enumerate(rows) if r['pattern'] in ('-..---','...-.')]))
  print('Unscored No.',e['number'],summary[-1]['statuses'],flush=True)
 runner.verify_frozen();save(out/'summary.json',dict(scope='SELECTION_FUNCTIONAL_CHECK_NOT_SCORED',records=summary,final_confirmation_inference=False,reference_used_for_inference=False,model_changes=False))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['pilot','probe']);a=ap.parse_args();pilot() if a.action=='pilot' else probe()
