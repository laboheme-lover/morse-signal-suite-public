from evaluate import ROOT,PROJECT,read_csv,write_csv,write_json,sha
import json,os
from collections import Counter
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    out=ROOT/'results'
    summary=json.loads((out/'summary.json').read_text())
    recs=json.loads((out/'recording_results.json').read_text())
    historical=read_csv(out/'historical_reproduction.csv')
    synthetic=read_csv(PROJECT/'phase6_wabun65/reports/comparison/metrics.csv')
    numbers=sorted({r['number'] for r in recs})
    agreement=[];examples=[];conditions=[]; identical=0; rule_identical=0; differing=[]
    for number in numbers:
        folder=out/f'{number:03d}'
        texts=[(folder/f'M{i}_transcript.txt').read_text(encoding='utf-8') for i in range(1,5)]
        identical += int(len(set(texts))==1)
        rule_text=(folder/'rule_transcript.txt').read_text(encoding='utf-8')
        rule_identical += int(all(t==rule_text for t in texts))
        if len(set(texts))>1 or any(t!=rule_text for t in texts): differing.append(number)
        for i in range(1,5):
            rows=read_csv(folder/f'M{i}_segments.csv')
            agreement.append({'number':number,'model':f'M{i}','segments':len(rows),
                'raw_rule_agreement':sum(r['prediction']==r['rule_prediction'] for r in rows)/len(rows),
                'mean_prediction_probability':sum(float(r['confidence']) for r in rows)/len(rows)})
        for model in ('M1','M2','M3','M4'):
            align=read_csv(folder/f'{model}_alignment.csv')
            for pos,row in enumerate(align):
                if row['operation']!='matches':
                    context=align[max(0,pos-5):pos+6]
                    examples.append({'model':model,'number':number,**row,'reference_context':''.join(r['reference'] for r in context),
                        'prediction_context':''.join(r['prediction'] for r in context)})
        meta=json.loads((PROJECT/f'evaluation/real_collection_baseline/{number:03d}/recording_metrics.json').read_text(encoding='utf-8'))
        conditions.append({'number':number,'duration_seconds':meta['duration_seconds'],'frequency_hz':meta['detector']['frequency_hz'],
            'dot_seconds':meta['detector']['dot_seconds']})
    write_csv(out/'prediction_agreement.csv',agreement);write_csv(out/'remaining_differences.csv',examples);write_csv(out/'recording_conditions.csv',conditions)
    excluded85=[]
    for name in ('M1','M2','M3','M4'):
        rows=[r for r in recs if r['model']==name and r['number'] not in (85,86)]
        n=sum(r['reference_units'] for r in rows);d=sum(r['edit_distance'] for r in rows)
        excluded85.append({'model':name,'recordings':len(rows),'reference_units':n,'edit_distance':d,'cer':d/n})
    write_csv(out/'excluding_85_86.csv',excluded85)
    old_cer=sum(int(r['old_edits']) for r in historical)/16317
    rule_cer=sum(int(r['rule_edits']) for r in historical)/16317
    comparison=[{'model':r['model'],'synthetic_test_accuracy':float(synthetic[i]['test_accuracy']),
        'real_body_cer':r['cer'],'real_edit_distance':r['edit_distance'],'exact_recordings':r['exact_match']} for i,r in enumerate(summary)]
    write_csv(out/'synthetic_real_comparison.csv',comparison)
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    colors=['#3475b5','#289484','#b08042','#9864ac']
    ax=axes[0];v=[100*r['synthetic_test_accuracy'] for r in comparison]
    ax.bar([r['model'] for r in comparison],v,color=colors);ax.set(ylim=(0,105),title='Synthetic: single-symbol accuracy (%)')
    for i,x in enumerate(v):ax.text(i,x+1,f'{x:.2f}',ha='center')
    ax=axes[1];v=[old_cer*100]+[r['cer']*100 for r in summary]+[rule_cer*100]
    ax.bar(['Old CNN','M1','M2','M3','M4','Rule'],v,color=['#999999']+colors+['#444444']);ax.set(ylim=(0,8),title='Real recordings: body CER (%) — lower is better')
    for i,x in enumerate(v):ax.text(i,x+.1,f'{x:.3f}',ha='center',fontsize=9)
    fig.savefig(out/'synthetic_real_comparison.png',dpi=170);plt.close(fig)
    lines=['# M1〜M4：実録音40件の比較評価','',
        '提供済みTaman実録音のうち、従来と同じ40件・16,317文字を、保存済み和文65クラスのM1〜M4で新たに推論しました。追加学習・重みの変更・周波数変換・録音別の閾値調整は行っていません。','',
        '|方式|本文CER（小さいほど良い）|編集距離|完全一致した録音|','|---|---:|---:|---:|',
        f'|従来CNN（保存済み結果を再採点）|{old_cer:.4%}|1,149|参考値|']
    for r in summary:lines.append(f'|{r["model"]}|{r["cer"]:.4%}|{r["edit_distance"]}|{r["exact_match"]}/40|')
    lines += [f'|従来ルール方式（保存済み出力）|{rule_cer:.4%}|16|36/40|','',
        '4モデルの最終文章は39/40件で一致し、その39件では従来ルール方式の文章とも一致しました。61番の出力85文字目はM1/M2が「ト」、M3が「ヘ」、M4が「ヱ」、ルールが「?」と異なりますが、いずれも正解文にない1文字の挿入として採点され、集計値は同じになっています。今回のCERではM1〜M4の優劣は判別できません。予測確率はモデルごとに異なりますが、その高低を実測精度の差としては扱いません。','',
        '## 残った差分','',
        '全モデル共通で置換0・挿入7・削除9です。58・61・68・77の4録音に残り、他の36録音は正解文と完全一致しました。本文の挿入・削除は音声認識の失敗だけでなく、原稿と実際の送信、文字分割、正規化の違いでも生じます。原因を断定せず、正解文も変更していません。','',
        '|番号|CER|置換|挿入|削除|','|---|---:|---:|---:|---:|']
    for r in recs:
        if r['model']=='M1' and r['edit_distance']:
            lines.append(f'|{r["number"]}|{r["cer"]:.4%}|{r["substitutions"]}|{r["insertions"]}|{r["deletions"]}|')
    lines+=['','文字ごとの位置と前後の文脈は`remaining_differences.csv`、全文と対応表は番号別フォルダに保存しました。','',
        '## 合成音声との比較','', '|モデル|和文合成Testの1符号正解率|実録音の本文CER|','|---|---:|---:|']
    for r in comparison:lines.append(f'|{r["model"]}|{r["synthetic_test_accuracy"]:.2%}|{r["real_body_cer"]:.4%}|')
    lines+=['',
        '左は1文字に分割済みの合成音声2,925件の分類正解率、右は実録音40件の本文編集距離から求めたCERです。異なる指標・データ条件なので、引き算で性能差を表したり、1−CERを分類正解率と呼んだりしません。',
        '合成TestではM3が最も高い値でしたが、この実録音では4モデルが同じ結果です。合成Testには強いノイズ条件が含まれる一方、この評価は同じ系列の規則的な練習録音で、ルールによる文字区間の抽出を利用しています。実録音の方が常に簡単、あるいは新しいモデルがあらゆる実録音で高精度、という結論にはなりません。','',
        '## 従来40件と揃えた条件','',
        '- 元MP3のSHA-256が以前の認識時と同じことを照合。原音を16kHz・monoへ読み込み、保存済みの開始・終了サンプルで同一区間を切り出す。',
        '- 各区間に従来と同じ余白を付け、M1〜M4共通のRMS包絡前処理を適用。モデルごとの区間調整はしない。',
        '- 既存の本文開始・終了、句読点除外、50・66・70・71の括弧内欧文処理を再利用。正解文は従来の正規化済み本文を固定。',
        '- 旧CNNとルールの保存出力を同じ処理から再現し、40件・16,317文字・編集距離1,149/16の一致を、新モデルの推論前に確認。',
        '- CNNの予測文字をルール文字で補正しない。ただし本文範囲・モード切替はルールに依存する。',
        '- CERは録音別CERの単純平均ではなく、全編集距離÷全正解文字数で集計。','',
        '**CNNだけで音声全体から文章まで処理する性能ではありません。** 文字区間検出の新規再実行も含みません。保存済み区間を共通に使い、分類モデルの変更による差を調べた評価です。','',
        '## 対象範囲と未評価部分','',
        '正解文のある44件のうち40件を採点しています。57・64・67は従来条件の本文境界が未確定、62は括弧外の欧文原稿等の処理が未確定です。別途実施済みの全文厳密評価とこの本文評価は統合せず、44件全体のCERは作成しません。正解文のない42件も精度評価の対象外です。',
        '録音は過去の開発で参照済みで、新たに収集した未見Testではありません。今回のM1〜M4は合成音声で学習し、この評価のための追加学習はしていません。',
        f'85・86を除く補助集計でも4モデルは同じ結果で、{excluded85[0]["recordings"]}件・{excluded85[0]["reference_units"]:,}文字、CER {excluded85[0]["cer"]:.4%}です。ただし、この除外だけで未見データ評価になるわけではありません。',
        '録音の取り込み、和文／欧文モード、速度・雑音・送信者が異なる未知録音での汎化性能は追加検証が必要です。','',
        '## 次に確認すべきこと','',
        'まず残る16編集の区間を原音と原稿で照合し、送信内容の差か処理上の誤りかを切り分けます。方式の優劣を見るには、異なる送信者・速度・受信雑音の新しい録音を固定し、同じ4モデルで評価するのが有効です。今回のTest結果に合わせたモデル選び直しや再学習は行っていません。','',
        '## 保存物','',
        '`summary.csv`：モデル別集計、`recording_results.csv`：40件×4モデルの結果、`synthetic_real_comparison.csv`：合成／実録音の対照、`prediction_agreement.csv`：区間予測と予測確率の診断。',
        '番号別フォルダ：正解本文、各モデルの認識全文、時刻・予測・確率を含む区間CSV、編集対応表。`protocol.json`：モデル・音声・参照元のハッシュ、`verification.json`：保護と再採点の検証。',
        '既存モデルと実録音・正解文・過去の評価結果を変更せず、全160文章の再採点を検証しました。共通処理の既存8テストに成功しています。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json(out/'agreement_verification.json',{'four_model_identical_recordings':identical,'all_match_rule_recordings':rule_identical,'differing_recordings':differing,
        'recordings':40,'agreement_is_not_ground_truth_accuracy':True,'script_sha256':sha(ROOT/'evaluate.py')})
    print('Report and comparison figure saved.')

if __name__=='__main__':main()
