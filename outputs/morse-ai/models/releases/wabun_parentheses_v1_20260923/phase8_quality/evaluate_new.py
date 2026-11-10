"""Fresh, fixed-model evaluation. Rehearsals never claim independent data."""
from intake import PROJECT, digest, historical, validate
from policy import render_body
from pathlib import Path
import argparse, copy, json, math, re, sys
sys.path.insert(0, str(PROJECT/'phase6_wabun65'))
from common import MODELS, envelope, collate, setup, write_json, write_csv
import torch
from audio_preprocessing import load_audio
from morse_segmentation import segment_morse, extract_character
from morse_table import REVERSE_TABLE
from evaluate_recording import edit_alignment

ROOT = Path(__file__).resolve().parent

def verify_frozen():
    for file in ('future_evaluation_plan.json', 'runner_lock.json'):
        plan=json.loads((ROOT/file).read_text(encoding='utf-8'))
        for path, expected in plan['sha256'].items():
            if digest(PROJECT/path)!=expected:raise ValueError(f'Frozen dependency changed: {path}')

def prepare(manifest, base, rehearsal=False):
    source=copy.deepcopy(manifest)
    if not rehearsal:
        if source.get('source_review_completed') is not True:
            raise ValueError('Manual source/exposure review must be completed before independent evaluation')
        known_audio,known_ref=historical()
    else:
        known_audio,known_ref=set(),set()
        for row in source.get('recordings',[]):row['declared_unseen']=True
    audit=validate(source,base,known_audio,known_ref)
    if audit['status']!='PASS':raise ValueError('; '.join(audit['errors']))
    for row in audit['recordings']:
        if not isinstance(row['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',row['id']):
            raise ValueError('id must be 1-80 ASCII letters/digits/underscore/hyphen')
        body=row.get('body',{})
        mode=body.get('mode')
        if mode not in ('full','protocol','window'):raise ValueError('Explicit body mode required: full, protocol or window')
        if mode=='window':
            start,end=body.get('start_seconds'),body.get('end_seconds')
            if not all(type(v) in (int,float) and math.isfinite(v) for v in (start,end)) or not 0<=start<end<=row['audio_info']['duration_seconds']:
                raise ValueError('Invalid predetermined body time window')
        row['declared_unseen']=False if rehearsal else True
    return audit

def select_body(rows, body):
    mode=body['mode']
    if mode=='full':return rows
    if mode=='window':
        # Do not silently split an observed character at a human-specified boundary.
        start,end=body['start_seconds'],body['end_seconds']
        if any(r['start_seconds']<start<r['end_seconds'] or r['start_seconds']<end<r['end_seconds'] for r in rows):
            raise ValueError('Body window cuts through an observed character')
        selected=[r for r in rows if start<=r['start_seconds'] and r['end_seconds']<=end]
    else:
        starts=[i for i,r in enumerate(rows) if r['pattern']=='-..---']
        ends=[i for i,r in enumerate(rows) if r['pattern']=='...-.']
        if len(starts)==len(ends)==1 and starts[0]<ends[0]:selected=rows[starts[0]+1:ends[0]]
        elif not starts and not ends and len(rows)>6 and [r['pattern'] for r in rows[:5]]==['....','.-.','....','.-.','-...-'] and rows[-1]['pattern']=='.-.-.':selected=rows[5:-1]
        else:raise ValueError('Missing or ambiguous accepted protocol framing')
    if not selected:raise ValueError('Empty body selection')
    return selected

def load_models():
    models={};cfg=None;labels=None
    for name,cls in MODELS.items():
        ck=torch.load(PROJECT/f'phase6_wabun65/runs/{name.lower()}_wabun65_20260922/best.pt',map_location='cpu',weights_only=True)
        current=sorted(ck['labels'],key=ck['labels'].get)
        if cfg is None:cfg=ck['config'];labels=current;setup(cfg)
        elif cfg['preprocessing']!=ck['config']['preprocessing'] or labels!=current:raise ValueError('Model input/label mismatch')
        model=cls(ck['config']).eval();model.load_state_dict(ck['state_dict']);models[name]=model
    return models,cfg,labels

def infer(body,audio,model,cfg,labels):
    rows=copy.deepcopy(body)
    items=[(envelope(extract_character(audio,r),16000,cfg),0,i) for i,r in enumerate(rows)]
    loader=torch.utils.data.DataLoader(items,batch_size=128,collate_fn=collate)
    with torch.inference_mode():
        for x,lengths,_,ids in loader:
            probs=model(x,lengths).softmax(-1)
            if not torch.isfinite(probs).all():raise ValueError('Non-finite model output')
            values,classes=probs.topk(3,dim=-1)
            for idx,cs,vs in zip(ids.tolist(),classes.tolist(),values.tolist()):
                rows[idx].update(prediction=labels[cs[0]],confidence=vs[0],top_k=[{'label':labels[c],'confidence':v} for c,v in zip(cs,vs)])
    return render_body(rows)

def aggregate(results):
    summaries=[]
    for name in MODELS:
        rows=[r for r in results if r['model']==name]
        n=sum(r['reference_units'] for r in rows);edits=sum(r['edit_distance'] for r in rows)
        summaries.append(dict(model=name,recordings=len(rows),reference_units=n,edit_distance=edits,cer=edits/n if n else None,
            failures=sum(r['status']!='OK' for r in rows),exact=sum(r['exact'] for r in rows),
            substitutions=sum(r['substitutions'] for r in rows),insertions=sum(r['insertions'] for r in rows),deletions=sum(r['deletions'] for r in rows),
            review_segments=sum(r['review_segments'] for r in rows)))
    return summaries

def run(manifest_path,out,rehearsal=False):
    if out.exists():raise FileExistsError(out)
    verify_frozen()
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    audit=prepare(manifest,manifest_path.parent,rehearsal)
    models,cfg,labels=load_models()
    out.mkdir(parents=True,exist_ok=False)
    write_json(out/'manifest_original.json',manifest)
    write_json(out/'prepared_inputs.json',audit)
    write_json(out/'protocol.json',{'scope':'REHEARSAL_KNOWN_OR_SYNTHETIC' if rehearsal else 'NEW_DATA_AFTER_MANUAL_EXPOSURE_REVIEW',
        'retraining':False,'fresh_audio_segmentation':True,'policy':'content_v2','body_rules_frozen_before_predictions':True,
        'failure_scoring':'Empty hypothesis, all reference units counted as deletions; failure count also reported',
        'independence_limit':'Submitter disclosure and identity checks; not independently proven unseen',
        'preprocessing':cfg['preprocessing'],'manifest_sha256':digest(manifest_path)})
    results=[]
    for entry in audit['recordings']:
        folder=out/entry['id'];folder.mkdir();ref=entry['normalized_reference']
        (folder/'reference.txt').write_text(ref,encoding='utf-8')
        common_error=''
        try:
            if digest(entry['audio'])!=entry['audio_sha256'] or digest(entry['reference'])!=entry['reference_sha256']:raise ValueError('Input changed after audit')
            audio=load_audio(entry['audio']);detected,detector=segment_morse(audio)
            for i,r in enumerate(detected):r.update(index=i,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
            body=select_body(detected,entry['body'])
            write_json(folder/'detected_segments.json',detected);write_json(folder/'detector.json',detector)
            write_json(folder/'selected_body.json',body)
        except (ValueError,OSError,RuntimeError) as exc:common_error=str(exc)
        for name,model in models.items():
            error=common_error;text='';rows=[];warnings=[]
            if not error:
                try:text,rows,warnings=infer(body,audio,model,cfg,labels)
                except (ValueError,OSError,RuntimeError) as exc:error=str(exc)
            metric,alignment=edit_alignment(ref,text)
            metric.update(id=entry['id'],group_id=entry['group_id'],model=name,status='FAILED' if error else 'OK',error=error,
                exact=int(text==ref and not error),review_segments=sum(bool(r['review_reason']) or r['text_prediction']=='□' for r in rows))
            results.append(metric)
            (folder/f'{name}.txt').write_text(text,encoding='utf-8')
            write_json(folder/f'{name}_segments.json',rows);write_json(folder/f'{name}_warnings.json',warnings)
            write_csv(folder/f'{name}_alignment.csv',alignment)
        write_json(out/'recording_results.json',results)
        print(f"{entry['id']}: "+', '.join(f"{r['model']} {r['status']} {r['edit_distance']}/{r['reference_units']}" for r in results[-4:]),flush=True)
    write_csv(out/'recording_results.csv',results)
    summary=aggregate(results);write_json(out/'summary.json',summary);write_csv(out/'summary.csv',summary)
    groups={g:aggregate([r for r in results if r['group_id']==g]) for g in sorted({r['group_id'] for r in results})}
    write_json(out/'group_summary.json',groups)
    verify_frozen()
    for entry in audit['recordings']:
        if digest(entry['audio'])!=entry['audio_sha256'] or digest(entry['reference'])!=entry['reference_sha256']:raise ValueError('Source changed during run')
    failures=sum(r['status']!='OK' for r in results)
    write_json(out/'verification.json',{'completed':True,'scope':'rehearsal' if rehearsal else 'new_data','models_and_sources_unchanged':True,'failed_model_recordings':failures})
    report=['# '+('動作確認用リハーサル（独立評価ではありません）' if rehearsal else '新規録音・固定条件評価'),'',
        '| モデル | 件数 | 文字数 | 編集数 | CER | 完全一致 | 処理失敗 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in summary:report.append(f"| {r['model']} | {r['recordings']} | {r['reference_units']} | {r['edit_distance']} | {r['cer']:.4%} | {r['exact']} | {r['failures']} |")
    report.extend(['','CERは正解に対する文字編集率です。本文抽出・正規化・モード処理を含み、CNN単体の分類Accuracyではありません。',
        '処理失敗は空の認識文として全参照文字を削除に数えます。成功例だけの集計ではありません。',
        '元音声を新たに分割・推論しました。事前指定の本文範囲を使い、正解に合わせて切り出し位置やモデルを調整していません。'])
    (out/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    return 2 if failures else 0

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--rehearsal',action='store_true')
    a=ap.parse_args();raise SystemExit(run(a.manifest,a.output,a.rehearsal))
