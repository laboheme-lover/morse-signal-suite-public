from common import *
import os
from collections import Counter
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    out=ROOT/'reports/comparison'
    rows=read_csv(out/'metrics.csv');conditions=read_csv(out/'conditions.csv')
    old=json.loads((out/'historical_baseline.json').read_text())
    names=[r['model'] for r in rows];colors=['#3475b5','#289484','#b08042','#9864ac']
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,field,title in zip(axes,['test_accuracy','errors'],['Wabun Test accuracy (%)','Errors out of 2,925']):
        values=[float(r[field])*(100 if field=='test_accuracy' else 1) for r in rows]
        ax.bar(names,values,color=colors)
        ax.set_title(title);ax.set_ylim(0,105 if field=='test_accuracy' else max(values)*1.2)
        for i,v in enumerate(values):ax.text(i,v+(1 if field=='test_accuracy' else max(values)*.02),f'{v:.2f}' if field=='test_accuracy' else str(int(v)),ha='center')
    fig.savefig(out/'model_comparison.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5),layout='constrained')
    for name,color in zip(names,colors):
        subset=[r for r in conditions if r['model']==name and r['field']=='snr_db' and r['condition']!='clean']
        subset.sort(key=lambda r:float(r['condition']))
        ax.plot([float(r['condition']) for r in subset],[100*float(r['accuracy']) for r in subset],marker='o',label=name,color=color)
    ax.set(xlabel='SNR (dB)',ylabel='Accuracy (%)',ylim=(0,103),title='Wabun Test: white + ESC-50 noise');ax.legend()
    fig.savefig(out/'snr_comparison.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for name,color in zip(names,colors):
        h=read_csv(ROOT/f'runs/{name.lower()}_wabun65_20260922/history.csv')
        for ax,field in zip(axes,['validation_loss','validation_accuracy']):
            ax.plot([int(r['epoch']) for r in h],[float(r[field]) for r in h],label=name,color=color)
            ax.set(xlabel='Epoch',ylabel=field);ax.legend()
    fig.savefig(out/'learning_curves.png',dpi=170);plt.close(fig)
    lines=['# 従来の和文テストによるM1〜M4の比較','',
        '和文65クラス・既存Test 2,925件（各45件）で比較しました。従来のm4_300のTrain 13,650件、Validation 2,925件を使用し、4モデルを新規学習しました。旧モデル・旧Testは変更していません。','',
        '|モデル|構造|Test正解率|Macro F1|誤分類|Validation正解率|採用epoch|パラメータ数|',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    arch=['1D-CNN＋BiLSTM','1D-CNN＋BiGRU','Multi-scale CNN＋BiGRU','Multi-scale CNN＋BiGRU＋Attention']
    for r,a in zip(rows,arch):
        lines.append(f'|{r["model"]}|{a}|{float(r["test_accuracy"]):.2%}|{float(r["macro_f1"]):.4f}|{r["errors"]}|{float(r["validation_accuracy"]):.2%}|{r["best_epoch"]}|{int(r["parameters"]):,}|')
    best=max(rows,key=lambda r:float(r['test_accuracy']))
    lines+=['',f'今回のTestで最も高い値だったのは{best["model"]}です。これは単一Seedの観測結果で、方式の一般的な優位性や統計的な有意差を示すものではありません。','',
        '## 学習・評価条件','',
        '- Seed 23456、最大30 epoch、batch 128、AdamW、初期学習率0.002、weight decay 0.0001。',
        '- Validation lossに従う学習率調整と早期終了。最低Validation lossの重みを採用。',
        '- RMS包絡前処理（300〜1,400Hz、20ms窓／10ms刻み）は4モデルで共通。',
        '- 4モデルの学習と重みの固定がすべて終わってからTestを評価。Testを使った再学習・設定調整なし。',
        '- 旧データの分割を保持し、WAVハッシュ・元ノイズ音源・base_sample_idのsplit間重複を検査。',
        '- 計算を並行実行したため、学習時間は公正な速度ベンチマークとして比較しない。','',
        '## 過去の和文モデルとの参考比較','',
        f'過去の初期和文65クラスCNNの保存済み評価は{old["accuracy"]:.2%}、誤分類{old["errors"]}件です。対象Testのファイル集合と正解ラベルが今回と同じであることを確認しました。今回は過去モデルの再推論はせず、保存済み結果を引用しています。',
        '旧モデルはメルスペクトログラムを使い、学習条件も異なります。M1〜M4同士の共通条件比較と、旧モデルとの差は区別してください。後から保存された別の和文モデルの結果ではありません。','',
        '## ノイズ条件別','', '|モデル|ノイズ|件数|正解率|','|---|---|---:|---:|']
    for r in conditions:
        if r['field']=='noise_type':lines.append(f'|{r["model"]}|{r["condition"]}|{r["samples"]}|{float(r["accuracy"]):.2%}|')
    lines+=['','## 各モデルで多かった誤分類','', '|モデル|正解 → 予測|件数|','|---|---|---:|']
    for name in names:
        predictions=read_csv(ROOT/f'runs/{name.lower()}_wabun65_20260922/evaluation/predictions.csv')
        counts=Counter((r['label'],r['predicted_label']) for r in predictions if r['correct']=='0')
        for (true,pred),count in counts.most_common(5):lines.append(f'|{name}|{true} → {pred}|{count}|')
    lines+=['','## 同じ音声での正誤の違い','', '|比較|両方正解|左のみ正解|右のみ正解|両方誤分類|','|---|---:|---:|---:|---:|']
    for r in read_csv(out/'paired_outcomes.csv'):
        lines.append(f'|{r["left"]} / {r["right"]}|{r["both_correct"]}|{r["left_only"]}|{r["right_only"]}|{r["both_wrong"]}|')
    lines+=['','## 結果の範囲','',
        'これは1文字に分割済みの合成音声の分類評価です。ESC-50の環境音を含みますが、モールス信号そのものの実録音評価ではありません。連続文章の分割、和文／欧文モードの切替、文章のCERは別途評価が必要です。',
        'このTestには以前の開発・評価履歴があります。完全に未知のデータへの汎化性能とは区別します。今回のモデル比較は各1Seedで、複数Seedによる再現性評価は未実施です。',
        '先行の英数字36クラス比較とはクラス数だけでなくTrain/Validationの内容と件数も違うため、両実験の正解率の差をクラス数だけの効果として解釈できません。',
        'ユーザーの希望に沿って和文テストを先に実施しました。実録音の推論はまだ実施していません。','',
        '## 保存内容','',
        '`metrics.csv`：比較集計、`conditions.csv`：条件別、`paired_outcomes.csv`：同じTest上の正誤比較、`verification.json`：保護・再集計検証。',
        '各runの`best.pt`、`history.csv`、`config.json`、`evaluation/predictions.csv`、`evaluation/per_class.csv`に重み・設定・全予測を保存しています。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    earlier=(PROJECT/'phase5_m4/reports/モデル比較と仕組みの解説.md').read_text(encoding='utf-8')
    explanation=earlier[earlier.index('## 2.'):earlier.index('## 9.')]
    for old_count,new_count in [('68,964','72,705'),('54,372','58,113'),('54,388','58,129'),('58,548','62,289')]:
        explanation=explanation.replace(old_count,new_count)
    explanation=explanation.replace('英数字36クラス','和文65クラス').replace('36候補','65候補')
    # Historical ranking cannot be carried into the new Wabun experiment.
    explanation=explanation.replace('今回の固定合成TestではM2が最も高い正解率でした。ただし1回の学習結果であり、', '以下の数値は今回の和文65クラス実験で確認します。1回の学習結果だけで、')
    explanation=explanation.replace('固定合成Testの正解率はM2を下回りました。', '性能の変化は後述の和文Testの実測値で判断します。')
    guide=['# 高校生向け：和文モールス認識M1〜M4の仕組みと比較','',
        '2026年9月22日・和文65クラス実験版。先行の英数字36クラス実験とは別に、従来の和文データで学習・評価した結果を説明します。','',
        '## 1. 何を比べたのか','',
        '1文字分のモールス音声を聞いて、和文・数字・記号など65種類のどれかを当てる4つの方法を比べました。文章の意味を理解するモデルではありません。短点「・」と長点「－」の長さ、順番、間隔から特徴を学びます。',
        '全モデルに同じ練習問題（Train 13,650件）と確認問題（Validation 2,925件）を使い、最後に同じ本番問題（Test 2,925件）で採点しました。本番問題の答えを使った追加学習はしていません。','',explanation,
        '## 9. 和文65種類での実測結果','', '|モデル|正解率|誤分類 / 2,925件|パラメータ数|','|---|---:|---:|---:|']
    for r in rows:guide.append(f'|{r["model"]}|{float(r["test_accuracy"]):.2%}|{r["errors"]}|{int(r["parameters"]):,}|')
    guide+=['',f'今回のTestで最も高い値は{best["model"]}でした。ただし、乱数の出発点を変えて繰り返した実験ではありません。順位がいつも同じになるとは限りません。',
        'パラメータとは学習で調整する数値です。数が多いほど必ず成績がよくなるわけではありません。Accuracyは正解件数÷全件数です。画面に出る1件の予測確率は、この正解率とは別の値です。','',
        '## 10. このテストで分かること・今後確認すること','',
        '今回分かるのは、以前から用意していた合成音声を1文字ずつ分類する成績です。雑音を加えた音声も含みます。実際の録音には反響、圧縮、音量変化、区切りの曖昧さなどがあるため、別に試す必要があります。',
        '長い録音を文字ごとに区切る処理が間違うと、分類モデルがよくても文章全体の認識は失敗します。そのため、単文字の正解率と、文章の文字誤り率（置換・挿入・削除を数えるCER）を分けます。',
        '以前の和文モデルの97.33%は同じTestでの参考値ですが、メルスペクトログラムという別の入力表現と異なる学習条件を使っています。今回の4モデル同士ほど条件を揃えた比較ではありません。',
        '今後は和文対応の保存モデルを固定し、実録音で比較します。今回、実録音の推論はまだしていません。','',
        '詳しい条件、ノイズ別の結果、誤分類例は同じフォルダのreport.mdに保存しています。説明はモデル実装と学習・評価記録に基づきます。']
    (out/'高校生向け_和文65モデル比較.md').write_text('\n'.join(guide)+'\n',encoding='utf-8')
    print('Saved comparison report and 3 figures.')

if __name__=='__main__':main()
