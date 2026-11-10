"""Versioned regression replay plus predeclared fresh synthetic diagnostic checks."""
from pathlib import Path
import json,hashlib
import numpy as np
from optical_video.core import analyze_trace,analyze_video
from optical_video.evaluate_coverage_stress import altered_video,distance
from morse_table import MORSE_TABLE

root=Path(__file__).parent;out=root/'diagnostics_v2';out.mkdir(exist_ok=False)
old=root/'coverage_stress_v1';old_protocol=json.loads((old/'protocol.json').read_text(encoding='utf-8'))
old_scores=json.loads((old/'results.json').read_text(encoding='utf-8'));old_specs={s['name']:s for s in old_protocol['cases']}
assert hashlib.sha256((root/'baseline_v1/core.py').read_bytes()).hexdigest()==old_protocol['source_sha256'][str((root/'core.py').resolve())]
fresh=[dict(name='new_clean',condition=dict(kind='baseline',level=0)),dict(name='new_step',condition=dict(kind='exposure_step',level=.35)),dict(name='new_drift',condition=dict(kind='exposure_drift',level=.72)),dict(name='new_noise',condition=dict(kind='pixel_noise',level=65))]
protocol=dict(version='diagnostics_v2',fresh_cases=fresh,fresh_text='ムヘナリツメイホ',fresh_seed=97223,
    historical_cases=45,historical_method='Replay frozen brightness traces; re-read rejected files',
    changes='Warnings only. No adaptive threshold, pulse correction, transcript correction or model training',
    limitations='Synthetic development diagnostics. Not independent real-camera evaluation.',
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'core.py',root/'diagnostics.py',Path(__file__))})
(out/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
rows=[]
for before in old_scores:
    name=before['name'];bundle=json.loads((old/(name+'_result.json')).read_text(encoding='utf-8'));saved=bundle['analysis'];new=None;error=''
    try:
        if saved:
            trace=saved['trace'];new=analyze_trace([r['time_seconds'] for r in trace],[r['brightness'] for r in trace],saved['video']['fps'],**old_specs[name]['options'])
        else:
            truth=json.loads((old/(name+'.json')).read_text(encoding='utf-8'));new=analyze_video(old/(name+'.avi'),tuple(truth['roi']),**old_specs[name]['options'])
    except ValueError as exc:error=str(exc)
    text=new['text'] if new else '';status=new['status'] if new else 'REJECTED'
    assert text==before['text'],'Diagnostic changed transcript'
    if new and saved:
        assert new['events']==saved['events'] and new['characters']==saved['characters'],'Diagnostic changed decoding'
    row=dict(name=name,category=before['category'],before_status=before['status'],after_status=status,exact=before['exact'],text_unchanged=True,
        new_diagnostic=bool(new and new['diagnostics']),unflagged_error_before=before['unflagged_error'],unflagged_error_after=status=='OK' and not before['exact'])
    rows.append(row)
    (out/(name+'.json')).write_text(json.dumps(dict(summary=row,analysis=new,error=error),ensure_ascii=False,indent=2),encoding='utf-8')
fresh_rows=[]
for case in fresh:
    path=out/(case['name']+'.avi');truth=altered_video(path,[MORSE_TABLE[c] for c in protocol['fresh_text']],case['condition'],seed=protocol['fresh_seed'])
    path.with_suffix('.truth.json').write_text(json.dumps(truth,indent=2),encoding='utf-8')
    r=analyze_video(path,tuple(truth['roi']));edits=distance(protocol['fresh_text'],r['text'])
    fresh_rows.append(dict(name=case['name'],status=r['status'],edits=edits,reference_units=len(protocol['fresh_text']),diagnostic=bool(r['diagnostics'])))
    (out/(case['name']+'_result.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
# Negative controls: known valid code followed by a quiet pause, and gradual quiet-background drift.
from optical_video.evaluate_coverage_stress import schedule
states,_=schedule([MORSE_TABLE[c] for c in 'イロハ'])
values=np.r_[np.where(states,220.,30.),np.full(900,30.)];t=np.arange(len(values))/30
pause=analyze_trace(t,values,30,dot_seconds=.3)
assert not pause['diagnostics'] and pause['text']=='イロハ'
controls=dict(long_quiet_pause_no_warning=True)
summary=dict(historical_cases=len(rows),all_transcripts_unchanged=True,
    unflagged_errors_before=sum(r['unflagged_error_before'] for r in rows),unflagged_errors_after=sum(r['unflagged_error_after'] for r in rows),
    exact_cases_new_diagnostic=sum(r['exact'] and r['new_diagnostic'] for r in rows),fresh=fresh_rows,controls=controls)
(out/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
