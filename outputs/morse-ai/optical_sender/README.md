# 和文モールス点滅送信 — 第1段階

Windows PCが静的ページを配信し、同じ信頼できるWi-FiのAndroidブラウザで開きます。音声版のCNNや学習環境は使用しません。外部API・CDN・登録・追加Pythonパッケージは不要です。

## 起動と終了

PowerShellで、このフォルダの親 `morse-ai` を開いて実行します。

```powershell
# まずPCだけで確認（既定は127.0.0.1、8765）
.\.venv\Scripts\python.exe .\optical_sender\serve.py

# Wi-FiアダプターのIPv4を確認
ipconfig

# 実際のLAN側IPv4に置換してAndroidへ配信
.\.venv\Scripts\python.exe .\optical_sender\serve.py --host <PCのLAN側IPv4アドレス> --port 8765
```

`<...>` はそのまま入力せず、`ipconfig` の使用中のWi-Fi接続のIPv4アドレスに置換します。VPN・仮想アダプター・デフォルトゲートウェイのアドレスは使いません。既存の `.venv` が使えなければ、インストール済みPython 3.10以降で `python .\optical_sender\serve.py` を実行できます。

- PC自身：`http://127.0.0.1:8765/`（既定起動時）
- Android：`http://<PCのLAN側IPv4アドレス>:8765/`（LAN側IPを明示して起動した場合）
- 終了：起動したPowerShellで **Ctrl+C**。

実際のLAN側IPは今回特定していません。PCとAndroidを同じ信頼できるWi-Fiへ接続してください。接続できない場合はIP、サーバーの起動、ネットワーク分離、組織の許可を確認します。必要な通信許可は管理者のルールに従い、そのアプリ・私設LANに限定します。ファイアウォール全体の無効化、ルーターのポート開放、外部公開は行わないでください。

サーバーは `public/` の6ファイルだけを配信し、ディレクトリ一覧、別フォルダ、シンボリックリンクは配信しません。既定はPC自身のみです。`0.0.0.0`、公開IP、ホスト名、IPv6は指定できません。Python簡易サーバーを本番・インターネット公開に使わないでください。

## 送信手順

1. 画面消灯時間を送信より長く設定し、画面の向きとブラウザの表示倍率を固定します。初回は暗い背景、1m、1文字「イ」で確認します。
2. 入力して「送信内容を確認」を押します。原文から変換した表記、送信単位、符号、信号時間を確認します。キーボードやアドレスバーによる表示領域変更で予定が無効になった場合、表示を固定して再確認します。
3. 注意事項のチェックを入れ、「3秒待って送信開始」を押します。3秒の待機後、中央48×48 CSS pxの四角だけが白／黒に変化します。
4. 送信は1回だけです。最後は消灯します。「停止・消灯」は待機中・送信中とも使えます。PCではEscapeも停止します。
5. 「予定JSONを保存」と「送信ログを保存」で2つのファイルを保存します。既定のダウンロード先はブラウザ設定に依存します。入力や画面サイズの変更後は「直近の送信予定JSONを保存」から、直近の実行に対応する予定を保存できます。新しい予定と古いログを混同せず、`plan_id` の一致を確認してください。

まず1文字、その後3〜5文字。撮影側は別のスマートフォン（第一候補AQUOS R10）を使います。1mの確認後に2m・3mへ進めます。Android実機の表示・点滅・保存・撮影結果はまだ未確認です。

## 入力と固定仕様

既存 `../morse_table.py` の `MORSE_TABLE` 全65項目を自動書き出ししています。光送信はそのうち括弧2項目を除く63単位です。対応表は手作業で複製していません。

- 通常サイズのカナ（ヰ・ヱを含む）、数字0〜9、濁点・半濁点、`ー` `、` `」`。
- 既存処理に合わせNFKC→NFD、ひらがな→カタカナ、結合濁点→独立濁点へ変換。半角カナ・全角数字も変換します。例：`が` → `カ゛`、2単位。
- 小書きカナ、漢字、英字、句点 `。`、空白・改行、空入力は位置と理由を表示して拒否します。空白を勝手に取り除きません。
- 括弧 `（ ） ( )` と括弧内欧文は次段階です。符号表には括弧を残しますが、入力は拒否します。括弧やホレ／ラタ等を自動付加しません。`ホレ` を入力した場合は普通の2文字として送ります。
- 短点200ms、長点600ms、符号内200ms、文字間600ms、開始前3,000ms。速度は変更できません。
- 文字間は前の最終点灯の終了から次の点灯の開始まで600msです。200msを追加しません。濁点など別単位の間も600msです。
- 信号時間上限60,000ms（3秒待機を除く）。入力処理上限1,000 Unicode文字。どちらも超過は明示的に拒否します。

## 予定と実行ログ

`schema/transmission.schema.json` はJSON Schema Draft 2020-12で予定と実行ログを定義します。時刻はすべてms。予定の最初の点灯は0、区間は `[start_ms,end_ms)`。末尾に架空の消灯区間は追加せず、`total_duration_ms` で最終消灯処理を記録します。開始前待機は信号区間と別です。

予定には、原文、送信表記、トークンと原文位置（1始まりUnicode文字位置／0始まりUTF-16位置）、対応表SHA-256、変換版、表示寸法・色・端末倍率、タイミング、監視設定、連続区間を保存。文字間消灯の `token_index` は直前の文字に対応します。予定は送信時に複製・再帰freezeされます。

実行ログには別の `run_id`、対応する `plan_id`、ページ版、端末・ブラウザ、開始・終了日時、`performance.now()` 系の時刻、切替予定からの遅れ、終了状態と理由を保存します。開始日時は開始ボタン処理時点で3秒待機を含みます。`signal_origin_processing_time_ms` は信号の基準予定時刻で、実発光の時刻ではありません。待機中の `executed_elapsed_ms` は負になります。任意時刻の停止・初期消灯は `planned_time_ms` と `lateness_ms` がnullです。

`requestAnimationFrame` で絶対経過時間を予定と比較します。最も早い未処理の切替が50msを超えて遅れたら中断し、遅れた区間をまとめて再生しません。最終消灯の遅れも監視します。停止、ページ非表示、画面寸法・倍率・位置の変更、実行エラーでは検出時に消灯します。自動再開・自動再送はありません。リロード後は待機・消灯、未保存ログは失われます。

このログは**表示切替処理の時刻**であり、実際の発光・液晶応答・カメラに映った時刻ではありません。JavaScriptが完全停止している間の即時消灯は保証できません。50msは実験用監視値です。正解予定JSONは将来の合成動画・評価用で、受信・解析への入力にしません。

## 点滅・画面消灯について

白／黒の小領域だけを切り替え、赤色点滅・全画面点滅・アニメーション・高速文字更新は行いません。最短の点滅周期は400ms（定常的には2.5回/秒）ですが、面積・輝度・実機の条件を含む適合試験はしていません。安全性やWCAG適合を保証しません。W3Cの「1秒間に3回を超える点滅、または閾値」の基準を確認して設計しています。

Wake Lockは必須にせず使用していません。LANのHTTPでは安全なコンテキスト要件を満たさないためです。端末の自動消灯設定を利用者が確認してください。

## 再生成・テスト（morse-aiフォルダで実行）

```powershell
.\.venv\Scripts\python.exe -B .\optical_sender\tools\export_morse_table.py
.\.venv\Scripts\python.exe -B -m unittest discover -s .\optical_sender\tests -p "test_*.py" -v
node --test --test-isolation=none .\optical_sender\tests\protocol.test.js
```

JSテストにはNode.js 22以降を推奨（送信ページや配信自体にNodeは不要）。Pythonテストを先に実行すると、既存の正規化処理からJS比較用フィクスチャを生成します。NodeテストはOSの子プロセス制限を避けるため非分離モードです。追加パッケージは不要です。

サンプル：`artifacts/plan_i.json`、`plan_ii.json`、`run_virtual_i.json`。仮想時刻ログは実機の計測結果ではありません。実ブラウザで保存した検証用JSONは `artifacts/browser/` に分離します。

## 参照資料（2026-09-17確認）

- [W3C WCAG 2.2: Three Flashes or Below Threshold](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold)
- [MDN: requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame)
- [MDN: performance.now](https://developer.mozilla.org/en-US/docs/Web/API/Performance/now)
- [MDN: visibilitychange](https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event)
- [MDN: Screen Wake Lock API](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API)
- [Python: http.server](https://docs.python.org/3/library/http.server.html)

今回は動画合成・動画解析・動画CNN・リアルタイム受信を実装していません。
