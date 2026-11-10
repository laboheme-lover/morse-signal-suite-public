# Phase 3 — M2：1D-CNN＋BiGRU

M1のCNN構成、RMS包絡の前処理、Split、Seedと学習設定をそろえ、BiLSTMをBiGRUへ変更した比較モデルです。1 WAV＝1符号の英数字36クラスが対象です。

## 共通条件

- Train 18,000件、Validation 3,600件、固定Test 1,620件。
- 16 kHz mono音声 → 300–1400 Hz帯域制限 → 20 ms窓／10 ms刻みRMS包絡 → 各音声の10/95パーセンタイルによる正規化。
- Conv1d 1→24（kernel 5）→ Conv1d 24→48（kernel 5、stride 2）→ 双方向GRU（各方向64ユニット）→ Dropout 0.15 → 36クラス。
- Seed 23456、AdamW、初期学習率0.002、batch 128、最大30 epoch、Validation lossによる学習率調整・モデル選択・早期終了。CPU 4スレッド。

M2は54,372パラメータです。M1と隠れ状態幅をそろえた比較で、パラメータ数を同一にした比較ではありません。音声の余白をCNN各層でマスクし、packed sequenceをGRUへ渡します。GRUの両方向の最終隠れ状態を分類に使用します。

`phase2_m1/m1/data.py` と `utils.py` を直接利用して、前処理・ローダー・乱数固定・指標を共通化しています。学習／評価CLIはM1の実装を基にモデルを切り替えたものです。M1のコード・重み・評価成果物には変更を加えず、そのハッシュを `reports/m1_baseline_manifest.json` に保存しました。学習時には共有コードもハッシュ記録します。

## 実行

PowerShellでこのREADMEのある `phase3_m2` を開きます。既存の `morse-ai/.venv` を使用します。

```powershell
..\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v

# 同名runがあれば停止。--run-name省略時は時刻を含む別名。
..\.venv\Scripts\python.exe -B -u -X utf8 scripts/train.py --run-name my_m2_run

# 学習・モデル選択を完了した後の評価。既存の評価結果は上書きしない。
..\.venv\Scripts\python.exe -B -X utf8 scripts/evaluate.py --run runs/my_m2_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/verify_run.py --run runs/my_m2_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/report.py --run runs/my_m2_run
..\.venv\Scripts\python.exe -B -X utf8 scripts/compare.py --m2-run runs/my_m2_run

# 16 kHz monoの1符号WAVを推論
..\.venv\Scripts\python.exe -B -X utf8 scripts/predict.py --checkpoint runs/my_m2_run/best.pt --wav 'C:\path\one_symbol.wav'
```

`config/m2.json` が設定ファイルです。比較CLIは、前処理・学習条件・Train/Validation/クラス順・TestのハッシュがM1と同じかを検証します。条件を変えた実験は、今回の同条件比較と区別してください。Testの固定件数を変更する用途は想定していません。

## 保存先

- `runs/m2_baseline_20260922/best.pt`：選択したM2の重み・設定・ラベル順。
- 同runの `history.csv`、`validation_metrics.json`、`evaluation/`：学習履歴、評価指標、全予測、混同行列、クラス別／ノイズ条件別成績。
- 同runの `phase3_report.md`、`figures/`：M2単独のレポートとPNG4種。
- `reports/comparison/comparison_report.md`：M1とM2の比較。
- 同comparisonの `metrics.csv`、`paired_outcomes.json`、`prediction_differences.csv`、比較PNG：同じサンプルでの正誤と条件別結果。
- `reports/unit_tests.txt`：12件の単体・統合テスト。

学習時にTestを開かず、別の評価CLIが評価前後に旧Test全3,022件を照合します。Test結果を基にした再学習は行いません。M1とM2は単一Seedでの基準実験であり、方式の優劣を一般化するには複数Seed・独立実録音などの追加評価が必要です。

今回のTestは既存合成音声です。文章全体の認識や、未見実録音の性能を測定したものではありません。前処理もM1と同じRMS包絡で、生波形直接入力ではありません。予測確率は正解率ではありません。

モデルの再現には `phase1_data` と `phase2_m1` を含むプロジェクトを保持してください。保存checkpointは推論用で、optimizer状態から中断学習を再開する機能は含みません。単独WAV推論では追加の学習データは不要ですが、共通モジュールへの参照が必要です。

API確認元：[PyTorch 2.14 GRU](https://docs.pytorch.org/docs/2.14/generated/torch.nn.GRU.html)。
