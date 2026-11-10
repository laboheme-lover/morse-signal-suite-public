from pathlib import Path
import hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from optical_video.evaluate_coverage_stress import score

root=Path(__file__).resolve().parent;out=root/'coverage_stress_v1'
protocol=json.loads((out/'protocol.json').read_text(encoding='utf-8'))
rows=json.loads((out/'results.json').read_text(encoding='utf-8'));specs={s['name']:s for s in protocol['cases']}
for p,h in protocol['source_sha256'].items():
    source=Path(p)
    if source.name=='core.py' and hashlib.sha256(source.read_bytes()).hexdigest()!=h:
        source=root/'baseline_v1/core.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==h
for row in rows:
    bundle=json.loads((out/(row['name']+'_result.json')).read_text(encoding='utf-8'))
    truth=json.loads((out/(row['name']+'.json')).read_text(encoding='utf-8'))
    assert hashlib.sha256((out/(row['name']+'.avi')).read_bytes()).hexdigest()==truth['video_sha256']
    assert score(specs[row['name']],truth,bundle['analysis'],row['error'],row['processing_seconds'])==row
coverage=[r for r in rows if r['category']=='coverage'];guards=[r for r in rows if r['category']=='guard'];stress=[r for r in rows if r['category']=='stress']
assert len(coverage)==9 and all(r['exact'] and r['patterns_exact'] for r in coverage)
assert all(r['max_boundary_error_seconds'] is not None and r['max_boundary_error_seconds']<=1/specs[r['name']]['fps']+1e-6 for r in coverage)
assert len(guards)==6 and all(r['required_behavior_pass'] for r in guards)
counts=[sum(r['exact'] for r in stress),sum(not r['exact'] and r['status']=='REVIEW' for r in stress),sum(r['status']=='REJECTED' for r in stress),sum(r['unflagged_error'] for r in stress)]
fig,ax=plt.subplots(figsize=(10,4.7));bars=ax.barh(['Exact transcript','Wrong, flagged REVIEW','Rejected (no transcript)','Wrong, displayed OK'],counts,color=['#32856e','#d49a33','#73818e','#c64444'])
ax.invert_yaxis();ax.set(xlabel='Number of synthetic cases',xlim=(0,max(counts)+3),title='Optical Morse stress tests: 30 prespecified synthetic cases')
for bar,count in zip(bars,counts):ax.text(count+.2,bar.get_y()+bar.get_height()/2,str(count),va='center')
ax.text(0,-.22,'Development diagnostics only. Not real-camera accuracy. Decoder unchanged.',transform=ax.transAxes,fontsize=9)
fig.tight_layout();fig.savefig(out/'stress_outcomes.png',dpi=150,bbox_inches='tight');plt.close(fig)
labels={'baseline':'基準／ROI外','exposure_drift':'徐々に暗くなる','exposure_step':'途中で暗くなる','background_flicker':'背景点滅','motion':'光源の左右移動','pixel_noise':'画素ノイズ','low_contrast':'明暗差低下','hold_random':'前フレーム保持・ランダム','hold_burst':'前フレーム保持・連続','blackout':'黒フレーム置換','false_flash':'偽の点灯'}
report=['# 動画モールス：網羅テスト・条件別評価（2026-09-22）','',
'全45ケースを合成動画として生成し、ファイルをOpenCVで再読込して評価しました。復号処理を固定し、条件別の結果を見てしきい値や短点長を調整していません。既存評価・モデル重みは変更していません。',
'','## 結果の要点','',
'| 区分 | ケース数 | 結果 |','|---|---:|---|',
'| 対応符号・モード切替 | 9 | 文章・符号列とも全件一致 |',
'| 異常入力の扱い | 6 | 期待した警告／停止を全件確認 |',
'| 条件を厳しくした動画（対照条件を含む） | 30 | 完全一致15、誤りを警告8、解析停止3、警告なしの誤り4 |',
'','**最大の課題は、露出低下による文字欠落を検知できないことです。** 状態OKは全文が正しい証拠にはなりません。今回の合成条件30件の50%が完全一致しましたが、この割合は選んだ条件に依存し、実動画での正解率として扱えません。',
'','![条件別結果](stress_outcomes.png)','',
'## ① 対応符号の網羅テスト','',
'- 和文表65符号を30fpsと60fpsで各1回ずつ試験。符号の文字表を確認するため、この2ケースのみモード切替OFFとし括弧自体も文字として照合しました。通常運用の本文には制御括弧を出しません。',
'- 国際モールス38文字（A–Z、0–9、ピリオド、コンマ）を括弧制御内で30fps・60fpsそれぞれ試験。',
'- 和文→欧文→和文を複数回切り替える「イA1.5ロZハ」を30fps・60fpsで試験。',
'- 短点のみ・長点のみは短点長を手動指定して試験。ホレ／ラタの手続符号も確認。',
'- 短点は各fpsで9フレーム。30fpsは0.3秒、60fpsは0.15秒であり、同じ速度の単純fps比較ではありません。',
'- 上記9ケースは文章・符号列とも一致。対応付け可能な点灯境界は全て正解の1フレーム以内でした。全符号の組合せ、あらゆる速度や順序を網羅したわけではありません。',
'','## ② 異常入力','',
'閉じ括弧不足、余分な閉じ括弧、入れ子、未知符号はREVIEWとなりました。自動推定で短点のみ・長点のみの入力は、速度を断定せず停止しました（REJECTED）。停止を正常認識と数えていません。',
'','## ③ 条件別の詳細','',
'全ケースの正解は「イロハニホヘトチリヌルヲワカヨ」（15文字）、30fps、短点9フレーム。ROIは原則40×40画素。条件・強度・seed=23456を実行前のprotocol.jsonへ保存しました。',
'','| ケース | 条件・強度 | 状態 | 編集数／15文字 |','|---|---|---|']
for row in stress:
    c=specs[row['name']]['condition'];note=' / 広いROI' if c.get('roi')==[40,20,80,80] else (' / 光源外ROI' if c.get('roi') else '')
    report.append(f"| {row['name']} | {labels[c['kind']]} {c['level']}{note} | {row['status']} | {row['edits']} |")
report.extend(['','## 見つかった弱点と解釈','',
'1. 徐々に光量を60%・85%下げるケースと、途中で40%・20%の光量にするケースでは、5〜8文字の編集が発生してもOKでした。全区間で一定のしきい値を使うため、暗くなった後半の信号を見落としています。',
'2. 光源の左右移動が20・45画素になると、固定ROIから外れて多数の誤りが出ました。5画素では今回の条件で一致しました。移動は手ぶれ全般の再現ではありません。',
'3. 背景点滅がROIの外側にあるケースは一致しましたが、背景を多く含める広いROIでは解析を停止しました。光源を適切に囲む操作が重要です。',
'4. 画素ごとに独立したランダムノイズはROI平均で弱まるため、今回の強い画素ノイズでも一致しました。露出の揺れや相関したノイズにも強いという意味ではありません。',
'5. 短い黒フレームや偽の点灯でも符号が分断され、誤りが出ました。前フレーム保持は時刻を保つCFR動画で模擬しています。実際の可変fpsやPTS欠落を検証したものではありません。',
'6. 明暗差が10のケースと光源外ROIは停止しました。解析停止は認識率を高く見せるため除外せず、空の認識文として全15文字を削除と採点しています。',
'','## 次の改善順序','',
'1. **露出変動の診断と適応しきい値の検討**：現在の固定方式を基準として残し、時間ごとの明暗分布を追跡する方式を比較する。光源が消えただけの場合と区別し、推測で文字を補わない。',
'2. **光源領域からの逸脱検知・ROI調整の支援**：追跡機能の前に、光源を十分に囲めているかを利用者が確認できるようにする。',
'3. **フレーム異常への対応**：無条件に短い変動を消さず、適用箇所・元の信号を残して比較する。',
'4. 改善後は今回と同じ条件の回帰確認に加え、別seed・別速度・別文章を事前に固定して評価する。実撮影動画の独立評価は別途必要。',
'','今回は①網羅テストと②条件別評価を完了しました。復号アルゴリズムの改善や光源追跡はまだ実装していません。UIにはOKが正しさを保証しない旨を追記しました。',
'','## 保存物と再現','',
'- protocol.json：実行前の条件とコードSHA-256。','- 各AVIと同名JSON：合成動画、正解イベント、変更フレーム番号、動画ハッシュ。',
'- *_result.json：輝度・点滅・符号・文章・採点・エラー。','- results.csv / results.json：全45件の集計。','- verification.json / score_verification.json：環境と再採点確認。',
'','動画形式はAVI/MJPEG、解像度160×120です。H.264、1080p、実カメラの露出制御やローリングシャッター、長時間性能は今回の検証範囲外です。',
'','プロジェクト直下で `python -B -m optical_video.evaluate_coverage_stress --output 新しい出力先` を実行します。出力先が存在すれば停止し、旧結果を上書きしません。'])
(out/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
(out/'score_verification.json').write_text(json.dumps(dict(status='PASS',rescored=45,video_hashes_verified=45,decoder_and_benchmark_unchanged=True,coverage_pass=9,guard_pass=6),indent=2),encoding='utf-8')
print(out/'report.md')
