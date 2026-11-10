"""Character-position warning audit using fixed saved text alignment."""
from pathlib import Path
import json,sys,csv
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent))
from morse_table import MORSE_TABLE,REVERSE_TABLE
from evaluate_recording import edit_alignment
from analyze_saved_errors import ui_review,read,write,sha

def emitted(rows):
    chars=[];inside=False
    for row in rows:
        pattern=row['pattern']
        if pattern==MORSE_TABLE['（']:inside=True;continue
        if pattern==MORSE_TABLE['）']:inside=False;continue
        if not inside and REVERSE_TABLE.get(pattern,'?') in '、」':continue
        for char in row['text_prediction']:chars.append((char,row))
    return chars

def audit(reference,text,rows):
    chars=emitted(rows)
    if ''.join(c for c,r in chars)!=text:raise ValueError('Cannot map saved hypothesis to segments')
    _,alignment=edit_alignment(reference,text);details=[]
    for a in alignment:
        index=a['hypothesis_index'];row=chars[index][1] if index!='' else None
        details.append(dict(**a,segment_index=row['index'] if row else None,
                            warned=ui_review(row) if row else False,localizable=row is not None,
                            start_seconds=row['start_seconds'] if row else None,end_seconds=row['end_seconds'] if row else None))
    return details

def summarize(rows):
    errors=[r for r in rows if r['operation']!='matches'];correct=[r for r in rows if r['operation']=='matches']
    tp=sum(r['warned'] for r in errors);fp=sum(r['warned'] for r in correct)
    deleted=sum(r['operation']=='deletions' for r in errors)
    return dict(TP=tp,FN=len(errors)-tp,FP=fp,TN=len(correct)-fp,deletions_without_output=deleted,
                error_position_recall=tp/len(errors) if errors else None,
                emitted_error_recall=tp/(len(errors)-deleted) if len(errors)>deleted else None,
                warning_precision=tp/(tp+fp) if tp+fp else None)

def main():
    out=ROOT/'position_warning_v1';out.mkdir(exist_ok=False);all_rows=[];hashes={}
    for metric in read(ROOT/'noise_expanded/results.json'):
        folder=ROOT/'noise_expanded'/metric['id'];p=folder/(metric['model']+'.json');data=read(p);meta=read(folder/'input.json')
        hashes[str(p.relative_to(ROOT.parent))]=sha(p)
        for r in audit(meta['reference'],data['text'],data['segments']):all_rows.append(dict(id=metric['id'],model=metric['model'],**r))
    summary=[dict(model=m,**summarize([r for r in all_rows if r['model']==m])) for m in ('M1','M2','M3','M4')]
    write(out/'summary.json',summary);write(out/'source_hashes.json',hashes)
    with (out/'positions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(all_rows[0]));w.writeheader();w.writerows(all_rows)
    lines=['# 文字位置での要確認評価','',
        '既存1,464件の正規化済み本文を、従来の編集距離と同じ決定的整列で対応付けました。置換・挿入の出力文字に実際に警告がある場合のみTPとします。削除には出力区間がないため、近隣文字や文章全体の警告で救済せずFNとしました。括弧制御符号は本文採点に含めません。',
        '重複文字等では最小編集距離の対応が複数あり得るため、整列上の位置評価であり、送信時刻の因果的特定ではありません。切替符号だけに出た警告は、その後の誤字に自動的には加算しません。M1～M4への既定条件0.8の模擬適用であり、配備CNNの実測ではありません。','',
        '|モデル|正しい位置の警告 TP|見逃し FN|正解文字への警告 FP|正解・警告なし TN|うち削除|誤り位置検出率|警告の適中率|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:lines.append('|'+s['model']+'|'+'|'.join(str(s[k]) for k in ('TP','FN','FP','TN','deletions_without_output'))+f"|{s['error_position_recall']:.1%}|{s['warning_precision']:.1%}|")
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
