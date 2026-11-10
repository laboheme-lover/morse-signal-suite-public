"""Replay the already evaluated 144 synthetic inputs; not a new holdout."""
from pathlib import Path
import sys
import soundfile as sf
ROOT=Path(__file__).resolve().parent;P=ROOT.parent;sys.path[:0]=[str(ROOT),str(P)]
from recording_experiment import read,save
from low_memory_recording_experiment import infer_recording
from intake import digest
import evaluate_new as runner

def main():
    out=ROOT/'real_low_memory_v1/synthetic_replay';out.mkdir(exist_ok=False)
    inputs=sorted((ROOT/'guard_experiment_v1/validation').glob('*/input.wav'));assert len(inputs)==144
    plan=dict(scope='REPLAY_OF_KNOWN_SYNTHETIC_INPUTS_NOT_NEW_HOLDOUT',inputs={str(p):digest(p) for p in inputs},
        script_sha256=digest(__file__),frontend_sha256=digest(ROOT/'low_memory_frontend.py'))
    save(out/'plan.json',plan);runner.verify_frozen();models,cfg,labels=runner.load_models();rows=[]
    for count,path in enumerate(inputs,1):
        audio,sr=sf.read(path,dtype='float32');assert sr==16000
        outputs,_,_=infer_recording(audio,models,cfg,labels,{'mode':'full'})
        old=read(path.parent/'detail.json')['outputs']
        for model in models:
            for method in ['baseline','combined_mode']:
                key=method+'_'+model;a=old[key];b=outputs[key]
                rows.append(dict(id=path.parent.name,model=model,method=method,text_equal=a['text']==b['text'],
                    patterns_equal=[r['pattern'] for r in a['segments']]==[r['pattern'] for r in b['segments']],error_equal=a['error']==b['error']))
        if count%36==0:print(f'synthetic replay {count}/144',flush=True)
    for path,h in plan['inputs'].items():assert digest(path)==h
    assert digest(ROOT/'low_memory_frontend.py')==plan['frontend_sha256'];runner.verify_frozen()
    save(out/'results.json',rows);save(out/'verification.json',dict(completed=True,cases=144,rows=len(rows),
        text_changes=sum(not r['text_equal'] for r in rows),pattern_changes=sum(not r['patterns_equal'] for r in rows),error_changes=sum(not r['error_equal'] for r in rows)))
    print(read(out/'verification.json'),flush=True)

if __name__=='__main__':main()
