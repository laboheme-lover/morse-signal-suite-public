"""Diagnose saved outputs without changing models, signals, or scoring."""
from pathlib import Path
import csv
import hashlib
import json
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT))
from morse_table import MORSE_TABLE
from evaluation_compare import SCHEMA, load_bundle

SIGNALS = {'wabun':'イロハニホヘト','mixed':'イ（ヤチツ）ロ','multi_mode':'イ（ヤチ）ロ（12）ハ'}

def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def write(path, obj): path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def ideal(signal, dot):
    unit = round(dot*16000); pad = round(dot*1.5*16000); cursor=0; inside=False; rows=[]
    for char in signal:
        pattern=MORSE_TABLE[char]
        duration=(sum(1 if c=='.' else 3 for c in pattern)+len(pattern)-1)*unit
        rows.append(dict(start_sample=cursor+pad,end_sample=cursor+pad+duration,
                         label=char,pattern=pattern,mode='international' if inside else 'wabun'))
        cursor += duration+2*pad
        if char in '（）': inside=char=='（'
    return rows

def diagnose(expected, observed):
    # Positive overlap with ideal tone spans, independent of predicted text.
    # Character gaps in this corpus are 3 dots.
    links=[]
    for r in observed:
        links.append([j for j,e in enumerate(expected) if min(e['end_sample'],r['end_sample'])-max(e['start_sample'],r['start_sample']) > 0])
    counts=Counter(j for link in links for j in link)
    result=dict(missing=sum(counts[j]==0 for j in range(len(expected))),
                split=sum(counts[j]>1 for j in range(len(expected))),
                merged=sum(len(link)>1 for link in links),extra=sum(not link for link in links),
                pattern_error=0,class_error=0,class_error_with_correct_pattern=0,mode_error=0,matched=0)
    for r,link in zip(observed,links):
        if len(link)!=1 or counts[link[0]]!=1: continue
        e=expected[link[0]]; result['matched']+=1
        result['pattern_error']+=r['pattern']!=e['pattern']
        if e['label'] not in '（）':
            wrong=r['prediction']!=e['label']
            result['class_error']+=wrong
            result['class_error_with_correct_pattern']+=wrong and r['pattern']==e['pattern']
            result['mode_error']+=r['mode']!=e['mode']
    return result

def ui_review(r):
    return bool(r.get('review_reason')) or (r['kind']=='character' and
        (r['confidence']<.8 or r['disagrees_with_rule'] or r['text_prediction'] in ('?','□') or r.get('error') is not None))

def confusion(rows, signal):
    tp=sum(r['edits']>0 and r[signal] for r in rows)
    fn=sum(r['edits']>0 and not r[signal] for r in rows)
    fp=sum(r['edits']==0 and r[signal] for r in rows)
    tn=sum(r['edits']==0 and not r[signal] for r in rows)
    return dict(TP=tp,FN=fn,FP=fp,TN=tn,誤り検出率=tp/(tp+fn) if tp+fn else None,
                警告中の誤り率=tp/(tp+fp) if tp+fp else None,正解時警告率=fp/(fp+tn) if fp+tn else None)

def main():
    source=ROOT/'noise_expanded'; out=ROOT/'saved_error_analysis'; out.mkdir(exist_ok=True)
    metrics=read(source/'results.json'); rows=[]; sources={}; all_segments=[]
    for path in [source/'plan.json',source/'results.json',PROJECT/'generate_morse_audio.py',PROJECT/'morse_table.py']:
        sources[str(path.relative_to(PROJECT))]=sha(path)
    for m in metrics:
        folder=source/m['id']; meta=read(folder/'input.json'); path=folder/(m['model']+'.json'); data=read(path)
        sources[str(path.relative_to(PROJECT))]=sha(path)
        sources[str((folder/'input.json').relative_to(PROJECT))]=sha(folder/'input.json')
        expected=ideal(SIGNALS[m['text_id']],m['dot_seconds']); diag=diagnose(expected,data['segments'])
        r=dict(id=m['id'],model=m['model'],input_sha256=meta['sha256'],reference=meta['reference'],hypothesis=data['text'],
               reference_units=m['reference_units'],edits=m['edit_distance'],status=m['status'],
               noise=m['noise'],snr_db=m['snr_db'],dot_seconds=m['dot_seconds'],text_id=m['text_id'],offset_seconds=m['offset_seconds'],
               baseline_alert=bool(data['warnings'] or m['review_segments'] or m['status']=='FAILED'),
               ui_alert=bool(data['warnings'] or any(ui_review(s) for s in data['segments']) or m['status']=='FAILED'),
               mode_sequence_mismatch=m['mode_pattern_sequence_mismatch'],**diag)
        rows.append(r)
        for s in data['segments']:
            all_segments.append(dict(id=m['id'],model=m['model'],index=s['index'],start_seconds=s['start_seconds'],end_seconds=s['end_seconds'],
                                     pattern=s['pattern'],prediction=s['prediction'],text_prediction=s['text_prediction'],confidence=s['confidence'],
                                     ui_review=ui_review(s),review_reason=s['review_reason'],disagrees_with_rule=s['disagrees_with_rule']))
    write(out/'cases.json',rows)
    for name,values in [('cases',rows),('segments',all_segments)]:
        with (out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    summary=[]
    for model in ('M1','M2','M3','M4'):
        rs=[r for r in rows if r['model']==model]; errors=[r for r in rs if r['edits']]
        summary.append(dict(model=model,cases=len(rs),error_cases=len(errors),edits=sum(r['edits'] for r in rs),
                            reference_units=sum(r['reference_units'] for r in rs),
                            boundary_cases=sum(any(r[k] for k in ('missing','split','merged','extra')) for r in errors),
                            pattern_cases=sum(r['pattern_error']>0 for r in errors),class_cases=sum(r['class_error']>0 for r in errors),
                            class_correct_pattern_cases=sum(r['class_error_with_correct_pattern']>0 for r in errors),
                            mode_cases=sum(r['mode_error']>0 for r in errors),mode_sequence_cases=sum(r['mode_sequence_mismatch'] for r in errors),
                            baseline=confusion(rs,'baseline_alert'),ui_default_simulation=confusion(rs,'ui_alert')))
        bundle=dict(schema=SCHEMA,name='拡充診断 '+model,scoring_policy='phase8-content-v2-normalized-codepoints',
                    scope='synthetic-noise-diagnostic',model_sha256=sha(PROJECT/f'phase6_wabun65/runs/{model.lower()}_wabun65_20260922/best.pt'),rows=rs)
        raw=json.dumps(bundle,ensure_ascii=False);load_bundle(raw.encode('utf-8'))
        (out/(model+'_comparison.json')).write_text(raw,encoding='utf-8')
    # Previous pilot is a separate saved evaluation. Its input samples differ;
    # the viewer must NOT treat aggregate differences as paired improvements.
    pilot=ROOT/'noise_pilot'; pilot_rows=[]
    for m in read(pilot/'results.json'):
        folder=pilot/m['id']; detail=folder/'results'/m['id']; model=m['model']
        segments=read(detail/(model+'_segments.json')); warnings=read(detail/(model+'_warnings.json'))
        pilot_rows.append(dict(id=m['id'],model=model,input_sha256=read(folder/'mixture.json')['wav_sha256'],
            reference=(detail/'reference.txt').read_text(encoding='utf-8').strip(),
            hypothesis=(detail/(model+'.txt')).read_text(encoding='utf-8').strip(),reference_units=m['reference_units'],edits=m['edit_distance'],status=m['status'],
            noise=m['condition'],snr_db=m['snr_db'],dot_seconds=.1,text_id='pilot_iroha',
            baseline_alert=bool(warnings or m['review_segments'] or m['status']=='FAILED'),
            ui_alert=bool(warnings or any(ui_review(s) for s in segments) or m['status']=='FAILED')))
        for path in [folder/'mixture.json',detail/'reference.txt',detail/(model+'.txt'),detail/(model+'_segments.json'),detail/(model+'_warnings.json')]:
            sources[str(path.relative_to(PROJECT))]=sha(path)
    sources[str((pilot/'results.json').relative_to(PROJECT))]=sha(pilot/'results.json')
    for model in ('M1','M2','M3','M4'):
        bundle=dict(schema=SCHEMA,name='初回予備診断 '+model,scoring_policy='phase8-content-v2-normalized-codepoints',scope='synthetic-noise-diagnostic',
                    model_sha256=sha(PROJECT/f'phase6_wabun65/runs/{model.lower()}_wabun65_20260922/best.pt'),rows=[r for r in pilot_rows if r['model']==model])
        raw=json.dumps(bundle,ensure_ascii=False);load_bundle(raw.encode('utf-8'))
        (out/('pilot_'+model+'_comparison.json')).write_text(raw,encoding='utf-8')
    write(out/'summary.json',summary)
    write(out/'provenance.json',dict(source_sha256=sources,script_sha256=sha(Path(__file__)),
                                   comparison_sha256=sha(PROJECT/'evaluation_compare.py'),ui_policy_source_sha256=sha(PROJECT/'predict_sequence.py'),
                                   threshold=.8,unit='whole-transcript case; not character warning localization',
                                   source_results_sha256=sha(source/'results.json')))
    lines=['# 保存済み推論の誤り・要確認表示の分析','',
           '366条件×4モデル＝1,464件。合成モールス＋環境音による診断であり、独立した実録音評価ではありません。モデル・評価基準・既存結果は変更していません。',
           '## 誤りの観測箇所','',
           '生成仕様から各文字の送信時刻を復元し、検出区間との時間的重なりで対応付けました。欠落・分割・結合・余分な区間を境界異常とし、一対一対応した区間だけで符号・CNNクラス・モードを照合しています。分類誤りは正解和文クラスとの比較です。括弧は制御符号で、本文文字として採点していません。',
           '各列は誤りがある文章のうち、当該現象が観測された件数です。重複があり、編集距離の原因別分配や因果関係の証明ではありません。境界一致も切り出し波形の完全性を保証しません。',
           '', '|モデル|誤り文章/366|編集距離|境界異常|符号誤り|CNN分類誤り|符号正解でもCNN誤り|モード誤り|開閉符号列不一致|',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        lines.append('|'+s['model']+'|'+'|'.join(str(s[k]) for k in ('error_cases','edits','boundary_cases','pattern_cases','class_cases','class_correct_pattern_cases','mode_cases','mode_sequence_cases'))+'|')
    lines+=['','## 要確認表示の診断','',
            '評価単位は文章1件です。TP＝誤りあり・警告あり、FN＝誤りあり・警告なし、FP＝本文正解・警告あり、TN＝本文正解・警告なし。警告が誤った文字を正しく指しているかは、この集計では評価していません。FPも確認が無意味だという意味ではありません。',
            '保存時の警告（未対応符号・モード異常・処理失敗等）と、既存アプリの既定条件（予測確率0.8未満・CNNと符号の不一致等）をM1～M4の保存結果に適用したシミュレーションを区別します。現在の配備CNNの実測成績ではありません。しきい値は調整していません。','',
            '|モデル|警告条件|TP|FN|FP|TN|誤り検出率|警告中の誤り率|正解時警告率|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        for key,label in [('baseline','保存時'),('ui_default_simulation','アプリ既定条件の模擬適用')]:
            c=s[key];lines.append('|'+s['model']+'|'+label+'|'+'|'.join(str(c[k]) for k in ('TP','FN','FP','TN'))+'|'+'|'.join('—' if c[k] is None else f'{c[k]:.1%}' for k in ('誤り検出率','警告中の誤り率','正解時警告率'))+'|')
    lines+=['','同一録音の切出し・同一文章の反復であり、1,464件を独立標本として統計的優劣を主張しません。検出率は予測確率の校正精度ではありません。',
            '警告なし誤りの残例：M3 / mixed_d160_STRAFFIC_o200_s-5。正解「イWFPロ」に対し「ウWFPロ」。観測符号とCNNが同じ誤りで一致し、予測確率も0.8以上だったため、模擬表示では警告できませんでした。',
            '詳細はcases.csv（全件）、segments.csv（全区間）、summary.json、入力結果のハッシュはprovenance.json。比較画面用のM1～M4_comparison.jsonを添付しています。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
