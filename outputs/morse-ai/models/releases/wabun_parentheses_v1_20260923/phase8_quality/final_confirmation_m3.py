"""Run only the precommitted M3 final confirmation plan from a frozen release."""
from pathlib import Path
import sys,json,time,hashlib,copy
import numpy as np,torch
P=Path(__file__).resolve().parent.parent;sys.path[:0]=[str(P),str(P/'phase8_quality'),str(P/'phase6_wabun65')]
from common import MODELS,setup
from evaluate_new import infer,select_body
from audio_preprocessing import load_audio
from morse_segmentation import segment_morse
from morse_table import REVERSE_TABLE
from wabun_runtime_policy import render_body
from evaluate_recording import edit_alignment
from evaluation_compare import distance
from new_recording_preparation import transform

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def verify():
 m=json.loads((P/'release_manifest.json').read_text(encoding='utf-8'))
 for rel,h in m['files'].items():assert digest(P/rel)==h,rel
 return m

def main():
 planpath=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();plan=json.loads(planpath.read_text(encoding='utf-8'))
 assert plan['model']=='M3' and plan['frontend']=='baseline' and plan['policy']=='wabun-parentheses-v1'
 assert digest(planpath)==planpath.with_suffix('.sha256').read_text().strip()
 m=verify();assert digest(P/'release_manifest.json')==plan['release_manifest_sha256'];out.mkdir(exist_ok=False)
 ck=torch.load(P/'phase6_wabun65/runs/m3_wabun65_20260922/best.pt',map_location='cpu',weights_only=True);cfg=ck['config'];labels=sorted(ck['labels'],key=ck['labels'].get);setup(cfg)
 model=MODELS['M3'](cfg).eval();model.load_state_dict(ck['state_dict']);results=[]
 for e in plan['recordings']:
  assert 12<=e['number']<=20 and e['role']=='final_confirmation'
  assert digest(e['audio'])==e['audio_sha256'] and digest(e['reference'])==e['reference_sha256']
  x=load_audio(e['audio'])
  for i,cond in enumerate(plan['conditions']):
   start=time.perf_counter();seed=plan['seed_base']+e['number']*100+i
   wave=x if cond['id']=='clean' else transform(x,cond,seed)[0];error='';text='';decoded=[];meta={}
   try:
    detected,meta=segment_morse(wave)
    for j,r in enumerate(detected):r.update(index=j,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
    body=select_body(detected,{'mode':'protocol'});_,decoded,_=infer(body,wave,model,cfg,labels);text,decoded,warnings=render_body(decoded)
   except (ValueError,OSError,RuntimeError) as exc:error=str(exc)
   metric,alignment=edit_alignment(e['normalized_reference'],text);assert distance(e['normalized_reference'],text)==metric['edit_distance']
   r=dict(metric,number=e['number'],condition=cond['id'],model='M3',status='FAILED' if error else 'OK',error=error,reference=e['normalized_reference'],hypothesis=text,seed=seed,seconds=time.perf_counter()-start)
   results.append(r);save(out/f"no{e['number']:02d}_{cond['id']}.json",dict(result=r,segments=decoded,detector=meta,alignment=alignment));save(out/'results.json',results)
   print(e['number'],cond['id'],r['edit_distance'],r['status'],flush=True)
 summary=[]
 for c in plan['conditions']:
  rs=[r for r in results if r['condition']==c['id']];assert len(rs)==9;n=sum(r['reference_units'] for r in rs);d=sum(r['edit_distance'] for r in rs)
  summary.append(dict(condition=c['id'],originals=9,units=n,edits=d,cer=d/n,failures=sum(r['status']!='OK' for r in rs),exact=sum(r['status']=='OK' and not r['edit_distance'] for r in rs),substitutions=sum(r['substitutions'] for r in rs),insertions=sum(r['insertions'] for r in rs),deletions=sum(r['deletions'] for r in rs)))
 save(out/'summary.json',summary);verify();assert digest(planpath)==planpath.with_suffix('.sha256').read_text().strip()
 for e in plan['recordings']:assert digest(e['audio'])==e['audio_sha256'] and digest(e['reference'])==e['reference_sha256']
 save(out/'verification.json',dict(completed=True,model='M3',rows=len(results),originals=9,conditions=7,models_and_code_unchanged=True,inputs_and_plan_unchanged=True,fresh_inference=True,independent_distance_verified=True,training=False,model_reselection=False))
 lines=['# M3 最終確認結果','','採用構成はM3＋baseline＋丸括弧内和文。No.12〜20だけを新規推論しました。原音が主評価で、加工条件は別集計です。推論前にモデル・コード・正解文・本文範囲・加工条件をハッシュ付きで固定しました。','','|条件|原音数|正解文字単位|編集数|CER|全文一致|処理失敗|','|---|---:|---:|---:|---:|---:|---:|']
 for r in summary:lines.append(f"|{r['condition']}|9|{r['units']}|{r['edits']}|{r['cer']:.2%}|{r['exact']}|{r['failures']}|")
 lines+=['','## 原音別結果','','|No.|文字単位|編集数|CER|状態|','|---|---:|---:|---:|---|']
 for r in results:
  if r['condition']=='clean':lines.append(f"|{r['number']}|{r['reference_units']}|{r['edit_distance']}|{r['cer']:.2%}|{r['status']}|")
 lines+=['','漢数字は数字として扱い、転記訂正はしていません。正解文は前置き・宛先を除いた本文です。No.15・19は宛先が折り返されているため先頭3行、他は先頭2行を除外する指定を推論前に固定しました。音声本文は既存のprotocol符号で抽出し、失敗は全参照文字の削除として計上します。','CERには本文抽出・正規化・モード処理が含まれ、CNN単体Accuracyではありません。原稿の不一致も誤りとして残しています。加工した63ケースは9件の原音に由来し、63件の独立録音ではありません。','既存の選定11件は一・二総通、最終確認9件は三総通です。収録元やセッションの独立性が外部検証されたデータではありません。学習時未使用の未知環境音試験でもありません。','許容CER等の数値的合格基準は事前指定されていないため、合否判定はせず測定結果を報告します。結果を使った再選定・閾値変更はしていません。今後この結果を見て調整する場合、この9件を未使用の最終確認用とは扱えません。']
 (out/'最終確認報告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__':main()
