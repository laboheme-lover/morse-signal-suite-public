# Phase 5 — M4：Multi-scale 1D-CNN＋BiGRU＋Attention

M3の特徴抽出器に、マスク付きの時間Attentionを追加した英数字36クラス・1符号分類モデルです。前処理・データ分割・学習方針を引き継いでM1〜M4を比較します。

## 構造

```text
16 kHz mono WAV
 → 共通RMS包絡前処理（300–1400 Hz帯域制限、20 ms窓／10 ms刻み）
 → 各音声の10/95パーセンタイルによる正規化
 → Multi-scale Conv1d：kernel 3/5/9、各8チャネル
 → 24チャネルへ結合 → Conv1d 24→48、kernel 5、stride 2
 → BiGRU（各方向64ユニット） → 時刻ごとの128次元状態
 → Attention：Linear 128→32 → tanh → Linear 32→1
 → paddingを除いたsoftmax → 状態の重み付き平均
 → Dropout 0.15 → Linear 128→36
```

M3では両方向の最終状態を連結して分類していました。M4では全時刻の状態を学習した重みで集約します。AttentionはTransformerのMulti-head Self-Attentionではなく、単一の時間方向の加算型スコアによるpoolingです。モデル規模は58,548パラメータで、M3より4,160個増えます。

CNN・GRU・分類層は `phase4_m3/m3/model.py` の初期化処理を継承します。共有層の初期値が同じSeedでM3と一致することをテストしています。追加Attentionによって学習中の乱数消費や更新は変わるため、学習全体の状態が同じになるという意味ではありません。

Attentionの余白スコアを負の無限大でマスクし、正規化重みを0にします。有効区間の重みの合計は1です。重みはモデル内部の集約方法を表すもので、因果的な説明や正解率を表しません。

## 共通実験条件

Train 18,000件、Validation 3,600件、固定Test 1,620件。Seed 23456、AdamW、初期学習率0.002、batch 128、最大30 epoch、Validation lossによる学習率調整・早期終了・モデル選択、CPU 4スレッドです。設定は `config/m4.json` に保存します。

前処理・データローダー・指標は `phase2_m1/m1/data.py` と `utils.py` を直接利用します。学習時はTrainとValidationのみを開きます。保存したモデルを別CLIでTest評価し、評価前後に旧Test全3,022件のハッシュと一覧を検証します。

## 実行

PowerShellでこのREADMEのある `phase5_m4` を開き、既存Python環境を使用します。

```powershell
..\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v

# 同名runがあれば停止。省略時は時刻を含むrun名。
..\.venv\Scripts\python.exe -B -u -X utf8 scripts/train.py --run-name my_m4_run

..\.venv\Scripts\python.exe -B -X utf8 scripts/evaluate.py --run runs/my_m4_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/verify_run.py --run runs/my_m4_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/report.py --run runs/my_m4_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/attention_example.py --run runs/my_m4_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/compare.py --m4-run runs/my_m4_run

# 16 kHz monoの1符号WAVを推論
..\.venv\Scripts\python.exe -B -X utf8 scripts/predict.py --checkpoint runs/my_m4_run/best.pt --wav 'C:\path\one_symbol.wav'
```

既存の学習run・Test評価結果は上書きしません。checkpointには重み・設定・ラベル順が含まれます。optimizer状態からの中断学習再開は今回含みません。

## 成果物

- `runs/m4_baseline_20260922/best.pt`：選択モデル。
- 同runの `config.json`、`history.csv`、`provenance.json`、`validation_metrics.json`、`evaluation/`：設定、履歴、環境・入力・共有コードハッシュ、指標・全予測。
- 同runの `phase5_report.md` と `figures/`：M4のレポートと学習曲線・混同行列・クラス別・SNR別・Attention例。
- 同runの `attention_example.json`：事前に固定したValidation先頭サンプルのAttention重みと出典。予測の良し悪しで例を選びません。
- `reports/comparison/`：M1〜M4の比較レポート、CSV、モデル別・ノイズ別PNG、全6組の正誤比較。
- `reports/unit_tests.txt`：16件の単体・統合テスト。
- `reports/baseline_manifest.json`：開始時のM1〜M3成果物のSHA-256。

M1〜M3の既存コード・重み・評価結果を変更しません。M4の実行には `phase1_data`、`phase2_m1`、`phase4_m3` の共通モジュールも必要です。全モデル比較にはM2の保存済み結果も必要です。

## 解釈上の範囲

各モデル単一Seed・既存合成Testでの初期比較です。Testは過去の開発・評価に使用されたデータで、未見実録音の汎化性能や文章のCERではありません。前処理はRMS包絡で、生波形を直接学習する構成ではありません。前処理と双方向GRUが音声全体を扱うためオフライン用途です。

学習率調整の規則は共通でも、Validationの推移に応じて実際の学習率は異なります。構造追加に伴うパラメータ数の増加もあります。複数Seedや独立実録音の評価を行うまでは、方式の優劣を一般化しません。Test結果に基づくモデル再選択・追加学習は行いません。

連続文章の区間検出、既存Streamlitアプリへの置換、M0の新規比較実装は今回の対象外です。
