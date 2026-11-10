"""Frozen-model continuous optical evaluation; no training or reference correction."""
import csv, html, json, shutil, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch
from extract import ROOT, OUT, sha
from predict import extract_features, classify_features

def score(reference, hypothesis):
    r=''.join(reference.split()); h=''.join(hypothesis.split())
    d=np.zeros((len(r)+1,len(h)+1),dtype=int)
    d[:,0]=np.arange(len(r)+1); d[0,:]=np.arange(len(h)+1)
    for i in range(1,len(r)+1):
        for j in range(1,len(h)+1):
            d[i,j]=min(d[i-1,j-1]+(r[i-1]!=h[j-1]),d[i-1,j]+1,d[i,j-1]+1)
    i,j=len(r),len(h); ops=[]; counts={'S':0,'D':0,'I':0}
    while i or j:
        if i and j and d[i,j]==d[i-1,j-1]+(r[i-1]!=h[j-1]):
            op='=' if r[i-1]==h[j-1] else 'S'; ops.append([op,r[i-1],h[j-1]])
            if op!='=': counts[op]+=1
            i-=1;j-=1
        elif i and d[i,j]==d[i-1,j]+1:
            ops.append(['D',r[i-1],'']);counts['D']+=1;i-=1
        else:
            ops.append(['I','',h[j-1]]);counts['I']+=1;j-=1
    return dict(N=len(r),predicted_units=len(h),**counts,errors=int(d[-1,-1]),CER=float(d[-1,-1])/len(r),exact=r==h,reference=r,hypothesis=h,alignment=ops[::-1])

def main():
    assert score('アイ','ア')['D']==1 and score('ア','アイ')['I']==1
    assert score('アイ','ウイ')['S']==1 and score('ア イ','アイ')['exact']
    source=ROOT/'optical-batch-test/splits/20261012_180252'
    dest=ROOT/'outputs/optical_ml_no41_50_evaluation_20261013'
    dest.mkdir(exist_ok=False); (dest/'frozen').mkdir(); (dest/'features').mkdir(); (dest/'predictions').mkdir()
    manifest=json.loads((source/'split_manifest.json').read_text(encoding='utf-8'))
    records=manifest['outputs']; assert len(records)==10
    files=[OUT/'models/cnn.pt',source/'split_manifest.json',Path(__file__),ROOT/'optical-batch-test/pc/splitter.py']
    files += [ROOT/'optical-ml'/name for name in ('predict.py','model.py','dataset.py','extract.py')]
    frozen=[]
    for p in files:
        target=dest/'frozen'/p.name; shutil.copy2(p,target)
        frozen.append(dict(path=str(p),sha256=sha(p),copy=str(target)))
    plan=dict(created_utc=datetime.now(timezone.utc).isoformat(),model='cnn',selection='Previously selected on augmented validation; tied accuracy with BiGRU, existing selection order chose CNN.',roi=manifest['roi'],unit_seconds=.3,isolated=False,normalization='Whitespace removal only; dakuten and punctuation retained as separate codepoints.',scope='10 transmitted first-sentence clips No.41-50 from 1635.mp4, not full original audio manuscripts.',limitations='Different source recording from training 1634.mp4; same shooting setup. Recording previously used for ROI/splitting development, and telegram boundaries previously checked with references. Not a fully untouched end-to-end blind test.',no_tuning=True,frozen_files=frozen)
    (dest/'evaluation_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    checkpoint=torch.load(dest/'frozen/cnn.pt',map_location='cpu',weights_only=False)
    rows=[]; begun=time.monotonic()
    for n,record in enumerate(records,41):
        p=source/record['file']; print(f'No.{n}: hashing and extracting',flush=True)
        identity=dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)); error=''; result={}; last=[time.monotonic()]
        def progress(fraction):
            if time.monotonic()-last[0]>20:
                print(f'No.{n}: {fraction:.0%}',flush=True);last[0]=time.monotonic()
        try:
            times,features,meta=extract_features(p,plan['roi'],progress)
            np.savez_compressed(dest/'features'/f'no{n}.npz',times=times,features=features)
            result=classify_features(times,features,checkpoint,unit=.3,isolated=False)
        except Exception as exc:
            error=f'{type(exc).__name__}: {exc}'
        metrics=score(record['labels'],result.get('text',''))
        row=dict(no=n,**metrics,failure=bool(error),error=error)
        rows.append(row)
        detail=dict(source=identity,prediction=result,metrics=row)
        (dest/'predictions'/f'no{n}.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'No.{n}: N={metrics["N"]} errors={metrics["errors"]} CER={metrics["CER"]:.2%} failure={error}',flush=True)
    for f in frozen: assert sha(Path(f['path']))==f['sha256'],f['path']
    total={k:sum(r[k] for r in rows) for k in ('N','predicted_units','S','D','I','errors')}
    total.update(CER=total['errors']/total['N'],exact=sum(r['exact'] for r in rows),failures=sum(r['failure'] for r in rows),recordings=len(rows),elapsed_seconds=time.monotonic()-begun)
    (dest/'results.json').write_text(json.dumps(dict(total=total,records=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    columns=['no','N','predicted_units','S','D','I','errors','CER','exact','failure','error','reference','hypothesis']
    with (dest/'results.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    table=''.join(f'<tr><td>{r["no"]}</td><td>{r["N"]}</td><td>{r["predicted_units"]}</td><td>{r["S"]}</td><td>{r["D"]}</td><td>{r["I"]}</td><td>{r["CER"]:.2%}</td><td>{"○" if r["exact"] else "×"}</td></tr>' for r in rows)
    details=''.join(f'<details><summary>No.{r["no"]} 正解と認識結果</summary><p>正解：{html.escape(r["reference"])}</p><p>認識：{html.escape(r["hypothesis"])}</p><p>{html.escape(r["error"])}</p></details>' for r in rows)
    page=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>光モールス連続電文評価</title><style>body{{font-family:Meiryo,sans-serif;margin:40px;max-width:1100px;color:#173047}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:10px;text-align:right}}.note{{background:#fff2db;padding:18px}}p{{line-height:1.8;overflow-wrap:anywhere}}details{{margin:16px 0}}</style><h1>光用CNN：No.41～50 連続電文評価</h1><p>固定モデル・再学習なし。短点300ms、ROI {plan['roi']}。文字区切り検出を含む評価です。</p><h2>CER {total['CER']:.2%} ／ {total['N']}文字単位・{total['errors']}修正</h2><p>置換 {total['S']}、削除 {total['D']}、挿入 {total['I']}。全文一致 {total['exact']}/10、処理失敗 {total['failures']}/10。</p><p>CERは、正解に合わせるために必要な最少の文字修正回数を正解文字数で割った値です。全電文の修正回数を合算して計算しています。単文字分類Accuracyとは異なります。</p><div class="note">対象は1635.mp4のNo.41～50の送信本文（最初の一文）です。元の44件全体や音声原稿全文の評価ではありません。学習元1634.mp4とは別録画ですが、同じ撮影環境で、ROI・分割開発で参照した録画です。電文単位の分割は以前に原稿と照合済みであり、未見の長時間動画全体に対する完全な独立評価ではありません。今回の文字認識では正解による補正を行っていません。</div><table><tr><th>No.</th><th>正解単位</th><th>出力単位</th><th>置換</th><th>削除</th><th>挿入</th><th>CER</th><th>全文一致</th></tr>{table}</table><p>空白のみ除外し、濁点・半濁点・句読点は別単位として採点。失敗時は空出力として削除に計上します。複数の最短対応がある場合、置換→削除→挿入の順に選ぶため、内訳はその対応に基づきます。</p>{details}</html>'''
    (dest/'評価結果.html').write_text(page,encoding='utf-8')
    (dest/'quality_check.txt').write_text('10電文を評価。モデル・推論コードの開始前後SHA256一致を確認。再学習・しきい値調整・正解補正なし。スコア関数の置換・削除・挿入・空白処理チェック通過。各動画の全フレーム読取と時刻順序は推論側で検査。HTMLのブラウザ視覚確認は未実施。\n',encoding='utf-8')
    print(json.dumps(total,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
