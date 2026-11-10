"""Frozen adaptive-v2 evaluation, No.53-86; reproducible resumable case outputs."""
import csv,gc,html,json,re,shutil,time
from pathlib import Path
import cv2,numpy as np,torch
from extract import ROOT,sha
from dataset import CONDITIONS,augment,features
from adaptive_timing_v2 import classify_adaptive
from predict import splitter
from evaluate_telegrams import score

DEST=ROOT/'outputs/optical_remaining_20261013'
FOLDERS=['20261013_113611','20261013_140102','20261013_122538','20261013_160355','20261013_161122','20261013_183416']
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare():
 records=[]
 for folder in FOLDERS:
  directory=ROOT/'optical-batch-test/splits'/folder;manifest=directory/'split_manifest.json'
  m=json.loads(manifest.read_text(encoding='utf-8'));assert m['status']=='complete'
  x,y,w,h=m['roi'];roi=[x+w//2-20,y+h//2-20,40,40]
  for r in m['outputs']:
   number=int(re.search(r'no(\d+)',r['id'])[1]);p=directory/r['file'];assert p.is_file()
   records.append(dict(no=number,path=str(p),reference=r['labels'],roi=roi,manifest=str(manifest),manifest_sha256=sha(manifest),original_roi=m['roi'],original_recording=m['source']['path'],bytes=p.stat().st_size))
 records.sort(key=lambda r:r['no']);assert [r['no'] for r in records]==list(range(53,87))
 frozen=ROOT/'outputs/optical_adaptive_timing_development_v2_20261013/implementation/adaptive_timing_v2.py'
 assert sha(frozen)==sha(ROOT/'optical-ml/adaptive_timing_v2.py')
 old=json.loads((ROOT/'outputs/optical_ml_no41_50_augmented_20261013/evaluation_plan.json').read_text(encoding='utf-8'))
 for f in old['frozen_files']:
  if Path(f['path']).name in ('predict.py','dataset.py','model.py','extract.py','splitter.py','cnn.pt'):assert sha(Path(f['path']))==f['sha256']
 files=[ROOT/'optical-ml'/n for n in ('adaptive_timing_v2.py','predict.py','dataset.py','model.py','extract.py','evaluate_telegrams.py','evaluate_remaining.py')]+[ROOT/'optical-batch-test/pc/splitter.py',ROOT/'outputs/optical_ml_20261013/models/cnn.pt']
 for directory in ('frozen','crops','features','predictions'):(DEST/directory).mkdir(exist_ok=True)
 if (DEST/'plan.json').exists():
  plan=json.loads((DEST/'plan.json').read_text(encoding='utf-8'))
  for f in plan['frozen']:assert sha(Path(f['path']))==f['sha256']
  return plan
 fixed=[]
 for p in files:
  shutil.copy2(p,DEST/'frozen'/p.name);fixed.append(dict(path=str(p),sha256=sha(p)))
 plan=dict(records=records,frozen=fixed,conditions=['original']+CONDITIONS,model='cnn',inference='adaptive_timing_v2.classify_adaptive(normalize_input=True)',seed_rule='2026101300 + no*100 + condition_index',variants_per_condition=1,roi_rule='Centered 40x40 inside previously selected split ROI; no variable ROI scaling.',no_tuning=True,scope='34 telegram clips from 6 recordings; 408 derived cases, not independent recordings. Model and timing frontend fixed after No.41-50 development. Telegram boundaries previously validated with reference patterns. Not blind end-to-end evaluation.',normalization='Whitespace only removed. Dakuten and symbols remain separate codepoints. Failure/hold scored as empty output.',source_crops='64x64 grayscale of original 128x128 neighborhood; exact same as preceding evaluation. No source media overwritten.')
 dump(DEST/'plan.json',plan);return plan

def extract(record):
 number=record['no'];cp=DEST/'crops'/f'no{number}.npy';tp=DEST/'crops'/f'no{number}_times.npy';proof=DEST/'crops'/f'no{number}.json';p=Path(record['path'])
 if proof.exists():
  saved=json.loads(proof.read_text(encoding='utf-8'));assert saved['identity']==splitter.identity(p)
  return np.load(cp,mmap_mode='r'),np.load(tp)
 before=splitter.identity(p);print(f'No.{number}: source SHA256',flush=True);digest=sha(p)
 meta=splitter.info(p);x,y,w,h=record['roi'];cx=x+20;cy=y+20
 assert cx>=64 and cy>=64 and cx+64<=meta['width'] and cy+64<=meta['height']
 frames=np.lib.format.open_memmap(cp,mode='w+',dtype=np.uint8,shape=(meta['frames'],64,64));times=[];cap=cv2.VideoCapture(str(p));last=time.monotonic()
 try:
  while True:
   ok,frame=cap.read()
   if not ok:break
   if len(times)>=meta['frames']:raise ValueError('Extra decoded frames')
   frames[len(times)]=cv2.resize(cv2.cvtColor(frame[cy-64:cy+64,cx-64:cx+64],cv2.COLOR_BGR2GRAY),(64,64),interpolation=cv2.INTER_AREA)
   times.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000)
   if time.monotonic()-last>20:print(f'No.{number}: decode {len(times)/meta["frames"]:.0%}',flush=True);last=time.monotonic()
 finally:cap.release()
 assert len(times)==meta['frames'] and len(times)>=3
 if times[0]>=times[1]:times[0]=splitter.verify_initial_timestamp(p,times[:3],meta['fps'])[0][0]
 times,fixes=splitter.correct_initial_timestamp(times,meta['fps']);times=np.asarray(times)
 assert np.isfinite(times).all() and np.all(np.diff(times)>0) and before==splitter.identity(p)
 frames.flush();np.save(tp,times);dump(proof,dict(identity=before,sha256=digest,metadata=meta,roi=record['roi'],timestamp_corrections=fixes))
 return frames,times

def report(plan):
 rows=[]
 for record in plan['records']:
  for condition in plan['conditions']:
   p=DEST/'predictions'/f'no{record["no"]}_{condition}.json'
   if p.exists():rows.append(json.loads(p.read_text(encoding='utf-8'))['metrics'])
 totals=[]
 for c in plan['conditions']:
  rs=[r for r in rows if r['condition']==c]
  if not rs:continue
  t={k:sum(r[k] for r in rs) for k in ('N','S','D','I','errors')}
  t.update(condition=c,cases=len(rs),CER=t['errors']/t['N'],character_score=1-t['errors']/t['N'],exact=sum(r['exact'] for r in rs),failures=sum(r['failure'] for r in rs));totals.append(t)
 dump(DEST/'results.json',dict(complete=len(rows)==408,totals=totals,records=rows))
 for filename,data in [('condition_summary.csv',totals),('per_case.csv',rows)]:
  if not data:continue
  keys=[k for k in data[0] if k not in ('alignment','timing')]
  with (DEST/filename).open('w',encoding='utf-8-sig',newline='') as f:
   wr=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');wr.writeheader();wr.writerows(data)
 names=dict(original='通常（元動画）',fast='高速',slow='低速',clean='軽微な速度・明るさ変化',dim='暗くする',bright='明るくする',rain='人工的な雨',fog='人工的な霧',static_light='別光源',sensor_noise='センサーノイズ',timing_jitter='時間の揺らぎ',mixed='複合加工')
 order=['fast','original','slow']+[c for c in CONDITIONS if c not in ('fast','slow')]
 with (DEST/'文字スコア比較表.csv').open('w',encoding='utf-8-sig',newline='') as f:
  wr=csv.writer(f);wr.writerow(['条件']+[f'No.{n}' for n in range(53,87)]+['合計（文字数加重）'])
  for c in order:
   lookup={r['no']:r for r in rows if r['condition']==c};total=next((t for t in totals if t['condition']==c),None)
   wr.writerow([names[c]]+[f'{1-lookup[n]["CER"]:.2%}' if n in lookup else '' for n in range(53,87)]+([f'{total["character_score"]:.2%}'] if total else ['']))
 trs=''
 for c in order:
  t=next((r for r in totals if r['condition']==c),None)
  if t:trs+=f'<tr><td>{names[c]}</td><td>{t["cases"]}/34</td><td>{t["character_score"]:.2%}</td><td>{t["CER"]:.2%}</td><td>{t["S"]}</td><td>{t["D"]}</td><td>{t["I"]}</td><td>{t["exact"]}/{t["cases"]}</td><td>{t["failures"]}</td></tr>'
 details=''.join(f'<details><summary>No.{r["no"]} {names[r["condition"]]}：CER {r["CER"]:.2%}</summary><p>正解：{html.escape(r["reference"])}</p><p>認識：{html.escape(r["hypothesis"])}</p><p>{html.escape(r["error"])}</p></details>' for r in rows)
 page=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>No.53～86 光モールス評価</title><style>body{{font-family:Meiryo,sans-serif;color:#173047;margin:40px;max-width:1300px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #bbb;padding:9px}}p{{line-height:1.8;overflow-wrap:anywhere}}.note{{background:#fff1d8;padding:16px}}details{{margin:12px 0}}</style><h1>光モールスNo.53～86：周期自動推定＋入力時間補正</h1><p>{len(rows)}/408ケース完了。CNNと試作v2を固定し、再学習・再調整・正解補正なし。</p><div class="note">34電文は6本の録画を分割したものです。加工を含む408ケースは独立408録画ではありません。No.41～50で開発した処理を追加録画に適用しましたが、電文分割は既に原稿と照合済みで、光源位置も事前指定しています。完全自動・未見の全工程評価ではありません。雨・霧は人工加工で、各条件・電文につき乱数1回です。</div><p>広い光源枠は中心40×40画素にそろえ、周囲128×128を64×64へ縮小する従来処理を使用。可変ROI補正は使っていません。No.63・64は区切点がないため全文で、文字数加重の合計への寄与が大きくなります。</p><p>文字スコア＝1−CER。CER＝正解に合わせるための最少修正回数÷正解文字数。単文字分類Accuracyではありません。空白のみ除外、濁点・記号も別単位。保留・失敗は空出力として全削除に計上します。</p><table><tr><th>条件</th><th>件数</th><th>文字スコア</th><th>CER</th><th>置換</th><th>削除</th><th>挿入</th><th>全文一致</th><th>保留・失敗</th></tr>{trs}</table><h2>電文別の正解と認識結果</h2>{details}</html>'''
 (DEST/'評価結果.html').write_text(page,encoding='utf-8')
 return rows,totals

def main():
 plan=prepare();ckpt=torch.load(DEST/'frozen/cnn.pt',map_location='cpu',weights_only=False)
 for record in plan['records']:
  n=record['no']
  if all((DEST/'predictions'/f'no{n}_{c}.json').exists() for c in plan['conditions']):continue
  frames,times=extract(record)
  for condition in plan['conditions']:
   dest=DEST/'predictions'/f'no{n}_{condition}.json'
   if dest.exists():continue
   print(f'No.{n}: {condition}',flush=True);parameters=None
   if condition=='original':f=features(frames);t=times
   else:
    a,parameters=augment(frames,times-times[0],condition,2026101300+n*100+CONDITIONS.index(condition),stress=False)
    f=features(a);t=np.arange(len(a))/30;del a;gc.collect()
   np.savez_compressed(DEST/'features'/f'no{n}_{condition}.npz',times=t,features=f)
   result={};error=''
   try:result=classify_adaptive(t,f,ckpt,normalize_input=True)
   except ValueError as exc:error=str(exc)
   metrics=score(record['reference'],result.get('text',''))
   row=dict(no=n,condition=condition,**metrics,failure=bool(error),error=error,timing=result.get('timing'))
   dump(dest,dict(metrics=row,prediction=result,parameters=parameters,source=record))
   print(f'No.{n}: {condition} N={metrics["N"]} errors={metrics["errors"]} CER={metrics["CER"]:.2%} hold={bool(error)}',flush=True)
  del frames;gc.collect();report(plan)
 for f in plan['frozen']:assert sha(Path(f['path']))==f['sha256']
 rows,totals=report(plan);assert len(rows)==408
 for r in rows:
  assert ''.join(x[1] for x in r['alignment'])==r['reference'] and ''.join(x[2] for x in r['alignment'])==r['hypothesis']
  assert r['errors']==r['S']+r['D']+r['I']
 (DEST/'quality_check.txt').write_text('408ケース完了。開始前後のモデル・推論・加工コードのSHA256一致。全フレーム読取・時刻単調増加・動画ファイルidentity不変を確認。元動画SHA256保存。全408文字対応と修正内訳を確認。推論への正解原稿や加工倍率の入力なし。再学習・調整なし。6録画の光源範囲の代表画像を目視確認。HTMLブラウザ視覚確認は未実施。\n',encoding='utf-8')
 print(json.dumps(totals,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
