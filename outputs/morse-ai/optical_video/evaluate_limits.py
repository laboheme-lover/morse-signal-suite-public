"""Predeclared boundary/black-floor/long-signal tests for three frozen methods."""
from pathlib import Path
import json,hashlib
import cv2,numpy as np
from optical_video.core import read_trace,analyze_trace,csv_text
from optical_video.evaluate_coverage_stress import schedule,distance
from morse_table import MORSE_TABLE

root=Path(__file__).parent;out=root/'limits_v4';out.mkdir(exist_ok=False)
cases=[]
for floor in (0,3,10):
    for fraction in (.25,.75):cases.append(dict(name=f'floor_{floor}_{fraction}',floor=floor,changes=[(fraction,.3)]))
cases.extend([dict(name='early_change',changes=[(.02,.3)]),dict(name='late_change',changes=[(.98,.3)])])
for interval in (1,2,4):cases.append(dict(name=f'repeated_{interval}s',repeat_seconds=interval))
for frames in (9,24,45):cases.append(dict(name=f'slow_{frames}',dot_frames=frames,reference='ムムヘイ',manual_dot=True))
for seconds in (3,10,30):cases.append(dict(name=f'pause_{seconds}',pause_seconds=seconds))
cases.extend([dict(name='clean_control'),dict(name='noise_control',noise=20),dict(name='constant_off',constant=False),dict(name='constant_on',constant=True)])
protocol=dict(cases=cases,default_reference='イロハニホヘト',fps=30,dot_frames=9,seed=67231,
    scope='Synthetic development limits, not real-camera accuracy. No parameter tuning after scoring.',
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'core.py',root/'adaptive.py',root/'change_points.py',root/'diagnostics.py',Path(__file__))})
(out/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
rows=[]
for c in cases:
    name=c['name'];reference=c.get('reference',protocol['default_reference']);frames=c.get('dot_frames',9)
    states,events=schedule([MORSE_TABLE[x] for x in reference],frames,30)
    if c.get('pause_seconds'):
        # Insert silence at a known character boundary, not inside a pulse.
        starts=[];cursor=3*frames
        for char in reference:
            starts.append(cursor);p=MORSE_TABLE[char]
            cursor+=frames*(sum(1 if s=='.' else 3 for s in p)+len(p)-1+3)
        boundary=next(i for i in starts if i>len(states)*.5)/30
        before=round(boundary*30);n=c['pause_seconds']*30;states=np.r_[states[:before],np.zeros(n,dtype=bool),states[before:]]
        for e in events:
            if e['start_seconds']>=boundary:e['start_seconds']+=c['pause_seconds'];e['end_seconds']+=c['pause_seconds']
    if 'constant' in c:states=np.full(300,c['constant'],dtype=bool);reference=''
    path=out/(name+'.avi');writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),30,(160,120));rng=np.random.default_rng(67231)
    if not writer.isOpened():raise RuntimeError('No MJPEG writer')
    changed=[]
    try:
        for i,state in enumerate(states):
            gain=1.
            for fraction,value in c.get('changes',[]):
                if i>=round(len(states)*fraction):gain=value
            if c.get('repeat_seconds'):gain=1 if (i//(30*c['repeat_seconds']))%2==0 else .3
            changed.append(gain)
            frame=np.full((120,160,3),35.,dtype=float);frame[40:80,60:100]=220 if state else c.get('floor',30)
            frame*=gain
            if c.get('noise'):frame+=rng.normal(0,c['noise'],frame.shape)
            writer.write(np.clip(frame,0,255).astype(np.uint8))
    finally:writer.release()
    truth=dict(case=c,reference=reference,events=events,gains=changed,video_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),note='Pauses inserted immediately before a known character start; reference unchanged')
    path.with_suffix('.json').write_text(json.dumps(truth,ensure_ascii=False,indent=2),encoding='utf-8')
    info,t,b=read_trace(path,(60,40,40,40))
    for method in ('fixed','adaptive','change_aware'):
        r=None;error=''
        try:r=analyze_trace(t,b,30,threshold_method=method,dot_seconds=frames/30 if c.get('manual_dot') else None)
        except ValueError as exc:error=str(exc)
        text=r['text'] if r else '';status=r['status'] if r else 'REJECTED'
        row=dict(name=name,method=method,reference=reference,text=text,reference_units=len(reference),edits=distance(reference,text),status=status,
            exact=text==reference,unflagged_error=bool(reference) and text!=reference and status=='OK',error=error,
            change_count=len(r['exposure_changes']) if r else 0,expected_rejection='constant' in c)
        rows.append(row);(out/(name+'_'+method+'.result.json')).write_text(json.dumps(dict(score=row,analysis=r),ensure_ascii=False,indent=2),encoding='utf-8')
    print(name+': '+', '.join(f"{r['method']} {r['status']} {r['edits']}" for r in rows[-3:]),flush=True)
(out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');(out/'results.csv').write_bytes(csv_text(rows).encode('utf-8-sig'))
for name,h in protocol['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
(out/'verification.json').write_text(json.dumps(dict(completed=True,cases=len(cases),method_runs=len(rows),code_unchanged=True,real_videos=0),indent=2),encoding='utf-8')
