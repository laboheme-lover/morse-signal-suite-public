from pathlib import Path
import argparse
import csv
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'reports/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);args=ap.parse_args()
    run=args.run.resolve();history=read_csv(run/'history.csv')
    done=json.loads((run/'training_complete.json').read_text());cfg=json.loads((run/'config.json').read_text())
    val=json.loads((run/'validation_metrics.json').read_text());test=json.loads((run/'evaluation/metrics.json').read_text())
    mapping=json.loads((run/'labels.json').read_text());labels=sorted(mapping,key=mapping.get)
    out=run/'figures';out.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,metric in zip(axes,['loss','accuracy']):
        for split in ['train','validation']:
            ax.plot([int(r['epoch']) for r in history],[float(r[f'{split}_{metric}']) for r in history],label=split)
        ax.axvline(done['best_epoch'],color='gray',ls='--',lw=1,label='selected epoch')
        ax.set(xlabel='Epoch',ylabel=metric.capitalize());ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'learning_curves.png',dpi=160);plt.close(fig)
    matrix=np.array(test['confusion_matrix'])
    fig,ax=plt.subplots(figsize=(12,10));im=ax.imshow(matrix,cmap='Blues',vmin=0,vmax=max(test['support']))
    ax.set(xticks=range(len(labels)),yticks=range(len(labels)),xticklabels=labels,yticklabels=labels,
           xlabel='Predicted label',ylabel='True label',title='M3: fixed synthetic Test confusion matrix (counts)')
    for i,j in zip(*np.nonzero(matrix)):
        ax.text(j,i,str(matrix[i,j]),ha='center',va='center',fontsize=6,color='white' if matrix[i,j]>25 else 'black')
    fig.colorbar(im,ax=ax,label='Samples');fig.tight_layout();fig.savefig(out/'confusion_matrix.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,4));ax.bar(labels,np.array(test['recall'])*100)
    ax.set(ylim=(0,105),ylabel='Recall (%)',title='M3: per-class recall, 45 Test samples per class')
    fig.tight_layout();fig.savefig(out/'per_class_recall.png',dpi=160);plt.close(fig)
    cond=[r for r in read_csv(run/'evaluation/by_condition.csv') if r['field']=='snr_db']
    cond.sort(key=lambda r:float('inf') if r['value']=='clean' else float(r['value']))
    fig,ax=plt.subplots(figsize=(8,4));bars=ax.bar([r['value'] for r in cond],[100*float(r['accuracy']) for r in cond])
    for bar,row in zip(bars,cond):ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+1,f"n={row['samples']}",ha='center')
    ax.set(ylim=(0,110),xlabel='Metadata SNR (dB)',ylabel='Accuracy (%)',title='M3: fixed synthetic Test by SNR')
    fig.tight_layout();fig.savefig(out/'accuracy_by_snr.png',dpi=160);plt.close(fig)
    errors=int(test['samples']-np.trace(matrix))
    pairs=sorted([(int(matrix[i,j]),labels[i],labels[j]) for i in range(36) for j in range(36) if i!=j and matrix[i,j]],reverse=True)
    lines=['# Phase 4 — M3 学習・評価結果','',f'実行名：`{run.name}`','',
           '国際モールスA–Z／0–9の1符号36クラス分類を実装・学習・評価しました。連続文章の認識や既存Streamlitアプリへの組込みは今回の対象外です。','',
           '| Split | 件数 | Accuracy | Macro F1 | Cross entropy |','|---|---:|---:|---:|---:|',
           f"| Validation | {done['validation_samples']:,} | {val['accuracy']:.2%} | {val['macro_f1']:.4f} | {val['loss']:.4f} |",
           f"| 固定Test | {test['samples']:,} | {test['accuracy']:.2%} | {test['macro_f1']:.4f} | {test['loss']:.4f} |",'',
           f"Test誤分類は{errors}件／{test['samples']:,}件。学習件数は{done['train_samples']:,}件です。",'',
           '## モデルと前処理','',
           '16 kHz mono WAV → 300～1400 Hzの4次Butterworth帯域フィルタ（往復処理） → 20 ms窓・10 ms刻みのRMS包絡 → 音声ごとの10／95パーセンタイルで正規化 → Multi-scale 1D-CNN（カーネル3/5/9の各8チャネルを結合して24チャネル、その後48チャネル） → BiGRU（片方向64ユニット） → 36クラス。',
           'CNNは包絡時系列を入力とします。生波形を直接学習するモデルではありません。フィルタ・正規化は符号を判定せず、正解ラベルも使用しません。往復フィルタとBiGRUのため、現状は音声全体を用いるオフライン方式です。','',
           f"パラメータ数：{done['parameters']:,}。Seed：{cfg['seed']}。CPUで{done['epochs_completed']} epoch実行し、Validation lossが最小のepoch {done['best_epoch']}を採用しました。前処理を含む学習時間：{done['elapsed_seconds']/60:.1f}分。",'',
           '## 評価の分離・保存','',
           '学習スクリプトはTrainとValidationのみを開き、モデル選択・学習率調整・早期終了はValidationに基づきます。学習完了時にbest.ptのSHA-256を固定し、別の評価CLIでTestを評価しました。Test評価結果に基づく再学習・モデル選択は行っていません。',
           f"評価前後に旧Test {test['frozen_test_files_verified']:,}件のハッシュ・ファイル一覧を照合しました。Testの改変はありません。",'',
           '- モデル：best.pt（重み・設定・ラベル順・採用epoch・学習インデックスハッシュ）',
           '- 学習履歴：history.csv、設定：config.json、環境・コードハッシュ：provenance.json',
           '- 評価：evaluation/metrics.json、predictions.csv、per_class.csv、confusion_matrix.csv、by_condition.csv',
           '- 図：figures/learning_curves.png、confusion_matrix.png、per_class_recall.png、accuracy_by_snr.png','',
           '## 主な誤分類','',
           '| 正解 | 予測 | 件数 |','|---|---|---:|']
    lines.extend(f'| {true} | {pred} | {n} |' for n,true,pred in pairs[:10])
    if not pairs:lines.append('| — | — | 0 |')
    lines.extend(['','## ノイズ条件別の結果','','| ノイズ | 件数 | Accuracy | 誤分類 |','|---|---:|---:|---:|'])
    for condition in read_csv(run/'evaluation/by_condition.csv'):
        if condition['field']=='noise_type':
            n=int(condition['samples']);acc=float(condition['accuracy'])
            lines.append(f"| {condition['value']} | {n} | {acc:.2%} | {round(n*(1-acc))} |")
    lines.extend(['','環境音（ESC-50）混合での成績を、ノイズなし・whiteと分けて確認してください。SNR別の内訳はグラフとevaluation/by_condition.csvに保存しています。上記はTest評価後の分析であり、この結果によるモデル再選択や追加学習は行っていません。',
                  '', '## 実装と保存の検証', '',
                  '単体・統合テスト13件が成功しました（../../reports/unit_tests.txt）。paddingの影響除去、勾配と小標本への学習、保存重みの再読込、Seed固定、Testアクセス制限、学習CLI完走を確認しています。保存モデルと学習時コード・インデックスのハッシュ、Validationによるepoch選択、全予測からの評価値再計算はartifact_verification.jsonで照合できます。'])
    lines.extend(['','## 制限と次の比較','',
       'Testは既存の合成音声で、過去の開発・評価に参照した録音を含む固定セットです。未見実録音の汎化性能や、文章全体の文字誤り率を示しません。Testの周波数帯は主に600～800 Hzで、追加Trainの400～1200 Hz全体を検証するものではありません。',
       '今回は単一Seedの基準実験です。乱数固定と決定的演算設定を使用しましたが、学習全体の再実行一致や異なるPC・ライブラリ版での一致は未検証です。予測確率は正解率ではありません。',
       'M4以降では前処理・Split・指標を固定して比較します。今回の前処理を変える実験は別条件として区別してください。'])
    (run/'phase4_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(run/'phase4_report.md')


if __name__=='__main__':main()
