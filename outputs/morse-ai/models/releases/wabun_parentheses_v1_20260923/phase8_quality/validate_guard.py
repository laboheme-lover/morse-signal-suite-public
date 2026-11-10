"""Development regression audit and predeclared new synthetic guard check."""
from pathlib import Path
import sys, json
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parent;P=ROOT.parent;sys.path[:0]=[str(ROOT),str(P)]
from recording_experiment import read,save
from intake import digest
from guarded_pipeline import guard,POLICY
from adaptive_pipeline import evaluate
from stress_frontend import synth
from noise_preparation import mix_at_snr
from evaluation_compare import distance
import evaluate_new as runner
OUT=ROOT/'guard_experiment_v1'

def main():
    if OUT.exists():raise FileExistsError(OUT)
    runner.verify_frozen()
    plan=dict(scope='SYNTHETIC_GUARD_DIAGNOSTIC_NOT_REAL_ACCEPTANCE',policy=POLICY,
        texts=[['kana','イロハ','イロハ'],['long','コヘソ','コヘソ'],['mixed','サ（イハ）シ','サABシ']],
        dots=[.075,.125,.205],profiles=['stable','jitter30','wobble60','combined'],seeds=[557,809],noise=['clean','gaussian_0dB'],conditions=144,
        no_post_validation_retuning=True,scripts={str(p.relative_to(P)):digest(p) for p in [Path(__file__),ROOT/'guarded_pipeline.py',ROOT/'adaptive_pipeline.py',ROOT/'stress_frontend.py']})
    save(OUT/'plan.json',plan)
    old=ROOT/'adaptive_experiment_v1/development';allrows=read(old/'results.json');regressions=[];metrics=[]
    for ident in sorted({r['id'] for r in allrows}):
        detectors=read(old/ident/'detectors.json');outputs={}
        for name in ['M1','M2','M3','M4']:
            for method in ['baseline','combined_mode']:
                data=read(old/ident/(method+'_'+name+'.json'));outputs[(method,name)]=(data['text'],data['segments'],data['warnings'],data['metric']['error'])
            result,meta=guard(outputs,detectors,name)
            base=next(r for r in allrows if r['id']==ident and r['model']==name and r['method']=='baseline')
            combined=next(r for r in allrows if r['id']==ident and r['model']==name and r['method']=='combined_mode')
            metrics.append(dict(id=ident,model=name,reference=base['reference'],baseline_edits=base['edits'],combined_edits=combined['edits'],
                guarded_edits=distance(base['reference'],result[0]),reference_units=base['reference_units'],guard=meta['guard']))
            if combined['edits']>base['edits']:
                keys=['missing','split','merged','extra','pattern_error','class_error','class_error_with_correct_pattern','mode_error']
                regressions.append(dict(id=ident,model=name,reference=base['reference'],baseline=base['hypothesis'],combined=combined['hypothesis'],guarded=result[0],
                    baseline_edits=base['edits'],combined_edits=combined['edits'],guarded_edits=metrics[-1]['guarded_edits'],
                    baseline_diagnostics={k:base[k] for k in keys},combined_diagnostics={k:combined[k] for k in keys},guard=meta['guard']))
    save(OUT/'development.json',metrics);save(OUT/'regression_analysis.json',regressions)
    models,cfg,labels=runner.load_models();rows=[]
    for text_id,signal,reference in plan['texts']:
        for dot in plan['dots']:
            for profile in plan['profiles']:
                for seed in plan['seeds']:
                    clean,expected,truth=synth(signal,dot,profile,seed)
                    for noise in plan['noise']:
                        ident=f'{text_id}_{dot}_{profile}_{seed}_{noise}'
                        wave=clean if noise=='clean' else mix_at_snr(clean,np.random.default_rng(seed+39000).normal(0,.1,len(clean)),0)[0]
                        folder=OUT/'validation'/ident;folder.mkdir(parents=True)
                        sf.write(folder/'input.wav',wave,16000,subtype='FLOAT')
                        outputs,detectors=evaluate(wave,models,cfg,labels,['baseline','combined','combined_mode'])
                        decisions={}
                        for name in models:
                            result,meta=guard(outputs,detectors,name);decisions[name]=meta['guard'];outputs[('guarded',name)]=result
                            for method in ['baseline','combined_mode','guarded']:
                                text,segments,warnings,error=outputs[(method,name)]
                                rows.append(dict(id=ident,model=name,method=method,reference=reference,hypothesis=text,reference_units=len(reference),
                                    edits=distance(reference,text),error=error,profile=profile,dot_seconds=dot,noise=noise,input_sha256=digest(folder/'input.wav'),
                                    fallback=meta['guard']['fallback'] if method=='guarded' else False))
                        save(folder/'detail.json',dict(outputs={m+'_'+n:dict(text=v[0],segments=v[1],warnings=v[2],error=v[3]) for (m,n),v in outputs.items()},decisions=decisions,truth=truth))
                        if len(rows)%288==0:print(f'guard validation {len(rows)//12}/144',flush=True)
    assert len(rows)==144*12
    for path,h in plan['scripts'].items():assert digest(P/path)==h
    runner.verify_frozen();save(OUT/'validation_results.json',rows)
    save(OUT/'verification.json',dict(completed=True,development_cases=666,validation_cases=144,models_unchanged=True,plan_hash=digest(OUT/'plan.json'),guard_hash=digest(ROOT/'guarded_pipeline.py')))
    print('guard validation PASS',flush=True)

if __name__=='__main__':main()
