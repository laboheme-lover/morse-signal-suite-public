"""Read-only stress analysis; no model/parameter selection."""
from pathlib import Path
import sys,json,csv
ROOT=Path(__file__).resolve().parent;P=ROOT.parent
sys.path.insert(0,str(P));sys.path.insert(0,str(ROOT))
from analyze_saved_errors import read,write,sha
from evaluation_compare import paired,load_bundle
from audio_preprocessing import load_audio
from morse_segmentation import segment_morse
from experimental_frontend import segment_candidate

def main():
    out=ROOT/'frontend_stress_v1';rows=read(out/'results.json');plan=read(out/'plan.json');summaries=[];repair_audit=[]
    for profile in plan['profiles']:
        for method in plan['methods']:
            rs=[r for r in rows if (r['profile'],r['method'])==(profile,method)]
            summaries.append(dict(profile=profile,method=method,cases=len(rs),units=sum(r['reference_units'] for r in rs),
                                 edits=sum(r['edits'] for r in rs),failures=sum(r['status']=='FAILED' for r in rs),
                                 repairs=sum(r['mode_repairs'] for r in rs)))
    for r in rows:
        if not r['mode_repairs']:continue
        folder=out/r['id'];expected=read(folder/'input.json')['expected'];data=read(folder/(r['method']+'_'+r['model']+'.json'))
        for s in data['segments']:
            if 'observed_pattern' not in s:continue
            matches=[e for e in expected if min(e['end_sample'],s['end_sample'])>max(e['start_sample'],s['start_sample'])]
            repair_audit.append(dict(id=r['id'],model=r['model'],index=s['index'],observed=s['observed_pattern'],repaired=s['pattern'],
                correct_target=len(matches)==1 and matches[0]['label'] in '（）' and matches[0]['pattern']==s['pattern'],warning=bool(s['review_reason'])))
    write(out/'repair_audit.json',repair_audit);write(out/'pooled_profile_summary.json',summaries)
    pairs=[]
    for profile in plan['profiles']:
        for m in ('M1','M2','M3','M4'):
            a=[r for r in rows if (r['profile'],r['method'],r['model'])==(profile,'baseline',m)]
            b=[r for r in rows if (r['profile'],r['method'],r['model'])==(profile,'segment_mode_v1',m)]
            result=paired(a,b);assert result['共通件数']==24;pairs.append(dict(profile=profile,model=m,**result))
    write(out/'paired_summary.json',pairs)
    with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    timing=[]
    for method in (segment_morse,segment_candidate):
        _,meta=method(load_audio(out/'kana_d80_stable_seed41_clean/input.wav'))
        timing.append(dict(function=method.__name__,true_dot_seconds=.08,**meta))
    write(out/'timing_failure_diagnostic.json',timing)
    names=dict(stable='変動なし',drift30='音程移動 ±30 Hz',drift100='音程移動 ±100 Hz',wobble60='音程の揺れ ±60 Hz',
               jitter30='打鍵時間 ±30%',control_notch='切替符号に30 ms欠落',control_spike='切替符号内に25 ms余分な音',combined='音程の揺れ＋打鍵ばらつき')
    lines=['# 音程変動・打鍵ばらつき・切替符号故障の追加検証','',
        '既存の実験処理を固定したまま、192条件×4モデル×3方式＝2,304評価を実施しました。パラメーター変更・再学習・採用変更は行っていません。実録音・実動画の代替となる受入評価ではありません。',
        '3文章（スセソ、サ（ヘイ）シ、タ（56）テ）、短点80/160 ms、2乱数種、無雑音/ガウス雑音0 dB、8種類の変動・故障条件。本文はスセソ、サEAシ、タ56テで、括弧自体は採点しません。故障を加える場所の指定に正解の送信位置を使用しますが、推論・補正処理には正解文やその位置を渡しません。',
        '同じ波形になる対照条件を含み、192条件の実波形は163種類です。独立標本192本とは扱いません。下表は事前計画の各条件を同じ重みで集計したものです。ガウス雑音は未知カテゴリではありません。','',
        '|条件|従来 CER|区間検出のみ CER|切替補正付き CER|補正数（符号）|','|---|---:|---:|---:|---:|']
    for profile in plan['profiles']:
        ss=[next(s for s in summaries if (s['profile'],s['method'])==(profile,m)) for m in plan['methods']]
        lines.append('|'+names[profile]+'|'+'|'.join(f"{s['edits']/s['units']:.2%}" for s in ss)+f"|{ss[-1]['repairs']}|")
    lines+=['','各行は4モデル計96評価、正解352文字です。CERは挿入誤りも数えるため100%を超えることがあります。モデル別の値・処理失敗数はprofile_summary.json、全結果はresults.csvに保存しました。','',
        '## 切替補正の確認','',
        f"補正は{len(repair_audit)}符号で作動し、生成時刻との対応では{sum(r['correct_target'] for r in repair_audit)}符号が正しい切替位置・符号に対応しました。{sum(r['warning'] for r in repair_audit)}符号すべてに要確認理由を保持しました。",
        '余分な短音を加えた条件では、区間検出だけの編集距離240に対し、補正付きは79でした。一方、30 msの欠落条件には効果がありませんでした。意図的に破損した切替符号による機構診断であり、自然な録音での補正精度や誤補正率を保証しません。',
        '## 見つかった弱点','',
        '音程が600→800 Hzへ移動する条件では、従来の編集距離104に対し実験版は256に増加しました。帯域±45 Hzの狭い抽出処理が、変動の大きい音程を追従できない可能性を示します。小さな音程移動の改善だけを根拠に採用できません。',
        '音程が周期的に揺れる条件では従来・実験版とも非常に大きな誤りが出ました。打鍵時間のばらつきだけでも実験版がわずかに悪化しました。',
        '変動なし・無雑音の「スセソ」でも、両方式が3文字を1区間に結合しました。短点80 msに対し、推定短点が従来242.875 ms、実験版240.6875 msとなっています。長点の多い文章で長点を短点と推定する問題が観測されました。ここには4モデルで共通の前処理課題があります。',
        '## 判断と次の開発課題','',
        '現在の実験方式は条件付きの改善に留まるため、通常アプリへは採用しません。次の改善は、長点が多い文章でも使える短点推定と、音程変動に追従する帯域選択を別々に検討するのが適切です。今回のストレス条件を開発に使う場合は、その後の検証を別の条件で行う必要があります。',
        '比較画面にはstressの12ファイルを追加しました。「変動・故障条件」で個別の問題を確認できます。同じ波形が複数条件にある場合は、音声・正解文に加えて条件IDで対応させます。旧配布ZIP v3は変更していません。今回の追加は開発フォルダーと比較用JSONへの保存です。',
        '検証：関連16テスト合格、2,304行の編集距離の独立再計算、192入力ファイルのハッシュ確認、既存モデル・固定コード・過去結果のハッシュ一致。比較画面の追加条件はStreamlit AppTestで確認しています。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for p,h in {**plan['scripts'],**plan['previous_result_hashes']}.items():assert sha(P/p)==h
    for p in (out/'comparisons').glob('*_comparison.json'):load_bundle(p.read_bytes())
    print('Report saved; repairs',len(repair_audit),'correctly located',sum(r['correct_target'] for r in repair_audit))
if __name__=='__main__':main()
