# Phase 2 — M1：1D-CNN＋BiLSTM

Phase 1の共通ローダーと固定Splitを利用した、国際モールスA–Z／0–9の36クラス分類モデルです。1ファイル＝1符号が対象です。学習・評価・1ファイル推論のCLIを実装しています。

既存Streamlitアプリの和文モデルの置換や、連続音声の文字区間検出は行いません。既存データ・Phase 1のコード・Testを変更しません。

## 入力と構造

```text
16 kHz mono WAV（Phase 1のWaveformDataset、ハッシュ照合あり）
  → 固定前処理：300–1400 Hz帯域制限、20 ms窓／10 ms刻みRMS
  → 音声ごとの10/95パーセンタイルによる振幅正規化、0–2へクリップ
  → Conv1d 1→24, kernel=5, stride=1 + ReLU
  → Conv1d 24→48, kernel=5, stride=2 + ReLU
  → BiLSTM, hidden=64（各方向）, 1層
  → Dropout 0.15 → Linear 128→36
```

学習可能パラメータは68,964個。CNNへの入力はRMS包絡の時系列です。生波形を直接CNNへ入力する方式と区別してください。前処理は正解ラベルや符号表で文字判定をせず、各WAVだけから決定します。Train全体やTestから推定した統計量も使いません。往復フィルタと双方向LSTMを使用するため、現状はオフライン処理です。

可変長入力はバッチ内でpaddingし、各CNNの出力でマスクを適用した後、packed sequenceとしてBiLSTMへ渡します。全体を固定時間へ引き伸ばしません。出力はラベル別logit、推論時のみsoftmaxで確率へ変換します。

モデル比較ではこの前処理も固定します。将来、生波形直接入力や異なる前処理を試す場合は、モデル構造変更と分けて記録してください。

## 学習条件

`config/m1.json` から変更できます。標準設定はSeed 23456、AdamW、初期学習率0.002、weight decay 0.0001、batch 128、最大30 epoch、勾配クリップ5です。Validation lossが改善しない場合は学習率を半減し、7 epoch連続で改善しなければ終了します。最小Validation lossの重みを採用します。CPUの4スレッドを利用します。

Train 18,000件、Validation 3,600件をすべて読み込みます。前処理した配列はそのプロセスのメモリに保持します。学習スクリプトはTestインデックス・Test manifest・Test音声を読みません。Test 1,620件の評価は学習後に別スクリプトで実行します。

## 実行方法

PowerShellでこのREADMEがある `phase2_m1` フォルダへ移動してください。既存の `morse-ai/.venv`（Python 3.11 / PyTorch CPU）を利用できます。追加インストールは不要でした。

```powershell
# 単体テスト
..\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v

# 学習：同名のrunがある場合は停止。省略時は時刻を含む別名になる。
..\.venv\Scripts\python.exe -B -u -X utf8 scripts/train.py --run-name my_m1_run

# Validationで確定したモデルを固定Testで評価
..\.venv\Scripts\python.exe -B -X utf8 scripts/evaluate.py --run runs/my_m1_run

# 学習曲線・混同行列・クラス別・SNR別グラフと報告書
..\.venv\Scripts\python.exe -B -X utf8 scripts/report.py --run runs/my_m1_run

# 保存モデル・選択epoch・予測CSVと集計値の整合性
..\.venv\Scripts\python.exe -B -X utf8 scripts/verify_run.py --run runs/my_m1_run

# 1符号のWAVを推論（16 kHz / monoを要求）
..\.venv\Scripts\python.exe -B -X utf8 scripts/predict.py --checkpoint runs/my_m1_run/best.pt --wav 'C:\path\one_symbol.wav'
```

MP3や連続文章を上の推論CLIへ直接渡すことは想定していません。予測上位5候補を表示します。予測確率は正解率ではありません。

## 保存物

```text
config/m1.json               設定
m1/                          データ前処理、モデル、評価関数
scripts/                     学習／評価／レポート／1ファイル推論
tests/                       padding、勾配、保存読込、分離などの検証
reports/                     実装検証記録
runs/<run-name>/
  best.pt                    Validationで選択した重み＋設定＋ラベル順
  config.json, labels.json    実行時の設定とクラス順
  provenance.json            環境版、入力インデックスとコードのSHA-256
  history.csv                各epochのTrain／Validationの指標
  training_complete.json     採用epoch、モデルハッシュ、実行時間
  validation_metrics.json    採用モデルのValidation指標
  evaluation/                Test指標、全予測、条件別・クラス別成績
  figures/                   PNGグラフ4種
  phase2_report.md            実測結果の日本語報告書
```

評価は学習完了記録のモデルハッシュを確認し、既存評価結果を上書きしません。評価前後に旧Test全3,022件をPhase 1のmanifestと照合します。保存するのは推論用の選択モデルです。中断した学習のoptimizer状態からの再開機能は今回含みません。

## 再現性と評価の範囲

Python／NumPy／PyTorchの乱数を固定し、PyTorchの決定的演算を要求します。同一Seedでも異なるOS・PyTorch版・CPU／GPU間で完全一致を保証するものではありません。モデルと前処理の設定はcheckpointに含めるため、別途設定を推測せず推論できます。

Testは過去の開発・評価で使われた既存合成音声です。「完全な未見実録音の性能」とは扱えません。Accuracyは1符号の36クラス分類であり、和文文章全体のCERではありません。前処理・ハイパーパラメータの選択にTest結果を使用しないでください。

API確認元：[PyTorch LSTM](https://docs.pytorch.org/docs/2.14/generated/torch.nn.LSTM.html)、[PyTorch 再現性](https://docs.pytorch.org/docs/2.14/notes/randomness.html)。

## 実装の確認資料

`reports/unit_tests.txt` に10件の成功記録、`reports/environment.json` に実行環境を保存しています。`reports/frontend_examples.png` はTrainのA（`.-`）について、ノイズなしとSNR −5 dBでの波形・前処理後の入力を並べた図です。対象ファイルとハッシュは同名のJSONに記録しています。

```powershell
# 前処理の確認図を再作成（Trainのみ）
..\.venv\Scripts\python.exe -B -X utf8 scripts/inspect_frontend.py
```

標準の完了実験は `runs/m1_baseline_20260922` です。実測結果は同フォルダの `phase2_report.md` を参照してください。
