"""Frozen v4 experiment: replay all 57 cases and fresh encoded exposure changes."""
from pathlib import Path
import hashlib,json
import cv2,numpy as np
from optical_video.core import analyze_trace,read_trace,csv_text
from optical_video.evaluate_coverage_stress import distance
from optical_video.synthetic import generate
from morse_table import MORSE_TABLE

root=Path(__file__).parent;out=root/'change_aware_v4';out.mkdir(exist_ok=False)
old=root/'adaptive_v3';scores=json.loads((old/'results.json').read_text(encoding='utf-8'))
old_protocol=json.loads((old/'protocol.json').read_text(encoding='utf-8'))
specs={s['name']:dict(s,reference=s['expected']) for s in json.loads((root/'coverage_stress_v1/protocol.json').read_text(encoding='utf-8'))['cases']}
specs.update({s['name']:dict(s,options={}) for s in old_protocol['fresh_cases']})
fresh=[]
for position in (.33,.67):
    for direction in ('down','up'):
        for noise in (0,20):fresh.append(dict(name=f'fresh_{len(fresh):02}',position=position,direction=direction,noise=noise,black_floor=False))
fresh.extend([dict(name='clean_control',position=.5,direction='none',noise=20,black_floor=False),dict(name='black_floor_step',position=.5,direction='down',noise=0,black_floor=True)])
protocol=dict(purpose='Synthetic development validation only',previous_cases=57,new_cases=fresh,new_reference='ヒカリノモールス123',fps=30,dot_frames=9,seed=99173,
    change_detection='3s before/after raw brightness jumps; both low/high shift same direction with two-level fit; no transcript/reference used',
    outputs='changes flagged REVIEW even when exact',fixed_default_retained=True,frozen_before_scoring=True,
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'core.py',root/'change_points.py',root/'adaptive.py',Path(__file__))})
(out/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
results=[]
def evaluate(name,category,reference,t,b,fps,options):
    for method in ('fixed','adaptive','change_aware'):
        r=None;error=''
        try:r=analyze_trace(t,b,fps,threshold_method=method,**options)
        except ValueError as exc:error=str(exc)
        text=r['text'] if r else '';status=r['status'] if r else 'REJECTED';edits=distance(reference,text)
        row=dict(name=name,category=category,method=method,status=status,reference=reference,reference_units=len(reference),text=text,edits=edits,exact=text==reference,
            unflagged_error=status=='OK' and text!=reference,change_count=len(r['exposure_changes']) if r else 0,error=error)
        results.append(row);(out/(name+'_'+method+'.json')).write_text(json.dumps(dict(score=row,analysis=r),ensure_ascii=False,indent=2),encoding='utf-8')
    print(name+': '+', '.join(f"{r['method']} {r['status']} {r['edits']}/{r['reference_units']}" for r in results[-3:]),flush=True)

for before in scores[::2]:
    name=before['name'];spec=specs[name]
    saved=json.loads((old/(name+'_fixed.json')).read_text(encoding='utf-8'))['analysis']
    if saved:t=[x['time_seconds'] for x in saved['trace']];b=[x['brightness'] for x in saved['trace']];fps=spec['fps']
    else:
        truth=json.loads((root/'coverage_stress_v1'/(name+'.json')).read_text(encoding='utf-8'))
        info,t,b=read_trace(root/'coverage_stress_v1'/(name+'.avi'),tuple(truth['roi']));fps=info['fps']
    evaluate(name,before['category'],spec['reference'],t,b,fps,spec['options'])
    for current in results[-3:-1]:
        previous=next(r for r in scores if r['name']==name and r['method']==current['method'])
        assert current['text']==previous['text'] and current['status']==previous['status'],'Existing method changed'

reference=protocol['new_reference'];clean=out/'clean_source.avi'
truth=generate(clean,[MORSE_TABLE[c] for c in reference],fps=30,dot_frames=9)
for spec in fresh:
    path=out/(spec['name']+'.avi');cap=cv2.VideoCapture(str(clean));n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));boundary=round(n*spec['position'])
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),30,(160,120));rng=np.random.default_rng(protocol['seed'])
    if not writer.isOpened():raise RuntimeError('No video writer')
    try:
        for i in range(n):
            ok,frame=cap.read()
            if not ok:raise ValueError('Input video truncated')
            frame=frame.astype(float)
            if spec['black_floor']:frame=np.maximum(0,frame-30)
            gain=(1 if i<boundary else .35) if spec['direction']=='down' else ((.35 if i<boundary else 1) if spec['direction']=='up' else 1)
            frame*=gain
            if spec['noise']:frame+=rng.normal(0,spec['noise'],frame.shape)
            writer.write(np.clip(frame,0,255).astype(np.uint8))
    finally:cap.release();writer.release()
    (out/(spec['name']+'.truth.json')).write_text(json.dumps(dict(spec=spec,original_truth=truth,change_seconds=boundary/30,reference=reference,sha256=hashlib.sha256(path.read_bytes()).hexdigest()),ensure_ascii=False,indent=2),encoding='utf-8')
    info,t,b=read_trace(path,(60,40,40,40));evaluate(spec['name'],'validation',reference,t,b,info['fps'],{})

summary=[]
for category in ('coverage','guard','stress','fresh','validation'):
    for method in ('fixed','adaptive','change_aware'):
        group=[r for r in results if r['category']==category and r['method']==method];n=sum(r['reference_units'] for r in group);e=sum(r['edits'] for r in group)
        summary.append(dict(category=category,method=method,cases=len(group),exact=sum(r['exact'] for r in group),review=sum(r['status']=='REVIEW' for r in group),rejected=sum(r['status']=='REJECTED' for r in group),unflagged_errors=sum(r['unflagged_error'] for r in group),reference_units=n,edits=e,cer=e/n if n else None))
(out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');(out/'results.csv').write_bytes(csv_text(results).encode('utf-8-sig'))
(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
for name,h in protocol['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
(out/'verification.json').write_text(json.dumps(dict(completed=True,cases=67,method_runs=201,previous_fixed_and_adaptive_114_unchanged=True,code_hashes_match=True,real_videos=0),indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
