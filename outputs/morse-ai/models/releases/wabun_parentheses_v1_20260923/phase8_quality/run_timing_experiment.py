"""Evaluate fixed timing-only replacement on development then locked new cases."""
from pathlib import Path
import sys,json,argparse
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parent;P=ROOT.parent
sys.path.insert(0,str(P));sys.path.insert(0,str(ROOT))
import evaluate_new as runner
from timing_frontend import segment_timing
from morse_segmentation import segment_morse
from morse_table import REVERSE_TABLE,MORSE_TABLE
from mixed_morse import INTERNATIONAL_REVERSE
from analyze_saved_errors import read,write,sha,ideal,SIGNALS
from run_frontend_experiment import result,summary
from stress_frontend import synth
from noise_preparation import mix_at_snr
from evaluation_compare import SCHEMA,load_bundle,distance,paired
OUT=ROOT/'timing_experiment_v1'
TEXTS=[('long','コソセ','コソセ'),('short','ヘイハ','ヘイハ'),('mixed','ニ（ハヘ）ホ','ニBEホ')]

def infer(audio,models,cfg,labels,method):
    meta={}
    try:
        body,meta=(segment_morse(audio) if method=='baseline' else segment_timing(audio))
        for i,r in enumerate(body):r.update(index=i,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
        error=''
    except (ValueError,RuntimeError) as exc:body=[];error=str(exc)
    outputs={}
    for name,model in models.items():
        if error:outputs[name]=('',[],[],error);continue
        try:
            text,segments,warnings=runner.infer(body,audio,model,cfg,labels)
            if meta.get('timing_ambiguous'):warnings.append('短点推定に異なる候補が残っています。要確認。')
            outputs[name]=(text,segments,warnings,'')
        except (ValueError,RuntimeError) as exc:outputs[name]=('',[],[],str(exc))
    return outputs,meta

def evaluate_case(stage,ident,audio_path,reference,expected,condition,models,cfg,labels,baseline=None):
    dest=OUT/stage/ident;dest.mkdir(exist_ok=False)
    h=sha(audio_path);audio=runner.load_audio(audio_path);all_rows=[]
    write(dest/'source.json',dict(audio=str(audio_path.resolve()),sha256=h,reference=reference,expected=expected))
    for method in ('baseline','timing_v1'):
        if method=='baseline' and baseline is not None:outputs=baseline;meta={}
        else:outputs,meta=infer(audio,models,cfg,labels,method)
        write(dest/(method+'_detector.json'),meta)
        for model,data in outputs.items():
            row,detail=result(ident,model,method,reference,data,h,condition,expected)
            row.update(estimated_dot_seconds=meta.get('dot_seconds'),timing_ambiguous=meta.get('timing_ambiguous',False))
            detail['metric']=row;write(dest/(method+'_'+model+'.json'),detail);all_rows.append(row)
    return all_rows

def save(stage,rows):
    directory=OUT/stage;write(directory/'results.json',rows);write(directory/'summary.json',summary(rows))
    comparisons=directory/'comparisons';comparisons.mkdir()
    paired_results=[]
    for model in ('M1','M2','M3','M4'):
        for method in ('baseline','timing_v1'):
            rs=[r for r in rows if (r['model'],r['method'])==(model,method)]
            b=dict(schema=SCHEMA,name=f'timing_{stage}_{method}_{model}',scoring_policy='phase8-content-v2-normalized-codepoints',scope='synthetic-noise-diagnostic',
                model_sha256=sha(P/f'phase6_wabun65/runs/{model.lower()}_wabun65_20260922/best.pt'),rows=rs)
            raw=json.dumps(b,ensure_ascii=False);load_bundle(raw.encode());(comparisons/f'timing_{stage}_{method}_{model}_comparison.json').write_text(raw,encoding='utf-8')
        paired_results.append(dict(model=model,**paired([r for r in rows if (r['model'],r['method'])==(model,'baseline')],[r for r in rows if (r['model'],r['method'])==(model,'timing_v1')])))
    write(directory/'paired_summary.json',paired_results)

def main(stage):
    runner.verify_frozen()
    if stage=='development':
        OUT.mkdir(exist_ok=False)
        for _,signal,reference in TEXTS:
            inside=False;text=''
            for c in signal:
                if c in '（）':inside=c=='（';continue
                text+=INTERNATIONAL_REVERSE[MORSE_TABLE[c]] if inside else c
            assert text==reference
        write(OUT/'plan.json',dict(scope='TIMING_ONLY_SYNTHETIC_DIAGNOSTIC',development=['noise_expanded 366','frontend_stress_v1 192'],
            held_texts=TEXTS,dots=[.07,.11,.19],profiles=['stable','jitter30','drift100'],seeds=[107,211],noise=['clean','gaussian_0dB'],held_conditions=108,
            estimator='Fit mark lengths to 1/3 units and gaps to 1/3/7 units, equal mean log residual weights, clip0.8; units15..500ms. Ambiguity margin0.03.',
            policy='No parameter selection or retuning after held evaluation. Preserve production. Baseline filtering unchanged; no mode repair.',
            scripts={str(p.relative_to(P)):sha(p) for p in [Path(__file__),ROOT/'timing_frontend.py',ROOT/'stress_frontend.py',ROOT/'run_frontend_experiment.py']},
            previous_results={str(p.relative_to(P)):sha(p) for p in [ROOT/'noise_expanded/results.json',ROOT/'frontend_stress_v1/results.json',ROOT/'frontend_experiment_v1/held/results.json']}))
    plan=read(OUT/'plan.json')
    for p,h in {**plan['scripts'],**plan['previous_results']}.items():assert sha(P/p)==h
    if stage=='held':
        lock=read(OUT/'validation_lock.json');assert lock['plan_sha256']==sha(OUT/'plan.json');assert lock['development_sha256']==sha(OUT/'development/results.json')
    (OUT/stage).mkdir(exist_ok=False);models,cfg,labels=runner.load_models();rows=[];counter=0
    if stage=='development':
        for dataset in ('noise_expanded','frontend_stress_v1'):
            old=read(ROOT/dataset/'results.json');cases={r['id']:r for r in old if r.get('method','baseline')=='baseline'}
            for old_id,m in cases.items():
                folder=ROOT/dataset/old_id;meta=read(folder/'input.json');baseline={}
                for name in models:
                    d=read(folder/((name if dataset=='noise_expanded' else 'baseline_'+name)+'.json'))
                    baseline[name]=(d['text'],d['segments'],d['warnings'],d['metric']['error'])
                expected=ideal(SIGNALS[m['text_id']],m['dot_seconds']) if dataset=='noise_expanded' else meta['expected']
                condition={k:v for k,v in m.items() if k in ('noise','snr_db','dot_seconds','text_id','offset_seconds','profile','seed','frequency_hz')};condition['dataset']=dataset
                rows+=evaluate_case(stage,dataset+'_'+old_id,folder/'input.wav',meta['reference'],expected,condition,models,cfg,labels,baseline)
                counter+=1
                if counter%60==0:print(f'development {counter}/558',flush=True)
        assert counter==558;save(stage,rows)
        write(OUT/'validation_lock.json',dict(plan_sha256=sha(OUT/'plan.json'),development_sha256=sha(OUT/'development/results.json'),parameters_unchanged=True))
    else:
        inputs=OUT/'held_inputs';inputs.mkdir()
        for text_id,signal,reference in plan['held_texts']:
            for dot in plan['dots']:
                for profile in plan['profiles']:
                    for seed in plan['seeds']:
                        clean,expected,meta=synth(signal,dot,profile,seed)
                        for noise in plan['noise']:
                            ident=f'{text_id}_d{round(dot*1000)}_{profile}_seed{seed}_{noise}'
                            if noise=='clean':audio=clean;mix={}
                            else:audio,mix=mix_at_snr(clean,np.random.default_rng(seed+9000).normal(0,.1,len(clean)),0)
                            path=inputs/(ident+'.wav');sf.write(path,audio,16000,subtype='FLOAT')
                            write(inputs/(ident+'.json'),dict(reference=reference,expected=expected,sha256=sha(path),mix=mix,**meta))
                            condition=dict(noise=noise,snr_db=None if noise=='clean' else 0,dot_seconds=dot,text_id=text_id,profile=profile,seed=seed,frequency_hz=700,dataset='timing_new_conditions')
                            rows+=evaluate_case(stage,ident,path,reference,expected,condition,models,cfg,labels)
                            counter+=1
                            if counter%24==0:print(f'held {counter}/108',flush=True)
        assert counter==108;save(stage,rows)
    for r in rows:assert distance(r['reference'],r['hypothesis'])==r['edits']
    for p,h in {**plan['scripts'],**plan['previous_results']}.items():assert sha(P/p)==h
    runner.verify_frozen();write(OUT/stage/'verification.json',dict(completed=True,cases=counter,rows=len(rows),independent_score_check=True,frozen_hashes_match=True))
    print(stage+' PASS',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['development','held']);main(parser.parse_args().stage)
