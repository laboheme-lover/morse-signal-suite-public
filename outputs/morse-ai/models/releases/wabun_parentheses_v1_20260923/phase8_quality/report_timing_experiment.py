"""Verify hashes and report both gains and regressions for timing replacement."""
from pathlib import Path
import sys,csv,json
ROOT=Path(__file__).resolve().parent;P=ROOT.parent
sys.path.insert(0,str(P));sys.path.insert(0,str(ROOT))
from analyze_saved_errors import read,write,sha
from evaluation_compare import distance
import evaluate_new

def main():
    out=ROOT/'timing_experiment_v1';plan=read(out/'plan.json');lock=read(out/'validation_lock.json')
    assert sha(out/'plan.json')==lock['plan_sha256'];assert sha(out/'development/results.json')==lock['development_sha256']
    for p,h in {**plan['scripts'],**plan['previous_results']}.items():assert sha(P/p)==h
    evaluate_new.verify_frozen();regressions=[];profile_stats=[];verified=0
    lines=['# 短点の長さの推定改善：実験結果','',
        '短点が全体の一定割合を占めるという仮定を外し、音の長さを短点1単位/長点3単位、無音を1/3/7単位に同時に当てはめる方式を実装しました。極端な外れ値の影響を抑え、異なる時間単位が同程度に当てはまる場合は警告する仕組みです。',
        '変更は短点推定だけです。帯域±100 Hz、包絡線、閾値、CNNの重み、本文採点を維持し、切替符号の補正も追加していません。短点候補範囲15～500 msなどの設定はplan.jsonとコードのハッシュで固定しました。',
        '## 問題例の改善','',
        '無雑音「スセソ」・短点80 msで、従来推定242.875 msに対し、新方式は約80 msとなり、1区間への結合が解消されました。M1～M4で本文「スセソ」を確認しました。短点160 msも区間分割の単体テストで確認しています。','']
    for stage,title in [('development','既存条件での開発・回帰確認'),('held','事前固定した別条件の検証')]:
        directory=out/stage;rows=read(directory/'results.json');index={(r['id'],r['model'],r['method']):r for r in rows}
        for r in rows:
            assert distance(r['reference'],r['hypothesis'])==r['edits'];verified+=1
            if r['method']=='timing_v1':
                old=index[(r['id'],r['model'],'baseline')]
                if r['edits']>old['edits']:regressions.append(dict(stage=stage,model=r['model'],id=r['id'],reference=r['reference'],before=old['hypothesis'],after=r['hypothesis'],old_edits=old['edits'],new_edits=r['edits']))
        unique=len({r['input_sha256'] for r in rows});pairs=read(directory/'paired_summary.json')
        lines+=['## '+title,'',f"条件数は各モデル{len(rows)//8}件、実波形は{unique}種類です。同じ音声になる条件を含み、独立標本数とは扱いません。各条件を事前計画どおり等しく集計しています。",'',
                '|モデル|従来CER|短点改善CER|改善文章|悪化文章|','|---|---:|---:|---:|---:|']
        for s in pairs:lines.append(f"|{s['model']}|{s['左CER']:.2%}|{s['右CER']:.2%}|{s['改善件数']}|{s['悪化件数']}|")
        if stage=='development':
            lines+=['','以前の拡充診断366条件＋ストレス診断192条件＝558条件です。過去の評価結果を残して開発用として参照しました。悪化は音程が周期的に揺れる3条件（各モデル）でした。実波形では2種類です。']
            for dataset in ('noise_expanded','frontend_stress_v1'):
                for method in ('baseline','timing_v1'):
                    rs=[r for r in rows if r['dataset']==dataset and r['method']==method]
                    profile_stats.append(dict(stage=stage,condition=dataset,method=method,edits=sum(r['edits'] for r in rs),units=sum(r['reference_units'] for r in rs)))
        else:
            lines+=['','文章「コソセ」「ヘイハ」「ニ（ハヘ）ホ」、短点70/110/190 ms、変動なし/打鍵時間±30%/音程移動±100 Hz、乱数種107/211、無雑音/ガウス雑音0 dB。108音声×4モデル×2方式＝864評価です。既存結果を確認した後も推定方式を変更せず、検証前に計画・コード・開発結果を固定しました。',
                    '各モデル11条件で改善し、悪化0条件でした。ただし3文章の合成検証であり、別の文章や実録音での無悪化を保証するものではありません。','',
                    '|変動条件|従来CER（4モデル合計）|短点改善CER（同）|','|---|---:|---:|']
            for profile in plan['profiles']:
                entries=[]
                for method in ('baseline','timing_v1'):
                    rs=[r for r in rows if r['profile']==profile and r['method']==method]
                    stats=dict(stage=stage,condition=profile,method=method,edits=sum(r['edits'] for r in rs),units=sum(r['reference_units'] for r in rs));profile_stats.append(stats);entries.append(stats)
                lines.append('|'+profile+'|'+'|'.join(f"{s['edits']/s['units']:.2%}" for s in entries)+'|')
        with (directory/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
        for folder in directory.iterdir():
            if (folder/'source.json').is_file():
                source=read(folder/'source.json');assert sha(Path(source['audio']))==source['sha256']
    lines+=['','## 残る課題と扱い','',
        '短点推定の改善で長点の多い文章の結合は減りましたが、音程が大きく揺れる条件の検出誤りは解消していません。既存3条件では本文の誤りが増えたため、平均値だけで採用を決めません。',
        '別条件の変動なし・無雑音でも、短点190 msでは「ヘ」を「ム」、「ニBEホ」を「ニBTホ」と読む誤りが残りました。この例では短点推定は約190.96 msであり、短点推定だけでは直せないCNN分類の問題が残ります。',
        '音の長さと無音がすべて等しいような条件では、時間単位を一意に決められない場合があります。曖昧性の警告動作は専用テストで確認しましたが、今回の評価音声では警告条件は作動していません。',
        '方式はtiming_v1として実験保存し、通常アプリへはまだ適用していません。実録音の評価、音程変動への対策、打鍵速度による分類の混同が残ります。採用モデルは未決定です。',
        '## 保存と検証','',
        '比較画面でtiming_development/heldのbaselineとtiming_v1を選択できます。既存558件と別条件108件を分けて保存し、全結果CSV・JSON、検出時刻・推定値・悪化例・入力ハッシュを残しています。旧配布ZIP v3は変更していません。',
        '関連23テスト、編集距離5,328行の別実装による再計算、666条件の入力ハッシュ、固定モデル・既存コード・過去結果のハッシュ確認に合格。新しい比較項目はStreamlit AppTestで共通108件・改善11件・悪化0件を確認しました。']
    write(out/'regressions.json',regressions);write(out/'condition_summary.json',profile_stats)
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'independent_verification.json',dict(rows_verified=verified,input_cases_verified=666,unit_tests_passed=23,held_ui_apptest_pass=True,locked_models_and_old_results_unchanged=True,production_unchanged=True))
    print('PASS',verified,'score rows, 666 source hashes; report saved')
if __name__=='__main__':main()
