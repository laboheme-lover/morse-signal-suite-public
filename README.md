# 和文モールス認識・送受信 / Morse Signal Suite

音声と光の和文モールス信号を認識するPCソフトと、Android向け送受信アプリの開発コードです。日本語向けの研究・試作ソフトです。

## ソフトの構成
| 対象 | 入口 | 主な機能 |
|---|---|---|
| PC音声 | outputs/morse-ai/app.py | 録音ファイル、M3、候補・区間音声・結果保存 |
| PC光 | optical-ml/app.py | 動画、光源候補と緑枠、周期推定、光CNN、候補修正 |
| PC動画分割 | optical-batch-test/pc/app.py | 長い試験動画を送信単位へ分割 |
| Android交信 | android-morse/app/ | 音・ライト送信、録音・動画・マイク・カメラ受信 |
| Android光試験送信 | android-morse/opticaltest/ | 試験単位選択、連続送信、進捗、遠隔開始 |

音声はM3＋baseline＋和文のみ（丸括弧内も和文）。RMS包絡を入力する複数幅1D-CNN＋双方向GRU、65クラスです。光はOpticalCNNと周期自動推定・入力時間補正を使います。

## PC版の起動
Python 3.11を用意し、リポジトリ直下で実行します。
```powershell
git clone https://github.com/laboheme-lover/morse-signal-suite-public.git
cd morse-signal-suite-public
py -3.11 -m venv .venv
.venv/Scripts/python.exe -m pip install -r ci/requirements-web.txt
.venv/Scripts/python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python.exe -m streamlit run outputs/morse-ai/app.py --server.address 127.0.0.1 --server.port 8501
```
光認識は最後のコマンドを次へ変更します。
```powershell
.venv/Scripts/python.exe -m streamlit run optical-ml/app.py --server.address 127.0.0.1 --server.port 8504
```
動画分割は `optical-batch-test/pc/app.py` を指定します。動画変換・切出しには別途FFmpegが必要です。旧開発環境を指すパスが一部に残るため、新しいPCで全機能が無設定で動く配布パッケージではありません。公開版のテスト用依存は `ci/requirements*.txt` を使います。各フォルダの旧requirementsや説明には開発当時の版も残っています。

## Android版
交信アプリは0.5.0。Javaによる音声M3・光CNNの推論実装と重みを含みます。JDK17、Android SDK、Gradleを使用します。
Windows向け準備・構築は `android-morse/tools/setup_environment.py`、`build.py`、`deploy.py` と `android-morse/README.md` を参照してください。環境準備はSDK等のダウンロードと利用条件への同意を伴うため、実行前にスクリプトを確認してください。
APK、署名鍵、SDKは含みません。Playストア公開版やiPhone版ではありません。光試験送信用の `assets/batches.json` は原稿を含むため除外しています。利用権限のある原稿から別途用意してください。

## テスト
```powershell
.venv/Scripts/python.exe ci/run_tests.py
.venv/Scripts/python.exe ci/test_web.py
# JDK17のjava / javacをPATHへ追加
.venv/Scripts/python.exe ci/test_android_core.py
```
GitHub Actionsはpush・Pull Request・手動実行に対応し、Windows/Linuxの基礎テスト、Web操作ロジック、Java共通処理を検証します。認識率の評価やAndroid実機試験ではありません。
2026-10-28の既存記録ではSH-51Fで交信アプリ31項目、音声M3 65ベクトル・光CNN 130ベクトルの照合を確認しています。実マイク・カメラ、実送信、Bluetooth 2台間通信、通話中の動作・遅延・発熱は別途確認が必要です。PCの評価値をスマホ性能として扱いません。

## 公開範囲・利用条件
- 自作コードはMITライセンスです。LICENSEを参照してください。
- 重み（.pt、モデル・フィルター.bin）はMIT対象外です。MODEL_USAGE.mdを参照してください。
- 第三者の依存物・素材には各権利者の条件が適用されます。THIRD_PARTY.mdを参照してください。
- 実録音・実動画・加工データ・評価原稿・端末ログ・認証情報は含みません。過去の全評価は本リポジトリだけでは再現できません。

公開版は2026-11-10に非公開開発版91977a4を基に作成した、過去のGit履歴を引き継がないスナップショットです。個人用パスと非公開評価メタデータを除去しました。重みは変更していません。音声の公開用整合性マニフェストは公開ファイルだけで再作成し、元評価時の保存版と区別しています。
GitHubへの公開はWebアプリの常設やスマホへの自動インストールではありません。利用者のPC・端末で実行します。

## オンライン試用版の準備
無料のStreamlit Community Cloudへ配備する入口を追加しました。音声は `cloud/audio_app.py`、光は `cloud/optical_app.py` です。所有者のログイン後に配備する手順と制限は [cloud/README.md](cloud/README.md) を参照してください。配備完了の公開URLは確認後に追記します。
