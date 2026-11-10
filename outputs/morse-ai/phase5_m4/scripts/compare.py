"""Four-model comparison of immutable, validation-selected runs."""
from pathlib import Path
import argparse
import csv
import itertools
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
from m1.utils import sha,write_json,write_csv,metrics


def read_json(path):return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def comparable_config(cfg):
    cfg=json.loads(json.dumps(cfg))
    cfg.pop('architecture',None)
    cfg['model'].pop('branch_kernels',None)
    cfg['model'].pop('attention_size',None)
    return cfg


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--m1-run',type=Path,default=ROOT.parent/'phase2_m1/runs/m1_baseline_20260922')
    ap.add_argument('--m2-run',type=Path,default=ROOT.parent/'phase3_m2/runs/m2_baseline_20260922')
    ap.add_argument('--m3-run',type=Path,default=ROOT.parent/'phase4_m3/runs/m3_baseline_20260922')
    ap.add_argument('--m4-run',type=Path,required=True)
    args=ap.parse_args()
    runs=[args.m1_run.resolve(),args.m2_run.resolve(),args.m3_run.resolve(),args.m4_run.resolve()];names=['M1','M2','M3','M4']
    configs=[read_json(r/'config.json') for r in runs]
    if any(comparable_config(c)!=comparable_config(configs[0]) for c in configs[1:]):raise ValueError('Shared settings differ')
    provenance=[read_json(r/'provenance.json') for r in runs]
    for key in ('inputs','python','torch','numpy','scipy','soundfile','device'):
        if any(p[key]!=provenance[0][key] for p in provenance[1:]):raise ValueError(f'Inputs/runtime differ: {key}')
    results=[read_json(r/'evaluation/metrics.json') for r in runs]
    for key in ('test_index_sha256','test_manifest_sha256','samples'):
        if any(r[key]!=results[0][key] for r in results[1:]):raise ValueError(f'Test differs: {key}')
    manifest=read_json(ROOT/'reports/baseline_manifest.json')
    for name,digest in manifest.items():
        if sha(ROOT.parent/name)!=digest:raise ValueError(f'Baseline artifact changed: {name}')
    predictions=[];table=[]
    for name,run,result in zip(names,runs,results):
        if sha(run/'best.pt')!=result['checkpoint_sha256']:raise ValueError('Checkpoint changed')
        rows=read_csv(run/'evaluation/predictions.csv')
        by_id={r['sample_id']:r for r in rows}
        if len(rows)!=result['samples'] or len(by_id)!=len(rows):raise ValueError('Incomplete/duplicate predictions')
        predictions.append(by_id)
        labels=read_json(run/'labels.json')
        recomputed=metrics([labels[r['true_label']] for r in rows],[labels[r['predicted_label']] for r in rows])
        if recomputed['confusion_matrix']!=result['confusion_matrix']:raise ValueError('Predictions do not match metrics')
        for key in ('accuracy','macro_f1'):
            if abs(recomputed[key]-result[key])>1e-12:raise ValueError('Metric mismatch')
        completed=read_json(run/'training_complete.json');val=read_json(run/'validation_metrics.json')
        selected=next(r for r in read_csv(run/'history.csv') if int(r['epoch'])==completed['best_epoch'])
        table.append({'model':name,'parameters':completed['parameters'],'best_epoch':completed['best_epoch'],
            'epochs_completed':completed['epochs_completed'],'validation_accuracy':val['accuracy'],
            'test_accuracy':result['accuracy'],'test_macro_f1':result['macro_f1'],
            'test_errors':len(rows)-int(np.trace(result['confusion_matrix'])),
            'training_seconds':completed['elapsed_seconds'],'selected_epoch_lr':float(selected['lr'])})
    if any(set(p)!=set(predictions[0]) for p in predictions[1:]):raise ValueError('Test sample IDs differ')
    for sid,a in predictions[0].items():
        for p in predictions[1:]:
            if any(p[sid][k]!=a[k] for k in ('true_label','filename','noise_type','snr_db')):raise ValueError('Test row metadata differs')
    pairs=[]
    for left,right in itertools.combinations(range(len(names)),2):
        row={'left':names[left],'right':names[right],'both_correct':0,'left_only_correct':0,'right_only_correct':0,'both_wrong':0}
        for sid in predictions[left]:
            a=predictions[left][sid];b=predictions[right][sid]
            good1=a['predicted_label']==a['true_label'];good2=b['predicted_label']==b['true_label']
            key=('both_correct' if good2 else 'left_only_correct') if good1 else ('right_only_correct' if good2 else 'both_wrong')
            row[key]+=1
        pairs.append(row)
    differing=[]
    for sid,a in predictions[0].items():
        guesses=[p[sid]['predicted_label'] for p in predictions]
        if len(set(guesses))>1:
            differing.append({'sample_id':sid,'true_label':a['true_label'],**dict(zip(names,guesses)),
                'noise_type':a['noise_type'],'snr_db':a['snr_db']})
    out=ROOT/'reports/comparison';out.mkdir(parents=True,exist_ok=True)
    write_csv(out/'metrics.csv',table);write_csv(out/'paired_outcomes.csv',pairs)
    if differing:write_csv(out/'prediction_differences.csv',differing)
    colors=['#386CB0','#1B9E77','#E6AB02','#984EA3']
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,column,label,scale in [(axes[0],'test_accuracy','Test accuracy (%)',100),(axes[1],'parameters','Parameters',1)]:
        values=[r[column]*scale for r in table];bars=ax.bar(names,values,color=colors)
        ax.set_ylabel(label);ax.set_ylim(0,110 if scale==100 else max(values)*1.2)
        for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+(1 if scale==100 else 1000),f'{value:.2f}' if scale==100 else f'{int(value):,}',ha='center')
    fig.tight_layout();fig.savefig(out/'model_comparison.png',dpi=160);plt.close(fig)
    noise_rows=[]
    for name,p in zip(names,predictions):
        for noise in sorted({r['noise_type'] for r in p.values()}):
            group=[r for r in p.values() if r['noise_type']==noise]
            noise_rows.append({'model':name,'noise_type':noise,'samples':len(group),
                'accuracy':sum(r['true_label']==r['predicted_label'] for r in group)/len(group)})
    write_csv(out/'noise_comparison.csv',noise_rows)
    noises=sorted({r['noise_type'] for r in noise_rows});x=np.arange(len(noises))
    fig,ax=plt.subplots(figsize=(9,4))
    for i,name in enumerate(names):
        index={r['noise_type']:r for r in noise_rows if r['model']==name}
        ax.bar(x+(i-(len(names)-1)/2)*.2,[index[n]['accuracy']*100 for n in noises],width=.2,color=colors[i],label=name)
    ax.set(xticks=x,xticklabels=noises,ylim=(0,110),ylabel='Test accuracy (%)',title='Same Test: performance by noise type');ax.legend(loc='upper left',bbox_to_anchor=(1,1))
    fig.tight_layout();fig.savefig(out/'noise_comparison.png',dpi=160);plt.close(fig)
    delta=(table[3]['test_accuracy']-table[2]['test_accuracy'])*100
    parameter_delta=table[3]['parameters']-table[2]['parameters']
    lines=['# M1・M2・M3・M4 比較レポート','',
        '同じTrain 18,000件・Validation 3,600件・固定Test 1,620件を使用した英数字36クラス・1符号分類です。', '',
        '| モデル | 構造 | パラメータ数 | 採用epoch | Validation正解率 | Test正解率 | Test Macro F1 | 誤分類 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r,structure in zip(table,['1D-CNN＋BiLSTM','1D-CNN＋BiGRU','Multi-scale 1D-CNN＋BiGRU','Multi-scale 1D-CNN＋BiGRU＋Attention']):
        lines.append(f"| {r['model']} | {structure} | {r['parameters']:,} | {r['best_epoch']} | {r['validation_accuracy']:.2%} | {r['test_accuracy']:.2%} | {r['test_macro_f1']:.4f} | {r['test_errors']} |")
    lines.extend(['',f'M4とM3のTest正解率差は{delta:+.2f}ポイント、パラメータ数の差は{parameter_delta:+,}個です。', '',
        '学習率の調整規則は共通ですが、Validationの推移に応じて実際の学習率は異なります。採用epochの学習率は'+', '.join(f"{r['model']}: {r['selected_epoch_lr']}" for r in table)+'です。固定した同一学習率スケジュールによる比較とは区別してください。', '',
        '## M4で変更した部分','',
        'M3のMulti-scale CNNとBiGRUを維持し、時刻ごとの128次元状態にLinear 128→32・tanh・Linear 32→1でスコアを付けます。paddingを除外したsoftmax重みで全時刻の状態を平均し、分類層へ入力します。M3の両方向の最終状態を連結する集約方法から変更しています。前処理・Seed・学習方針は共通です。',
        'M4はM3より4,160パラメータ増加しています。構造の追加とパラメータ数の増加を分離した比較ではありません。M3とM4の共有層が同じSeedで同じ初期重みになることをテストしましたが、学習中の乱数消費や更新は一致しません。Attentionの重みは因果的な説明ではありません。', '',
        '## 同じサンプルでの正誤比較','',
        '| 比較 | 両方正解 | 左のみ正解 | 右のみ正解 | 両方誤り |','|---|---:|---:|---:|---:|'])
    for r in pairs:lines.append(f"| {r['left']} / {r['right']} | {r['both_correct']} | {r['left_only_correct']} | {r['right_only_correct']} | {r['both_wrong']} |")
    lines.extend(['','## ノイズ別','', '| モデル | ノイズ | 件数 | 正解率 |','|---|---|---:|---:|'])
    for r in noise_rows:lines.append(f"| {r['model']} | {r['noise_type']} | {r['samples']} | {r['accuracy']:.2%} |")
    lines.extend(['','## 検証と制限','',
        'モデル選択はValidation lossのみで行い、選択後に固定Testを評価しました。Test結果による再学習・モデル選び直しはありません。Train/Validation/クラス順/Testのハッシュとライブラリ版の一致、予測CSVと集計値の整合性を検証しました。既存M1・M2・M3成果物とTestは変更していません。',
        'M4の単体・統合テスト16件に成功しました。padding不変性、全分岐への勾配、保存重みの再読込、Testアクセス制限、学習CLIの完走を含みます。',
        '単一Seedでの比較です。既存合成Testには過去の開発・評価履歴があり、未見実録音の性能や文章のCERではありません。方式の優劣の一般化には複数Seedなどの追加検証が必要です。今回の前処理はRMS包絡であり、生波形を直接学習する構成ではありません。',
        '学習時間は実行記録としてCSVに保存していますが、同時負荷を統制した速度測定ではありません。', '',
        'M4モデル：../../runs/'+runs[3].name+'/best.pt。モデル別の結果は各runのレポート、予測CSV、混同行列で確認できます。',
        'M1〜M4の単一Seedによる初期比較を完了しました。方式の優劣を判断する次の検証として、複数Seedと開発から独立した実録音での評価が必要です。'])
    (out/'comparison_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    checks={'status':'PASS','same_training_and_preprocessing_settings':True,'same_indices_and_test':True,
        'same_library_versions':True,'predictions_metrics_match':True,'baseline_files_preserved':len(manifest),
        'm4_minus_m3_accuracy_pp':delta,'m4_minus_m3_parameters':parameter_delta}
    write_json(out/'comparison_checks.json',checks)
    print(json.dumps({'models':table,'checks':checks,'pairs':pairs},indent=2))


if __name__=='__main__':main()
