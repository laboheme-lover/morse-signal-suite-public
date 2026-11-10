"""Replay all 88 v4 examples to verify warning-only v5 changes."""
from pathlib import Path
import hashlib,json
from optical_video.core import analyze_trace,read_trace,csv_text

root=Path(__file__).parent;out=root/'limits_warning_v5';out.mkdir(exist_ok=False)
roster={s['name']:s for s in json.loads((root/'coverage_stress_v1/protocol.json').read_text(encoding='utf-8'))['cases']}
roster.update({s['name']:dict(s,options={}) for s in json.loads((root/'adaptive_v3/protocol.json').read_text(encoding='utf-8'))['fresh_cases']})
limits={s['name']:s for s in json.loads((root/'limits_v4/protocol.json').read_text(encoding='utf-8'))['cases']}
old=[]
for group in ('change_aware_v4','limits_v4'):
    old.extend((group,r) for r in json.loads((root/group/'results.json').read_text(encoding='utf-8')) if r['method']=='change_aware')
protocol=dict(cases=len(old),scope='warning-only regression on known synthetic videos',
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'core.py',root/'change_points.py',Path(__file__))})
(out/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
rows=[]
for group,before in old:
    name=before['name'];suffix='_change_aware.result.json' if group=='limits_v4' else '_change_aware.json'
    saved=json.loads((root/group/(name+suffix)).read_text(encoding='utf-8'))['analysis']
    options=roster.get(name,{}).get('options',{}).copy()
    if group=='limits_v4' and limits[name].get('manual_dot'):options['dot_seconds']=limits[name]['dot_frames']/30
    new=None;error=''
    try:
        if saved:
            trace=saved['trace'];t=[r['time_seconds'] for r in trace];b=[r['brightness'] for r in trace];fps=round(1/(t[1]-t[0]))
        else:
            source=root/group/(name+'.avi')
            if not source.exists():source=root/'coverage_stress_v1'/(name+'.avi')
            truth=json.loads(source.with_suffix('.json').read_text(encoding='utf-8'));info,t,b=read_trace(source,tuple(truth.get('roi',[60,40,40,40])));fps=info['fps']
        new=analyze_trace(t,b,fps,threshold_method='change_aware',**options)
    except ValueError as exc:error=str(exc)
    text=new['text'] if new else '';status=new['status'] if new else 'REJECTED'
    assert text==before['text']
    if saved and new:assert saved['events']==new['events'] and saved['characters']==new['characters']
    row=dict(group=group,name=name,text=text,text_unchanged=True,before_status=before['status'],after_status=status,
        correct=before['exact'],new_suspicion=bool(new and new['exposure_suspicions']),unflagged_before=before['unflagged_error'],unflagged_after=status=='OK' and not before['exact'])
    rows.append(row)
    (out/(group+'_'+name+'.json')).write_text(json.dumps(dict(comparison=row,analysis=new,error=error),ensure_ascii=False,indent=2),encoding='utf-8')
summary=dict(cases=len(rows),all_transcripts_and_events_unchanged=True,unflagged_before=sum(r['unflagged_before'] for r in rows),unflagged_after=sum(r['unflagged_after'] for r in rows),
    correct_cases_new_suspicion=sum(r['correct'] and r['new_suspicion'] for r in rows),new_suspicion_cases=[r['name'] for r in rows if r['new_suspicion']])
(out/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');(out/'comparison.csv').write_bytes(csv_text(rows).encode('utf-8-sig'))
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
for name,h in protocol['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
print(json.dumps(summary,ensure_ascii=False,indent=2))
