"""Fixed baseline across supplied recordings; ambiguous references are not silently rewritten."""
import contextlib,csv,hashlib,json,re,unicodedata
from pathlib import Path
import torch
from threadpoolctl import threadpool_limits
from evaluate_recording import evaluate_recording,canonical_reference,edit_alignment
from analyze_recording_body import select_body


def prepare_reference(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'^\s*HR\s+HR\s*','',text)
    text=re.sub(r'<(?:ホレ|ラタ)>','',text)
    text=text.translate(str.maketrans('','','★?「」'))
    return canonical_reference(text)


def run():
    source=Path('C:/Users/DEVELOPER/OneDrive/デスクトップ/和文モールス信号サンプル')
    out=Path('evaluation/real_collection_baseline');out.mkdir(exist_ok=False)
    checkpoint=Path('models/saved_wabun_cnn_20260914/best_model.pt')
    results=[]
    for ref in sorted((source/'TEXT').glob('*.txt'),key=lambda p:int(p.stem)):
        number=int(ref.stem);folder=out/f'{number:03d}'
        r=dict(number=number,previously_exposed=number in (85,86))
        audio=list((source/'Sound').glob(f'Taman_{number} *.mp3'))
        try:
            if len(audio)!=1:raise ValueError('Nonunique audio match')
            with (out/f'{number:03d}.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log):
                metric=evaluate_recording(audio[0],None,checkpoint,folder)
            r.update(duration_seconds=metric['duration_seconds'],detector=metric['detector'],audio_sha256=metric['audio_sha256'])
            raw=ref.read_text(encoding='utf-8-sig')
            (folder/'reference_original.txt').write_text(raw,encoding='utf-8')
            normalized=prepare_reference(raw)
            (folder/'reference_body.txt').write_text(normalized,encoding='utf-8')
            with (folder/'segments.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            body=select_body(rows)
            cnn=''.join(row['prediction'] for row in body);rule=''.join(row['rule_prediction'] for row in body)
            cm,alignment=edit_alignment(normalized,cnn);rm,_=edit_alignment(normalized,rule)
            r.update(status='scored',cnn=cm,rule=rm,body_segments=len(body),
                     positional_accuracy=sum(a==b for a,b in zip(normalized,cnn))/len(normalized) if len(normalized)==len(cnn) else None)
            for name,value in [('cnn_body.txt',cnn),('rule_body.txt',rule)]:
                (folder/name).write_text(value,encoding='utf-8')
            with (folder/'body_alignment.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(alignment[0]));w.writeheader();w.writerows(alignment)
        except Exception as exc:r.update(status='needs_review',reason=str(exc))
        results.append(r)
        (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f"{number}: {r['status']} "+(f"CNN CER={r['cnn']['cer']:.2%}; rule CER={r['rule']['cer']:.2%}" if r['status']=='scored' else r['reason']),flush=True)
    summary=dict(checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),model_updated=False,
                 preprocessing='original baseline, no frequency translation',total_recordings=len(results),groups={})
    for group,subset in [('all_scored',[r for r in results if r['status']=='scored']),
                         ('excluding_prior_exposure',[r for r in results if r['status']=='scored' and not r['previously_exposed']])]:
        n=sum(r['cnn']['reference_units'] for r in subset)
        summary['groups'][group]=dict(recordings=len(subset),reference_units=n,
            cnn_cer=sum(r['cnn']['edit_distance'] for r in subset)/n if n else None,
            rule_cer=sum(r['rule']['edit_distance'] for r in subset)/n if n else None,
            cnn_substitutions=sum(r['cnn']['substitutions'] for r in subset),
            cnn_insertions=sum(r['cnn']['insertions'] for r in subset),cnn_deletions=sum(r['cnn']['deletions'] for r in subset))
    summary['needs_review']=[r for r in results if r['status']!='scored']
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    torch.set_num_threads(1)
    with threadpool_limits(limits=1):run()
