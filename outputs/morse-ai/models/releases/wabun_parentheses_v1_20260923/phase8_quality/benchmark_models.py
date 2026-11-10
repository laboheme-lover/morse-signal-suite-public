"""Sequential Windows CPU process benchmarks for the four frozen Wabun models."""
from pathlib import Path
import argparse,ctypes,gc,hashlib,json,os,platform,statistics,subprocess,sys,time
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent

def memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('peak','working','qpp','qp','qnp','qn','page','peakpage')]
    c=Counters();c.cb=ctypes.sizeof(c);kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=ctypes.c_void_p
    api=ctypes.WinDLL('psapi');api.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
    if not api.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):raise ctypes.WinError()
    return dict(working_mib=c.working/1024**2,peak_mib=c.peak/1024**2)

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def worker(name,manifest):
    started=time.perf_counter();base=memory();sys.path.insert(0,str(PROJECT));sys.path.insert(0,str(ROOT))
    import evaluate_new as runner
    import torch
    from morse_segmentation import segment_morse
    from morse_table import REVERSE_TABLE
    from evaluate_recording import edit_alignment
    import_seconds=time.perf_counter()-started
    checkpoint=PROJECT/f'phase6_wabun65/runs/{name.lower()}_wabun65_20260922/best.pt';begin=time.perf_counter()
    ck=torch.load(checkpoint,map_location='cpu',weights_only=True);cfg=ck['config'];labels=sorted(ck['labels'],key=ck['labels'].get)
    runner.setup(cfg);assert torch.get_num_threads()==4
    model=runner.MODELS[name](cfg).eval();model.load_state_dict(ck['state_dict']);params=sum(p.numel() for p in model.parameters())
    del ck;gc.collect();load_seconds=time.perf_counter()-begin;ready_seconds=time.perf_counter()-started;ready_memory=memory()
    items=json.loads(Path(manifest).read_text(encoding='utf-8'));results=[]
    # First call and warmed calls are separate; order rotates in parent manifest.
    for item in items['inputs']:
        assert sha(item['path'])==item['sha256'];timings=[];texts=[];stage=[]
        for repeat in range(6):
            start=time.perf_counter();audio=runner.load_audio(item['path']);loaded=time.perf_counter()
            rows,detector=segment_morse(audio)
            for i,r in enumerate(rows):r.update(index=i,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
            segmented=time.perf_counter();text,_,warnings=runner.infer(rows,audio,model,cfg,labels);end=time.perf_counter()
            timings.append(end-start);texts.append(text);stage.append(dict(load_seconds=loaded-start,segmentation_seconds=segmented-loaded,features_model_decode_seconds=end-segmented))
        assert len(set(texts))==1,'Non-deterministic predictions'
        metric,_=edit_alignment(item['reference'],texts[0])
        results.append(dict(id=item['id'],audio_seconds=item['duration_seconds'],first_call_seconds=timings[0],
            warmed_seconds=timings[1:],warmed_median_seconds=statistics.median(timings[1:]),stages=stage,score=metric,
            real_time_factor=statistics.median(timings[1:])/item['duration_seconds']))
    print(json.dumps(dict(model=name,import_seconds=import_seconds,model_load_seconds=load_seconds,ready_seconds=ready_seconds,
        baseline_memory=base,ready_memory=ready_memory,final_memory=memory(),parameters=params,checkpoint_mib=checkpoint.stat().st_size/1024**2,
        checkpoint_sha256=sha(checkpoint),threads=torch.get_num_threads(),results=results)),flush=True)

def main():
    sys.path.insert(0,str(PROJECT));sys.path.insert(0,str(ROOT))
    import evaluate_new as runner
    from generate_morse_audio import generate_morse_audio
    import numpy as np
    import soundfile as sf
    out=ROOT/'model_operations';out.mkdir(exist_ok=False);runner.verify_frozen()
    unit=np.concatenate([generate_morse_audio(c,.1,700,.7,padding=.15) for c in 'イロハ']);items=[]
    for ident,copies in [('short',1),('medium',20),('long',80)]:
        path=out/(ident+'.wav');audio=np.tile(unit,copies);sf.write(path,audio,16000,subtype='FLOAT')
        items.append(dict(id=ident,path=str(path.resolve()),sha256=sha(path),reference='イロハ'*copies,duration_seconds=len(audio)/16000))
    plan=dict(scope='Same-PC CPU diagnostic; not model selection',python=sys.version,platform=platform.platform(),cpu=os.environ.get('PROCESSOR_IDENTIFIER'),
        logical_processors=os.cpu_count(),torch_threads=4,process_repetitions=3,warmed_repetitions=5,inputs=items,script_sha256=sha(__file__),
        timing_scope='Per-request load_audio + segmentation + envelope/features + model + mode processing. No GUI/render/download. Ready time measured in new process; OS disk caches not purged.',
        memory_scope='Windows working set and process-lifetime peak, including Python/Torch/imported modules, buffers and model, excluding parent process/browser.')
    (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8');runs=[]
    for repeat in range(3):
        # Rotate both model and input order to reduce systematic order effects.
        models=['M1','M2','M3','M4'];models=models[repeat:]+models[:repeat]
        ordered=items[repeat:]+items[:repeat];manifest=out/f'inputs_{repeat}.json';manifest.write_text(json.dumps({'inputs':ordered}),encoding='utf-8')
        for name in models:
            start=time.perf_counter()
            p=subprocess.run([sys.executable,'-B','-X','utf8',str(Path(__file__).resolve()),'--worker',name,'--manifest',str(manifest)],capture_output=True,text=True,encoding='utf-8',timeout=240)
            if p.returncode:raise RuntimeError(p.stderr)
            row=json.loads(p.stdout);row.update(repetition=repeat,subprocess_wall_seconds=time.perf_counter()-start);runs.append(row)
            (out/'runs.json').write_text(json.dumps(runs,indent=2),encoding='utf-8');print(f'{name} process {repeat+1}/3 complete',flush=True)
    runner.verify_frozen();assert sha(__file__)==plan['script_sha256']
    for item in items:assert sha(item['path'])==item['sha256']
    summary=[]
    for name in ('M1','M2','M3','M4'):
        trials=[r for r in runs if r['model']==name];conditions=[]
        for item in items:
            data=[next(c for c in r['results'] if c['id']==item['id']) for r in trials];values=[v for c in data for v in c['warmed_seconds']]
            assert all(c['score']['edit_distance']==0 for c in data),'Clean baseline did not decode correctly'
            conditions.append(dict(id=item['id'],audio_seconds=item['duration_seconds'],median_seconds=statistics.median(values),min_seconds=min(values),max_seconds=max(values),
                real_time_factor=statistics.median(values)/item['duration_seconds'],observations=len(values)))
        summary.append(dict(model=name,parameters=trials[0]['parameters'],checkpoint_mib=trials[0]['checkpoint_mib'],
            ready_seconds_median=statistics.median(r['ready_seconds'] for r in trials),model_load_seconds_median=statistics.median(r['model_load_seconds'] for r in trials),
            ready_working_mib_median=statistics.median(r['ready_memory']['working_mib'] for r in trials),peak_mib_max=max(r['final_memory']['peak_mib'] for r in trials),conditions=conditions))
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    lines=['# M1～M4 運用負荷比較','', '同一Windows PC・CPU・PyTorch 4スレッド。モデルごとに新規プロセスを3回起動し、各入力を初回1回＋継続5回処理。実行は直列、順序を入れ替えた。',
        '入力は同じ合成「イロハ」の反復で、短・中・長の3条件。UI描画時間は含まない。起動時間はPythonコード開始後の依存読込・モデル準備。OSのファイルキャッシュは消去しておらず完全なコールド起動ではない。',
        'メモリはPython・Torch・バッファ等を含むプロセス値。最大値はプロセス全期間のピークで、モデル重み単体の容量ではない。','',
        '|モデル|準備時間中央値 秒|モデル読込 秒|準備後メモリ MiB|最大メモリ MiB|重み MiB|','|---|---:|---:|---:|---:|---:|']
    for r in summary:lines.append(f"|{r['model']}|{r['ready_seconds_median']:.3f}|{r['model_load_seconds_median']:.3f}|{r['ready_working_mib_median']:.1f}|{r['peak_mib_max']:.1f}|{r['checkpoint_mib']:.2f}|")
    lines+=['','|入力|音声 秒|M1処理 秒|M2処理 秒|M3処理 秒|M4処理 秒|','|---|---:|---:|---:|---:|---:|']
    for item in items:
        values=[next(c for c in r['conditions'] if c['id']==item['id']) for r in summary]
        lines.append('|'+item['id']+f"|{item['duration_seconds']:.2f}|"+'|'.join(f"{v['median_seconds']:.3f}" for v in values)+'|')
    lines+=['','処理秒は15観測の中央値。音声読込・区間検出・特徴生成・推論・モード処理を含む。初回値、範囲、実時間比、CPU等はruns.json／summary.json／plan.jsonに保存。',
        '全モデル・全反復で本文一致を確認。速度・メモリだけでは採用を決定しない。実録音の長さ・文字数・雑音で所要時間は変わる。別PC性能の保証ではない。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (out/'verification.json').write_text(json.dumps(dict(completed=True,process_runs=len(runs),request_runs=12*3*6,models_and_sources_unchanged=True)),encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker');p.add_argument('--manifest');a=p.parse_args()
    worker(a.worker,a.manifest) if a.worker else main()
