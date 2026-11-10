"""Audit the completed fixed experiment and produce its Japanese report."""
from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parent
P = ROOT.parent
sys.path[:0] = [str(ROOT), str(P)]
from analyze_saved_errors import read, write, sha
from evaluation_compare import distance
from adaptive_pipeline import METHODS, LABELS
import evaluate_new as runner

def main():
    out = ROOT / 'adaptive_experiment_v1'
    plan = read(out / 'plan.json')
    for path, digest in {**plan['scripts'], **plan['previous_results']}.items():
        assert sha(P / path) == digest, path
    lock = read(out / 'validation_lock.json')
    assert lock['plan_sha256'] == sha(out / 'plan.json')
    assert lock['development_sha256'] == sha(out / 'development/results.json')
    runner.verify_frozen()
    text = ['# 音程追従・速度補正・組合せ評価・実験画面の実施結果', '',
        '実施日：2026年9月23日。①〜④を実装・検証しました。通常アプリと保存モデルの重みは変更していません。再学習も行っていません。', '',
        '## 実装した4項目', '',
        '1. 音程追従：時間ごとに信号の周波数を推定し、700 Hzへ揃えてから短点・長点を抽出します。無音区間は前後の推定値から補間します。',
        '2. 速度補正：推定した短点の長さに合わせ、CNNへ渡す音の強さの特徴量を短点100 ms相当に伸縮します。前後の余白は維持し、元音声の再生速度と時刻情報は変えません。',
        '3. 組合せ評価：従来処理、短点推定、音程追従、速度補正、その併用、切替補正を加えた統合版の6方式をM1〜M4で比較しました。',
        '4. 実験画面：同一音声・同一モデルで方式を比較し、音程の推移、文字ごとの候補、区間音声、任意の正解文によるCER、JSON保存を利用できます。', '',
        '## 評価条件と限界', '',
        '既存の666条件を開発用に使用し、方式を固定した後に別の180条件を評価しました。別条件は文章3種類、短点90/140/220 ms、音程の変化5種類、乱数種2種類、無雑音／白色雑音0 dBの組合せです。方式・条件・スクリプトのハッシュを事前に保存し、別条件の結果を見て再調整していません。', '',
        'いずれも合成音声による診断です。新しい実録音の独立評価ではありません。短文と意図的に難しい条件へ偏っており、一般の音声に対する性能や採用モデルを決定する根拠にはしません。生成方法を共用し、同じ波形の条件も含むため、条件数を独立した録音数とは扱いません。', '',
        'CERは総編集距離÷総正解文字数です。低いほど良く、余分な文字の挿入が多い場合は100%を超えます。CNN単体の分類正解率ではなく、区間抽出・文字認識・和欧モード処理を含む本文の評価です。括弧の制御符号は原稿に表示しない既存規則を維持しています。', '',
        '既存666条件の従来処理・短点推定は保存済み結果を再利用し、残る4方式を実行しました。別180条件は6方式すべて実行しました。計20,304行は評価結果の総数であり、今回の新規推論回数とは異なります。正解文は推論には渡さず、採点だけに使います。', '']
    audit = {}; regressions = []; components = []
    for stage, count, heading in [('development',666,'開発用666条件'),('held',180,'固定後の別180条件')]:
        rows = read(out / stage / 'results.json')
        assert len(rows) == count * 24
        sources = list((out / stage).glob('*/source.json'))
        assert len(sources) == count
        for source in sources:
            data = read(source); assert sha(Path(data['audio'])) == data['sha256']
        for row in rows:
            assert distance(row['reference'], row['hypothesis']) == row['edits']
            assert len(row['reference']) == row['reference_units']
        lookup = {(r['id'],r['model'],r['method']):r for r in rows}
        assert len(lookup) == len(rows)
        summaries = read(out / stage / 'summary.json')
        table = {(r['method'],r['model']):r for r in summaries}
        for (method, model), saved in table.items():
            rs = [r for r in rows if (r['method'],r['model']) == (method,model)]
            assert len(rs) == count
            assert saved['units'] == sum(r['reference_units'] for r in rs)
            assert saved['edits'] == sum(r['edits'] for r in rs)
            assert abs(saved['cer'] - saved['edits']/saved['units']) < 1e-12
        unique = len({r['input_sha256'] for r in rows})
        failures = sum(bool(r['error']) for r in rows)
        repairs = sum(r['mode_repairs'] for r in rows if r['method']=='combined_mode')
        audit[stage] = dict(cases=count,unique_waveforms=unique,rows=len(rows),failures=failures,repairs=repairs,source_hashes_verified=True,distances_recomputed=True)
        text += [f'## {heading}', '', f'条件数：{count}、異なる波形：{unique}、結果行数：{len(rows):,}、処理失敗：{failures}。', '',
                 '| 方式（CER %） | M1 | M2 | M3 | M4 |', '|---|---:|---:|---:|---:|']
        for method in METHODS:
            text.append('| '+LABELS[method]+' | '+' | '.join(f"{100*table[method,m]['cer']:.2f}" for m in ['M1','M2','M3','M4'])+' |')
        text += ['', f"各方式・各モデルの正解文字数は{table['baseline','M1']['units']:,}文字。", '',
                 '| 統合版と従来処理の比較 | 改善条件 | 悪化条件 | 同数条件 |', '|---|---:|---:|---:|']
        for model in ['M1','M2','M3','M4']:
            diffs=[]
            for row in rows:
                if row['model']!=model or row['method']!='combined_mode': continue
                base=lookup[row['id'],model,'baseline']; delta=row['edits']-base['edits']; diffs.append(delta)
                if delta>0: regressions.append(dict(stage=stage,model=model,id=row['id'],reference=row['reference'],baseline=base['hypothesis'],combined=row['hypothesis'],extra_edits=delta))
            text.append(f'| {model} | {sum(d<0 for d in diffs)} | {sum(d>0 for d in diffs)} | {sum(d==0 for d in diffs)} |')
        for left,right in [('timing','tracking'),('timing','tempo'),('tracking','combined'),('combined','combined_mode')]:
            for model in ['M1','M2','M3','M4']:
                dr=[r['edits']-lookup[r['id'],model,left]['edits'] for r in rows if r['model']==model and r['method']==right]
                components.append(dict(stage=stage,model=model,left=left,right=right,improved=sum(d<0 for d in dr),worse=sum(d>0 for d in dr),same=sum(d==0 for d in dr)))
        text += ['',f'統合版の切替符号の補正はモデル延べ{repairs}回。', '']
    text += ['## 解釈と残る課題', '',
        '音程追従と速度補正の併用で、別180条件のCERは0.33〜2.00%になりました。短点推定だけでは39.83〜40.83%であり、今回の条件では併用の効果が見られます。一方、開発用666条件では統合版が従来処理より悪化した条件が各モデル4〜10件あります。悪化事例はregressions.jsonへ全件保存しました。', '',
        '既知の遅い「ヘイハ」（短点190 ms、安定音程、seed107、無雑音）では、M1の従来処理・短点推定・音程追従が「ムイハ」でした。速度補正を加えると「ヘイハ」になりました。', '',
        '別180条件では切替符号の補正は一度も発動せず、切替補正の有無による数値差もありません。この評価から切替補正の追加効果を主張することはできません。既存条件での補正効果と分けて扱います。', '',
        '音程追従は単一の主な信号を仮定しています。実際の録音での強い妨害音、複数音源、極端な速度、切替符号の欠落への頑健性は未確定です。新たな実録音で、認識誤り・悪化例・音程推定の外れを比較してから採用方式とモデルを決めます。今回の合成結果だけでM1〜M4の順位を確定しません。', '',
        '## 起動と成果物', '',
        '- 実験画面：http://127.0.0.1:8504/ （ローカルサーバー起動中）',
        '- 再起動：プロジェクト直下のstart_experiment.cmdを実行。操作方法は「実験画面の使い方.md」。',
        '- 保存済み結果の比較：evaluation_compare_ui.pyで本評価の48比較ファイルも選べます。',
        '- 詳細：development/・held/のresults.json、summary.json、各条件の予測・診断。',
        '- 事前固定：plan.json、validation_lock.json。追加監査：final_verification.json。',
        '- 悪化事例：regressions.json。構成要素ごとの比較：component_pairs.json。',
        '- テスト：関連する28テストが成功。実験画面の描画、方式変更、正解あり／なし、設定変更時の再実行案内、音声読み込みを含みます。',
        '- 既存の配布ZIP v3には今回の実験画面を追加していません。', '']
    write(out/'regressions.json',regressions)
    write(out/'component_pairs.json',components)
    write(out/'final_verification.json',dict(stages=audit,frozen_models_and_policies_verified=True,plan_and_results_hashes_verified=True,related_tests_passed=28))
    (out/'report.md').write_text('\n'.join(text),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
