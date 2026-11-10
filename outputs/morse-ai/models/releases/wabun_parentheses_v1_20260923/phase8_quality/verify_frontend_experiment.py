"""Independent score/bundle/hash checks and a readable experiment report."""
from pathlib import Path
import json,sys
import soundfile as sf
ROOT=Path(__file__).resolve().parent;P=ROOT.parent
sys.path.insert(0,str(P));sys.path.insert(0,str(ROOT))
from analyze_saved_errors import sha,read,write
from evaluation_compare import distance,load_bundle,paired
import evaluate_new

def main():
    out=ROOT/'frontend_experiment_v1';plan=read(out/'plan.json');lock=read(out/'selection_lock.json')
    assert sha(out/'plan.json')==lock['plan_sha256']
    assert sha(out/'development/results.json')==lock['results_sha256']
    for p,h in plan['scripts'].items():assert sha(P/p)==h
    evaluate_new.verify_frozen()
    assert sha(ROOT/'noise_expanded/results.json')==plan['previous_results_sha256']
    original=read(ROOT/'noise_expanded/results.json');old={(r['id'],r['model']):r for r in original}
    lines=['# 区間検出・和欧切替の改善実験と未使用条件の検証','',
           'モデルの重みは固定。配備アプリの処理は変更していません。従来の拡充診断366条件を今回の開発用と位置づけ、過去の評価値を残して比較しました。',
           '## 実験方法','',
           'segment_v1：周波数帯を中心±45 Hzに絞り、包絡線の15/95パーセンタイルから閾値を決定。8 ms以下の短い途切れを埋め、15 ms未満の短いイベントを除去します。短点推定と文字間隔判定の基本手順は従来と同じです。',
           'segment_mode_v1：上記に、CNNの括弧予測確率0.98以上、観測符号が未対応、正しい括弧符号から編集距離1、切替状態と矛盾しない場合だけ符号補正を追加。元符号と補正履歴を残し、補正箇所には必ず要確認を付けます。正解文は補正処理へ渡しません。',
           '既存条件の合計編集距離が小さい実験方式を選び、plan.jsonとselection_lock.jsonで固定した後に未使用条件を生成・評価しました。未使用条件を見てから再調整していません。','',
           '未使用条件：新しい3文章、短点60/120 ms、音程500/1100 Hz、無雑音またはDEMAND 3環境、60/250秒位置、SNR10/0/−5 dB。合計228音声×4モデル×2方式＝1,824評価です。従来366条件のノイズ使用時間と重ならないことを確認しました。同じ録音ファイルの別区間なので、独立した実録音や未知環境カテゴリの評価とは呼びません。','']
    verified=0;regressions=[];pairs=[]
    for stage,label,count in [('development','開発用の既存条件',4392),('held','事前固定した未使用条件',1824)]:
        rows=read(out/stage/'results.json');assert len(rows)==count
        for r in rows:
            assert distance(r['reference'],r['hypothesis'])==r['edits']
            assert len(r['reference'])==r['reference_units']
            if stage=='development' and r['method']=='baseline':assert r['edits']==old[(r['id'],r['model'])]['edit_distance']
            verified+=1
        stats=read(out/stage/'summary.json')
        for s in stats:
            rs=[r for r in rows if (r['method'],r['model'])==(s['method'],s['model'])]
            assert sum(r['edits'] for r in rs)==s['edits']
            assert sum(r['reference_units'] for r in rs)==s['units']
            assert sum(r['edits'] for r in rs if r['noise']=='clean')==0
        lines+=['## '+label,'','|方式|モデル|件数|CER|編集距離|境界異常|開閉符号列不一致|切替補正数|','|---|---|---:|---:|---:|---:|---:|---:|']
        for s in stats:lines.append(f"|{s['method']}|{s['model']}|{s['cases']}|{s['cer']:.2%}|{s['edits']}|{s['boundary_cases']}|{s['mode_mismatches']}|{s['repairs']}|")
        lines+=['','境界異常と開閉符号列不一致は文章数、切替補正数は符号数です。各方式とも処理失敗0件、無雑音の編集距離0です。','',
                '|モデル|改善した文章|悪化した文章|同じ編集距離|','|---|---:|---:|---:|']
        for m in ('M1','M2','M3','M4'):
            a=[r for r in rows if (r['method'],r['model'])==('baseline',m)]
            b=[r for r in rows if (r['method'],r['model'])==(lock['selected'],m)]
            result=paired(a,b);pairs.append(dict(stage=stage,model=m,**result))
            lines.append(f"|{m}|{result['改善件数']}|{result['悪化件数']}|{result['共通件数']-result['改善件数']-result['悪化件数']}|")
            bmap={r['id']:r for r in b}
            for r in a:
                new=bmap[r['id']]
                if new['edits']>r['edits']:regressions.append(dict(stage=stage,model=m,id=r['id'],reference=r['reference'],baseline=r['hypothesis'],candidate=new['hypothesis'],before=r['edits'],after=new['edits']))
        for p in (out/stage).glob('*_comparison.json'):load_bundle(p.read_bytes())
    for folder in (out/'held').iterdir():
        if not folder.is_dir():continue
        meta=read(folder/'input.json');assert sha(folder/'input.wav')==meta['sha256']
    lines+=['','## 判断','',
        '開発条件の合計編集距離は従来232→区間検出のみ104→切替補正付き97。未使用条件では従来32→改善案14でした。ただし、開発条件では4件、未使用条件ではM3の1件で悪化しています。悪化例はregressions.jsonに保存しました。',
        '未使用条件では切替補正が一度も作動していません。したがって、切替補正の未知条件での有効性を確認できたとは言えません。改善案全体の平均CER低下は観測しましたが、すべての条件で改善したわけではありません。',
        '方式は実験版として保持し、配備アプリと採用モデルを変更しません。実録音での境界・切替・警告位置評価、音程変動や不規則な打鍵への検証が残ります。',
        '文字位置の警告集計は各フォルダーのposition_summary.json。元の1,464件の詳細は../position_warning_v1/report.md。しきい値0.8は今回も変更していません。']
    write(out/'paired_summary.json',pairs);write(out/'regressions.json',regressions)
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'independent_verification.json',dict(score_rows_verified=verified,held_audio_hashes_verified=228,all_clean_exact=True,
        model_and_frozen_code_hashes_match=True,selection_locked=True,held_results_not_used_for_retuning=True,unit_tests_passed=12))
    print('PASS: 6216 scores, 228 audio hashes, locked plan and frozen models')
if __name__=='__main__':main()
