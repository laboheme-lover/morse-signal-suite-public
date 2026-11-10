"""Frozen Wabun M1--M4 on the historical 40-recording protocol."""
from pathlib import Path
import sys,json,csv,copy
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
sys.path.insert(0,str(PROJECT/'phase6_wabun65'))
sys.path.insert(0,str(PROJECT))
from common import MODELS,envelope,collate,sha,write_json,write_csv,read_csv,setup
import torch
from audio_preprocessing import load_audio
from morse_segmentation import extract_character
from analyze_recording_body import select_body
from mixed_morse import decode_mixed
from evaluate_recording import edit_alignment
from src.test_protection import verify_lock

def body_rows(rows,mixed):
    if not mixed:return select_body(rows)
    starts=[i for i,r in enumerate(rows) if r['pattern']=='-..---']
    ends=[i for i,r in enumerate(rows) if r['pattern']=='...-.']
    if len(starts)!=1 or len(ends)!=1 or ends[0]<=starts[0]:raise ValueError('Ambiguous body')
    return rows[starts[0]+1:ends[0]]

def decode(rows,mixed):
    if mixed:return decode_mixed(rows)
    return ''.join(r['prediction'] for r in rows),''.join(r['rule_prediction'] for r in rows)

def main():
    out=ROOT/'results';out.mkdir(parents=True,exist_ok=False)
    source=PROJECT/'evaluation'
    roster=json.loads((source/'final_report/report_config.json').read_text(encoding='utf-8'))['selected_records']
    assert len(roster)==40 and len({r['number'] for r in roster})==40
    runs=[PROJECT/f'phase6_wabun65/runs/m{i}_wabun65_20260922' for i in range(1,5)]
    checkpoints=[torch.load(p/'best.pt',map_location='cpu',weights_only=True) for p in runs]
    cfg=checkpoints[0]['config'];setup(cfg)
    labels=sorted(checkpoints[0]['labels'],key=checkpoints[0]['labels'].get)
    models={}
    protected={}
    def protect(path):
        protected[str(path)]=sha(path)
    for name,run,ck in zip(MODELS,runs,checkpoints):
        done=json.loads((run/'training_complete.json').read_text())
        assert done['checkpoint_sha256']==sha(run/'best.pt')
        assert ck['labels']==checkpoints[0]['labels'] and ck['config']['preprocessing']==cfg['preprocessing']
        model=MODELS[name](ck['config']).eval();model.load_state_dict(ck['state_dict']);models[name]=model
        protect(run/'best.pt')
    frozen=verify_lock(PROJECT/'phase1_data')
    prepared=[];historical=[]
    # Establish every reference, body and source hash before new predictions.
    for rec in roster:
        number=rec['number'];folder=source/f'real_collection_baseline/{number:03d}'
        meta=json.loads((folder/'recording_metrics.json').read_text(encoding='utf-8'))
        audio=Path(meta['audio_path'])
        assert sha(audio)==meta['audio_sha256'],f'Original recording changed: {number}'
        rows=read_csv(folder/'segments.csv')
        mixed=number in (50,66,70,71)
        body=body_rows(rows,mixed)
        ref=(source/rec['reference']).read_text(encoding='utf-8')
        old,rule=decode(body,mixed)
        assert old==(source/rec['cnn']).read_text(encoding='utf-8'),f'Historical CNN not reproduced: {number}'
        assert rule==(source/rec['rule']).read_text(encoding='utf-8'),f'Historical rule not reproduced: {number}'
        old_metric,_=edit_alignment(ref,old);rule_metric,_=edit_alignment(ref,rule)
        historical.append({'number':number,'reference_units':len(ref),'old_edits':old_metric['edit_distance'],'rule_edits':rule_metric['edit_distance']})
        for path in (audio,folder/'segments.csv',folder/'recording_metrics.json',source/rec['reference'],source/rec['cnn'],source/rec['rule']):protect(path)
        prepared.append((number,audio,body,ref,mixed,rule,meta))
    assert sum(r['reference_units'] for r in historical)==16317
    assert sum(r['old_edits'] for r in historical)==1149
    assert sum(r['rule_edits'] for r in historical)==16
    write_csv(out/'historical_reproduction.csv',historical)
    excluded=[{'number':n,'reason':'Body boundaries ambiguous' if n!=62 else 'Unbracketed international reference and unresolved body mapping'} for n in (57,62,64,67)]
    write_csv(out/'excluded_recordings.csv',excluded)
    write_json(out/'protocol.json',{'recordings':40,'reference_units':16317,'normalization':'Frozen historical normalized references: NFKC, full-size kana, separated dakuten; body punctuation excluded; international within parentheses for mixed subset',
        'body_and_mode':'Frozen historical rule boundaries/patterns, shared across all models; not CNN-only end-to-end',
        'preprocessing':cfg['preprocessing'],'frequency_translation':False,'retraining':False,'test_time_tuning':False,
        'unseen_recordings':False,'excluded':excluded,'protected_sources':protected})
    results=[]
    for number,audio_path,body,ref,mixed,rule,meta in prepared:
        folder=out/f'{number:03d}';folder.mkdir()
        (folder/'reference.txt').write_text(ref,encoding='utf-8')
        audio=load_audio(audio_path)
        assert abs(len(audio)/16000-meta['duration_seconds'])<1/16000
        items=[]
        for i,row in enumerate(body):
            segment={k:int(row[k]) for k in ('start_sample','end_sample')}
            assert 0<=segment['start_sample']<segment['end_sample']<=len(audio)
            items.append((envelope(extract_character(audio,segment),16000,cfg),0,i))
        loader=torch.utils.data.DataLoader(items,batch_size=128,collate_fn=collate)
        for name,model in models.items():
            predrows=copy.deepcopy(body)
            with torch.inference_mode():
                for x,lengths,_,ids in loader:
                    prob=model(x,lengths).softmax(-1);values,pred=prob.max(-1)
                    for idx,p,v in zip(ids.tolist(),pred.tolist(),values.tolist()):
                        predrows[idx]['prediction']=labels[p]
                        predrows[idx]['confidence']=v
            text,diagnostic=decode(predrows,mixed)
            assert diagnostic==rule
            metric,alignment=edit_alignment(ref,text)
            metric.update(model=name,number=number,exact_match=int(text==ref),input_segments=len(body))
            results.append(metric)
            (folder/f'{name}_transcript.txt').write_text(text,encoding='utf-8')
            write_csv(folder/f'{name}_alignment.csv',alignment)
            write_csv(folder/f'{name}_segments.csv',[{k:r[k] for k in ('index','start_sample','end_sample','pattern','prediction','confidence','rule_prediction')} for r in predrows])
        (folder/'rule_transcript.txt').write_text(rule,encoding='utf-8')
        write_json(out/'recording_results.json',results)
        print(f'{number}: '+', '.join(f'{r["model"]} CER={r["cer"]:.2%}' for r in results[-4:]),flush=True)
    write_csv(out/'recording_results.csv',results)
    summary=[]
    for name in models:
        subset=[r for r in results if r['model']==name];n=sum(r['reference_units'] for r in subset)
        row={'model':name,'recordings':len(subset),'reference_units':n,
            **{k:sum(r[k] for r in subset) for k in ('edit_distance','substitutions','insertions','deletions','exact_match')}}
        row['cer']=row['edit_distance']/n
        row['mean_recording_cer']=sum(r['cer'] for r in subset)/len(subset)
        summary.append(row)
    write_json(out/'summary.json',summary);write_csv(out/'summary.csv',summary)
    assert all(sha(p)==h for p,h in protected.items()),'Protected input changed'
    assert len(verify_lock(PROJECT/'phase1_data'))==len(frozen)
    for number,_,_,ref,_,_,_ in prepared:
        for name in models:
            text=(out/f'{number:03d}/{name}_transcript.txt').read_text(encoding='utf-8')
            metric,_=edit_alignment(ref,text)
            saved=next(r for r in results if r['number']==number and r['model']==name)
            assert all(metric[k]==saved[k] for k in metric)
    write_json(out/'verification.json',{'status':'PASS','protected_files_unchanged':len(protected),'frozen_synthetic_test_files_unchanged':len(frozen),
        'historical40_reproduced':True,'all_160_transcripts_rescored':True,'model_updated':False})
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
