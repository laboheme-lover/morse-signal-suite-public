"""Prespecified development benchmark, not a real-camera accuracy estimate."""
from pathlib import Path
import argparse,hashlib,json,platform,time
import cv2
import numpy as np
from optical_video.core import analyze_video,csv_text,LATIN
from optical_video.synthetic import generate
from morse_table import MORSE_TABLE,DIGITS

ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def distance(reference,prediction):
    row=list(range(len(prediction)+1))
    for i,a in enumerate(reference,1):
        nxt=[i]
        for j,b in enumerate(prediction,1):nxt.append(min(row[j]+1,nxt[-1]+1,row[j-1]+(a!=b)))
        row=nxt
    return row[-1]

def schedule(patterns,frames=9,fps=30):
    states=[False]*(3*frames);events=[]
    for pattern in patterns:
        for i,s in enumerate(pattern):
            start=len(states);states.extend([True]*(frames*(1 if s=='.' else 3)))
            events.append(dict(start_seconds=start/fps,end_seconds=len(states)/fps,symbol=s))
            states.extend([False]*(frames if i<len(pattern)-1 else frames*3))
    return np.array(states),events

def altered_video(path,patterns,condition,seed=23456):
    """Fixed-rate video: frame loss is explicitly emulated by held/black frames."""
    fps=30;states,events=schedule(patterns);rng=np.random.default_rng(seed)
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),fps,(160,120))
    if not writer.isOpened():raise RuntimeError('MJPEG writer unavailable')
    previous=None;modified=[]
    try:
        for i,on in enumerate(states):
            t=i/fps;kind=condition['kind'];level=condition.get('level',0)
            background=35.;off=30.;lit=220.;center=80.;on_value=bool(on)
            gain=1.
            if kind=='exposure_drift':gain=1-level*(i/max(1,len(states)-1))
            if kind=='exposure_step':gain=1 if i<len(states)//2 else level
            if kind=='background_flicker':background=35+level*(np.sin(2*np.pi*1.7*t)>0)
            if kind=='motion':center+=level*np.sin(2*np.pi*.11*t)
            if kind=='low_contrast':lit=30+level
            if kind=='false_flash' and i%(30*4)<level:
                on_value=True;modified.append(i)
            frame=np.full((120,160,3),background,dtype=float)
            x=int(round(center))-20
            frame[40:80,max(0,x):min(160,x+40)]=lit if on_value else off
            frame*=gain
            if kind=='pixel_noise':frame+=rng.normal(0,level,frame.shape)
            frame=np.clip(frame,0,255).astype(np.uint8)
            if kind=='hold_random' and previous is not None and rng.random()<level:
                frame=previous.copy();modified.append(i)
            if kind=='hold_burst' and previous is not None and i%120 in range(15,15+int(level)):
                frame=previous.copy();modified.append(i)
            if kind=='blackout' and i%120 in range(15,15+int(level)):
                frame[:]=0;modified.append(i)
            writer.write(frame);previous=frame
    finally:writer.release()
    return dict(patterns=patterns,events=events,fps=fps,dot_seconds=.3,roi=condition.get('roi',[60,40,40,40]),
                conditions=condition,seed=seed,changed_frame_indices=modified,
                timing='CFR 30fps; held/black frame substitutions, not actual VFR timestamp loss')

def cases():
    result=[]
    for fps in (30,60):
        result.append(dict(name=f'wabun65_{fps}',category='coverage',patterns=list(MORSE_TABLE.values()),expected=''.join(MORSE_TABLE),fps=fps,options={'mixed':False}))
        table=LATIN|DIGITS|{'.':'.-.-.-',',':'--..--'}
        result.append(dict(name=f'international38_{fps}',category='coverage',patterns=[MORSE_TABLE['（']]+list(table.values())+[MORSE_TABLE['）']],expected=''.join(table),fps=fps,options={}))
        result.append(dict(name=f'multi_switch_{fps}',category='coverage',patterns=[MORSE_TABLE['イ'],MORSE_TABLE['（'],LATIN['A'],DIGITS['1'],'.-.-.-',DIGITS['5'],MORSE_TABLE['）'],MORSE_TABLE['ロ'],MORSE_TABLE['（'],LATIN['Z'],MORSE_TABLE['）'],MORSE_TABLE['ハ']],expected='イA1.5ロZハ',fps=fps,options={}))
    result.extend([
        dict(name='dot_only_manual',category='coverage',patterns=['.','.','.'],expected='ヘヘヘ',fps=30,options={'dot_seconds':.3}),
        dict(name='dash_only_manual',category='coverage',patterns=['-','-','-'],expected='ムムム',fps=30,options={'dot_seconds':.3}),
        dict(name='prosigns',category='coverage',patterns=['-..---',MORSE_TABLE['イ'],MORSE_TABLE['ロ'],'...-.'],expected='イロ',fps=30,options={}),
        dict(name='missing_close',category='guard',patterns=[MORSE_TABLE['（'],LATIN['A']],expected='A',fps=30,options={},required_status='REVIEW'),
        dict(name='extra_close',category='guard',patterns=[MORSE_TABLE['イ'],MORSE_TABLE['）']],expected='イ',fps=30,options={},required_status='REVIEW'),
        dict(name='nested_open',category='guard',patterns=[MORSE_TABLE['（'],MORSE_TABLE['（'],LATIN['A'],MORSE_TABLE['）']],expected='A',fps=30,options={},required_status='REVIEW'),
        dict(name='unknown_code',category='guard',patterns=['........',MORSE_TABLE['イ']],expected='□イ',fps=30,options={},required_status='REVIEW'),
        dict(name='dot_only_auto',category='guard',patterns=['.','.','.'],expected='',fps=30,options={},required_status='REJECTED'),
        dict(name='dash_only_auto',category='guard',patterns=['-','-','-'],expected='',fps=30,options={},required_status='REJECTED')])
    # Same fixed content and settings for every stress level. No retuning after seeing results.
    text='イロハニホヘトチリヌルヲワカヨ';patterns=[MORSE_TABLE[c] for c in text]
    conditions=[dict(kind='baseline',level=0)]
    for kind,levels in [('exposure_drift',[.3,.6,.85]),('exposure_step',[.7,.4,.2]),('background_flicker',[80,180]),('motion',[5,20,45]),('pixel_noise',[15,40,80]),('low_contrast',[30,16,10]),('hold_random',[.05,.2,.5]),('hold_burst',[1,4,10]),('blackout',[1,4]),('false_flash',[1,5])]:
        conditions.extend(dict(kind=kind,level=level) for level in levels)
    conditions.extend([dict(kind='background_flicker',level=180,roi=[40,20,80,80]),dict(kind='baseline',level=0,roi=[0,0,20,20])])
    for i,c in enumerate(conditions):result.append(dict(name=f'stress_{i:02d}_{c["kind"]}',category='stress',patterns=patterns,expected=text,fps=30,options={},condition=c))
    return result

def score(spec,truth,result,error,seconds):
    text='' if result is None else result['text'];candidate='' if result is None else result['candidate_text']
    found=[] if result is None else [r['pattern'] for r in result['characters']]
    status='REJECTED' if result is None else result['status'];expected=spec['expected']
    edits=distance(expected,text);pattern_edits=distance(truth['patterns'],found)
    pulses=[] if result is None else [e for e in result['events'] if e['on']]
    # Timing errors only have an unambiguous positional pairing if the complete code sequence matches.
    timing=None
    if found==truth['patterns'] and len(pulses)==len(truth['events']):
        timing=max((abs(a[k]-b[k]) for a,b in zip(pulses,truth['events']) for k in ('start_seconds','end_seconds')),default=0.)
    return dict(name=spec['name'],category=spec['category'],status=status,reference=expected,text=text,candidate=candidate,
        reference_units=len(expected),edits=edits,cer=edits/len(expected) if expected else None,exact=text==expected,
        pattern_units=len(truth['patterns']),pattern_edits=pattern_edits,patterns_exact=found==truth['patterns'],
        expected_pulses=len(truth['events']),detected_pulses=len(pulses),max_boundary_error_seconds=timing,
        unflagged_error=status=='OK' and text!=expected,error=error,processing_seconds=seconds,
        required_behavior_pass=(status==spec['required_status'] and (not expected or text==expected)) if 'required_status' in spec else None)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'coverage_stress_v1');args=ap.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False);specs=cases()
    protected={str(p):sha(p) for p in (ROOT/'core.py',ROOT/'synthetic.py',ROOT/'evaluate_coverage_stress.py',ROOT.parent/'morse_table.py')}
    protocol=dict(purpose='Development synthetic coverage/stress audit; not independent real-video accuracy',cases=specs,
        frozen_before_run=True,decoder_tuned=False,source_sha256=protected,seed=23456,
        rejection_scoring='empty hypothesis counted against full reference; no CER for empty guard reference',
        timing_metric='positional event boundaries only when all code patterns and pulse count match',
        no_video_models_trained=True)
    (out/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    results=[]
    for spec in specs:
        path=out/(spec['name']+'.avi')
        if spec['category']=='stress':truth=altered_video(path,spec['patterns'],spec['condition'])
        else:truth=generate(path,spec['patterns'],fps=spec['fps'],dot_frames=9)
        truth['expected_text']=spec['expected'];truth['video_sha256']=sha(path)
        path.with_suffix('.json').write_text(json.dumps(truth,ensure_ascii=False,indent=2),encoding='utf-8')
        start=time.perf_counter();result=None;error=''
        try:result=analyze_video(path,tuple(truth['roi']),**spec['options'])
        except (ValueError,cv2.error) as exc:error=str(exc)
        row=score(spec,truth,result,error,time.perf_counter()-start);results.append(row)
        (out/(spec['name']+'_result.json')).write_text(json.dumps(dict(score=row,analysis=result),ensure_ascii=False,indent=2),encoding='utf-8')
        print(f"{spec['name']}: {row['status']} edits={row['edits']}/{row['reference_units']} pattern_edits={row['pattern_edits']} unflagged={row['unflagged_error']}",flush=True)
    assert all(sha(p)==h for p,h in protected.items())
    (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'results.csv').write_bytes(csv_text(results).encode('utf-8-sig'))
    summary={category:dict(cases=len(group),exact=sum(r['exact'] for r in group),rejected=sum(r['status']=='REJECTED' for r in group),review=sum(r['status']=='REVIEW' for r in group),unflagged_errors=sum(r['unflagged_error'] for r in group)) for category in ('coverage','guard','stress') if (group:=[r for r in results if r['category']==category])}
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (out/'verification.json').write_text(json.dumps(dict(completed=True,decoder_unchanged=True,cases=len(results),real_videos=0,python=platform.python_version(),opencv=cv2.__version__,numpy=np.__version__,platform=platform.platform()),indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
