from evaluate_four import ROOT,PROJECT,read_csv,write_json,write_csv,edit_alignment,ITU
import json,os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    out=ROOT/'additional_four'
    protocol=json.loads((out/'protocol.json').read_text(encoding='utf-8'))
    prior=out/'protocol_before_user_clarification.json'
    if not prior.exists():write_json(prior,protocol)
    protocol.update(user_confirmed_convention='Parentheses switch to international Morse; they are not text in the manuscript.',
        official_mode='content_without_mode_brackets',main_score='Body CER excluding observed mode-control bracket segments. Reference retains ASCII letters, uppercased; no invented brackets.',
        supplementary_score='The retained-bracket calculation is a pre-clarification diagnostic only, not a recognition-error result.',
        legacy_comparable=False,merge_with_old40=False)
    write_json(out/'protocol.json',protocol)
    all_results=json.loads((out/'recording_results.json').read_text())
    official=[r for r in all_results if r['mode']=='content_without_mode_brackets']
    summary=[r for r in json.loads((out/'summary.json').read_text()) if r['mode']=='content_without_mode_brackets']
    write_csv(out/'official_recording_results.csv',official);write_csv(out/'official_summary.csv',summary)
    write_json(out/'official_summary.json',summary)
    for r in official:
        folder=out/f'{r["number"]:03d}'
        ref=(folder/'reference_normalized.txt').read_text(encoding='utf-8')
        text=(folder/f'{r["model"]}_content_without_mode_brackets.txt').read_text(encoding='utf-8')
        met,_=edit_alignment(ref,text)
        assert met['edit_distance']==r['edit_distance']==0
        assert met['reference_units']==r['reference_units']
    assert all(r['reference_units']==2057 and r['edit_distance']==0 for r in summary)
    boundaries=read_csv(out/'boundaries.csv')
    fig,ax=plt.subplots(figsize=(8.5,3.2),layout='constrained');ax.axis('off')
    cells=[]
    for n in (57,62,64,67):
        selected=[r for r in official if r['number']==n]
        cells.append([str(n),str(selected[0]['reference_units'])]+[f'{next(r for r in selected if r["model"]==name)["cer"]:.2%}' for name in ('M1','M2','M3','M4')])
    table=ax.table(cellText=cells,colLabels=['Recording','Reference units','M1 CER','M2 CER','M3 CER','M4 CER'],loc='center',cellLoc='center')
    table.auto_set_font_size(False);table.set_fontsize(11);table.scale(1,1.8)
    for (r,c),cell in table.get_celld().items():
        cell.set_facecolor('#dceafa' if r==0 else ('#f3f6fa' if r%2 else 'white'))
    ax.set_title('Additional real recordings: body CER\nMode-control parentheses excluded by user convention',fontsize=12)
    fig.savefig(out/'official_comparison.png',dpi=170);plt.close(fig)
    lines=['# 57・62・64・67：M1〜M4実録音の追加評価','',
        '**正式結果：4録音・2,057文字で、M1〜M4すべてCER 0%（編集誤り0）でした。**','',
        'ユーザー確認：「（）は英数字モールスを使うためのお作法であり、原稿には表示されない」。このため、音声中の括弧符号はモード切替に使用し、本文の採点文字には含めません。原稿に括弧を追加していません。','',
        '|録音|正解文字数|M1 CER|M2 CER|M3 CER|M4 CER|','|---|---:|---:|---:|---:|---:|']
    for n in (57,62,64,67):
        selected=[r for r in official if r['number']==n]
        lines.append(f'|{n}|{selected[0]["reference_units"]}|'+ '|'.join(f'{next(r for r in selected if r["model"]==name)["cer"]:.2%}' for name in ('M1','M2','M3','M4'))+'|')
    lines+=['|合計|2,057|0.00%|0.00%|0.00%|0.00%|','',
        'ルール方式も同じ4件でCER 0%でした。各モデルとも置換0・挿入0・削除0で、正規化した本文が全文一致しています。今回の4録音ではモデル間の性能差は確認できません。','',
        '## 保留原因をどう扱ったか','',
        '57・64・67は「ホレ／ラタ」の組がなく、従来の本文抽出では採点できませんでした。今回は音声に先頭HR HR＋区切り符号`-...-`、末尾に終結符号`.-.-.`があることを確認し、その間を本文として扱う条件を追加しました。和文として読むと「メ」「ン」にもなるため、本文中の同じ文字を削除せず、この先頭・末尾の構造を満たす場合に限ります。',
        f'区切り・終結の符号の位置付けは[ITU-R M.1677-1（Part II 3・5）]({ITU})に基づきます。今回の録音でその用途に使われているとの判断は、先頭・末尾の符号配置によります。正解文に合う位置を探索して切り出してはいません。',
        '62は従来の「ホレ／ラタ」で本文を抽出できます。IPCC・cm・kmなどのASCII英字を原稿の正解として受け付け、大文字へ正規化します。録音にある5組の括弧は欧文モード制御として除外します。括弧内のCNN出力は、予測した符号を欧文表へ読み替えており、ルールの正解文字で補正していません。','',
        '## 原音による確認','',
        '元MP3のハッシュを照合し、従来と同じ分割器を原音に再実行しました。4件とも全区間の開始・終了サンプルと短点長点パターンが保存済み情報と一致しました。個々のモデルで境界を変えたり、正解文を使って区間を調節したりしていません。','',
        '|録音|本文の開始秒|本文の終了秒|抽出条件|','|---|---:|---:|---|']
    for r in boundaries:lines.append(f'|{r["number"]}|{float(r["body_start_seconds"]):.3f}|{float(r["body_end_seconds"]):.3f}|{r["method"]}|')
    lines+=['','## 評価条件','',
        '- 和文65クラス版M1〜M4を固定し、新たに原音を入力して推論。追加学習・モデル変更・周波数変換なし。',
        '- 正解はNFKC、カナ大小の統一、濁点の分離、本文の空白・句読点・明示的な手続符号表記の除外。62では英字大文字化を追加。',
        '- 区切りの判定、本文の句読点除外、欧文モード切替はルールに依存。モード用括弧は本文に出さず採点対象外。',
        '- CERは総編集距離÷総正解文字数。1−CERをCNN単体の分類Accuracyとは呼ばない。','',
        '## 過去の結果との関係','',
        '従来40件の結果は変更していません。今回は本文抽出を拡張し、括弧を制御符号として除外する評価条件を明記した追加4件の評価です。従来40件は一部の原稿上の括弧も数えていたため、その数値と機械的に足した44件統合CERは作成しません。44件をまとめる場合は、同じ括弧除外方針で全件を再集計する必要があります。',
        '前回の全文・表記保持評価とも異なります。今回の0%は、以前の全文評価に誤りがあったという意味ではなく、本文抽出・正規化・モデルが異なる実験の結果です。',
        'ユーザー確認前に試算した「括弧を保持する」値は、62で10挿入でした。しかし確認いただいたお作法では本文の誤認識には当たりません。これを正式なエラー件数として扱いません。監査用の旧試算は元のCSVに残し、正式表は`official_*`に分離しています。','',
        '## 結論の範囲','',
        '同じ系列の練習音声・開発参照済み録音に対する、ルール補助を含む本文評価です。未知の送信者、強い雑音、異なる速度での性能を保証するものではありません。本文範囲の判断までCNNが学習したわけではありません。','',
        '## 保存物','',
        '- `official_recording_results.csv`：4件×M1〜M4およびルールの正式結果。',
        '- `official_summary.csv/json`：4件合計。',
        '- `057`、`062`、`064`、`067`：原稿コピー、正規化原稿、各モデルの区間予測、認識文章、編集対応表。正式文章は`*_content_without_mode_brackets.txt`。',
        '- `boundaries.csv`、各録音の`mode_controls.json`：本文範囲と制御符号の時刻。',
        '- `protocol.json`：ユーザー確認後の正式評価方針。`protocol_before_user_clarification.json`：確認前の試算方針。',
        '- `verification.json`：原音の再分割、重み・元データ保護、全試算の再採点。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json(out/'official_verification.json',{'status':'PASS','official_scores_recomputed':len(official),'recordings':4,'reference_units':2057,
        'mode_parentheses_excluded_by_user_confirmation':True,'reference_brackets_invented':False,'models_updated':False,'old40_results_changed':False})
    print('Official report saved: all four models, 2,057 reference units, zero edits.')

if __name__=='__main__':main()
