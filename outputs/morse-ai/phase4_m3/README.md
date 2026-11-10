# Phase 4 — M3：Multi-scale 1D-CNN＋BiGRU

英数字A–Z／0–9の36クラス・1 WAV＝1符号を対象に、M2の最初のCNNを異なるカーネル幅の3分岐へ変更したモデルです。M1・M2の前処理、データ分割、学習条件を継承して比較します。

## モデル

```text
16 kHz mono WAV
 → 共通前処理：300–1400 Hz帯域制限、20 ms窓／10 ms刻みRMS包絡
 → 音声ごとの10/95パーセンタイル正規化
 → 並列Conv1d：kernel 3 / 5 / 9、各8チャネル、ReLU
 → 結合：24チャネル
 → Conv1d 24→48、kernel 5、stride 2、ReLU
 → BiGRU（各方向64ユニット、1層）
 → Dropout 0.15 → Linear 128→36
```

短い変化と長い変化を異なる幅の畳み込みで扱う構成です。入力は100 Hz刻みのRMS包絡で、生波形直接入力ではありません。カーネル幅は学習開始前に3・5・9へ固定し、Test結果による調整は行いません。

M2の24チャネルを3分岐へ配分するため、M3は54,388パラメータで、M2の54,372個から16個の増加です。第2畳み込み・BiGRU・分類層の構成はM2と同じです。各分岐と第2畳み込みの出力を実際の音声長でマスクし、packed sequenceをGRUへ渡します。Attentionは今回含みません。

## データ・学習条件

Train 18,000件、Validation 3,600件、固定Test 1,620件。Seed 23456、AdamW、初期学習率0.002、batch 128、最大30 epoch、Validation lossによる学習率調整と早期終了、CPU 4スレッドです。設定は `config/m3.json` に保存します。

前処理と共通ローダー・指標は `phase2_m1/m1/data.py` と `utils.py` を直接インポートします。学習スクリプトはTrain／Validationだけを読み、最小Validation lossのcheckpointを保存します。別CLIが固定Testを評価し、前後に旧Test全3,022件のハッシュ・一覧を照合します。

## 実行手順

PowerShellでこのREADMEのある `phase4_m3` フォルダを開き、既存のPython環境を使用します。

```powershell
..\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v

# 同名runの上書きは不可。省略すると時刻を含むrun名。
..\.venv\Scripts\python.exe -B -u -X utf8 scripts/train.py --run-name my_m3_run

..\.venv\Scripts\python.exe -B -X utf8 scripts/evaluate.py --run runs/my_m3_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/verify_run.py --run runs/my_m3_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/report.py --run runs/my_m3_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/compare.py --m3-run runs/my_m3_run

# 16 kHz / monoの1符号WAVを推論
..\.venv\Scripts\python.exe -B -X utf8 scripts/predict.py --checkpoint runs/my_m3_run/best.pt --wav 'C:\path\one_symbol.wav'
```

比較CLIはM1・M2の保存済み予測を読み、学習設定の共通部分、入力インデックス、Test、ライブラリ版、モデルハッシュ、予測CSVからの再集計を検査します。カーネル分岐以外の学習条件を変更した実験は、同条件比較に混ぜないでください。

## 成果物

- `runs/m3_baseline_20260922/best.pt`：重み・設定・ラベル順・採用epoch。
- 同runの `history.csv`、`validation_metrics.json`、`evaluation/`：学習履歴、全予測、条件別・クラス別成績、混同行列。
- 同runの `phase4_report.md`、`figures/`：M3単独の結果とPNG4種。
- `reports/comparison/comparison_report.md`：M1・M2・M3の比較。
- 同comparisonの `metrics.csv`、`paired_outcomes.csv`、`prediction_differences.csv`、PNG2種：同じサンプルの正誤とモデル規模・ノイズ別比較。
- `reports/unit_tests.txt`：13件の単体・統合テスト。
- `reports/baseline_manifest.json`：開始時のM1・M2成果物のSHA-256。

既存のM1・M2コード、保存モデル、評価結果を変更しません。M3のcheckpointにはoptimizer状態からの学習再開機能は含みません。推論にはプロジェクト内の共通モジュールも必要です。

## 結果の解釈

単一Seed・既存合成音声での基準比較です。未見実録音の性能や文章全体のCERを示しません。今回はM2と近いパラメータ数ですが、同じSeedでも全層が同じ初期重みになるわけではありません。比較結果は複数Seedでの優劣の一般化とは区別してください。

前処理は各音声のRMS包絡を使用し、フィルタとBiGRUが音声全体を扱うオフライン構成です。連続文章の区間検出、MP3の自動変換、既存Streamlitアプリのモデル置換は今回の対象外です。予測確率は正解率ではありません。
