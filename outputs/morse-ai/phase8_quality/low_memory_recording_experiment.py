"""Low-memory variant of the frozen recording runner; original retained."""
from pathlib import Path
import argparse, copy, csv, gc, json, sys, time
ROOT=Path(__file__).resolve().parent; P=ROOT.parent
sys.path[:0]=[str(ROOT),str(P)]
import evaluate_new as runner
from adaptive_pipeline import METHODS, infer_prepared
from low_memory_frontend import track_carrier
from timing_frontend import segment_timing
from morse_segmentation import segment_morse
from morse_table import REVERSE_TABLE
from experimental_frontend import repair_mode
from policy import normalize_reference
from intake import digest
from benchmark_models import memory
from evaluate_recording import edit_alignment
from evaluation_compare import SCHEMA, distance

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(p)

def prepare(out):
    if out.exists():raise FileExistsError(out)
    runner.verify_frozen();entries=[]
    for folder in sorted((ROOT/'results').glob('[0-9][0-9][0-9]')):
        ident=folder.name;n=int(ident);old=P/'evaluation/real_collection_baseline'/ident
        meta=read(old/'recording_metrics.json');audio=Path(meta['audio_path'])
        assert digest(audio)==meta['audio_sha256']
        src=P/'phase7_real'/('additional_four' if n in (57,62,64,67) else 'results')/ident/'M1_segments.csv'
        with src.open(encoding='utf-8-sig') as f: body=list(csv.DictReader(f))
        with (old/'segments.csv').open(encoding='utf-8-sig') as f: full=list(csv.DictReader(f))
        def sample(r,edge):return int(r[edge+'_sample']) if edge+'_sample' in r else round(float(r[edge+'_seconds'])*16000)
        start=min(sample(r,'start') for r in body);end=max(sample(r,'end') for r in body)
        before=max([int(r['end_sample']) for r in full if int(r['end_sample'])<=start] or [0])
        after=min([int(r['start_sample']) for r in full if int(r['start_sample'])>=end] or [round(meta['duration_seconds']*16000)])
        ref=old/'reference_original.txt';text=normalize_reference(ref.read_text(encoding='utf-8-sig'))
        assert text==(folder/'reference.txt').read_text(encoding='utf-8')
        entries.append(dict(id=ident,audio=str(audio),audio_sha256=digest(audio),reference_path=str(ref),reference_sha256=digest(ref),reference=text,
            duration_seconds=meta['duration_seconds'],body=dict(mode='window',start_seconds=(before+start)/32000,end_seconds=(end+after)/32000),
            historical_body_source=str(src),historical_body_sha256=digest(src)))
    assert len(entries)==44
    scripts=[Path(__file__),ROOT/'low_memory_frontend.py',ROOT/'adaptive_pipeline.py',ROOT/'timing_frontend.py',ROOT/'experimental_frontend.py',ROOT/'policy.py']
    save(out/'manifest.json',dict(scope='KNOWN_REAL_RECORDING_DEVELOPMENT_DIAGNOSTIC',methods=METHODS,models=['M1','M2','M3','M4'],
        body_policy='Fixed before predictions: midpoint outside first/last historical body segment; same window for every method. No reference-driven crop.',
        failure_policy='Keep failed recording in denominator; empty hypothesis; never drop failed cases.',
        scripts={str(p.relative_to(P)):digest(p) for p in scripts},recordings=entries))
    print('Prepared 44 known recordings',flush=True)

def infer_recording(audio,models,cfg,labels,window):
    prepared={};output={};detectors={};timings={}
    for method in METHODS:
        source='tracking' if method in ('tracking','combined','combined_mode') else ('baseline' if method=='baseline' else 'timing')
        if source not in prepared:
            t=time.perf_counter()
            try:
                wave=audio;track={}
                if source=='tracking':wave,track=track_carrier(audio)
                rows,meta=(segment_morse(wave) if source=='baseline' else segment_timing(wave))
                for i,r in enumerate(rows):r.update(index=i,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
                meta.update(track)
                try:meta['protocol_body_segments']=len(runner.select_body(rows,{'mode':'protocol'}));meta['protocol_error']=''
                except ValueError as exc:meta['protocol_error']=str(exc)
                body=runner.select_body(rows,window)
                prepared[source]=(body,wave,meta,'')
            except (ValueError,RuntimeError) as exc:prepared[source]=([],audio,{},str(exc))
            timings[source+'_preparation_seconds']=time.perf_counter()-t
        body,wave,meta,error=prepared[source];detectors[method]=meta
        for name,model in models.items():
            t=time.perf_counter();data=dict(text='',segments=[],warnings=[],error=error)
            if not error:
                try:
                    if method=='combined_mode':
                        previous=output['combined_'+name]
                        if previous['error']:raise ValueError(previous['error'])
                        text,rows,warnings=repair_mode(previous['segments'])
                    else:text,rows,warnings=infer_prepared(body,wave,model,cfg,labels,meta['dot_seconds'] if method in ('tempo','combined') else None)
                    if meta.get('timing_ambiguous'):warnings.append('短点推定に複数候補があります。要確認。')
                    data.update(text=text,segments=rows,warnings=warnings)
                except (ValueError,RuntimeError) as exc:data['error']=str(exc)
            data['inference_seconds']=time.perf_counter()-t;output[method+'_'+name]=data
    return output,detectors,timings

def aggregate(out,manifest):
    rows=[];performance=[]
    for entry in manifest['recordings']:
        path=out/entry['id']/'result.json'
        if not path.exists():continue
        data=read(path);assert data['input_sha256']==entry['audio_sha256']
        rows+=data['metrics'];performance.append(dict(id=entry['id'],**data['performance']))
    save(out/'results.json',rows);save(out/'performance.json',performance)
    summaries=[]
    for method in METHODS:
        for model in manifest['models']:
            rs=[r for r in rows if r['method']==method and r['model']==model]
            n=sum(r['reference_units'] for r in rs);d=sum(r['edits'] for r in rs)
            summaries.append(dict(method=method,model=model,cases=len(rs),units=n,edits=d,cer=d/n if n else None,failures=sum(r['status']=='FAILED' for r in rs)))
            save(out/'comparisons'/f'real_{method}_{model}_comparison.json',dict(schema=SCHEMA,name=f'known_real_{method}_{model}',scope=manifest['scope'],scoring_policy='phase8-content-v2-fixed-historical-window',rows=rs))
    save(out/'summary.json',summaries)
    return rows

def run(out,limit=None):
    manifest=read(out/'manifest.json');runner.verify_frozen()
    for path,h in manifest['scripts'].items():assert digest(P/path)==h,path
    model_start=time.perf_counter();models,cfg,labels=runner.load_models();load_seconds=time.perf_counter()-model_start
    count=0
    for entry in manifest['recordings']:
        dest=out/entry['id']/'result.json'
        if dest.exists():continue
        if limit is not None and count>=limit:break
        count+=1;start=time.perf_counter();before=memory();audio=None
        try:
            assert digest(entry['audio'])==entry['audio_sha256']
            assert digest(entry['reference_path'])==entry['reference_sha256']
            audio=runner.load_audio(entry['audio']);loaded=time.perf_counter()
            output,detectors,timings=infer_recording(audio,models,cfg,labels,entry['body'])
        except (ValueError,OSError,RuntimeError) as exc:
            loaded=time.perf_counter();detectors={};timings={}
            output={m+'_'+n:dict(text='',segments=[],warnings=[],error=str(exc)) for m in METHODS for n in models}
        elapsed=time.perf_counter()-start;metrics=[]
        for key,data in output.items():
            method,name=key.rsplit('_',1);metric,_=edit_alignment(entry['reference'],data['text'])
            metric.update(id=entry['id'],model=name,method=method,input_sha256=entry['audio_sha256'],reference=entry['reference'],hypothesis=data['text'],
                edits=metric['edit_distance'],status='FAILED' if data['error'] else 'OK',error=data['error'],dataset='known_real44',
                ui_alert=bool(data['warnings']) or any(r.get('review_reason') for r in data['segments']))
            metrics.append(metric)
        perf=dict(audio_seconds=entry['duration_seconds'],load_seconds=loaded-start,evaluation_seconds=elapsed,
            all_methods_real_time_factor=elapsed/entry['duration_seconds'],memory_before=before,memory_after=memory(),preparation=timings,
            model_load_seconds_this_process=load_seconds,memory_scope='Process-lifetime peak working set; includes all four models and imports; not per-file incremental peak.')
        save(dest,dict(input_sha256=entry['audio_sha256'],outputs=output,detectors=detectors,metrics=metrics,performance=perf))
        print(entry['id']+f' {elapsed:.1f}s '+', '.join(f"{r['method']}/{r['model']}={r['edits']}" for r in metrics if r['model']=='M1'),flush=True)
        del audio,output,detectors;gc.collect()
        save(out/'progress.json',dict(completed=len(list(out.glob('*/result.json'))),total=len(manifest['recordings'])))
    rows=aggregate(out,manifest)
    if len(rows)==len(manifest['recordings'])*24:
        for row in rows:assert distance(row['reference'],row['hypothesis'])==row['edits']
        for entry in manifest['recordings']:
            for path,h in [(entry['audio'],entry['audio_sha256']),(entry['reference_path'],entry['reference_sha256']),(entry['historical_body_source'],entry['historical_body_sha256'])]:assert digest(path)==h
        for path,h in manifest['scripts'].items():assert digest(P/path)==h
        runner.verify_frozen();save(out/'verification.json',dict(completed=True,rows=len(rows),inputs_and_models_unchanged=True,independent_edit_distance_verified=True))
    print(f'Saved {len(rows)} evaluation rows',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','run']);ap.add_argument('--output',type=Path,default=ROOT/'real_low_memory_v1');ap.add_argument('--limit',type=int)
    a=ap.parse_args();prepare(a.output) if a.action=='prepare' else run(a.output,a.limit)
