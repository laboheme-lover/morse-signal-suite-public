"""Apply unchanged single-character image augmentation to entire telegram clips."""
import csv,html,json,shutil,time
from datetime import datetime,timezone
from pathlib import Path
import cv2,numpy as np,torch
from extract import ROOT,OUT,sha
from dataset import CONDITIONS,augment,features
from predict import classify_features
from evaluate_telegrams import score

def main():
    base=ROOT/'outputs/optical_ml_no41_50_evaluation_20261013'
    dest=ROOT/'outputs/optical_ml_no41_50_augmented_20261013'
    dest.mkdir(exist_ok=False)
    for name in ('frozen','predictions','source_crops'): (dest/name).mkdir()
    source=ROOT/'optical-batch-test/splits/20261012_180252'
    manifest=json.loads((source/'split_manifest.json').read_text(encoding='utf-8'))
    plan=json.loads((base/'evaluation_plan.json').read_text(encoding='utf-8'))
    for f in plan['frozen_files']:
        assert sha(Path(f['path']))==f['sha256']
        shutil.copy2(f['copy'],dest/'frozen'/Path(f['copy']).name)
    shutil.copy2(__file__,dest/'frozen'/Path(__file__).name)
    plan.update(created_utc=datetime.now(timezone.utc).isoformat(),conditions=CONDITIONS,variants_per_recording_condition=1,seed_rule='2026101300 + telegram_number * 100 + condition_index',stress=False,augmentation='Unmodified optical-ml/dataset.py augment on entire telegram image sequence before character segmentation; same standard ranges as single-character experiment.',clean_note='clean also applies mild speed/gain changes and margins; original is reported separately.',independence='110 variants of 10 source clips, not 110 independent recordings.',output='Source crops, exact seeds and parameters, predictions; full-size derived videos are not stored.')
    (dest/'evaluation_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    checkpoint=torch.load(dest/'frozen/cnn.pt',map_location='cpu',weights_only=False)
    rows=[];recipes=[]
    for number,record in enumerate(manifest['outputs'],41):
        p=source/record['file'];raw=np.load(base/'features'/f'no{number}.npz');times=raw['times'];times=times-times[0]
        x,y,w,h=plan['roi'];cx=x+w//2;cy=y+h//2
        print(f'No.{number}: decoding augmentation source',flush=True)
        cap=cv2.VideoCapture(str(p));frames=[]
        try:
            while True:
                ok,frame=cap.read()
                if not ok:break
                frames.append(cv2.resize(cv2.cvtColor(frame[cy-64:cy+64,cx-64:cx+64],cv2.COLOR_BGR2GRAY),(64,64),interpolation=cv2.INTER_AREA))
        finally:cap.release()
        frames=np.asarray(frames);assert len(frames)==len(times)
        # Match the extraction convention used in original inference exactly.
        assert np.allclose(features(frames),raw['features'],atol=1e-4)
        crop=dest/'source_crops'/f'no{number}.npz'
        np.savez_compressed(crop,frames=frames,times=times)
        for ci,condition in enumerate(CONDITIONS):
            seed=2026101300+number*100+ci
            print(f'No.{number}: {condition}',flush=True)
            a,parameters=augment(frames,times,condition,seed,stress=False)
            f=features(a);t=np.arange(len(a))/30;result={};error=''
            try:result=classify_features(t,f,checkpoint,unit=.3,isolated=False)
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            metrics=score(record['labels'],result.get('text',''))
            row=dict(no=number,condition=condition,**metrics,failure=bool(error),error=error)
            rows.append(row);recipes.append(dict(no=number,condition=condition,source_crop=str(crop),parameters=parameters))
            (dest/'predictions'/f'no{number}_{condition}.json').write_text(json.dumps(dict(parameters=parameters,prediction=result,metrics=row),ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'No.{number}: {condition} CER={metrics["CER"]:.2%}',flush=True)
            del a,f
        del frames
    original=json.loads((base/'results.json').read_text(encoding='utf-8'))
    allrows=[dict(r,condition='original') for r in original['records']]+rows
    totals=[]
    for condition in ['original']+CONDITIONS:
        subset=[r for r in allrows if r['condition']==condition]
        total={k:sum(r[k] for r in subset) for k in ('N','predicted_units','S','D','I','errors')}
        total.update(condition=condition,CER=total['errors']/total['N'],character_score=1-total['errors']/total['N'],exact=sum(r['exact'] for r in subset),failures=sum(r['failure'] for r in subset),cases=len(subset))
        totals.append(total)
    (dest/'results.json').write_text(json.dumps(dict(totals=totals,records=allrows),ensure_ascii=False,indent=2),encoding='utf-8')
    (dest/'recipes.json').write_text(json.dumps(recipes,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,data in [('condition_summary.csv',totals),('per_recording.csv',allrows)]:
        columns=[k for k in data[0] if k!='alignment']
        with (dest/name).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(data)
    names=dict(original='元動画',clean='軽微な速度・明るさ変化',fast='高速',slow='低速',dim='暗くする',bright='明るくする',rain='人工的な雨',fog='人工的な霧',static_light='点滅しない別光源',sensor_noise='センサーノイズ',timing_jitter='時間の揺らぎ',mixed='複合加工')
    table=''.join(f'<tr><td>{names[r["condition"]]}</td><td>{r["CER"]:.2%}</td><td>{r["character_score"]:.2%}</td><td>{r["S"]}</td><td>{r["D"]}</td><td>{r["I"]}</td><td>{r["exact"]}/10</td><td>{r["failures"]}/10</td></tr>' for r in totals)
    detail=''.join(f'<tr><td>{r["no"]}</td><td>{names[r["condition"]]}</td><td>{r["CER"]:.2%}</td><td>{r["errors"]}</td></tr>' for r in allrows)
    page=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>光・連続電文の加工条件別評価</title><style>body{{font-family:Meiryo,sans-serif;margin:40px;max-width:1200px;color:#173047}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:10px}}p{{line-height:1.8}}.note{{background:#fff2db;padding:18px}}</style><h1>光用CNN：No.41～50 加工条件別評価</h1><p>単文字と同じ画像加工を、文字分割前の電文全体に適用しました。元動画10件＋11加工条件×10件＝120ケース。新たな独立録画120件ではありません。モデル・推論処理は固定し、再学習・調整・正解補正を行っていません。</p><div class="note">各加工は電文・条件ごとに固定乱数1回です。複数乱数による安定性は未評価。学習元とは別の録画ですが同じ撮影環境で、過去のROI・分割開発に使用済み。電文境界は既に原稿照合済み。雨・霧は人工加工であり、実天候の性能ではありません。</div><p>速度・時間の揺らぎを含め、受信側の短点設定は300msのままです。加工に合わせた自動速度補正は追加していません。clean条件にも0.9～1.1倍の速度・0.8～1.2倍の明るさ変化などがあるため、無加工の元動画と区別しています。</p><p>CER＝最少文字修正回数÷正解文字数。文字スコア＝1−CERであり、単文字分類Accuracyではありません。空白のみ除外し、濁点・記号も各1単位として採点。処理失敗は空出力として計上。</p><table><tr><th>加工</th><th>CER</th><th>文字スコア（1−CER）</th><th>置換</th><th>削除</th><th>挿入</th><th>全文一致</th><th>処理失敗</th></tr>{table}</table><h2>電文別明細</h2><table><tr><th>No.</th><th>条件</th><th>CER</th><th>修正数</th></tr>{detail}</table></html>'''
    (dest/'評価結果.html').write_text(page,encoding='utf-8')
    for f in plan['frozen_files']:assert sha(Path(f['path']))==f['sha256']
    assert len(rows)==110 and all(r['cases']==10 for r in totals)
    (dest/'quality_check.txt').write_text('モデル・推論コードSHA256開始前後一致。元動画10＋加工110ケース。元動画から再抽出した特徴と前回特徴の一致を確認。各条件同一正解を使用し、正解による区切り修正なし。加工後は30fps。受信短点設定300ms固定。乱数1回／電文・条件。HTMLのブラウザ視覚確認は未実施。\n',encoding='utf-8')
    print(json.dumps(totals,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
