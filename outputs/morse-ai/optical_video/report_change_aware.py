from pathlib import Path
import hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from optical_video.evaluate_coverage_stress import distance

root=Path(__file__).parent;out=root/'change_aware_v4'
rows=json.loads((out/'results.json').read_text(encoding='utf-8'));summary=json.loads((out/'summary.json').read_text());protocol=json.loads((out/'protocol.json').read_text(encoding='utf-8'))
assert len(rows)==201
for row in rows:
    bundle=json.loads((out/(row['name']+'_'+row['method']+'.json')).read_text(encoding='utf-8'))
    text=bundle['analysis']['text'] if bundle['analysis'] else ''
    assert text==row['text'] and distance(row['reference'],text)==row['edits']
for name,h in protocol['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h
for spec in protocol['new_cases']:
    truth=json.loads((out/(spec['name']+'.truth.json')).read_text(encoding='utf-8'))
    assert hashlib.sha256((out/(spec['name']+'.avi')).read_bytes()).hexdigest()==truth['sha256']
sample='new_30_step';a=json.loads((out/(sample+'_adaptive.json')).read_text(encoding='utf-8'))['analysis'];b=json.loads((out/(sample+'_change_aware.json')).read_text(encoding='utf-8'))['analysis']
tr=b['trace'];t=[r['time_seconds'] for r in tr];change=b['exposure_changes'][0]['time_seconds']
fig,ax=plt.subplots(figsize=(11,4.4));ax.plot(t,[r['signal'] for r in tr],label='Brightness')
ax.plot(t,[r['threshold_on'] for r in a['trace']],label='Adaptive v3 ON',ls='--',color='orange')
ax.plot(t,[r['threshold_on'] for r in tr],label='Change-aware ON',color='green')
ax.axvline(change,color='red',ls=':',label='Detected exposure change')
ax.set(xlim=(change-2,change+2),xlabel='Time (seconds)',ylabel='Brightness',title='Synthetic abrupt dimming: boundary-aware thresholds');ax.legend();fig.tight_layout();fig.savefig(out/'change_boundary.png',dpi=150);plt.close(fig)
labels={'fixed':'固定＋見落とし診断','adaptive':'適応v3','change_aware':'変化点対応v4'}
report=['# 急な明るさ変化への対応（2026-09-22）','',
'明るい側と暗い側の基準が同時に変化する場所を検出し、前後を混ぜずに適応しきい値を計算する方式を追加しました。変化点が検出された動画は、文章が正しく見えてもREVIEWとし、時刻と根拠を表示します。',
'','## 比較結果','',
'| 対象 | 方式 | 完全一致 | 編集数／正解文字数 | 警告なしの誤り件数 |','|---|---|---:|---:|---:|']
for category,title in [('coverage','符号網羅9件'),('stress','厳しい条件30件'),('fresh','前回の追加12件'),('validation','今回の新規合成10件')]:
    for method,label in labels.items():
        r=next(s for s in summary if s['category']==category and s['method']==method)
        report.append(f"| {title} | {label} | {r['exact']}/{r['cases']} | {r['edits']}/{r['reference_units']} | {r['unflagged_errors']} |")
report.extend(['','別途、異常入力6件は各方式で従来と同じ警告／停止でした。今回の比較は計67ケース×3方式＝201結果です。認識できなかったケースも空の認識文として削除に数え、除外していません。',
'','前回誤りが残っていた24／30／60fpsの急変動画3本は、新方式で全文一致しました。過去の固定・適応v3の114結果については、本文と状態が以前から変わっていないことを確認しています。旧版core.py、adaptive.py、ui.pyをbaseline_v3に保存しました。',
'','![変化点付近のしきい値](change_boundary.png)','',
'## 今回追加した動画','',
'正解は「ヒカリノモールス123」（11文字）、30fps、短点9フレーム、seed=99173です。動画の約33%／67%の位置で光量を1→0.35または0.35→1に変え、画素ノイズなし／標準偏差20を組み合わせた8件、変化なしの対照1件、消灯輝度をほぼゼロにした急変1件を生成しました。条件は評価前にprotocol.jsonへ固定しました。',
'','8件の変化あり動画と1件の対照動画は全文一致しました。消灯輝度がほぼゼロの動画では変化点を検出できず、1文字の誤りが残りましたが、点灯時間の異常としてREVIEWを出しました。この結果を、未確認の撮影条件でもすべて警告できるという意味には扱いません。',
'','正しく読めた急変動画8件もREVIEWです。誤認識件数と要確認件数は別です。変化なしの新規対照動画と符号網羅9件には、変化点警告は出ませんでした。既存ストレス試験では、急変しても正しく読めた3件に確認のための警告が加わっています。',
'','## 判定方法','',
'生の輝度に比較的大きな差があるフレームを候補とし、その前後それぞれ最大3秒の10・90パーセンタイルを比較します。暗い側と明るい側が同方向へ動き、各区間の輝度がそれぞれ二つの水準に十分近い候補を採用します。近接候補は当てはまりが良いものにまとめます。正解文や文字の候補は変化点検出に使いません。',
'','採用した変化点で動画の輝度列を分け、区間内で既存の適応しきい値を計算します。局所明暗差が不足する場合は、その区間全体のしきい値へ戻します。既存の固定方式や適応v3のアルゴリズムは変更していません。',
'','## 画面と保存','',
'「点灯判定方式」に「変化点対応（実験的）」を追加しました。既定は固定方式のままです。解析結果には警告、変化した時刻、変化前後の明暗の値を表示します。グラフには実際に使用したしきい値が出ます。',
'','詳細JSONはoptical-video-v4とし、exposure_changesに変化点の時刻・フレーム・前後の輝度・当てはまりを保存します。診断・文字・符号・点灯区間も残します。解析開始時刻が0以外の場合も、変化点の秒数は元動画上の時刻です。',
'','## 限界と次の確認事項','',
'- 消灯輝度がゼロ近傍だと、暗い側の変化が確認できず、変化点を見逃す場合があります。',
'- 端に近い急変、短い区間に連続する変化、片側が長い点灯／消灯だけの場合は十分な前後情報がありません。',
'- 背景や別光源の変化を露出変動と区別できる保証はありません。原因は断定せず確認を求めます。',
'- 同じ開発用合成動画を使って改善を重ねています。独立した実動画の精度、H.264、カメラ露出制御、手ぶれ全般は未評価です。',
'','今回のテストで警告なしの誤りは0件でしたが、一般的な安全保証ではありません。認識文章を自動確定してよい段階とはしておらず、実験機能として保持します。',
'','関連20テストに成功。保存された201結果を再採点し、10本の新規合成動画とコードのハッシュも確認しました。旧評価・音声モデル重みは変更していません。'])
(out/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
(out/'score_verification.json').write_text(json.dumps(dict(status='PASS',rescored=201,new_video_hashes_verified=10,code_hashes_match=True,real_videos=0),indent=2),encoding='utf-8')
print(out/'report.md')
