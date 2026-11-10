from pathlib import Path
import sys,json,hashlib
P=Path(__file__).resolve().parent.parent;sys.path[:0]=[str(P),str(P/'phase8_quality')]
from wabun_runtime_policy import render_body,normalize_reference,VERSION
from evaluate_recording import edit_alignment
from evaluation_compare import distance,SCHEMA,load_bundle
from new_recording_preparation import D,digest,save
from evaluate_new import verify_frozen
verify_frozen();source=D/'selection_results';out=D/'wabun_parentheses_v1';out.mkdir(exist_ok=False)
manifest=json.loads((D/'selection_manifest.json').read_text(encoding='utf-8'));methods=['baseline','timing','tracking','tempo','combined'];models=['M1','M2','M3','M4'];results=[];inputs={}
for entry in manifest['recordings']:
 assert entry['role']=='selection' and entry['original_number']<=11
 path=source/entry['id']/'result.json';inputs[str(path.relative_to(P))]=digest(path);data=json.loads(path.read_text(encoding='utf-8'))
 ref=normalize_reference(Path(entry['reference']).read_text(encoding='utf-8'));assert ref==data['metrics'][0]['reference']
 for method in methods:
  for model in models:
   raw=data['outputs'][method+'_'+model];old=next(r for r in data['metrics'] if r['method']==method and r['model']==model)
   text,rows,warnings=render_body(raw['segments']) if not raw['error'] else ('',[],[])
   metric,_=edit_alignment(ref,text);assert distance(ref,text)==metric['edit_distance']
   results.append(dict(metric,id=entry['id'],original_number=entry['original_number'],condition=entry['condition'],method=method,model=model,reference=ref,hypothesis=text,input_sha256=entry['audio_sha256'],edits=metric['edit_distance'],old_edits=old['edits'],status='FAILED' if raw['error'] else 'OK',error=raw['error'],dataset='selection11_wabun_parentheses',ui_alert=bool(warnings) or any(r.get('review_reason') for r in rows)))
summary=[]
conditions=[c['id'] for c in json.loads((D/'augmentation_plan.json').read_text(encoding='utf-8'))['conditions']]
for cond in conditions:
 for method in methods:
  for model in models:
   rs=[r for r in results if (r['condition'],r['method'],r['model'])==(cond,method,model)];assert len(rs)==11
   units=sum(r['reference_units'] for r in rs);edits=sum(r['edits'] for r in rs);old=sum(r['old_edits'] for r in rs)
   summary.append(dict(condition=cond,method=method,model=model,originals=11,units=units,edits=edits,cer=edits/units,old_edits=old,old_cer=old/units,failures=sum(r['status']=='FAILED' for r in rs)))
   if method=='baseline':
    bundle=dict(schema=SCHEMA,name=f'wabun_{cond}_{model}',scope='SELECTION_ONLY_CACHED_CNN_RESCORE',scoring_policy=VERSION,rows=rs);load_bundle(json.dumps(bundle).encode());save(out/'comparisons'/f'{cond}_{model}.json',bundle)
save(out/'results.json',results);save(out/'summary.json',summary)
for path,h in inputs.items():assert digest(P/path)==h
verify_frozen();save(out/'verification.json',dict(policy=VERSION,records=len(results),originals=11,conditions=7,methods=methods,original_results_unchanged=True,source_result_hashes=inputs,policy_sha256=digest(P/'wabun_runtime_policy.py'),models_unchanged=True,final_confirmation_inferred=0,retraining=False,fresh_inference=False,reference_changed=False,independent_distance_verified=True))
lines=['# 丸括弧内も和文として解釈する再評価','','ユーザー指定により丸括弧の自動欧文切替を停止しました。通常画面は括弧を表示し、実験・評価の本文CERでは括弧・句読点を除外します。選定用11原音×7条件のみを使用。モデルの再学習・重み更新はありません。','','保存済みの同一区間・CNN予測を再利用した再採点です。音声を再推論した結果ではありません。元の評価結果は上書きしていません。正解文・本文範囲は同一で、漢数字を数字として扱う指定も維持しています。','','欧文切替の補正に依存するcombined_modeとguardedは今回の和文運用の候補から外し、baseline/timing/tracking/tempo/combinedの5方式を比較しました。','','## クリーン原音・baseline','','|モデル|旧CER|新CER|旧編集数|新編集数|','|---|---:|---:|---:|---:|']
for r in summary:
 if r['condition']=='clean' and r['method']=='baseline':lines.append(f"|{r['model']}|{r['old_cer']:.2%}|{r['cer']:.2%}|{r['old_edits']}|{r['edits']}|")
lines+=['','## 条件別baseline CER','','|条件|M1|M2|M3|M4|','|---|---:|---:|---:|---:|']
for c in conditions:lines.append('|'+c+'|'+'|'.join(f"{next(r['cer'] for r in summary if (r['condition'],r['method'],r['model'])==(c,'baseline',m)):.2%}" for m in models)+'|')
lines+=['','詳細はsummary.json、個別認識文はresults.json、比較画面用ファイルはcomparisonsにあります。','最終確認用No.12〜20は推論していません。採用モデルは未決定です。残る誤りには原稿の転記違い、区間検出、文字分類の影響が含まれ得ます。77条件を77件の独立録音とは扱いません。','変更対象は作業フォルダーの通常画面・実験画面と追加の和文解釈処理です。過去再現用の凍結CLIと配布済みv4 ZIPは旧挙動のまま保持しています。新しい運用では更新した画面を使用してください。']
(out/'再評価報告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps([r for r in summary if r['condition']=='clean' and r['method']=='baseline'],ensure_ascii=False,indent=2))
