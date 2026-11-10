"""Compare frozen predictions; never train or select using Test results."""
from pathlib import Path
import argparse
import csv
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'phase2_m1'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'reports/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from m1.utils import sha,write_json,write_csv


def read_json(path):return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--m1-run',type=Path,default=ROOT.parent/'phase2_m1/runs/m1_baseline_20260922')
    ap.add_argument('--m2-run',type=Path,required=True)
    args=ap.parse_args();runs=[args.m1_run.resolve(),args.m2_run.resolve()]
    configs=[read_json(r/'config.json') for r in runs]
    second={k:v for k,v in configs[1].items() if k!='architecture'}
    if configs[0]!=second:raise ValueError('Training/preprocessing settings differ')
    provenance=[read_json(r/'provenance.json') for r in runs]
    if provenance[0]['inputs']!=provenance[1]['inputs']:raise ValueError('Train/Validation/labels differ')
    for key in ('python','torch','numpy','scipy','soundfile','device'):
        if provenance[0][key]!=provenance[1][key]:raise ValueError(f'Runtime differs: {key}')
    summary=[read_json(r/'evaluation/metrics.json') for r in runs]
    for key in ('test_index_sha256','test_manifest_sha256','samples'):
        if summary[0][key]!=summary[1][key]:raise ValueError(f'Evaluation differs: {key}')
    for run,result in zip(runs,summary):
        if sha(run/'best.pt')!=result['checkpoint_sha256']:raise ValueError('Evaluated checkpoint changed')
    baseline=ROOT.parent/'phase2_m1'
    manifest=read_json(ROOT/'reports/m1_baseline_manifest.json')
    for name,digest in manifest.items():
        if sha(baseline/name)!=digest:raise ValueError(f'Original M1 artifact changed: {name}')
    predictions=[{r['sample_id']:r for r in read_csv(run/'evaluation/predictions.csv')} for run in runs]
    if set(predictions[0])!=set(predictions[1]):raise ValueError('Test sample IDs differ')
    pair_counts={'both_correct':0,'m1_only_correct':0,'m2_only_correct':0,'both_wrong':0}
    differences=[]
    for sid,a in predictions[0].items():
        b=predictions[1][sid]
        if a['true_label']!=b['true_label'] or a['filename']!=b['filename']:raise ValueError('Sample/label mismatch')
        good1=a['true_label']==a['predicted_label'];good2=b['true_label']==b['predicted_label']
        key=('both_correct' if good2 else 'm1_only_correct') if good1 else ('m2_only_correct' if good2 else 'both_wrong')
        pair_counts[key]+=1
        if a['predicted_label']!=b['predicted_label']:
            differences.append({'sample_id':sid,'true_label':a['true_label'],'m1_prediction':a['predicted_label'],
                'm2_prediction':b['predicted_label'],'m1_correct':int(good1),'m2_correct':int(good2),
                'noise_type':a['noise_type'],'snr_db':a['snr_db']})
    out=ROOT/'reports/comparison';out.mkdir(parents=True,exist_ok=True)
    table=[]
    for name,run,test in zip(['M1','M2'],runs,summary):
        done=read_json(run/'training_complete.json');val=read_json(run/'validation_metrics.json')
        table.append({'model':name,'parameters':done['parameters'],'epochs_completed':done['epochs_completed'],
            'best_epoch':done['best_epoch'],'validation_accuracy':val['accuracy'],'test_accuracy':test['accuracy'],
            'test_macro_f1':test['macro_f1'],'test_errors':test['samples']-sum(np.diag(test['confusion_matrix']).tolist()),
            'training_seconds':done['elapsed_seconds']})
    write_csv(out/'metrics.csv',table)
    if differences:write_csv(out/'prediction_differences.csv',differences)
    write_json(out/'paired_outcomes.json',pair_counts)
    delta=(table[1]['test_accuracy']-table[0]['test_accuracy'])*100
    reduced=(1-table[1]['parameters']/table[0]['parameters'])*100
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,column,label,scale in [(axes[0],'test_accuracy','Test accuracy (%)',100),(axes[1],'parameters','Parameters',1)]:
        values=[r[column]*scale for r in table];bars=ax.bar(['M1: BiLSTM','M2: BiGRU'],values,color=['#386CB0','#1B9E77'])
        ax.set_ylabel(label);ax.set_ylim(0,110 if scale==100 else max(values)*1.2)
        for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+(1 if scale==100 else 1000),f'{value:.2f}' if scale==100 else f'{int(value):,}',ha='center')
    fig.tight_layout();fig.savefig(out/'m1_m2_comparison.png',dpi=160);plt.close(fig)
    groups=[read_csv(r/'evaluation/by_condition.csv') for r in runs]
    noise=sorted({r['value'] for r in groups[0] if r['field']=='noise_type'})
    fig,ax=plt.subplots(figsize=(9,4));x=np.arange(len(noise))
    noise_rows=[]
    for i,group in enumerate(groups):
        index={r['value']:r for r in group if r['field']=='noise_type'}
        ax.bar(x+(i-.5)*.36,[100*float(index[k]['accuracy']) for k in noise],width=.36,label=['M1','M2'][i])
        noise_rows.extend({'model':['M1','M2'][i],**index[k]} for k in noise)
    ax.set(xticks=x,xticklabels=noise,ylim=(0,110),ylabel='Test accuracy (%)',title='Same Test: performance by noise type');ax.legend()
    fig.tight_layout();fig.savefig(out/'noise_comparison.png',dpi=160);plt.close(fig)
    write_csv(out/'noise_comparison.csv',noise_rows)
    lines=['# M1・M2 比較レポート','',
        '共通のTrain 18,000件・Validation 3,600件・固定Test 1,620件で比較しました。前処理はM1の実装をそのままインポートしています。Seedと学習条件は同一で、再帰層をBiLSTMからBiGRUへ変更しました。', '',
        '| モデル | パラメータ | 採用epoch | Validation正解率 | Test正解率 | Test Macro F1 | 誤分類 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in table:lines.append(f"| {r['model']} | {r['parameters']:,} | {r['best_epoch']} | {r['validation_accuracy']:.2%} | {r['test_accuracy']:.2%} | {r['test_macro_f1']:.4f} | {r['test_errors']} |")
    lines.extend(['',f'M2とM1のTest正解率差：{delta:+.2f}ポイント。M2のパラメータ数は{reduced:.2f}%少なくなりました。', '',
        '## 同じサンプルでの正誤比較','',f"両方正解：{pair_counts['both_correct']}件。M1のみ正解：{pair_counts['m1_only_correct']}件。M2のみ正解：{pair_counts['m2_only_correct']}件。両方誤り：{pair_counts['both_wrong']}件。",'',
        '## ノイズ条件別','', '| モデル | ノイズ | 件数 | 正解率 |','|---|---|---:|---:|'])
    for r in noise_rows:lines.append(f"| {r['model']} | {r['value']} | {r['samples']} | {float(r['accuracy']):.2%} |")
    lines.extend(['','## 比較条件と制限','',
        'Train/Validationインデックス・クラス順・Testインデックス・Test manifestのハッシュ一致を確認しました。M1の既存コード・モデル・評価成果物も開始時のハッシュから変わっていません。M2はValidation lossで選択したモデルを一度Test評価し、その結果による再学習やハイパーパラメータ変更はしていません。',
        '1符号の英数字36クラス分類です。入力は帯域制限後のRMS包絡で、生波形を直接学習する方式ではありません。Testは開発・評価履歴のある既存合成音声で、未見実録音の汎化性能を表しません。',
        '比較は同じ隠れ状態幅・単一Seedです。パラメータ数を一致させた比較や複数Seedによるばらつき評価ではありません。この数値差だけで方式の優劣を一般化しないでください。学習時間は各実行時の記録であり、同時負荷を統制した速度ベンチマークではありません。', '',
        'M2の重み：../../runs/'+runs[1].name+'/best.pt。モデル別の学習履歴・混同行列・予測CSVは各runに保存しています。',
        '次の予定モデルはM3：Multi-scale 1D-CNN＋BiGRUです。今回のM2は比較の基準として保存し、M3以降も同じ前処理・Splitで評価します。'])
    (out/'comparison_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json(out/'comparison_checks.json',{'status':'PASS','identical_training_settings':True,'identical_indices':True,
        'identical_test':True,'identical_library_versions':True,'m1_preserved_files':len(manifest),'paired_samples':sum(pair_counts.values()),
        'accuracy_difference_percentage_points':delta,'parameter_reduction_percent':reduced})
    print(json.dumps({'models':table,'paired':pair_counts,'delta_pp':delta},indent=2))


if __name__=='__main__':main()
