"""Re-score frozen predictions under the user-confirmed mode-control convention."""
from evaluate_four import ROOT,PROJECT,read_csv,write_csv,write_json,sha,decode_drop_controls,edit_alignment
import json,os
from pathlib import Path

def main():
    out=ROOT/'unified44';out.mkdir(exist_ok=False)
    numbers=sorted([int(p.name) for p in (ROOT/'results').iterdir() if p.is_dir() and p.name.isdigit()]+[57,62,64,67])
    assert len(numbers)==len(set(numbers))==44
    protected={};results=[];changes=[];differences=[]
    for number in numbers:
        extra=number in (57,62,64,67)
        src=ROOT/('additional_four' if extra else 'results')/f'{number:03d}'
        refpath=src/('reference_normalized.txt' if extra else 'reference.txt')
        previous=refpath.read_text(encoding='utf-8')
        reference=previous.replace('（','').replace('）','')
        protected[str(refpath)]=sha(refpath)
        changes.append({'number':number,'previous_units':len(previous),'mode_parentheses_removed':len(previous)-len(reference),'reference_units':len(reference)})
        folder=out/f'{number:03d}';folder.mkdir()
        (folder/'reference.txt').write_text(reference,encoding='utf-8')
        for name in ('M1','M2','M3','M4'):
            path=src/f'{name}_segments.csv';rows=read_csv(path);protected[str(path)]=sha(path)
            text,rule=decode_drop_controls(rows)
            metric,alignment=edit_alignment(reference,text)
            metric.update(number=number,model=name,exact_recording=int(text==reference))
            results.append(metric)
            (folder/f'{name}_transcript.txt').write_text(text,encoding='utf-8')
            write_csv(folder/f'{name}_alignment.csv',alignment)
            for i,row in enumerate(alignment):
                if row['operation']!='matches':
                    context=alignment[max(0,i-8):i+9]
                    differences.append({'number':number,'model':name,**row,
                        'reference_context':''.join(r['reference'] for r in context),'prediction_context':''.join(r['prediction'] for r in context)})
        metric,alignment=edit_alignment(reference,rule);metric.update(number=number,model='Rule',exact_recording=int(rule==reference));results.append(metric)
        (folder/'Rule_transcript.txt').write_text(rule,encoding='utf-8');write_csv(folder/'Rule_alignment.csv',alignment)
    write_csv(out/'reference_normalization_changes.csv',changes)
    write_csv(out/'recording_results.csv',results);write_csv(out/'remaining_differences.csv',differences)
    summary=[]
    for name in ('M1','M2','M3','M4','Rule'):
        rows=[r for r in results if r['model']==name]
        n=sum(r['reference_units'] for r in rows);d=sum(r['edit_distance'] for r in rows)
        summary.append({'model':name,'recordings':len(rows),'reference_units':n,'edit_distance':d,'cer':d/n,
            **{k:sum(r[k] for r in rows) for k in ('substitutions','insertions','deletions','exact_recording')}})
    write_csv(out/'summary.csv',summary);write_json(out/'summary.json',summary)
    synthetic=read_csv(PROJECT/'phase6_wabun65/reports/comparison/metrics.csv')
    comparison=[{'model':r['model'],'synthetic_accuracy':float(synthetic[i]['test_accuracy']),'real_body_cer':r['cer'],
        'parameters':int(synthetic[i]['parameters']),'real_edit_distance':r['edit_distance']} for i,r in enumerate(summary[:4])]
    write_csv(out/'synthetic_real_comparison.csv',comparison)
    for r in results:
        folder=out/f'{r["number"]:03d}'
        metrics,_=edit_alignment((folder/'reference.txt').read_text(encoding='utf-8'),(folder/f'{r["model"]}_transcript.txt').read_text(encoding='utf-8'))
        assert all(metrics[k]==r[k] for k in metrics)
    assert all(sha(p)==h for p,h in protected.items())
    protocol={'version':'44-recording unified mode-parentheses exclusion v1','user_convention':'Mode-switch parentheses are not manuscript text.',
        'prediction_processing':'Remove observed bracket-control segments while retaining their mode-switch effect; never strip arbitrary predicted characters.',
        'reference_processing':'Remove fullwidth parentheses from already-normalized references; preserve every other normalized character.',
        'framing':'Original HORE/RATA for 41 recordings; HR HR BT ... AR for 57,64,67 per validated boundary protocol.',
        'new_inference':False,'retraining':False,'source_hashes':protected,
        'decimal_or_question_mark_policy_changed':False,'previous_reports_overwritten':False}
    write_json(out/'protocol.json',protocol)
    write_json(out/'verification.json',{'status':'PASS','records':44,'all_220_scores_recomputed':True,'source_files_unchanged':len(protected),
        'reference_units':summary[0]['reference_units'],'parentheses_removed_from_references':sum(r['mode_parentheses_removed'] for r in changes)})
    render_report(out,summary,comparison,results,changes)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

def render_report(out,summary,comparison,results,changes):
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    n=summary[0]['reference_units'];removed=sum(r['mode_parentheses_removed'] for r in changes)
    lines=['# 実録音44件：M1〜M4統一評価レポート','',
        f'**44録音・{n:,}文字を同じ括弧処理で再採点しました。M1〜M4はいずれもCER {summary[0]["cer"]:.4%}、編集誤り16、完全一致40/44件でした。**','',
        'ユーザー確認に従い、括弧は英数字モードへの切替に使い、本文の採点から除外します。保存済みのモデル予測を再集計しており、モデルの追加学習・重みの変更・音声の再推論は行っていません。','',
        '|モデル|合成Test：1符号正解率|実録音44件：本文CER|実録音の編集誤り|パラメータ数|','|---|---:|---:|---:|---:|']
    for r in comparison:lines.append(f'|{r["model"]}|{r["synthetic_accuracy"]:.2%}|{r["real_body_cer"]:.4%}|{r["real_edit_distance"]}|{r["parameters"]:,}|')
    lines+=['', 'ルール方式も同じ本文CERでした。Accuracyは高いほど良く、CERは低いほど良い指標です。1−CERを分類Accuracyとして扱いません。今回の実録音CERでは4モデルの優劣は判別できません。','',
        '## 40件と追加4件の統一方法','',
        f'従来40件の16,317文字と追加4件の2,057文字を出発点とし、旧正解文に含まれていたモード用括弧{removed}文字を除外しました。合計は18,374−{removed}＝{n:,}文字です。',
        '出力側は括弧符号が実際に検出された区間を採点から除きます。予測文章の「（」「）」という文字を一律に削除して誤認識を隠す方法ではありません。括弧区間が欧文への切替を制御する点は維持します。正解文には括弧を追加していません。',
        '57・64・67は先頭HR HR＋BTと末尾ARの条件で本文を抽出した保存結果を使用し、他41件は従来のホレ／ラタの本文範囲を使用しました。いずれもモデルの予測や正解文に合わせて境界を変えていません。','',
        '## 残った16編集の内訳と解釈','',
        '|録音|編集数|観察できたこと|解釈と未確認事項|','|---|---:|---|---|',
        '|58|挿入2|原稿「０．６」の小数点が旧正規化で落ち「06」になる一方、出力は「0テン6」|表記・読み方と正規化の不一致。モデルの置換誤りとしては数えていない|',
        '|68|挿入4|原稿に2か所の「1.5」、正規化後は「15」、出力は「1テン5」|58と同じ表記・正規化の影響|',
        '|61|挿入1|原稿の疑問符が旧正規化で除かれる。対応区間の符号は `..--..`。M1/M2は「ト」、M3は「ヘ」、M4は「ヱ」と予測|疑問符を含まない65クラスへの強制分類と、採点時の疑問符除外が関係。モデル間で出力は同じではない|',
        '|77|削除9|原稿の「オンドトシツド」に相当する説明部分が、全モデルとルールの出力に現れない|原稿と実際の送信、分割処理等の切り分けは未確定。送信内容の省略と断定しない|','',
        'この内訳は保存済み原稿・区間符号・予測・編集対応表の照合によるものです。原音の全区間を人が聴いて正解を書き直した評価ではありません。',
        '小数点を「テン」に変える、疑問符区間を採点から除く、77の原稿を削るなどの追加変更は行っていません。今回変更したのは、確認いただいた括弧の扱いだけです。公式値は16編集のまま保持します。','',
        '## 高校生向け：今回の数値の読み方','',
        '合成Testは、1文字分の音を65種類から当てる試験です。実録音のCERは、認識した文章を正解文に直すための置換・挿入・削除の回数を数えます。試験の問題も採点方法も違うため、2つの百分率をそのまま比べてはいけません。',
        '今回の録音は規則的な練習信号です。各モデルの文章は43/44件で同じでしたが、61番では違う余分な文字が1文字ずつ出たため、文章が違っても同じ点数になりました。CERが同点だから、モデル内部の判断も全部同じという意味ではありません。','',
        '## 評価の限界と次の検証','',
        '全44件には過去の開発で参照した録音が含まれます。未知の実録音だけの評価ではありません。本文抽出・モード切替・句読点処理をルールで補助しており、CNN単体の全自動文章認識性能でもありません。合成Testは各モデル1Seedです。',
        '次の改善は、①小数点・疑問符・手続符号の採点規約を事前に固定する、②65クラスにない符号を無理に既知文字へ分類せず要確認にする、③異なる送信者・速度・雑音の未使用録音を用意する、の順が有効です。これらは今回の実装・再学習には含めていません。','',
        '今回の結果だけでは実運用に使うモデルを確定せず、M1〜M4の保存モデルを維持します。以前の40件・追加4件の報告も当時の条件の記録として残します。','',
        '## 保存ファイル','',
        '`summary.csv/json`：44件集計、`recording_results.csv`：録音別、`reference_normalization_changes.csv`：括弧除外による分母の変化、`remaining_differences.csv`：誤りの位置と文脈。',
        '各番号フォルダ：統一した正解本文、モデル別文章、編集対応。`protocol.json`：処理条件と入力ハッシュ、`verification.json`：全220組（44件×5方式）の再計算と入力不変検証。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    fig,ax=plt.subplots(figsize=(10,3.6),layout='constrained');ax.axis('off')
    cells=[[r['model'],f'{r["synthetic_accuracy"]:.2%}',f'{r["real_body_cer"]:.4%}',str(r['real_edit_distance'])] for r in comparison]
    table=ax.table(cellText=cells,colLabels=['Model','Synthetic accuracy','Real body CER','Real edits'],cellLoc='center',loc='center')
    table.auto_set_font_size(False);table.set_fontsize(12);table.scale(1,1.8)
    for (r,c),cell in table.get_celld().items():cell.set_facecolor('#dceafa' if r==0 else ('#f3f6fa' if r%2 else 'white'))
    ax.set_title(f'Wabun M1-M4: 44 real recordings, {n:,} reference units\nDifferent metrics: higher accuracy / lower CER is better')
    fig.savefig(out/'comparison.png',dpi=170);plt.close(fig)
    single=[r for r in results if r['model']=='M1']
    fig,ax=plt.subplots(figsize=(12,4),layout='constrained')
    ax.bar([str(r['number']) for r in single],[100*r['cer'] for r in single],color='#3475b5')
    ax.set(xlabel='Recording number',ylabel='Body CER (%)',title='All four models have the same CER per recording',ylim=(0,2.3))
    ax.tick_params(axis='x',labelsize=8)
    fig.savefig(out/'cer_by_recording.png',dpi=170);plt.close(fig)

if __name__=='__main__':main()
