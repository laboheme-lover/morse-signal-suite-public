"""Fixed-vs-adaptive paired development evaluation with immutable outputs."""
from pathlib import Path
import hashlib,json,time
import cv2,numpy as np
from optical_video.core import analyze_trace,read_trace,csv_text
from optical_video.evaluate_coverage_stress import distance
from optical_video.synthetic import generate
from morse_table import MORSE_TABLE

root=Path(__file__).parent;out=root/'adaptive_v3';out.mkdir(exist_ok=False)
old=root/'coverage_stress_v1';old_protocol=json.loads((old/'protocol.json').read_text(encoding='utf-8'))
previous=json.loads((old/'results.json').read_text(encoding='utf-8'))
v2={r['name']:r for r in json.loads((root/'diagnostics_v2/comparison.json').read_text(encoding='utf-8'))}
specs=old_protocol['cases'];fresh=[]
for fps,frames in ((24,8),(30,12),(60,10)):
    for condition in ('clean','drift','step','noise'):
        fresh.append(dict(name=f'new_{fps}_{condition}',fps=fps,dot_frames=frames,condition=condition,reference='カモメノイロハ012',seed=81236))
protocol=dict(purpose='Experimental development comparison, not independent real-camera evaluation',historical_cases=45,fresh_cases=fresh,
    method='Centered 3-second 10/90 percentile windows; local contrast <15 falls back to global thresholds; no tuning per case',
    fixed_default_retained=True,rejected_hypothesis='',frozen_before_scoring=True,
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'adaptive.py',root/'core.py',Path(__file__))})
(out/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
results=[]
def evaluate(name,category,reference,t,brightness,fps,options):
    for method in ('fixed','adaptive'):
        start=time.perf_counter();r=None;error=''
        try:r=analyze_trace(t,brightness,fps,**options,threshold_method=method)
        except ValueError as exc:error=str(exc)
        text=r['text'] if r else '';status=r['status'] if r else 'REJECTED';edits=distance(reference,text)
        row=dict(name=name,category=category,method=method,status=status,reference_units=len(reference),edits=edits,cer=edits/len(reference) if reference else None,text=text,exact=text==reference,
            unflagged_error=status=='OK' and text!=reference,error=error,processing_seconds=time.perf_counter()-start)
        results.append(row)
        (out/(name+'_'+method+'.json')).write_text(json.dumps(dict(score=row,analysis=r),ensure_ascii=False,indent=2),encoding='utf-8')
    print(name+': '+', '.join(f"{r['method']} {r['status']} {r['edits']}/{r['reference_units']}" for r in results[-2:]),flush=True)

for spec,before in zip(specs,previous):
    assert spec['name']==before['name'];name=spec['name'];saved=json.loads((old/(name+'_result.json')).read_text(encoding='utf-8'))['analysis']
    if saved:
        t=[r['time_seconds'] for r in saved['trace']];brightness=[r['brightness'] for r in saved['trace']];fps=saved['video']['fps']
    else:
        truth=json.loads((old/(name+'.json')).read_text(encoding='utf-8'));info,t,brightness=read_trace(old/(name+'.avi'),tuple(truth['roi']));fps=info['fps']
    evaluate(name,spec['category'],spec['expected'],t,brightness,fps,spec['options'])
    assert results[-2]['text']==before['text'] and results[-2]['status']==v2[name]['after_status'],'Fixed baseline changed'

for spec in fresh:
    name=spec['name'];clean=out/(name+'_clean.avi');path=out/(name+'.avi')
    truth=generate(clean,[MORSE_TABLE[c] for c in spec['reference']],spec['fps'],spec['dot_frames'])
    cap=cv2.VideoCapture(str(clean));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),spec['fps'],(160,120));rng=np.random.default_rng(spec['seed'])
    if not writer.isOpened():raise RuntimeError('Video writer failed')
    try:
        for i in range(count):
            ok,frame=cap.read()
            if not ok:raise ValueError('Clean fixture truncated')
            frame=frame.astype(float);kind=spec['condition']
            if kind=='drift':frame*=1-.7*i/max(1,count-1)
            elif kind=='step':frame*=1 if i<count//2 else .3
            elif kind=='noise':frame+=rng.normal(0,45,frame.shape)
            writer.write(np.clip(frame,0,255).astype(np.uint8))
    finally:cap.release();writer.release()
    (out/(name+'.truth.json')).write_text(json.dumps(dict(spec=spec,truth=truth,sha256=hashlib.sha256(path.read_bytes()).hexdigest()),ensure_ascii=False,indent=2),encoding='utf-8')
    info,t,b=read_trace(path,(60,40,40,40));evaluate(name,'fresh',spec['reference'],t,b,info['fps'],{})

summary=[]
for category in ('coverage','guard','stress','fresh'):
    for method in ('fixed','adaptive'):
        rows=[r for r in results if r['category']==category and r['method']==method];n=sum(r['reference_units'] for r in rows);e=sum(r['edits'] for r in rows)
        summary.append(dict(category=category,method=method,cases=len(rows),exact=sum(r['exact'] for r in rows),rejected=sum(r['status']=='REJECTED' for r in rows),review=sum(r['status']=='REVIEW' for r in rows),unflagged_errors=sum(r['unflagged_error'] for r in rows),reference_units=n,edits=e,cer=e/n if n else None))
(out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');(out/'results.csv').write_bytes(csv_text(results).encode('utf-8-sig'))
(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
for name,h in protocol['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
(out/'verification.json').write_text(json.dumps(dict(completed=True,paired_cases=57,fixed45_matches_v2=True,code_unchanged_during_evaluation=True,real_videos=0),indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
