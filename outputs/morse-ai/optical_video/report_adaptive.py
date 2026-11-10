from pathlib import Path
import hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from optical_video.evaluate_coverage_stress import distance

root=Path(__file__).parent;out=root/'adaptive_v3'
protocol=json.loads((out/'protocol.json').read_text(encoding='utf-8'))
rows=json.loads((out/'results.json').read_text(encoding='utf-8'));summary=json.loads((out/'summary.json').read_text())
refs={s['name']:s['expected'] for s in json.loads((root/'coverage_stress_v1/protocol.json').read_text(encoding='utf-8'))['cases']}
refs.update({s['name']:s['reference'] for s in protocol['fresh_cases']})
for row in rows:
    bundle=json.loads((out/(row['name']+'_'+row['method']+'.json')).read_text(encoding='utf-8'))
    hypothesis=bundle['analysis']['text'] if bundle['analysis'] else ''
    assert hypothesis==row['text'] and distance(refs[row['name']],hypothesis)==row['edits']
for name,h in protocol['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
for spec in protocol['fresh_cases']:
    truth=json.loads((out/(spec['name']+'.truth.json')).read_text(encoding='utf-8'))
    assert hashlib.sha256((out/(spec['name']+'.avi')).read_bytes()).hexdigest()==truth['sha256']
fig,axes=plt.subplots(2,1,figsize=(11,7))
for ax,name in zip(axes,('new_30_drift','new_30_step')):
    r=json.loads((out/(name+'_adaptive.json')).read_text(encoding='utf-8'))['analysis'];tr=r['trace'];t=[x['time_seconds'] for x in tr]
    ax.plot(t,[x['signal'] for x in tr],label='Brightness',lw=1)
    ax.plot(t,[x['threshold_on'] for x in tr],label='Adaptive ON threshold',color='orange')
    ax.axhline(r['threshold_on'],label='Fixed ON threshold',color='red',ls='--')
    ax.set(xlabel='Time (seconds)',ylabel='Brightness',title=name+' (synthetic)');ax.legend(loc='upper right')
fig.tight_layout();fig.savefig(out/'threshold_comparison.png',dpi=140);plt.close(fig)
report=['# 適応しきい値の比較評価（2026-09-22）','',
'周辺の明るさに合わせて点灯判定を変える「適応しきい値」を実験機能として追加しました。徐々に暗くなる合成動画で改善が見られましたが、急な変化で警告のない誤認識が残るため、既定の固定方式は維持します。',
'','## 同一入力での比較','',
'| 区分 | 方式 | 完全一致 | 編集数／正解文字数 | CER | 警告なしの誤り件数 |','|---|---|---:|---:|---:|---:|']
for category,title in [('coverage','符号網羅9ケース'),('stress','厳しい条件30ケース'),('fresh','追加12ケース')]:
    for method,label in [('fixed','固定'),('adaptive','適応')]:
        s=next(r for r in summary if r['category']==category and r['method']==method)
        report.append(f"| {title} | {label} | {s['exact']}/{s['cases']} | {s['edits']}/{s['reference_units']} | {s['cer']:.2%} | {s['unflagged_errors']} |")
report.extend(['','括弧異常・未知符号・自動速度推定不能の6ケースは、両方式で同じ警告／停止となりました。空の正解を持つ停止確認もあるため、通常の認識率と混ぜていません。',
'','固定方式は見落とし診断を追加したv2との比較です。既存45ケースについて、固定方式の文章と状態がv2から変わっていないことを確認しました。',
'','## 改善した点・残る問題','',
'- 既存の露出変動4ケースは適応方式で全文一致しました。20画素の光源移動1ケースも一致しましたが、追跡機能を実装したわけではありません。',
'- 追加動画の徐々に暗くなる3ケースは、いずれも全文一致しました。',
'- 追加動画の急な露出低下3ケースでは1〜2文字の誤りが残り、すべてOKでした。固定方式は同ケースで誤りが多い一方、REVIEWを出していました。誤り数の削減と警告の確実さは別の評価軸です。',
'- 今回、固定方式で全文一致したケースは適応方式でも全文一致しました。ただし別の速度・長い点灯・撮影条件でも悪化しないという保証ではありません。',
'','![固定と適応のしきい値](threshold_comparison.png)','',
'## 試験条件と方式','',
'既存45ケースは凍結済み輝度列で比較し、保存済み解析がないものは動画を再読込しました。追加12ケースは別文章「カモメノイロハ012」（10文字）、seed=81236で動画を新たに生成・読込しました。24fps／短点8フレーム、30fps／12フレーム、60fps／10フレームの3組と、明瞭・徐々に70%減光・途中で光量30%・画素ノイズの4条件です。',
'','両方式で入力・ROI・復号規則を共通にし、ケースごとの再調整はしていません。条件とコードハッシュは採点前にprotocol.jsonへ記録しました。解析停止は空の認識文として正解文字の削除に数え、集計から除外していません。',
'','適応方式は中央3秒の10・90パーセンタイルから、その差の35%／65%に消灯・点灯しきい値を置きます。局所の明暗差が15未満なら全体の固定しきい値へ戻します。使用したしきい値と戻したフレーム数を保存します。未来側のフレームも参照する録画解析用で、リアルタイム処理ではありません。',
'','短点長の推定や符号表を正解に合わせて変更していません。文字を辞書や文脈から補う処理もありません。中心窓が急な露出変化をまたぐと、変化前後の明るさが混ざり、境界付近の短点・長点が崩れる可能性があります。',
'','## 操作','',
'動画画面の「点灯判定方式」で「適応しきい値（実験的）」を選び、再解析します。既定は「固定しきい値（従来）」です。方式を変更すると古い結果は無効になり、画面に実験機能の制約を表示します。手動しきい値との同時使用はできません。',
'','グラフには時間ごとに変わるしきい値を表示します。JSONのスキーマはoptical-video-v3で、threshold_method、adaptive_window_seconds、adaptive_fallback_frames、各フレームのthreshold_on／threshold_offを保存します。従来の最上位threshold_on／threshold_offは全体固定値であり、適応方式で実際に使った値はtrace内の列を参照してください。',
'','## 検証・残タスク','',
'関連16テストに成功しました。保存された114結果（57ケース×2方式）の文章を再採点し、結果と一致しました。固定v2のcore.pyとui.pyはbaseline_v2に保存し、過去の評価データは上書きしていません。',
'','次の改善候補は急な露出変化の診断と、変化点をまたがないしきい値推定です。長い点灯・長い消灯、さらに異なる文章と速度を含めて、警告の出しすぎも確認する必要があります。今回は試作方式の比較までを完了し、実撮影評価・正式な既定方式の変更・H.264検証は未実施です。',
'','これらは開発用合成動画の結果で、実撮影での精度保証や独立Testの性能ではありません。音声CNN・M1〜M4の学習や採用判断とは独立した処理です。'])
(out/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
(out/'score_verification.json').write_text(json.dumps(dict(status='PASS',rescored_results=len(rows),new_video_hashes_verified=12,code_hashes_match=True,real_videos=0),indent=2),encoding='utf-8')
print(out/'report.md')
