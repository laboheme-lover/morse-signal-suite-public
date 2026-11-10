# 和文モールス信号AI翻訳アプリ — Milestone 10・Streamlit

Windows / Python 3.11 向けの最小データ生成プロジェクトです。
現段階では和文1符号のWAV生成、波形・メルスペクトログラムの保存まで実装しています。
速度・周波数・振幅・タイミングのランダム化とホワイトノイズ追加にも対応しました。
ESC-50環境音の取得、fold分離、SNR指定混合にも対応しました。
WAVからPyTorch Tensorへの変換と、train/validation/test DataLoaderも実装済みです。
小型CNNの学習・評価・実録音検証、単一文字推論、連続音声推論API、Streamlit画面を実装済みです。

## アプリを起動

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

起動後は http://127.0.0.1:8501 を開き、WAV/MP3を選んで「認識する」を押します。内蔵サンプルでも試せます。
PowerShell用の run_app.ps1 も利用できます。操作方法と52テストの検証結果は `VERIFICATION_M10.md` を参照してください。

## セットアップ（PowerShell）

このREADMEのある `morse-ai` フォルダをPowerShellで開いて実行します。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Python 3.11が必要です。未導入なら [Python公式配布](https://www.python.org/downloads/windows/) から導入してください。
`setup.ps1` も上記処理を行います。仮想環境のActivateは不要で、実行ポリシーの変更も不要です。
同梱の `.venv` はこのPCの現在位置で作成したものです。移動・別PCへのコピー時はPython 3.11で再作成してください。
実測した依存パッケージ全体は `requirements-lock.txt` に記録します。再現時は `-r requirements-lock.txt` も利用できます。

## 実行

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -v
.\.venv\Scripts\python.exe -X utf8 generate_morse_audio.py --char イ --output data/clean/i.wav
.\.venv\Scripts\python.exe -X utf8 visualize_audio.py data/clean/i.wav --output-dir evaluation
```

画像は `evaluation/i_waveform_mel.png`、数値配列は `evaluation/i_mel.npy` です。
ウィンドウ表示する場合は可視化コマンドの末尾に `--show` を付けます。
別文字の例: `--char モ --output data/clean/mo.wav`。出力先を省略すると常に `data/clean/i.wav` を上書きします。

## ファイル

| ファイル | 内容 |
|---|---|
| `morse_table.py` | 和文符号表、文字正規化、1符号の取得 |
| `test_morse_table.py` | 対象文字・符号・正規化・入力エラーのテスト |
| `generate_morse_audio.py` | 1符号の音声生成とPCM WAV保存 |
| `visualize_audio.py` | 共通前処理を使う波形・メル画像、NumPy配列保存 |
| `audio_preprocessing.py` | WAV読込・メル変換・固定長Tensor化の共通関数 |
| `morse_dataset.py` | PyTorch Dataset、DataLoader、バッチ検証CLI |
| `test_audio.py` | 信号の長さ・無音・周波数・全クラス生成・WAV/Mel往復確認 |
| `requirements.txt` | Milestone 1～5の直接依存（torch CPU版を含む） |
| `requirements-lock.txt` | 実行環境の全依存バージョン |
| `setup.ps1` | Windows向けセットアップ補助 |
| `.gitignore` | 仮想環境、キャッシュ、生成データを除外 |
| `VERIFICATION.md` | 実行結果と環境の記録 |

`data/clean`、`data/noisy`、`data/dataset`、`data/ESC-50-master`、`models`、`evaluation` を用意しています。
ESC-50の取得状況は `esc50_manager.py` で確認できます。保存済みモデルは `models/saved_wabun_cnn_20260914/best_model.pt` です。

## 符号と音声仕様

- カタカナ48字（ヰ・ヱを含む）、濁点・半濁点2種、数字10種、主要記号5種、合計65クラス。
- 記号: 長音 `ー`、区切点 `、`、段落 `」`、括弧 `（` `）`。
- [無線局運用規則 別表第一号](https://laws.e-gov.go.jp/law/325M50080000017) の和文を採用。
  確認には [e-Gov XML API](https://laws.e-gov.go.jp/api/1/lawdata/325M50080000017) も使用。
- 数字は略体を使いません。英字・国際モールス・手続符号は対象外です。
- ひらがな、半角カナ、全角数字、半角括弧は正規化します。
  `normalize_text('ガ')` は `カ゛` ですが、WAV生成は1符号限定なので `ガ` を直接指定するとエラーになります。
  カナと濁点を別々に生成してください。小書き文字・漢字・空白・句点 `。` は明示的にエラーにします。
- 16,000 Hz / モノラル / PCM 16 bit、700 Hz、振幅0.7、短点0.1秒、長点0.3秒、符号内無音0.1秒。
- 前後に0.1秒ずつ無音を付加。クリック軽減用の5 msフェードを付け、符号の長さは変えません。
- `イ` (`.-`) は計0.7秒、11,200サンプル。
- メル変換は `librosa`、64バンド、FFT 512、hop 128、power=2、center=True。
  dB基準は固定値1.0、top_db=80。学習段階で同じ関数を共有する構成です。
- 可視化は時間方向を切り詰めません。DatasetはMilestone 5で512フレームに右paddingします。
  画像は確認用で、CNNへの入力に画像ファイルを使う設計ではありません。

## 次段階

Milestone 7の独立test評価まで実行済みです。精度改善後の採用モデルは `models/improved_best.pt` です。
共通validationでAccuracy 97.68%を確認しました。詳細は `ACCURACY_IMPROVEMENT.md` を参照してください。
独立testではAccuracy 97.33%、Macro F1 0.9735でした。詳細は `INDEPENDENT_TEST_REPORT.md` を参照してください。
実録音は音声と正解文の提供待ちで、まだ評価していません。

## Milestone 2: 条件の違う音声を生成

```powershell
.\.venv\Scripts\python.exe -X utf8 generate_variations.py --output-dir data/variations/my_run --labels イ モ ゜ --seed 20260914
```

3文字 × 3速度 × (clean + white noise 5条件) = 54 WAVと `metadata.csv` を保存します。
`--repeats 2` なら各文字・速度に元信号を2個生成します。出力先は新しいフォルダを指定してください。
既存フォルダへの上書きはエラーにします。途中失敗した実行は別の出力先で再実行してください。
今回の生成済みサンプルは `data/variations/m2_demo` にあります。

- `augment_audio.py`: ランダム条件生成、ホワイトノイズ、SNR混合。
- `generate_variations.py`: 少量比較実験のWAV・CSV生成。
- `test_augmentation.py`: 範囲、ジッター、周波数、SNR、量子化後SNR、seed再現、metadata検証。
- 新しい依存パッケージはありません。
- slow: 短点0.13～0.17秒、normal: 0.09～0.11秒、fast: 0.05～0.07秒。
- 周波数600～800 Hz、振幅0.4～0.9。1文字内で基準速度・周波数・振幅を固定。
- 各短点・長点・符号内無音を独立に±10%変動。サンプル単位に丸めます。
- 前後無音各0.1秒と5 msフェードは従来どおり。ホワイトノイズは無音部にも加わります。
- SNRは20、10、5、0、-5 dB。全区間（無音を含む）の平均二乗電力比で設定します。
- 混合ピークが0.98を超える場合、信号とノイズを一緒に縮小しSNRを維持します。
  `amplitude` は混合前の振幅、`mix_gain` は保存前の共通倍率です。
  `measured_snr_db` は量子化前の値。PCM16保存後の値はテストで誤差0.01 dB以内を確認しています。
- 同一 `base_sample_id` は同一元信号です。将来splitを作る際には必ず同じsplitへまとめてください。
  この段階では `split=unassigned` とし、train/validation/testの割当は行いません。

metadataには仕様の基本列（filepath、split、label、morse_code、speed、dot_duration、
frequency_hz、amplitude、noise_type、snr_db、ESC-50用の空欄4列）のほか、
seed、master_seed、base_sample_id、実際の区間長を持つtiming_samples(JSON)、サンプル数、
mix_gain、測定SNR、SNR定義、生成器・NumPyバージョン、WAVのSHA-256を保存します。
filepathはmetadata.csvのあるフォルダからの相対パスです。CSVはExcelで開きやすいUTF-8 BOM形式です。
seedは64 bit整数で、再生成にはCSVからPythonの `int` として読み込んでください。
Excelで数値として編集・再保存すると桁が失われることがあります。
同じseedと引数、同じ生成コード・依存バージョンで再現できます。

## Milestone 3: ESC-50環境音

```powershell
# 公式metadata、LICENSE、各foldの検証用2音源を取得（再実行可）
.\.venv\Scripts\python.exe -X utf8 esc50_manager.py --download --per-fold 2
# fold別の登録件数・取得件数・除外件数を表示（ネット接続不要）
.\.venv\Scripts\python.exe -X utf8 esc50_manager.py
# 新しい出力フォルダへ、最大10音源×5段階SNRの試験WAVを保存
.\.venv\Scripts\python.exe -X utf8 add_esc50_noise.py --available-only --output-dir data/esc50_my_run
```

生成済み: `data/esc50_demo/metadata.csv` と train/validation/test内の計50 WAV。
追加パッケージはありません。`test_esc50.py` を含むテストは既存のunittestコマンドで実行します。

- `esc50_manager.py`: metadata検査、公式配布の取得、split別候補、音源の切り出し。
- `add_esc50_noise.py`: 単一文字と環境音のSNR混合、少量デモ生成。
- train=fold 1～3、validation=fold 4、test=fold 5を固定。
- 公式metadata全2000行を検査し、splitをまたぐsrc_fileの全レコードを除外します。
  固定した取得版ではsrc_file `209698`、`234879` の計5音源が該当します。
  利用可能カタログはtrain 1200、validation 398、test 397です。
  同じtrain内のfold 2/3間の元音源共有は許容し、fold番号の付け替えはしません。
- 少量取得時は `--available-only` を明示します。未指定なら対象splitに音源欠損があるとエラーになります。
  実験音源は各foldのファイル名順先頭2件で、全カテゴリを代表するサンプルではありません。
- 全利用可能音源を取得する場合は `--download --per-fold 0`。
- 公式リポジトリのcommit `33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6` に取得版を固定。
  `download_manifest.json` に取得元とSHA-256を記録。中断時は同じダウンロードコマンドで再開できます。
  登録済みファイルの改変や、内容が違う既存ファイルは上書きせずエラーにします。
- 16 kHz・モノラルへ変換してランダム切り出し。要求が音源より長ければ循環反復。
  無音切り出しは最大32回選び直し、見つからなければ明示的にエラーにします。
- 混合はMilestone 2の共通関数を使用。全区間RMS基準、共通倍率でピーク0.98以下を確保します。
- metadataにESC-50 filename/category/fold/src_file、noise_seed、切り出し開始サンプル、
  反復有無、変換前sample rate、音源とカタログのSHA-256を保存します。
- 同一元モールス信号のノイズ違いは同じbase_sample_idを持ち、同じsplitに属します。
  現在のsplit別WAVは処理検証用で、モデル評価用データセットではありません。

ESC-50出典: Karol J. Piczak, [ESC-50公式リポジトリ](https://github.com/karolpiczak/ESC-50)。
データセット全体のライセンスはCC BY-NC 3.0です。取得フォルダに公式LICENSEと
個別音源の帰属情報を保存しています。配布時にはこのライセンス情報も保持してください。

## Milestone 4: 全クラスのデータセット

```powershell
# 最初に全65クラス×10件。出力先は新しいフォルダを指定
.\.venv\Scripts\python.exe -X utf8 generate_dataset.py --samples-per-class 10 --available-only --output-dir data/dataset/my_smoke
# 少量検証成功後、全利用可能ESC-50を取得（未取得の場合）
.\.venv\Scripts\python.exe -X utf8 esc50_manager.py --download --per-fold 0
# 全65クラス×300件。ESC-50の部分取得は許可しない
.\.venv\Scripts\python.exe -X utf8 generate_dataset.py --samples-per-class 300 --output-dir data/dataset/my_300
# 既存データを再検証
.\.venv\Scripts\python.exe -X utf8 generate_dataset.py --validate-only --output-dir data/dataset/my_300
```

`generate_dataset.py` の既定値は1クラス10件、seed=20260914です。
今回の生成済みデータは `data/dataset/m4_smoke`（650 WAV）と `data/dataset/m4_300`（19,500 WAV）です。
両方の全件監査が成功しています。詳細は `VERIFICATION_M4.md` を参照してください。
65クラスの標準順はmorse_table.pyの挿入順です。実際のラベルと整数の対応はlabel_mapping.jsonを参照してください。
Windowsで安全な数値フォルダ・数値ファイル名を使い、ラベルをmetadata.csvに記録します。

出力フォルダの内容:

- `metadata.csv`: 1 WAVごとの仕様必須列と、seed・波形長・区間長・元音源情報・ハッシュなど。
- `dataset_config.json`: 件数、seed、ラベル、ESC-50取得状況、除外音源、Python/NumPyバージョン、生成時コードハッシュ。
- `label_mapping.json`: 文字→クラス番号。
- `validation_report.json`: 全WAV検証結果と条件別件数、最大フレーム数。
- `train/000/...wav`、`validation/000/...wav`、`test/000/...wav`。

分割は各文字について70/15/15の最大剰余法で決定します。
10件時は7/2/1と7/1/2を交互にし、全体455/98/97件。
300件時は各文字210/45/45、全体13650/2925/2925件です。
ノイズの種類はclean/white/esc50を各splitでほぼ均等に配置し、速度3種とSNR5段階も循環配置します。
各文字・split内では条件順をseedでシャッフルします。10件では全条件の組合せを文字ごとに網羅できません。
300件はノイズ種を合計した件数で、ノイズ種ごとに300件ではありません。

各WAVは独立の元モールス信号を持ち、同じ元信号の複数ノイズ版をsplit間で共有しません。
ESC-50は既定で全利用対象音源が必要です。`--available-only` は少量動作確認用です。
取得候補のカタログは全体でもsrc_fileがsplitをまたがないよう、Milestone 3の除外規則を継承します。
CSVのseedは64 bit整数なので、Excelで数値として編集・再保存しないでください。
再現には固定した音源・ライブラリ・生成コードを用います。ESC-50の切り出しは保存されたファイル名と開始位置からも再構成できます。

全件でWAV形式、パス、ハッシュ、ラベル、条件、区間長、元信号、SNR、splitを検査します。
ESC-50を含む波形の再構成も検査し、成功後に `dataset_config.json` のstatusをcompleteにします。
中断・失敗時のstatusはgeneratingのままです。未完成データを学習に使わず、別の出力先で再実行してください。
既存出力の上書き・自動削除は行いません。

大量生成ではESC-50候補と変換済み音源をキャッシュします（音源は最大128件）。
その実行中はESC-50ファイルを差し替えないでください。
最大フレーム数は16 kHz、hop=128、center=Trueに対する `1 + samples // 128` を全WAVで集計した値です。
Milestone 5では最大439フレームを確認したうえで、固定入力長512を採用しました。

## Milestone 5: PyTorch入力

CPU版PyTorch 2.14.0+cpuを導入しました。CUDA/GPUは不要です。
新規環境は冒頭のrequirements.txtをインストールしてください。
torchvision・torchaudioは今回の前処理に使わないため導入していません。

```powershell
# 全19,500件をDataset→DataLoader経由で1周検証
.\.venv\Scripts\python.exe -X utf8 morse_dataset.py --root data/dataset/m4_300 --output-dir evaluation/m5/full --batch-size 32
# 各splitの2バッチだけ確認する場合
.\.venv\Scripts\python.exe -X utf8 morse_dataset.py --max-batches 2 --output-dir evaluation/m5/quick
```

```python
from morse_dataset import create_dataloaders
from audio_preprocessing import wav_to_tensor, PreprocessConfig

if __name__ == '__main__':
    loaders = create_dataloaders('data/dataset/m4_300', batch_size=32, num_workers=0)
    x, y = next(iter(loaders['train']))
    print(x.shape, x.dtype)  # [32, 1, 64, 512], torch.float32
    print(y.shape, y.dtype)  # [32], torch.int64
    single = wav_to_tensor('data/clean/i.wav', PreprocessConfig())
```

`MorseDataset(root, split, config)` は `(入力Tensor, ラベルTensor)` を返します。
ラベルは既存label_mapping.jsonを参照し、全splitで同じ0～64の対応を使います。
trainのみseed付きでシャッフルし、validation/testはCSV順です。`drop_last=False` で最後の端数も取得します。

前処理はaudio_preprocessing.pyに統一しました。visualize_audio.pyも同じ関数を参照し、
従来の `from visualize_audio import compute_mel_db` 等は引き続き利用できます。
将来のpredict.pyも `wav_to_tensor` / `audio_to_tensor` を利用してください。

- 16 kHz mono、64 Mel、FFT512、hop128、center=True、power=2。
- dBはref=1.0、top_db=80。今回は追加の統計正規化なし（float32のdB値）。
- 右側のみ-100 dBで512フレームまでpadding。元メルの全フレームを維持。
- Dataset初期化時に各WAVヘッダの実フレーム数を確認し、512を超える場合はエラー。
  単一ファイル用関数では `allow_truncate=True` を明示すると警告付きで末尾を切り詰められます。
  学習用Datasetはこのオプションを使わず、入力長不足を検出します。
- 検証時にpreprocessing.jsonとdataloader_report.jsonを保存。後続のモデル保存時にも
  前処理設定とラベル対応を併せて保存してください。

Windowsでは `num_workers=0` が既定です。今回の実行環境では2ワーカーを試すと
名前付きパイプ作成でWinError 5（アクセス拒否）が発生したため、複数ワーカーの実動作は未確認です。
0ワーカーで少量版・300件版の全データを検証済みです。
別の環境で複数ワーカーを使用する場合も、呼び出しは必ず `if __name__ == '__main__':` 内に置いてください。
CLIはWindowsのspawn起動・freeze_supportに対応しています。

## Milestone 6: 小型CNNと学習

```powershell
# 少量版で20エポック。出力先には新しいフォルダを指定
.\.venv\Scripts\python.exe -X utf8 train.py --root data/dataset/m4_smoke --output-dir models/my_smoke --epochs 20 --cache
# 学習テストを含む全テスト
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -q
```

今回の実行済みモデルは `models/m6_smoke/best_model.pt` です。
追加パッケージはありません。CPU、4スレッド、num_workers=0、batch_size=32、Adam、lr=1e-3、
CrossEntropyLoss、seed=20260914で学習しました。既定の入力は[1,64,512]です。

- `morse_cnn.py`: Conv2d→BatchNorm→ReLU→MaxPoolを3段（1→16→32→64）。
  AdaptiveAvgPool2d((1,16))で時間方向の位置を残し、Flatten→Linear128→ReLU→Dropout0.3→Linear65。
  パラメータ数162,993。forwardはSoftmax前のlogitsを返します。
- `train.py`: train/validationのDatasetだけを構築。test WAVの読込・モデル評価は行いません。
- validation Accuracyが厳密に更新された時だけbest_model.ptを置き換えます。同点では先に得られたモデルを保持。
- `--cache` はtrain/validationの固定TensorをRAMへ保持します。小規模データ向けで、全量学習では
  RAM使用量が大きくなるため省略できます。既存出力フォルダは上書きしません。
- 履歴history.csvは各epoch後に書き出し、モデルは一時ファイルから置き換えます。
  学習中断からの自動再開は今回の対象外です。

保存内容: best_model.pt、label_mapping.json、preprocessing.json、run_config.json、history.csv、training_summary.json。
チェックポイントにはモデル重み、optimizer状態、モデル構成、選択epoch、validation指標、
ラベル対応、前処理設定、seed・データmetadataとコードのハッシュを保存します。
チェックポイント読込は `load_checkpoint` で行い、weights_only=True、ラベル対応・前処理仕様の検査、evalモードへの切替を行います。

```python
from morse_cnn import load_checkpoint
model, preprocessing, checkpoint = load_checkpoint('models/m6_smoke/best_model.pt')
```

今回の結果: 20エポックの少量学習で、train評価Loss 4.403→2.981、train評価Accuracy 2.20%→20.88%。
best validation Accuracyは5.10%（7エポック目、5/98件）でした。これは学習・保存処理の動作確認で、
実用的な認識精度を達成したものではありません。後半はvalidationが改善しなかったため、
最終epochではなく7エポック目を保存しています。300件版での学習は今回は実行していません。
結果と制限の詳細はVERIFICATION_M6.mdを参照してください。

## 認識精度の改善実験

Milestone 6のモデルは保存したまま、300件版のtrain/validationで比較実験を追加しました。
詳細な結果は `ACCURACY_IMPROVEMENT.md` にまとめています。
採用モデルは `models/improved_best.pt`、採用情報は `models/recommended_model.json` です。
`load_checkpoint('models/improved_best.pt')` で構成と前処理を含めて読み込めます。
test WAVは今回の比較・選択にも使用しません。

```powershell
# 従来構成を300件版で5エポック学習
.\.venv\Scripts\python.exe -X utf8 train.py --root data/dataset/m4_300 --output-dir models/my_baseline300 --epochs 5 --cache
# 時間方向の受容範囲を広げた構成、位置区画32、Dropout0.1
.\.venv\Scripts\python.exe -X utf8 train.py --root data/dataset/m4_300 --output-dir models/my_temporal300 --epochs 5 --cache --variant temporal --temporal-bins 32 --dropout 0.1
# best重みから、学習率を下げて追加5エポック（Adamの状態は新規）
.\.venv\Scripts\python.exe -X utf8 train.py --root data/dataset/m4_300 --output-dir models/my_finetune --epochs 5 --cache --variant temporal --temporal-bins 32 --dropout 0.1 --lr 0.0003 --init-checkpoint models/my_temporal300/best_model.pt
# 同一validationで条件別に比較
.\.venv\Scripts\python.exe -X utf8 compare_validation.py --checkpoints models/my_baseline300/best_model.pt models/my_temporal300/best_model.pt models/my_finetune/best_model.pt --output-dir evaluation/my_comparison
```

`variant=temporal` は、入力の固定倍率1/80、周波数方向のMaxPool(4,1)、時間方向9のConvカーネルを使います。
倍率はモデルforward内で処理するため、学習・推論で違う前処理になりません。
既存のvariantを持たないチェックポイントは従来構成として読み込めます。
モデル種別、位置区画数、Dropout値はチェックポイントへ保存します。
今回の改善構成は340,433パラメータです。
`--init-checkpoint` は重みを引き継ぐ追加学習用で、データのラベル対応・前処理・モデル構成が一致しない場合はエラーになります。
学習の厳密な中断再開機能ではありません。

全量のtrain/validationを `--cache` で保持するとTensor本体だけで約2.0 GiBを使用し、
構築時はさらに作業メモリが必要です。RAMに余裕がなければこのオプションを省略してください。
比較結果はvalidationのAccuracy、Macro F1、SNR別・ノイズ別・速度別Accuracyと予測CSVとして保存します。

## Milestone 7: 固定モデルの独立test評価

`evaluate_model.py` は採用時のモデルとmetadataのSHA-256を検査し、testだけを評価します。
実行済み結果は `evaluation/independent_test` に保存しています。

```powershell
.\.venv\Scripts\python.exe -X utf8 evaluate_model.py --output-dir evaluation/my_fixed_test
```

全体Accuracy・Macro F1、SNR/ノイズ/速度別指標、予測CSV、誤認識ペア、混同行列、SNR別グラフを保存します。
今回の結果をモデルの再選択・チューニングには使用していません。
提供MP3と正解文での録音評価も実施しました。詳細は `REAL_RECORDING_REPORT.md`、結果は `evaluation/real_recording` に保存しています。
本文296文字の固定CNN正解率は48.99%、ルール方式は100%でした。本文範囲の指定にはルール方式を使用しています。
連続音声の分割は `morse_segmentation.py`、固定モデルの録音評価は `evaluate_recording.py`、補助的な本文評価は `analyze_recording_body.py` です。

## 連続速度データによる再学習

追加学習後のモデルは `models/continuous_v1/best_model.pt` です。
提供MP3の本文正解率は48.99%から91.89%、従来validationは97.68%から98.15%へ改善しました。
詳細は `RETRAINING_REPORT.md` を参照してください。今回のMP3は開発用評価であり、新モデルの独立test成績は未測定です。
旧 `models/improved_best.pt` と採用情報は従来の独立test結果の再現用として保持しています。

新規提供録音85でも固定モデルをテストしました。本文正解率93.41%（425/455）、CER6.59%。
結果は `TAMAN85_TEST_REPORT.md` と `evaluation/taman85_continuous_v1` に保存しています。

## 任意の搬送波変換

`evaluate_recording.py` に `--target-frequency-hz 700` を付けると、速度を保ったままCNN入力の搬送波を700 Hzへ移します。
元周波数は自動推定、または `--frequency-hz 3272` のように指定できます。
検証結果は `CARRIER_PREPROCESSING_REPORT.md` を参照してください。録音85では微改善しましたが、天気晴朗の録音はこの処理だけでは解読できていません。

## Milestone 8: 単一文字推論

単一文字WAVの推論は predict.py で実行できます。既定で保存済みモデルを使い、上位3候補・予測確率・メル配列を返します。--output-dir でJSON・NPY・PNGを保存します。使用例と46テストの結果は VERIFICATION_M8.md を参照してください。

## Milestone 9: 連続音声推論

predict_sequence.py で連続WAV/MP3を分割し、各文字の時刻・候補・要確認情報と認識文字列を保存します。括弧内の欧文切り替えと任意の周波数変換に対応しています。使用例、実録音の一致検証、50テストの結果は VERIFICATION_M9.md を参照してください。
