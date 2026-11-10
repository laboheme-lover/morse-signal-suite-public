from pathlib import Path
import json,hashlib,collections
from new_recording_preparation import P,D,digest,save,entries
rdir=D/'selection_results';v=json.loads((rdir/'verification.json').read_text(encoding='utf-8'));assert v['completed']
rows=json.loads((rdir/'results.json').read_text(encoding='utf-8'));assert len(rows)==77*24
manifest=json.loads((D/'selection_manifest.json').read_text(encoding='utf-8'));mapping={r['id']:r for r in manifest['recordings']}
assert len(mapping)==77 and all(r['role']=='selection' and r['original_number']<=11 for r in mapping.values())
lock=json.loads((D/'selection_preparation_lock.json').read_text(encoding='utf-8'))
for file,key in [('selection_manifest.json','manifest_sha256'),('reference_preparation.json','reference_preparation_sha256'),('augmentation_plan.json','augmentation_plan_sha256'),('split_plan.json','split_sha256')]:assert digest(D/file)==lock[key]
for file,h in lock['scripts'].items():assert digest(P/file)==h
for e in entries():
 assert digest(e['audio'])==e['audio_sha256'] and digest(e['reference'])==e['reference_sha256']
conditions=[c['id'] for c in json.loads((D/'augmentation_plan.json').read_text(encoding='utf-8'))['conditions']]
methods=['baseline','timing','tracking','tempo','combined','combined_mode'];models=['M1','M2','M3','M4'];summary=[]
for cond in conditions:
 for method in methods:
  for model in models:
   rs=[r for r in rows if mapping[r['id']]['condition']==cond and r['method']==method and r['model']==model];assert len(rs)==11
   units=sum(r['reference_units'] for r in rs);edits=sum(r['edits'] for r in rs)
   summary.append(dict(condition=cond,method=method,model=model,originals=11,units=units,edits=edits,cer=edits/units,failures=sum(r['status']!='OK' for r in rs),exact=sum(r['status']=='OK' and r['edits']==0 for r in rs),substitutions=sum(r['substitutions'] for r in rs),insertions=sum(r['insertions'] for r in rs),deletions=sum(r['deletions'] for r in rs)))
save(D/'condition_summary.json',summary)
# Keep raw generic-runner files unchanged; make explicitly labelled viewer exports.
from evaluation_compare import SCHEMA,load_bundle
for cond in conditions:
 for model in models:
  rs=[dict(r,dataset='new_selection_11',condition=cond,original_number=mapping[r['id']]['original_number']) for r in rows if mapping[r['id']]['condition']==cond and r['method']=='baseline' and r['model']==model]
  bundle=dict(schema=SCHEMA,name=f'selection_{cond}_baseline_{model}',scope='MODEL_SELECTION_NOT_FINAL_CONFIRMATION',scoring_policy='content_v2_kanji_digits_body_protocol',rows=rs)
  payload=json.dumps(bundle,ensure_ascii=False).encode('utf-8');load_bundle(payload)
  save(D/'viewer_comparisons'/f'selection_{cond}_baseline_{model}.json',bundle)
def get(c,m,k):return next(r for r in summary if (r['condition'],r['method'],r['model'])==(c,m,k))
lines=['# 新規録音・選定用11件の第1回評価','','No.1〜11だけを使用しました。No.12〜20の最終確認推論、学習、モデルの更新は実施していません。','','## 採点条件','','正解文の漢数字を1桁ずつ0〜9へ変換し、数字と仮名は原稿の指定が正しいというユーザー指示で採点しました。「二」を文脈から「ニ」へ直す等の転記訂正は行っていません。原文・変換文・正規化文はreference_preparation.jsonに保存しています。','各原稿の先頭2行（前置き・宛先）を除いた本文を採点対象とし、音声では既存の開始・終了符号によるprotocol抽出を使用しました。時刻を正解に合わせて調整していません。句読点・括弧等は既存content_v2方針で正規化します。区切り検出失敗等は正解全文を削除として計上します。','CERは本文抽出・モード解釈・正規化を含む文字編集率で、CNN単体の分類Accuracyではありません。原稿に転記誤りが残っている場合、その不一致もCERに含まれます。','','## 従来前処理baselineでのモデル比較','','|条件|M1 CER|M2 CER|M3 CER|M4 CER|','|---|---:|---:|---:|---:|']
for c in conditions:lines.append('|'+c+'|'+ '|'.join(f"{get(c,'baseline',m)['cer']:.2%}" for m in models)+'|')
lines+=['','## 前処理を含めた比較（クリーン原音）','','|方式|M1 CER|M2 CER|M3 CER|M4 CER|','|---|---:|---:|---:|---:|']
for m in methods:lines.append('|'+m+'|'+ '|'.join(f"{get('clean',m,k)['cer']:.2%}" for k in models)+'|')
lines+=['','## 前処理を含めた比較（複合条件）','','|方式|M1 CER|M2 CER|M3 CER|M4 CER|','|---|---:|---:|---:|---:|']
for m in methods:lines.append('|'+m+'|'+ '|'.join(f"{get('combined',m,k)['cer']:.2%}" for k in models)+'|')
lines+=['','## モード処理の共通誤り','','No.4・5・8・9では、原稿の括弧内にカタカナがある一方、現行処理が括弧符号を欧文開始・和文復帰と解釈し、カタカナ予測を英字や□へ変換する事例を確認しました。正解文や凍結ルールを直して点数を改善することはせず、そのまま採点しています。','この共通処理の不一致がCERに含まれるため、今回の数値だけでCNNの優劣を判断できません。次は選定データ上で、括弧が引用表記かモード指定かを区別する対応を検討し、変更する場合は別の評価版として比較する必要があります。']
errors=collections.Counter(r['error'] for r in rows if r['status']!='OK')
lines+=['','## 確認と限界','',f"77ケース×6方式×4モデル＝{len(rows)}結果を集計。元録音は11件です。処理失敗は{sum(errors.values())}結果。全条件別の編集数・S/I/D・全文一致・失敗数はcondition_summary.jsonに保存しました。",'雑音は合成白色ガウス雑音20/10/5 dB。SNRは無音区間を含む録音全体の平均電力を基準とします。音程揺れは±20 Hz・0.3 Hz周期、速度は0.9倍（音程も変わる再生速度変更）。複合条件は音程揺れ＋速度0.9倍＋雑音10 dB。音量は必要な場合のみ全体減衰し、クリッピングを避けました。','独立した短点・長点の長さの揺らぎや未知の実環境音に対する評価は、今回の加工条件に含みません。','同一原音の加工ケースは相互に関連するため、77件の独立録音として統計的な優位性を主張しません。原音と加工条件は別集計で、条件数で恣意的に重み付けした総合順位は付けていません。','選定側は一・二総通、最終確認側は三総通という用途分割です。条件の違いと収録元の共通性があり得るため、独立した録音セッションや実環境全般への汎化を保証しません。','比較画面へ読み込めるbaselineの条件別28ファイルをviewer_comparisonsに保存しました。汎用実行器の生出力に残るknown_real44等の名称は今回のデータの出所を表しません。集計と比較用書き出しはselection_manifest.jsonの対応表に基づいています。','採用候補・前処理・許容性能の条件は未確定です。最終確認用9件は引き続き保留します。']
for error,n in errors.items():lines.append(f'- {error}: {n}結果')
(D/'評価報告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
save(D/'completion_checks.json',dict(selection_originals=11,conditions=7,scored_rows=len(rows),final_confirmation_inferred=0,training_executed=False,sources_unchanged=True,preparation_locks_verified=True,final_role_guard_test_passed=True,augmentation_reproducibility_and_snr_test_passed=True,report_sha256=digest(D/'評価報告.md')))
print('Saved selection report',flush=True)
print(json.dumps([r for r in summary if r['condition']=='clean'],ensure_ascii=False,indent=2))
