# Phase 1 — モールス音声データ生成・管理基盤

対象は**国際モールスA–Z／0–9の36クラス・1 WAV＝1符号**です。M0–M4のモデル本体・学習・精度比較は実装しません。PyTorch/TensorFlowなしで、音声・ラベル・Splitを返す共通インターフェースを提供します。

## 今回のデータ

| Split | 既存再利用 | 新規生成 | 合計 | 1クラス |
|---|---:|---:|---:|---:|
| Train | 11,160 | 6,840 | 18,000 | 500 |
| Validation | 2,340 | 1,260 | 3,600 | 100 |
| Test | 1,620 | 0 | 1,620 | 45 |

元データの44,525件を監査しました。既存和文65クラスのうち、英数字と符号が一致する36クラスを再利用しています。例：元ラベル「イ」の `.-` を国際モールスのAとして扱います。音声は1符号なので波形の意味をこの対応で一意に決められます。「゛」の `..` はIに対応します。**原文の和文テキストを英訳したわけではありません。** 元ラベル・符号・変換方針をCSVに残し、WAVや元metadataは一切書き換えていません。

Train/Validationは `../data/dataset/continuous_v1`、共通評価Testは `../data/dataset/m4_300/test` を参照します。`m4_smoke` は監査対象で、採用データには含めません。旧データ全体のTest 3,022件をハッシュ固定し、その中の36クラス1,620件を共通評価に使用します。Testは再生成しません。

これは既存の評価履歴があるSynthetic Testです。「新規に収集した未見実録音Test」ではありません。固定Testの既存周波数帯は主に600–800Hzで、新しい400–1200Hzの全範囲を評価できるとは限りません。M1–M4はこの同じ評価インデックスを使い、Testで学習やハイパーパラメータ選択をしないでください。

## フォルダ

```text
phase1_data/
  config/config.yaml           # JSON構文で書いた有効なYAML 1.2（追加依存なし）
  config/morse_table.json       # 既存の欧文・数字表から抽出した中央定義
  src/                         # 音声・ノイズ・監査・保護・管理・可視化
  scripts/                     # CLI
  tests/                       # 単体テスト
  data/generated/train/        # 追加WAV
  data/generated/validation/   # 追加WAV
  metadata/train.csv           # 学習専用インデックス
  metadata/validation.csv      # 検証専用インデックス
  metadata/test.csv            # 作成後固定の評価専用インデックス
  metadata/metadata.csv        # 閲覧用の統合metadata。学習用には使わない
  metadata/existing_*.csv      # 既存データの採用基準を固定
  metadata/generated/         # バッチ・Split別の追記metadata
  metadata/runs/              # 実行時config、ソフトウェア版、ソースSHA-256
  reports/dataset_audit.csv
  reports/dataset_audit_summary.txt
  reports/test_manifest.csv   # 旧Test全件のSHA-256基準。上書きしない
  reports/test_lock.json
  reports/evaluation_index_lock.json
  reports/leakage.csv
  reports/class_counts.csv
  reports/figures/            # 波形・スペクトログラム・4種の分布
```

既存WAVを `data/existing` や `data/test` にコピー・移動する代わりに、元の場所を読み取り専用で参照します。Testフォルダに新しいファイルを生成する機能はありません。既存ファイルの上書き・ディレクトリ初期化・削除処理はありません。

## 環境・実行

Python 3.11以上、NumPy、SciPy、soundfile、matplotlibを使用します。既存 `morse-ai/.venv` の導入済みライブラリで実行できます。追加インストールは行っていません。`requirements.txt` は今回の主要ライブラリの版です。

PowerShellで**この `phase1_data` フォルダ**を開きます。

```powershell
# 既存および生成済みWAVの実体を検査。初回だけTest基準を作成、以後照合。
..\.venv\Scripts\python.exe -B -X utf8 scripts/audit_dataset.py

# 監査済み既存データから固定インデックスを作成／照合
..\.venv\Scripts\python.exe -B -X utf8 scripts/prepare_dataset.py

# 不足数だけを表示（ファイルを作成・更新しない）
..\.venv\Scripts\python.exe -B -X utf8 scripts/generate_dataset.py --dry-run

# 不足分を生成。今回の目標達成後は0件となる。
..\.venv\Scripts\python.exe -B -X utf8 scripts/generate_dataset.py

# 全採用WAVのハッシュ・リーク・Seed再現を確認し、PNGも生成
..\.venv\Scripts\python.exe -B -X utf8 scripts/verify_dataset.py --figures

# 単体テスト
..\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v
```

任意の別設定ファイルは `--config path/to/config.yaml`、少数生成は `--limit 10`。設定内の既存ソースパスはconfigの置き場所ではなく `phase1_data` を基準に解決します。監査と保護、既存インデックス公開を先に実施してください。既存データやSplit採用基準が変わる場合、固定基準を自動で作り直すことはありません。別の実験ディレクトリとして設計し直してください。

## 設定

`config/config.yaml` はJSON構文で記述したYAML 1.2サブセットです。標準Pythonのjsonで読み込むため、引用符・カンマを保持して編集します。インデント形式の一般YAMLを読み込む実装ではありません。追加のYAMLパッケージを導入せずに動かせるよう、この形式を選びました。

- `sample_rate`：16,000Hz。WAV、mono、PCM16。
- `frequency.min/max`：400–1200Hz。
- `dot_duration_ms.min/max`：60–180ms。
- `amplitude.min/max`：0.2–1.0（混合前の信号振幅）。
- `timing_jitter.min/max`：-0.10～+0.10。±0.20、±0.30も指定可能。
- `noise_types`：`none`、`gaussian`、`white`。
- `snr_db`：20、10、5、0、-5。
- `samples_per_class`：Train目標500、`validation_samples_per_class`：Validation目標100。既存件数を含む目標です。
- `random_seed`：12345。Split・ラベル・生成番号・合成条件から独立したSeedを派生。

目標数を1,000へ増やせば不足Trainだけを追記します。目標を下げても削除しません。条件を変えても、目標数に既に達していれば生成は0件です。条件違いの実験には別実験としてデータ版を管理してください。既存の固定クラス順・Test基準・既存サンプルレートとの整合性を壊す変更は検査で停止します。

## 信号・ノイズ

国際モールス表は既存 `mixed_morse.py` のLATINと `morse_table.py` のDIGITSから抽出し、`config/morse_table.json` で一元管理します。単体テストで既存表との一致を検査します。A–Z／0–9以外を黙って変換しません。

時間構造は短点1、長点3、符号内1、文字間3、単語間7単位です。`generate_signal('A B', ...)` はスペースを7単位の単語間隔として扱います。文字間3に符号内1を加算しません。通常のデータセット生成は1符号1クラスのみです。先頭末尾に100msの余白、点灯音に5msのコサイン立ち上がり／立ち下がりを設定できます。時間変動はON/OFF区間ごとに適用し、サンプル境界をmetadataへ記録します。

`gaussian` は独立正規乱数の白色雑音、`white` は独立一様乱数の白色雑音です。「Gaussian」と「White」が排他的な物理分類であるという意味ではありません。noise_typeで乱数分布を区別します。将来の録音ノイズは `noise_generator.PROVIDERS` と同じ `(length, rng) -> mono array` インターフェースで追加できます。実録音ノイズの新規取込は今回実装せず、既存ESC-50混合WAVはそのまま再利用します。

SNRは余白を含む全録音RMS基準です。既存 `augment_audio.mix_at_snr` 関数本体を読み取り再利用し、信号と雑音を共通倍率で縮小してクリッピングを避けます。混合前amplitudeと実際の倍率mix_gainを別記録します。cleanのSNRは空欄。生成時SNRとPCM保存後SNRを両方記録します。

## Test保護とリーク

`reports/test_manifest.csv` はfilename、元ラベル、対応後ラベル、SHA-256、SR、durationを記録し、`test_lock.json` がmanifest自身のハッシュを固定します。後続の検証で削除・変更・追加・インデックス改変を検出します。自動的なTest修復・再生成はありません。ファイルシステムACLを変更していないため、外部ツールによる変更そのものを物理的に禁止する仕組みではなく、検出して停止する仕組みです。

WAV全体ハッシュに加え、復号PCMとSR・shapeのハッシュでも検査します。Test由来波形のTrain混入、採用Split間の同一音声、同一波形の矛盾ラベル、採用Split間のESC-50元録音重複はERROR。ファイル名が同じでも内容が異なる場合はWARNINGです。既存監査の23警告は名前一致のみで、音声ハッシュのSplit間重複ではありません。

生成先はこのプロジェクトの `data/generated/train` と `validation` に限定し、Test・既存データ・ルート外・リンク経由の書込みを拒否します。同名ファイルがある場合 `_extra1` 等を付けます。既知WAVと同一の生成結果は追記前に拒否します。失敗時のWAVやmetadataを自動削除しません。プロセス強制終了で `.generation.lock` が残った場合は、実行中プロセスと途中出力を確認してから手動で対処してください。未登録WAVは監査で検出します。

## モデル共通の読み込み

`phase1_data` をPythonの検索パスへ追加して利用します。

```python
from src.dataset_manager import WaveformDataset

train = WaveformDataset('train')
validation = WaveformDataset('validation')
example = train[0]
# audio: np.ndarray float32 [samples]
# sample_rate, label, label_index, split, sample_id, path

# 明示的に評価用途と指定した場合のみTestを開く
test = WaveformDataset('test', purpose='evaluation')
```

波形は可変長です。モデル側でバッチのpadding/maskを用意してください。訓練用読み込みは `metadata/train.csv` とラベル順のみを読み、統合metadata・Testインデックス・Test音声を参照しません。モデル非依存で、テンソル変換やネットワークは含みません。学習用としてTestを要求すると例外になります。

## 再現性・確認資料

同じ合成config・Seed・ソフトウェア版ならWAVのバイト列を再現します。生成日時とバッチ名は毎回変わるため、metadataファイル全体のバイト一致を主張しません。生成済みの各WAVは保存したSeedと実行時configで再生成し、SHA-256を確認できます。NumPy、SciPy、soundfile/libsndfile、Python、生成コードと既存SNR関数のハッシュを保存しています。

`reports/figures` のPNGは人間による品質確認用で、学習入力には使いません。Waveform/Spectrogramの対象ファイルは `figure_provenance.json`、分布は採用インデックスを対象にしています。周波数・SNR分布はmetadataの生成条件であり、WAVから推定した値ではありません。

`reports/phase1_completion.md` に実測件数、単体テスト、保護・再現性確認、制限とPhase 2への引き継ぎを記録します。

時間比率と英数字符号の確認元：[ITU-R M.1677-1（Annex 1, Part I）](https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.1677-1-200910-I!!PDF-E.pdf)。2026-09-22確認。
