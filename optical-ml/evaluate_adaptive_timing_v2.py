"""Development ablation on previously evaluated No.41-50; no weight training."""
import csv,html,json,shutil
from pathlib import Path
import numpy as np,torch
from extract import ROOT,sha
from dataset import augment,features
from predict import classify_features
from adaptive_timing_v2 import classify_adaptive
from evaluate_telegrams import score

def main():
    old=ROOT/'outputs/optical_ml_no41_50_augmented_20261013'
    base=ROOT/'outputs/optical_ml_no41_50_evaluation_20261013'
    dest=ROOT/'outputs/optical_adaptive_timing_development_v2_20261013'
    dest.mkdir(exist_ok=False);(dest/'implementation').mkdir();(dest/'predictions').mkdir()
    frozen=json.loads((old/'evaluation_plan.json').read_text(encoding='utf-8'))['frozen_files']
    for f in frozen:assert sha(Path(f['path']))==f['sha256']
    for name in ('adaptive_timing_v2.py','evaluate_adaptive_timing_v2.py','test_adaptive_timing_v2.py'):
        shutil.copy2(ROOT/'optical-ml'/name,dest/'implementation'/name)
    plan=dict(scope='Development experiment on the same 120 cases previously evaluated. Not independent validation.',methods=['fixed_300ms','auto_segmentation','auto_segmentation_and_input'],model_sha256=sha(old/'frozen/cnn.pt'),changes='Estimate dot duration from pulse/gap ratios, then optionally convert time to the 300 ms reference clock before the unchanged classifier.',no_training=True,no_reference_used_in_inference=True,rule='Reject insufficient, ambiguous or irregular timing; no silent fallback.',implementation_hashes={p.name:sha(p) for p in (dest/'implementation').glob('*.py')})
    plan['revision']='v2: Three-frame majority filtering only for period estimation, added after v1 rejected artificial rain/mixed cases. Same development data reused; all v1 results retained.'
    (dest/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    ckpt=torch.load(old/'frozen/cnn.pt',map_location='cpu',weights_only=False)
    previous=json.loads((old/'results.json').read_text(encoding='utf-8'))
    recipes=json.loads((old/'recipes.json').read_text(encoding='utf-8'))
    rows=[]
    for number in range(41,51):
        print(f'No.{number}: development comparison',flush=True)
        raw=np.load(base/'features'/f'no{number}.npz')
        crop=np.load(old/'source_crops'/f'no{number}.npz')
        cases=[dict(condition='original',parameters=None)]+[r for r in recipes if r['no']==number]
        for case in cases:
            condition=case['condition'];expected=next(r for r in previous['records'] if r['no']==number and r['condition']==condition)
            if condition=='original':t,f=raw['times'],raw['features'];speed=1.
            else:
                a,params=augment(crop['frames'],crop['times'],condition,case['parameters']['seed'],stress=False)
                assert params==case['parameters']
                f=features(a);t=np.arange(len(a))/30;speed=params['speed'];del a
            for method in plan['methods']:
                result={};error=''
                try:
                    if method=='fixed_300ms':result=classify_features(t,f,ckpt,unit=.3,isolated=False)
                    else:result=classify_adaptive(t,f,ckpt,normalize_input=method=='auto_segmentation_and_input')
                except ValueError as exc:error=str(exc)
                metrics=score(expected['reference'],result.get('text',''))
                if method=='fixed_300ms':assert metrics['hypothesis']==expected['hypothesis'],(number,condition,'baseline mismatch')
                row=dict(no=number,condition=condition,method=method,**metrics,failure=bool(error),error=error,timing=result.get('timing'),nominal_unit_diagnostic_only=.3/speed)
                rows.append(row)
                (dest/'predictions'/f'no{number}_{condition}_{method}.json').write_text(json.dumps(dict(result=result,metrics=row),ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{number} {condition}: errors '+str([r['errors'] for r in rows[-3:]]),flush=True)
    totals=[]
    for condition in ['ALL']+[r['condition'] for r in previous['totals']]:
        for method in plan['methods']:
            subset=[r for r in rows if r['method']==method and (condition=='ALL' or r['condition']==condition)]
            total={k:sum(r[k] for r in subset) for k in ('N','S','D','I','errors')}
            total.update(condition=condition,method=method,CER=total['errors']/total['N'],exact=sum(r['exact'] for r in subset),failures=sum(r['failure'] for r in subset),cases=len(subset))
            totals.append(total)
    (dest/'results.json').write_text(json.dumps(dict(totals=totals,records=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    with (dest/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(totals[0]));writer.writeheader();writer.writerows(totals)
    names=dict(original='元動画',clean='軽微な変化',fast='高速',slow='低速',dim='暗くする',bright='明るくする',rain='人工的な雨',fog='人工的な霧',static_light='別光源',sensor_noise='センサーノイズ',timing_jitter='時間の揺らぎ',mixed='複合加工',ALL='全条件（参考合算）')
    trs=''
    for c in ['original','fast','slow','clean','dim','bright','rain','fog','static_light','sensor_noise','timing_jitter','mixed','ALL']:
        ts=[next(r for r in totals if r['condition']==c and r['method']==m) for m in plan['methods']]
        trs+=f'<tr><td>{names[c]}</td>'+''.join(f'<td>{r["CER"]:.2%}</td>' for r in ts)+f'<td>{ts[-1]["exact"]}/{ts[-1]["cases"]}</td><td>{ts[-1]["failures"]}/{ts[-1]["cases"]}</td></tr>'
    page=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>点滅周期の自動推定：開発比較</title><style>body{{font-family:Meiryo,sans-serif;color:#173047;margin:40px;max-width:1100px}}td,th{{border:1px solid #ccc;padding:10px}}table{{border-collapse:collapse;width:100%}}p{{line-height:1.8}}.note{{background:#fff2db;padding:16px}}</style><h1>点滅周期の自動推定と入力補正</h1><div class="note">以前のNo.41～50・120ケースを使った開発比較です。独立した最終評価ではありません。モデルの重みは固定し、正解文字列や加工倍率を周期推定に使っていません。</div><p>現行：300ms固定。案A：点灯を1・3単位、消灯を1・3・7単位として短点時間を推定し、文字区切りのしきい値だけ変更。案B：案Aに加え、時間軸を300ms相当に換算して、切り出し余白・補間間隔・長さ特徴もそろえます。</p><table><tr><th>条件</th><th>現行CER</th><th>案A CER</th><th>案B CER</th><th>案B 全文一致</th><th>案B 保留・失敗</th></tr>{trs}</table><p>CER＝正解に合わせるための最少修正数÷正解文字数。保留は空出力として全削除に計上。全条件合算は同じ10録画を繰り返した集計で、独立120録画ではありません。現行結果120件の完全再現も確認しています。</p><h2>制約</h2><p>動画内の速度がほぼ一定であることが前提です。点滅が少ない・周期が曖昧・時刻欠落・明暗差不足なら保留します。実際の雨・霧、手持ち撮影、別端末、新しい速度や電文での確認は未実施です。現行アプリへ自動反映していません。</p></html>'''
    page=page.replace('<h1>点滅周期の自動推定と入力補正</h1>','<h1>点滅周期の自動推定と入力補正：試作v2</h1><p>試作v1では雨・複合条件で周期推定が保留になったため、推定時のみ前後3フレームの多数決を追加しました。分類器へ入る明るさデータは変更していません。同じ開発データで見直した結果です。</p>')
    (dest/'比較結果.html').write_text(page,encoding='utf-8')
    for f in frozen:assert sha(Path(f['path']))==f['sha256']
    print(json.dumps([r for r in totals if r['condition'] in ('ALL','fast','slow','original')],ensure_ascii=False),flush=True)

if __name__=='__main__':main()
