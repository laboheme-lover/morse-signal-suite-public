"""Audit the memory candidate without modifying previous results."""
from pathlib import Path
import sys,statistics
ROOT=Path(__file__).resolve().parent;P=ROOT.parent;sys.path[:0]=[str(ROOT),str(P)]
from recording_experiment import read,save
from intake import digest
import evaluate_new as runner

def main():
    out=ROOT/'real_low_memory_v1';old=ROOT/'real_adaptive_v1';plan=read(out/'acceptance_plan.json')
    assert digest(old/'results.json')==plan['old_results_sha256']
    assert digest(ROOT/'low_memory_frontend.py')==plan['low_memory_frontend_sha256']
    runner.verify_frozen();manifest=read(out/'manifest.json');comparisons=[];delta_max=0
    assert read(out/'verification.json')['completed']
    for entry in manifest['recordings']:
        a=read(old/entry['id']/'result.json');b=read(out/entry['id']/'result.json')
        assert a['input_sha256']==b['input_sha256']==entry['audio_sha256']
        for key,x in a['outputs'].items():
            y=b['outputs'][key];patterns_equal=[r['pattern'] for r in x['segments']]==[r['pattern'] for r in y['segments']]
            delta=None
            if patterns_equal and x['segments']:
                delta=max(abs(r[k]-s[k]) for r,s in zip(x['segments'],y['segments']) for k in ['start_sample','end_sample']);delta_max=max(delta_max,delta)
            comparisons.append(dict(id=entry['id'],method_model=key,text_equal=x['text']==y['text'],error_equal=x['error']==y['error'],patterns_equal=patterns_equal,max_boundary_sample_change=delta))
    assert len(comparisons)==1056
    changed=[r for r in comparisons if not (r['text_equal'] and r['error_equal'] and r['patterns_equal'])]
    save(out/'parity.json',dict(rows=len(comparisons),changes=changed,max_boundary_sample_change=delta_max,details=comparisons))
    perf=read(out/'performance.json');oldperf=read(old/'performance.json');bench=read(out/'fresh_process_benchmark/comparison.json')
    synth=read(out/'synthetic_replay/verification.json')
    accepted=not changed and bench['outputs_equal'] and bench['new_peak_mib']<bench['original_peak_mib'] and not any(synth[k] for k in ['text_changes','pattern_changes','error_changes'])
    # Separate names let the viewer distinguish equal scoring policies and scopes.
    for path in (out/'comparisons').glob('*.json'):
        bundle=read(path);bundle['name']='low_memory_'+bundle['name'];save(out/'viewer_comparisons'/path.name,bundle)
    text=['# 長い実録音のメモリ削減・検証報告','',
        '実施日：2026年9月23日。省メモリ版の一括評価を追加しました。従来版・通常アプリ・モデル重み・既存評価結果は変更していません。','',
        '## 変更点','',
        '音程検出に使う周波数解析を小分けに行い、全録音分の大きな周波数配列を同時に保持しないようにしました。位相の回転計算も小分けにし、中間配列を使い終わった時点で解放します。', '',
        'ヒルベルト変換は実数FFTと計算しやすい長さへのゼロ詰めを利用します。この変更は録音端の数値的な扱いを変えるため、元の波形とビット単位で同一とは主張しません。通常版を置き換えず、別の実装として同じ音声で検証しました。', '',
        '## 認識結果への影響','',
        f'- 既知44録音、6方式×M1〜M4の1,056結果を比較。本文・点線列・処理成否の不一致は{len(changed)}件。',
        f'- 対応する文字区間の境界の最大差：{delta_max}サンプル（{delta_max/16:.4f} ms）。',
        '- 比較に使った本文範囲・正解文・モデル・採点規則は前回から固定。括弧の和欧切替処理も同じです。',
        f"- 既存の合成144条件を再実行し、従来処理と統合処理の1,152結果で本文差{ synth['text_changes']}件、点線列差{synth['pattern_changes']}件、処理成否差{synth['error_changes']}件。",
        '- これは既知データでの退行確認であり、未知録音への汎化性能やモデル採用の判断ではありません。','',
        '## メモリ測定','',
        '最長の064（約20.8分）について、従来版と省メモリ版を別々の新しいPythonプロセスで順番に実行しました。全4モデルを読み、6方式で処理する同じ条件です。','',
        '| 最長録音・新しいプロセスでの測定 | 従来版 | 省メモリ版 |','|---|---:|---:|',
        f"| 最大ワーキングセット | {bench['original_peak_mib']/1024:.2f} GiB | {bench['new_peak_mib']/1024:.2f} GiB |",
        f"| 音声読込＋6方式×4モデルの処理時間 | {bench['original_seconds']:.1f}秒 | {bench['new_seconds']:.1f}秒 |",'',
        f"この条件での最大メモリ削減率は{bench['reduction_fraction']:.1%}でした。最大メモリにはPython、ライブラリ、4モデル、音声処理用配列を含みます。PC全体やブラウザーの使用量ではありません。",'',
        '各方式1回の測定で、OSのディスクキャッシュは消していません。速度は参考値であり、繰り返し測定の平均ではありません。メモリのピークはプロセス起動から測定しています。','',
        f"44録音の連続評価では、プロセス全体の最大メモリが前回{max(r['memory_after']['peak_mib'] for r in oldperf)/1024:.2f} GiB、今回は{max(r['memory_after']['peak_mib'] for r in perf)/1024:.2f} GiBでした。連続評価は別のテストも動作中だったため、速度比較の根拠には上の単独プロセス測定を使います。",'',
        '## 判定と使い方','',
        ('事前に決めた認識結果の維持・メモリ削減条件を満たしました。省メモリ版を一括評価の選択肢として利用できます。' if accepted else '事前条件に未達の項目があります。通常利用へは採用せず、検証用として結果を保存します。'),'',
        '新規評価では `batch_recordings_low_memory.py` を使います。入力一覧の形式、出力先の固定、途中再開の方法は従来の一括評価と同じです。従来コマンドと同じ出力先を混ぜて使わないでください。詳細はプロジェクト直下「省メモリ一括評価の使い方.md」。', '',
        '今回確認した実録音は4.9〜20.8分です。30分は入力受付の上限であり、30分の実録音での完走確認ではありません。録音全体の配列とモデルは保持するので、メモリ使用量が録音の長さによらず一定になる仕組みではありません。', '',
        '自動切り戻しの補正ガードは前回の検証で一部の誤りを増やしたため、引き続き採用保留です。今回のメモリ削減によって、その判断は変えません。', '',
        '## 保存した証跡','',
        '- manifest.json／acceptance_plan.json：入力、コード、採用条件の固定。',
        '- results.json／summary.json：実録音の評価。',
        '- parity.json：従来実装との1,056結果の比較。',
        '- fresh_process_benchmark/：個別プロセスでのメモリと時間の測定。',
        '- synthetic_replay/：合成144条件の再確認。',
        '- completion_checks.json：テストと最終確認の記録。','']
    (out/'report.md').write_text('\n'.join(text),encoding='utf-8')
    save(out/'acceptance_result.json',dict(accepted_as_optional_batch=accepted,production_changed=False,changed_rows=len(changed),fresh_process_comparison=bench,synthetic=synth))
    print('Optional batch acceptance:',accepted,flush=True)

if __name__=='__main__':main()
