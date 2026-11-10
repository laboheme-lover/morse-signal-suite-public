"""Sequential fresh-process comparison of the longest known recording."""
from pathlib import Path
import argparse,json,subprocess,sys,time,platform,os,importlib.metadata
ROOT=Path(__file__).resolve().parent;P=ROOT.parent;sys.path[:0]=[str(ROOT),str(P)]
from intake import digest
from recording_experiment import read,save
from benchmark_models import memory
import evaluate_new as runner

def worker(mode,out):
    runner.verify_frozen()
    entry=next(r for r in read(ROOT/'real_adaptive_v1/manifest.json')['recordings'] if r['id']=='064')
    assert digest(entry['audio'])==entry['audio_sha256']
    if mode=='original':from recording_experiment import infer_recording
    else:from low_memory_recording_experiment import infer_recording
    t=time.perf_counter();models,cfg,labels=runner.load_models();model_seconds=time.perf_counter()-t
    t=time.perf_counter();audio=runner.load_audio(entry['audio']);outputs,detectors,timings=infer_recording(audio,models,cfg,labels,entry['body'])
    seconds=time.perf_counter()-t
    save(out,dict(mode=mode,input_sha256=entry['audio_sha256'],audio_seconds=entry['duration_seconds'],model_load_seconds=model_seconds,
        evaluation_seconds=seconds,memory=memory(),outputs={k:dict(text=d['text'],error=d['error'],patterns=[r['pattern'] for r in d['segments']]) for k,d in outputs.items()}))
    runner.verify_frozen()

def main():
    out=ROOT/'real_low_memory_v1/fresh_process_benchmark';out.mkdir(exist_ok=False)
    paths=[Path(__file__),ROOT/'low_memory_frontend.py',ROOT/'low_memory_recording_experiment.py',ROOT/'recording_experiment.py']
    plan=dict(recording='064',modes=['original','low_memory'],repetitions=1,order='original then low_memory',
        platform=platform.platform(),python=sys.version,cpu=os.environ.get('PROCESSOR_IDENTIFIER'),
        versions={k:importlib.metadata.version(k) for k in ['numpy','scipy','torch','librosa']},
        memory_scope='Fresh-process peak working set includes imports, four models and entire audio processing; excludes parent/browser',
        time_scope='load_audio plus six methods and four models, excluding model load, JSON serialization and GUI. One run, OS caches not purged.',
        scripts={str(p.relative_to(P)):digest(p) for p in paths})
    save(out/'plan.json',plan)
    for mode in plan['modes']:
        completed=subprocess.run([sys.executable,'-B','-X','utf8',str(Path(__file__)),'--worker',mode,'--output',str(out/(mode+'.json'))],cwd=P,capture_output=True,text=True,encoding='utf-8',creationflags=0x08000000)
        (out/(mode+'.log')).write_text(completed.stdout+completed.stderr,encoding='utf-8')
        completed.check_returncode();r=read(out/(mode+'.json'));print(mode,r['memory'],r['evaluation_seconds'],flush=True)
    a=read(out/'original.json');b=read(out/'low_memory.json')
    for path,h in plan['scripts'].items():assert digest(P/path)==h
    save(out/'comparison.json',dict(outputs_equal=a['outputs']==b['outputs'],original_peak_mib=a['memory']['peak_mib'],new_peak_mib=b['memory']['peak_mib'],
        reduction_fraction=1-b['memory']['peak_mib']/a['memory']['peak_mib'],original_seconds=a['evaluation_seconds'],new_seconds=b['evaluation_seconds']))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--worker',choices=['original','low_memory']);ap.add_argument('--output',type=Path);a=ap.parse_args()
    worker(a.worker,a.output) if a.worker else main()
