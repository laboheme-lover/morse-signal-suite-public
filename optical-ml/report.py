"""Generate transparent Japanese development report from recorded metrics."""
import json,csv,html,shutil,collections,hashlib
from pathlib import Path
import numpy as np
from extract import OUT,ROOT,sha

NAMES={'clean':'基本（軽微な揺らぎ）','fast':'高速','slow':'低速','dim':'暗い','bright':'明るい','rain':'人工の雨','fog':'人工の霧','static_light':'常時点灯の別光源','sensor_noise':'センサーノイズ','timing_jitter':'周期の揺らぎ','mixed':'複合加工'}

def main():
 r=json.loads((OUT/'training_results.json').read_text(encoding='utf-8'));cfg=json.loads((OUT/'dataset/config.json').read_text(encoding='utf-8'))
 records=[json.loads(x) for x in (OUT/'dataset/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
 assert len(records)==9295 and len({x['parameters']['seed'] for x in records})==9295
 counts=dict(collections.Counter(x['split'] for x in records));z=np.load(OUT/'dataset/features.npz')
 assert z['x'].shape==(9295,5,256) and np.isfinite(z['x']).all()
 audit=dict(samples=len(records),split_counts=counts,unique_sources=len({x['source_id'] for x in records}),source_recordings=1,unique_seeds=9295,finite_features=True,source_overlap_between_splits=True,independent_test=False)
 (OUT/'dataset/audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
 preds=np.load(OUT/'predictions.npz')
 with (OUT/'per_class.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['model','label','n','correct','accuracy'])
  for name in ('cnn','multiscale_bigru','rule'):
   for i,label in enumerate(cfg['classes']):
    m=(preds['split']==2)&(preds['truth']==i);ok=int(sum(preds[name][m]==i));w.writerow([name,label,int(m.sum()),ok,ok/int(m.sum())])
 lines=['光モールス機械学習 開発版v1（2026-10-13）','',f'開発用の選定：{r["selected_development_model"]}（加工検証の正解率で選択）','学習・検証・テストは同じ65元動画から派生。別録画での独立テストではない。','実際の雨・霧・撮影機種・距離変更での性能は未検証。', '']
 for row in r['results']:
  if row['condition']=='ALL':lines.append(f"{row['model']} / {row['split']}: {row['correct']}/{row['n']} = {row['accuracy']*100:.2f}%")
 (OUT/'結果概要.txt').write_text('\n'.join(lines),encoding='utf-8')
 sections=[]
 order=['fast','clean','slow','dim','bright','timing_jitter','rain','fog','static_light','sensor_noise','mixed']
 for split,title in [('test_augmented','加工テスト（学習・検証とは別の乱数、同じ元動画）'),('stress','強い加工による追加確認（同じ元動画）')]:
  rows=[]
  for cond in ['ALL']+order:
   cells=[]
   for name in ['cnn','multiscale_bigru','rule']:
    a=next(x for x in r['results'] if x['split']==split and x['model']==name and x['condition']==cond)
    cells.append(f"<td>{a['accuracy']*100:.2f}%<small>{a['correct']} / {a['n']}</small></td>")
   rows.append('<tr><th>'+NAMES.get(cond,'全条件')+'</th>'+''.join(cells)+'</tr>')
  sections.append(f'<h2>{title}</h2><table><tr><th>条件</th><th>1D-CNN</th><th>複数幅CNN＋双方向GRU</th><th>簡易ルール（今回実装）</th></tr>'+''.join(rows)+'</table>')
 previews=''.join(f'<figure><figcaption>{NAMES[c]}</figcaption><video controls preload="metadata" src="preview/{c}.mp4" width="192"></video></figure>' for c in order)
 body=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>光モールス機械学習・開発結果</title><style>body{{font:17px/1.7 Meiryo,sans-serif;max-width:1100px;margin:40px auto;color:#17304b;padding:0 20px}}h1,h2{{color:#12395a}}table{{border-collapse:collapse;width:100%;margin:20px 0}}td,th{{border:1px solid #ccd5df;padding:8px;text-align:left}}th{{background:#edf5f7}}small{{display:block;color:#52616c}}.warn{{border-left:6px solid #df9d36;background:#fff4df;padding:18px}}figure{{display:inline-block;margin:10px}}video{{image-rendering:pixelated}}code{{background:#eef2f5}}</style>
<h1>光モールス機械学習・開発結果</h1><p>2026年10月13日／単文字65クラス／和文のみ（括弧も文字として扱う）</p>
<div class="warn"><b>独立した実録画での性能ではありません。</b> 1634.mp4の65文字を基にした加工データです。各文字の同じ元映像が学習・検証・加工テストに含まれます。高い数値でも、新しい録画や実際の雨・霧で同じ性能を保証しません。数値的合格基準は設定していません。</div>
<h2>作成データ</h2><p>合計9,295件：学習5,720、検証1,430、加工テスト1,430、強い加工715。各文字・各条件を均等に生成。元の分割動画のハッシュ、時間区間、加工パラメータ、乱数、ラベルを保存しました。</p>
<p>保存物は元映像の64×64画素切り出し、加工画像から抽出した明るさ時系列、モデル入力テンソル、再生成用の全レシピです。9,295本すべてのMP4を保存したものではありません。11条件の見本MP4を保存し、任意のサンプルを <code>export_variant.py</code> で再生成できます。</p>
<h2>処理とモデル</h2><p>40×40画素の光源を中心に128×128画素を切り出し → 64×64へ縮小 → 画像上で加工 → 中央平均・中央上位輝度・周辺輝度などを抽出 → 5チャンネル×256時点に整形 → 65文字分類。5チャンネルは背景差分の平均と上位輝度、背景の明るさ、中央の明るさ、継続時間です。</p>
<p>1D-CNNは畳み込みと時間方向16区画の特徴を用います。比較モデルは幅3・5・9のCNN＋双方向GRUです。音声M3とは別モデルで、音声の学習済み重みは流用していません。AdamW、学習率0.002、重み減衰0.001、バッチ64、最大40エポック。検証損失でチェックポイントを選択し、加工テストを使った再調整はしていません。各モデル1 seedのみです。</p>
<p>検証正解率は両モデル99.58％で同率です。同率時の実装上の登録順によりCNNを既定にしています。優越性を確認したという意味ではありません。開発用選定：<b>{r['selected_development_model']}</b>。この選定は実運用の最終採用を意味しません。簡易ルールは今回比較用に実装したもので、既存アプリの全機能を再現したものではありません。雨の短い誤検出を除く処理はありません。ルール方式は同じ輝度のしきい値と点灯・消灯時間を利用します。短点長は消灯間隔から推定し、単一パルスの場合は300msを使うため、極端な速度では曖昧になります。</p>
{''.join(sections)}
<h2>加工範囲</h2><p>高速1.25～1.65倍、低速0.60～0.85倍、暗さ0.25～0.55倍、明るさ1.4～2.1倍。基本条件を含め軽微な速度0.90～1.10倍・明るさ0.8～1.2倍を共通に付加（主条件の指定がある場合はその範囲）。余白もランダムに変化させます。雨は移動する明るい筋と部分減光、霧はぼかしと白い散乱光、別光源は時間変化しない光の重畳です。物理シミュレーションではありません。</p>
<p>強い加工では高速2.2倍・低速0.45倍・暗さ0.1倍・濃霧・光源への強い重なり等を確認します。基本・明るい条件等は通常範囲の追加乱数です。すべての条件が未学習カテゴリという意味ではありません。</p>
<h2>加工の見本（「ロ」）</h2>{previews}
<h2>限界と次の確認</h2><p>単文字の分類試験です。連続動画での光源検出、文字区切り、文字分類を含む文章CERは今回の評価対象外です。実験用認識アプリでは連続動画の区切りも実装していますが、精度未検証です。別の日・別の撮影条件で各文字を複数回録画し、録画単位で学習・検証・最終テストを分離する必要があります。人工の雨・霧の追加だけでは実天候の検証を代替できません。</p>
<p><a href="evaluation.csv">条件別CSV</a> ／ <a href="per_class.csv">文字別CSV</a> ／ <a href="dataset/audit.json">データ監査</a> ／ <a href="結果概要.txt">結果概要</a></p></html>'''
 (OUT/'評価結果.html').write_text(body,encoding='utf-8')
 folder=OUT/'implementation';folder.mkdir(exist_ok=True)
 for p in (ROOT/'optical-ml').glob('*.py'):shutil.copy2(p,folder/p.name)
 files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='checksums.json']
 (OUT/'checksums.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in files},ensure_ascii=False,indent=2),encoding='utf-8')
 print('\n'.join(lines))

if __name__=='__main__':main()
