# 和文65クラスでのM1〜M4比較

ユーザー指定の従来の和文Testを用いた比較実験です。実録音の推論より先に実施します。

## データとモデル

元データは `../data/dataset/m4_300`。既存の分割・WAV・正解ラベルを変更せず、Train 13,650件、Validation 2,925件、Test 2,925件を使用します。各クラスはTrain 210件、Validation/Test各45件です。和文・濁点/半濁点・数字・記号の65クラスです。

先行36クラスモデルから重みを引き継がず、M1〜M4を65出力にして新規学習します。各モデルは既存の実装をインポートします。原ファイルを変更しないため、先行モデルの再現性を保ちます。

共通RMS包絡前処理、Seed 23456、最大30 epoch、AdamW、初期学習率0.002、batch 128、CPU 4スレッドです。Validation lossで学習率を調整し、最小lossの重みを採用します。Testは学習・採用epoch選択に使用しません。

この実験のTrain/Validationは先行36クラス実験と件数・内容が異なります。36クラス実験との単純な差分を「和文への拡張だけの効果」とはみなしません。4つの65クラスモデル同士は同じデータと学習方針で比較します。

## 実装

- `prepare.py`：既存WAVのSHA-256、split間の同一音声・元ノイズ音源・base_sample_id重複を検査。インデックスとラベル順を固定。
- `common.py`：既存包絡処理とモデルを利用する65クラス用データローダー・指標。学習経路ではTestのインデックスやWAVを読みません。
- `train.py`：Train/Validationのみで新規学習。同名runの上書きを拒否。
- `evaluate.py`：4モデルの完了・最低Validation lossでの選択を確認してから、同じTestで評価。再評価による上書きを拒否。
- `report.py`：保存した評価値から比較資料・グラフを作成。
- `test_wabun.py`：65番目のクラスを含む指標、4モデルの出力・勾配・再読込・余白不変性、Test読込制限。

`metadata/lock.json`には各インデックスとクラス順のハッシュを記録します。旧Test全3,022件は既存の保護機構で評価前後に検証します。今回採点するのは、そのうち従来のm4_300 Test 2,925件です。

## 再現コマンド

このREADMEのフォルダでPowerShellを開きます。既存Python環境を使用し、追加インストールは不要です。

```powershell
..\.venv\Scripts\python.exe -B -X utf8 -m unittest test_wabun -v

# 新たな実験を実行する場合は、run名を新しくする。
..\.venv\Scripts\python.exe -B -u -X utf8 train.py --model M1 --run-name another_m1_run
```

今回の保存名は `runs/m1_wabun65_20260922` 〜 `runs/m4_wabun65_20260922` です。`evaluate.py`はこの4runを比較する専用エントリーポイントです。`prepare.py`は準備完了後の再実行を拒否します。

## 結果の場所

- `reports/comparison/report.md`：全体の比較結果と解釈。
- `reports/comparison/metrics.csv`、`conditions.csv`：全体・ノイズ・SNR・速度別。
- `reports/comparison/paired_outcomes.csv`：モデル間の同じサンプルでの正誤。
- 各runの `best.pt`：重み、構成、ラベル順、採用epochを含むチェックポイント。
- 各runの `evaluation/predictions.csv`：元ファイル、正解、予測、予測確率。
- `reports/data_audit.json`、`reports/comparison/verification.json`：データ監査・成果物の検証。

これは合成された1符号の評価です。実録音、連続文章、モード切替、文章CERは別途評価します。Testには過去の開発・評価履歴があり、モデルごとに1Seedの比較です。比較結果だけで方式の普遍的な優劣を断定しません。
