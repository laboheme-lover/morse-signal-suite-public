"""Fixed six-way ablation, followed by a predeclared new-condition check."""
from pathlib import Path
import sys,json,argparse
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parent;P=ROOT.parent
sys.path.insert(0,str(P));sys.path.insert(0,str(ROOT))
import evaluate_new as runner
from adaptive_pipeline import evaluate,METHODS
from analyze_saved_errors import read,write,sha
from run_frontend_experiment import result,summary
from stress_frontend import synth
from morse_table import MORSE_TABLE
from mixed_morse import INTERNATIONAL_REVERSE
from noise_preparation import mix_at_snr
from evaluation_compare import SCHEMA,load_bundle,distance,paired
OUT=ROOT/'adaptive_experiment_v1'
TEXTS=[('long','ソスコ','ソスコ'),('mixed','ロ（イハ）リ','ロABリ'),('short','ヘムヘ','ヘムヘ')]

def save(stage,rows):
    directory=OUT/stage;write(directory/'results.json',rows);write(directory/'summary.json',summary(rows));dest=directory/'comparisons';dest.mkdir()
    comparisons=[]
    for model in ('M1','M2','M3','M4'):
        for method in METHODS:
            rs=[r for r in rows if (r['model'],r['method'])==(model,method)]
            b=dict(schema=SCHEMA,name=f'adaptive_{stage}_{method}_{model}',scoring_policy='phase8-content-v2-normalized-codepoints',scope='synthetic-noise-diagnostic',
                   model_sha256=sha(P/f'phase6_wabun65/runs/{model.lower()}_wabun65_20260922/best.pt'),rows=rs)
            raw=json.dumps(b,ensure_ascii=False);load_bundle(raw.encode());(dest/f'adaptive_{stage}_{method}_{model}_comparison.json').write_text(raw,encoding='utf-8')
            if method!='baseline':comparisons.append(dict(model=model,method=method,**paired([r for r in rows if (r['model'],r['method'])==(model,'baseline')],rs)))
    write(directory/'paired_summary.json',comparisons)

def case(stage,ident,source,reference,expected,condition,models,cfg,labels,cached=None):
    directory=OUT/stage/ident;directory.mkdir();audio=runner.load_audio(source);h=sha(source)
    write(directory/'source.json',dict(audio=str(source.resolve()),sha256=h,reference=reference,expected=expected))
    methods=METHODS if cached is None else [m for m in METHODS if m not in ('baseline','timing')]
    outputs,detectors=evaluate(audio,models,cfg,labels,methods)
    if cached:outputs.update(cached)
    write(directory/'detectors.json',detectors);rows=[]
    for (method,model),data in outputs.items():
        row,detail=result(ident,model,method,reference,data,h,condition,expected);meta=detectors.get(method,{})
        row.update(estimated_dot_seconds=meta.get('dot_seconds'),tracked_min_hz=meta.get('tracked_min_hz'),tracked_max_hz=meta.get('tracked_max_hz'),
                   feature_time_scale=(.1/meta['dot_seconds']) if method in ('tempo','combined','combined_mode') and meta.get('dot_seconds') else None)
        detail['metric']=row;write(directory/(method+'_'+model+'.json'),detail);rows.append(row)
    return rows

def main(stage):
    runner.verify_frozen()
    if stage=='development':
        OUT.mkdir(exist_ok=False)
        for _,signal,reference in TEXTS:
            text='';inside=False
            for c in signal:
                if c in '（）':inside=c=='（';continue
                text+=INTERNATIONAL_REVERSE[MORSE_TABLE[c]] if inside else c
            assert text==reference
        scripts=[Path(__file__),ROOT/'adaptive_pipeline.py',ROOT/'timing_frontend.py',ROOT/'experimental_frontend.py',ROOT/'stress_frontend.py',ROOT/'run_frontend_experiment.py']
        previous=[ROOT/'timing_experiment_v1/development/results.json',ROOT/'timing_experiment_v1/held/results.json',ROOT/'frontend_stress_v1/results.json',ROOT/'noise_expanded/results.json']
        write(OUT/'plan.json',dict(scope='SYNTHETIC_ABLATION_NOT_REAL_RECORDING_ACCEPTANCE',methods=METHODS,development_cases=666,
            held_texts=TEXTS,dots=[.09,.14,.22],profiles=['stable','wobble60','drift100','jitter30','combined'],seeds=[307,419],noise=['clean','gaussian_0dB'],held_cases=180,
            policy='All six variants fixed before data; no post-held retuning or automatic production adoption. 100ms envelope target, preserve padding. No reference passed to inference.',
            scripts={str(p.relative_to(P)):sha(p) for p in scripts},previous_results={str(p.relative_to(P)):sha(p) for p in previous}))
    plan=read(OUT/'plan.json')
    for p,h in {**plan['scripts'],**plan['previous_results']}.items():assert sha(P/p)==h
    if stage=='held':
        lock=read(OUT/'validation_lock.json');assert lock['plan_sha256']==sha(OUT/'plan.json');assert lock['development_sha256']==sha(OUT/'development/results.json')
    (OUT/stage).mkdir(exist_ok=False);models,cfg,labels=runner.load_models();rows=[];counter=0
    if stage=='development':
        for old_stage in ('development','held'):
            old_dir=ROOT/'timing_experiment_v1'/old_stage
            metrics=read(old_dir/'results.json');cases={r['id']:r for r in metrics if r['method']=='baseline'}
            for ident,m in cases.items():
                folder=old_dir/ident;source=read(folder/'source.json');cached={}
                for model in models:
                    for method,old_method in [('baseline','baseline'),('timing','timing_v1')]:
                        data=read(folder/(old_method+'_'+model+'.json'));cached[(method,model)]=(data['text'],data['segments'],data['warnings'],data['metric']['error'])
                condition={k:v for k,v in m.items() if k in ('noise','snr_db','dot_seconds','text_id','offset_seconds','profile','seed','frequency_hz','dataset')}
                rows+=case(stage,old_stage+'_'+ident,Path(source['audio']),source['reference'],source['expected'],condition,models,cfg,labels,cached)
                counter+=1
                if counter%50==0:print(f'development {counter}/666',flush=True)
        assert counter==666;save(stage,rows)
        write(OUT/'validation_lock.json',dict(plan_sha256=sha(OUT/'plan.json'),development_sha256=sha(OUT/'development/results.json'),retuning=False))
    else:
        inputs=OUT/'held_inputs';inputs.mkdir()
        for text_id,signal,reference in plan['held_texts']:
            for dot in plan['dots']:
                for profile in plan['profiles']:
                    for seed in plan['seeds']:
                        clean,expected,meta=synth(signal,dot,profile,seed)
                        for noise in plan['noise']:
                            ident=f'{text_id}_d{round(dot*1000)}_{profile}_seed{seed}_{noise}'
                            if noise=='clean':wave=clean;mix={}
                            else:wave,mix=mix_at_snr(clean,np.random.default_rng(seed+19000).normal(0,.1,len(clean)),0)
                            path=inputs/(ident+'.wav');sf.write(path,wave,16000,subtype='FLOAT');write(inputs/(ident+'.json'),dict(reference=reference,expected=expected,sha256=sha(path),mix=mix,**meta))
                            condition=dict(noise=noise,snr_db=None if noise=='clean' else 0,dot_seconds=dot,text_id=text_id,profile=profile,seed=seed,frequency_hz=700,dataset='adaptive_new_conditions')
                            rows+=case(stage,ident,path,reference,expected,condition,models,cfg,labels);counter+=1
                            if counter%30==0:print(f'held {counter}/180',flush=True)
        assert counter==180;save(stage,rows)
    for r in rows:assert distance(r['reference'],r['hypothesis'])==r['edits']
    for p,h in {**plan['scripts'],**plan['previous_results']}.items():assert sha(P/p)==h
    runner.verify_frozen();write(OUT/stage/'verification.json',dict(completed=True,cases=counter,rows=len(rows),independent_score_check=True,frozen_hashes_match=True))
    print(stage+' PASS',flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['development','held']);main(parser.parse_args().stage)
