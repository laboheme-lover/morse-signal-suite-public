"""Replay reference-free guard decisions, independently audit and report real results."""
from pathlib import Path
import sys,csv,statistics,json
ROOT=Path(__file__).resolve().parent;P=ROOT.parent;sys.path[:0]=[str(ROOT),str(P)]
from recording_experiment import read,save
from guarded_pipeline import guard
from adaptive_pipeline import LABELS
from evaluation_compare import distance,SCHEMA
from intake import digest
import evaluate_new as runner

def finalize(out):
    manifest=read(out/'manifest.json');original=read(out/'results.json');rows=list(original);decisions=[];differences=[]
    assert len(original)==len(manifest['recordings'])*24
    for entry in manifest['recordings']:
        result=read(out/entry['id']/'result.json');outputs={}
        for key,data in result['outputs'].items():
            method,model=key.rsplit('_',1);outputs[(method,model)]=(data['text'],data['segments'],data['warnings'],data['error'])
        for model in manifest['models']:
            guarded,meta=guard(outputs,result['detectors'],model)
            base=next(r for r in result['metrics'] if r['method']=='baseline' and r['model']==model)
            combined=next(r for r in result['metrics'] if r['method']=='combined_mode' and r['model']==model)
            row=dict(base,method='guarded',hypothesis=guarded[0],edits=distance(entry['reference'],guarded[0]),status='FAILED' if guarded[3] else 'OK',error=guarded[3])
            # Do not copy stale alignment counts from the baseline.
            from evaluate_recording import edit_alignment
            metric,_=edit_alignment(entry['reference'],guarded[0]);row.update(metric)
            rows.append(row);decisions.append(dict(id=entry['id'],model=model,**meta['guard']))
            if combined['edits']!=base['edits'] or base['edits']:
                br=outputs[('baseline',model)][1];cr=outputs[('combined_mode',model)][1]
                differences.append(dict(id=entry['id'],model=model,baseline_edits=base['edits'],combined_edits=combined['edits'],guarded_edits=row['edits'],
                    baseline_segments=len(br),combined_segments=len(cr),observed_patterns_equal=[r['pattern'] for r in br]==[r['pattern'] for r in cr],
                    baseline=base['hypothesis'],combined=combined['hypothesis'],reference=entry['reference']))
        save(out/entry['id']/'guard_decisions.json',[r for r in decisions if r['id']==entry['id']])
    for row in rows:assert distance(row['reference'],row['hypothesis'])==row['edits']
    summaries=[]
    methods=manifest['methods']+['guarded']
    for method in methods:
        for model in manifest['models']:
            rs=[r for r in rows if r['method']==method and r['model']==model];n=sum(r['reference_units'] for r in rs);d=sum(r['edits'] for r in rs)
            summaries.append(dict(method=method,model=model,cases=len(rs),units=n,edits=d,cer=d/n if n else None,failures=sum(r['status']=='FAILED' for r in rs)))
            save(out/'comparisons'/f'real_{method}_{model}_comparison.json',dict(schema=SCHEMA,name=f'known_real_{method}_{model}',scope=manifest['scope'],scoring_policy='phase8-content-v2-fixed-historical-window',rows=rs))
    save(out/'guard_results.json',rows);save(out/'guard_summary.json',summaries);save(out/'guard_decisions.json',decisions);save(out/'differences.json',differences)
    runner.verify_frozen()
    for entry in manifest['recordings']:
        assert digest(entry['audio'])==entry['audio_sha256'];assert digest(entry['reference_path'])==entry['reference_sha256']
    save(out/'guard_verification.json',dict(completed=True,rows=len(rows),reference_free_selection=True,independent_distances_verified=True,guard_sha256=digest(ROOT/'guarded_pipeline.py')))
    return rows,summaries,decisions

def main():
    out=ROOT/'real_adaptive_v1';rows,summaries,decisions=finalize(out);manifest=read(out/'manifest.json')
    old={}
    with (ROOT/'results/recording_results.csv').open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):old[(f"{int(r['number']):03d}",r['model'])]=int(r['edit_distance'])
    reproduction=[dict(id=r['id'],model=r['model'],old_edits=old[(r['id'],r['model'])],fresh_edits=r['edits']) for r in rows if r['method']=='baseline' and old[(r['id'],r['model'])]!=r['edits']]
    save(out/'historical_score_differences.json',reproduction)
    text=['# 実録音比較・悪化分析・補正ガード・一括評価の実施結果','',
        '実施日：2026年9月23日。①〜④を実行しました。既存モデルの重み・通常版の推論・従来の採点結果は変更していません。', '',
        '## ① 既存実録音44件の新旧比較','',
        'Sound内86音声のうち、既存評価と対応する正解文のある44録音（従来40件＋57・62・64・67）を再処理しました。残る42件はこの44件比較に含めていません。開発時に参照済みの録音であり、新規の独立評価ではありません。', '',
        '保存された本文区間の先頭・末尾と隣接区間の中間を本文窓として事前固定し、全方式で同一範囲を使用しました。音声全体から区間を新たに抽出し、窓内の文字を再推論しています。原稿に合わせた切り出し調整はしていません。括弧は和欧切替制御として表示から除く従来規則です。', '',
        'この評価は既知の本文範囲を利用した条件付き評価です。開始・終了符号から本文範囲を自動決定する性能は別で、各detectorsのprotocol_errorへ診断を保存しています。', '',
        '| 方式：編集数／正解文字数（CER） | M1 | M2 | M3 | M4 |','|---|---:|---:|---:|---:|']
    lookup={(r['method'],r['model']):r for r in summaries}
    for method in manifest['methods']+['guarded']:
        text.append('| '+({'guarded':'補正ガード（検証用）'}.get(method,LABELS.get(method,method)))+' | '+' | '.join(f"{lookup[method,m]['edits']}/{lookup[method,m]['units']}（{lookup[method,m]['cer']:.4%}）" for m in manifest['models'])+' |')
    text+=['',f'再処理した従来方式と前回採点の不一致：{len(reproduction)}モデル・録音組。処理失敗：{sum(r["status"]=="FAILED" for r in rows)}行。失敗も正解文字数に含め、空の認識文として削除誤りに数えます。','',
        '| 追加4録音 | 正解文字数 | 従来 M1/M2/M3/M4 編集数 | 統合 M1/M2/M3/M4 編集数 |','|---|---:|---|---|']
    for ident in ['057','062','064','067']:
        rs=[r for r in rows if r['id']==ident]
        text.append(f"| {ident} | {rs[0]['reference_units']} | "+' / '.join(str(next(r['edits'] for r in rs if r['model']==m and r['method']=='baseline')) for m in manifest['models'])+' | '+' / '.join(str(next(r['edits'] for r in rs if r['model']==m and r['method']=='combined_mode')) for m in manifest['models'])+' |')
    g=ROOT/'guard_experiment_v1';reg=read(g/'regression_analysis.json');dev=read(g/'development.json');val=read(g/'validation_results.json')
    text+=['','## ② 悪化原因と改善案の検証','',
        f'前回の合成666条件で悪化した27モデル・条件組（異なる条件16件）を全件分析しました。そのうち{sum(r["combined_diagnostics"]["class_error_with_correct_pattern"]>r["baseline_diagnostics"]["class_error_with_correct_pattern"] for r in reg)}組では、観測した点・線が正しい区間でCNNの分類誤りが増えています。分類誤り以外の区間数・符号誤り・モード誤りもregression_analysis.jsonに保存しました。これは原因の切り分けで、補正のどの内部演算が原因かを完全に証明するものではありません。','',
        '安定音程なのに打鍵間隔が不規則で、従来方式と統合方式の観測符号列が同一の場合、補正によって文字判定だけが変わる問題に対して、録音全体を従来処理へ戻す案を実装しました。','',
        '## ③ 不確かな補正への対処','',
        '補正ガードは、短点推定の曖昧さ、追跡に使える音区間の不足、補正処理の失敗、上記の不規則な打鍵を判定します。閾値はguard_experiment_v1/plan.jsonに固定しました。正解文・ファイル名・モデルの予測確率を選択条件に使用しません。文字単位の継ぎはぎはせず、録音全体を一方の方式で解釈して和欧モードの整合性を保ちます。','',
        '従来処理と統合補正の区間・符号・文字が異なる箇所には、原音の確認を促す警告を付けました。相違は誤りそのものを意味しません。','',
        '| 開発666条件 | 統合の総編集数 | ガードの総編集数 | 従来より悪化：統合→ガード |','|---|---:|---:|---|']
    for m in manifest['models']:
        rs=[r for r in dev if r['model']==m]
        text.append(f"| {m} | {sum(r['combined_edits'] for r in rs)} | {sum(r['guarded_edits'] for r in rs)} | {sum(r['combined_edits']>r['baseline_edits'] for r in rs)} → {sum(r['guarded_edits']>r['baseline_edits'] for r in rs)} |")
    text+=['','固定後に新しい文章・速度・乱数種を組み合わせた144条件でも検証しました（各方式・各モデル480文字）。生成方法は共通であり、実録音ではありません。','',
        '| 別144条件 | 統合 CER | ガード CER |','|---|---:|---:|']
    for m in manifest['models']:
        text.append('| '+m+' | '+' | '.join(f"{sum(r['edits'] for r in val if r['model']==m and r['method']==method)/480:.2%}" for method in ['combined_mode','guarded'])+' |')
    text+=['','**自動切り戻しは通常利用へ採用しません。** 悪化する条件数は減りましたが、開発用ではM2〜M4、別144条件ではM2・M3の総編集数が増えました。閾値を検証結果に合わせて調整し直していません。実験画面に検証用の選択肢とこの注意を表示し、既定の方式は維持しています。','',
        f'今回の実録音でガードが従来へ戻した回数：{sum(r["fallback"] for r in decisions)}モデル・録音組。既知録音で差が小さくても、未知録音への安全性を保証しません。','',
        '## ④ 長い録音の一括評価','',
        'batch_recordings.pyに、録音一覧からの連続評価、1録音ごとの結果保存、途中からの再開、出力先の二重起動防止、開始後のマニフェスト変更検出を実装しました。入力音声・正解文・モデルのハッシュも照合します。方法間で音声の処理を共有し、録音を1本ずつ処理します。','']
    perf=read(out/'performance.json');dur=[r['audio_seconds'] for r in perf];secs=[r['evaluation_seconds'] for r in perf]
    text += [f"- 音声の長さ：{min(dur)/60:.1f}〜{max(dur)/60:.1f}分、合計{sum(dur)/3600:.2f}時間。",
        f"- 6方式×4モデルの1録音あたり処理時間：中央値{statistics.median(secs):.1f}秒、最大{max(secs):.1f}秒。合計{sum(secs)/60:.1f}分。",
        f"- 評価プロセス全体の最大ワーキングセット：{max(r['memory_after']['peak_mib'] for r in perf):.0f} MiB。",
        '- メモリ値はPython・全4モデル・音声バッファを含むプロセス起動後のピークです。1録音だけの増分やPC全体の使用量ではありません。',
        '- 時間は音声読み込みから6方式の推論まで。初期モデル読み込み・結果JSON保存・画面描画は含めません。検証中に別のテストも動作しているため、隔離環境での速度ベンチマークではありません。',
        '- コマンド版の入力上限は30分／512 MiB。これは受付上限であり、30分の実録音での完走を確認した意味ではありません。ブラウザーの対話画面は120秒の制限を維持します。','',
        '## 保存場所と利用方法','',
        '- 詳細結果：real_adaptive_v1/guard_results.json、guard_summary.json、differences.json、各録音のresult.json。',
        '- 悪化分析と合成検証：guard_experiment_v1/。',
        '- 実験画面： http://127.0.0.1:8504/ 。補正ガードは「比較する処理」から選択します。',
        '- 保存結果の比較： http://127.0.0.1:8503/ 。known_realを選択してください。',
        '- 起動と再開の手順：プロジェクト直下「実録音一括評価の使い方.md」。',
        '- 最終的なモデル・前処理の採用は、新しい録音での独立評価後に判断します。','']
    (out/'report.md').write_text('\n'.join(text),encoding='utf-8')
    print('real report and guard replay PASS',flush=True)

if __name__=='__main__':main()
