"""Reference-free conservative experiment selection; never a correctness guarantee."""
import copy
from adaptive_pipeline import evaluate as evaluate_original, METHODS as ORIGINAL_METHODS, LABELS as ORIGINAL_LABELS
METHODS=ORIGINAL_METHODS+['guarded']
LABELS={**ORIGINAL_LABELS,'guarded':'補正ガード付き実験版'}
POLICY=dict(version='guard-v1',irregular_timing_loss=.25,stable_pitch_span_hz=32,minimum_active_fraction=.20,
            fallback='Whole recording only; no character-level splicing or confidence-based truth selection')

def guard(outputs,detectors,name):
    """outputs use (method,model) keys and (text,rows,warnings,error) values."""
    base=outputs[('baseline',name)];candidate=outputs[('combined_mode',name)]
    meta=detectors.get('combined_mode',{});reasons=[];selected='combined_mode'
    same_patterns=bool(base[1]) and [r['pattern'] for r in base[1]]==[r['pattern'] for r in candidate[1]]
    if candidate[3]:reasons.append('統合補正の処理失敗')
    if meta.get('timing_ambiguous'):reasons.append('短点の推定候補が複数')
    if meta.get('active_frame_fraction',1)<POLICY['minimum_active_fraction']:reasons.append('追跡に使える音区間が少ない')
    span=meta.get('tracked_max_hz',0)-meta.get('tracked_min_hz',0)
    if meta.get('timing_fit_loss',0)>POLICY['irregular_timing_loss'] and span<=POLICY['stable_pitch_span_hz'] and same_patterns:
        reasons.append('音程は安定しているが打鍵間隔が不規則で、従来処理と観測符号が一致')
    if reasons and not base[3] and base[1]:selected='baseline'
    text,rows,warnings,error=copy.deepcopy(outputs[(selected,name)])
    if reasons:warnings.append('補正ガード：'+'／'.join(reasons)+'。'+('録音全体を従来処理へ戻しました。要確認。' if selected=='baseline' else '従来処理も利用できません。要確認。'))
    other=candidate[1] if selected=='baseline' else base[1]
    differences=[]
    for r in rows:
        start,end=r['start_sample'],r['end_sample']
        match=max(other,key=lambda q:max(0,min(end,q['end_sample'])-max(start,q['start_sample'])),default=None)
        overlap=max(0,min(end,match['end_sample'])-max(start,match['start_sample'])) if match else 0
        changed=not match or overlap<.5*(end-start) or r['pattern']!=match['pattern'] or r.get('text_prediction')!=match.get('text_prediction')
        if changed:
            r['review_reason']='／'.join(x for x in [r.get('review_reason',''),'処理方式によって区間・符号・文字が異なります。原音を要確認。'] if x)
            differences.append(dict(index=r.get('index'),start_seconds=start/16000,end_seconds=end/16000))
    if differences:warnings.append(f'従来処理と統合補正の相違区間：{len(differences)}。正誤を判定したものではありません。')
    decision=dict(selected_method=selected,reasons=reasons,fallback=selected=='baseline',same_observed_patterns=same_patterns,
        disagreement_intervals=differences,policy=POLICY)
    chosen_meta=copy.deepcopy(detectors.get(selected,{}));chosen_meta['guard']=decision
    return (text,rows,warnings,error),chosen_meta

def evaluate(audio,models,cfg,labels,methods=None):
    methods=list(methods or METHODS)
    if not methods or any(m not in METHODS for m in methods):raise ValueError('Unknown experiment method')
    needed=[m for m in ORIGINAL_METHODS if m in methods or ('guarded' in methods and m in ('baseline','combined','combined_mode'))]
    outputs,detectors=evaluate_original(audio,models,cfg,labels,needed)
    if 'guarded' in methods:
        for name in models:
            outputs[('guarded',name)],gmeta=guard(outputs,detectors,name)
            # Selection uses acoustic metadata and observed codes, not model scores.
            detectors['guarded']=gmeta
    return {k:v for k,v in outputs.items() if k[0] in methods},{m:detectors[m] for m in methods}
