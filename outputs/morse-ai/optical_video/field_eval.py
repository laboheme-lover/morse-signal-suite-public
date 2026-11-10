"""Frozen, grouped field-video evaluation. No training or automatic tuning."""
from pathlib import Path
import argparse,csv,hashlib,json,math,re,time,unicodedata
import numpy as np
import cv2
from optical_video.core import read_trace,analyze_trace

ROOT=Path(__file__).resolve().parents[1]
METHODS=('fixed','adaptive','change_aware')
POLICY='optical-transcript-v1'
CODE=('optical_video/field_eval.py','optical_video/core.py','optical_video/adaptive.py','optical_video/change_points.py','optical_video/diagnostics.py','morse_table.py')

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def normalize(text):
    # Preserve punctuation and decimals. Parentheses are mode controls, not text.
    text=unicodedata.normalize('NFKC',text);out=[];inside=False
    for c in text:
        if c=='(':
            if inside:raise ValueError('Nested mode parentheses')
            inside=True;continue
        if c==')':
            if not inside:raise ValueError('Unmatched mode close')
            inside=False;continue
        if c.isspace():continue
        if 'ぁ'<=c<='ゖ':c=chr(ord(c)+0x60)
        if c.isascii():c=c.upper()
        out.append(c)
    if inside:raise ValueError('Unclosed mode parentheses')
    return unicodedata.normalize('NFD',''.join(out))

def score(reference,hypothesis):
    # Linear-memory Levenshtein with deterministic S, then D, then I tie handling.
    previous=[(j,0,j,0) for j in range(len(hypothesis)+1)]
    for i,a in enumerate(reference,1):
        row=[(i,0,0,i)]
        for j,b in enumerate(hypothesis,1):
            d,s,ins,delete=previous[j-1];sub=(d+(a!=b),s+(a!=b),ins,delete)
            d,s,ins,delete=previous[j];drop=(d+1,s,ins,delete+1)
            d,s,ins,delete=row[-1];add=(d+1,s,ins+1,delete)
            row.append(min((sub,drop,add),key=lambda x:x[0]))
        previous=row
    d,s,i,de=previous[-1]
    return dict(reference_units=len(reference),edits=d,substitutions=s,insertions=i,deletions=de,cer=d/len(reference) if reference else None,exact=reference==hypothesis)

def freeze(manifest_path,lock_path):
    manifest_path=Path(manifest_path).resolve();lock_path=Path(lock_path)
    if lock_path.exists():raise FileExistsError(lock_path)
    m=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if m.get('schema')!='optical-field-manifest-v1' or m.get('source_review_completed') is not True:raise ValueError('Complete the manifest and source review first')
    if not m.get('videos'):raise ValueError('Empty manifest is not an accepted evaluation')
    if m.get('normalization')!=POLICY:raise ValueError('Explicit normalization policy required')
    rows=[];ids=set();hashes=set();groups={};prior_hashes=set();prior_text=set();prior_groups={};prior_files={}
    for name in m.get('prior_locks',[]):
        p=(manifest_path.parent/name).resolve();old=json.loads(p.read_text(encoding='utf-8'))
        prior_files[str(p)]=sha(p)
        for r in old['videos']:
            prior_hashes.add(r['video_sha256']);prior_text.add(r['normalized_reference']);prior_groups.setdefault(r['group_id'],set()).add(r['role'])
    for source in m['videos']:
        r=dict(source);ident=r.get('id','');group=r.get('group_id');role=r.get('role')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',ident) or ident in ids:raise ValueError('Invalid/duplicate video id')
        if not isinstance(group,str) or not group or role not in ('development','selection','final','rehearsal'):raise ValueError('Specify group and role')
        if group in groups and groups[group]!=role:raise ValueError('A recording group cannot span roles')
        if group in prior_groups and prior_groups[group]!={role}:raise ValueError('Historical group spans roles')
        if role=='final' and r.get('declared_unseen') is not True:raise ValueError('Final requires confirmed unseen status')
        for field in ('source','camera','exposure','conditions'):
            if not isinstance(r.get(field),str) or not r[field].strip():raise ValueError('Missing '+field)
        video=(manifest_path.parent/r['video']).resolve();ref=(manifest_path.parent/r['reference']).resolve()
        if not video.is_file() or video.suffix.lower() not in ('.avi','.mp4') or not 0<video.stat().st_size<=200*1024**2:raise ValueError('Invalid video file or size')
        text=normalize(ref.read_text(encoding='utf-8-sig'))
        if not 0<len(text)<=5000:raise ValueError('Reference must have 1..5000 normalized units')
        vh=sha(video)
        if vh in hashes:raise ValueError('Duplicate video bytes')
        if role=='final' and (vh in prior_hashes or text in prior_text):raise ValueError('Final overlaps historical video/reference')
        roi=r.get('roi')
        if not isinstance(roi,list) or len(roi)!=4 or any(type(v) is not int for v in roi) or min(roi[:2])<0 or min(roi[2:])<=0:raise ValueError('Invalid ROI')
        bounds=r.get('range_seconds')
        if not isinstance(bounds,list) or len(bounds)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in bounds) or not 0<=bounds[0]<bounds[1]<=600:raise ValueError('Explicit time range required')
        options=r.get('options',{})
        if set(options)-{'dot_seconds','invert','mixed','character_gap_seconds'}:raise ValueError('Unsupported or method-specific option')
        for k in ('dot_seconds','character_gap_seconds'):
            if options.get(k) is not None and (type(options[k]) not in (int,float) or not math.isfinite(options[k]) or options[k]<=0):raise ValueError('Invalid timing option')
        for k in ('invert','mixed'):
            if k in options and type(options[k]) is not bool:raise ValueError('Invalid boolean option')
        if options.get('mixed',True) is not True:raise ValueError('This evaluation policy requires mixed mode')
        r.update(video=str(video),reference=str(ref),video_sha256=vh,reference_sha256=sha(ref),normalized_reference=text,options=options)
        ids.add(ident);hashes.add(vh);groups[group]=role;rows.append(r)
    # A familiar transcript in a different split also leaks information.
    for r in rows:
        if r['role']=='final' and any(o['role']!='final' and o['normalized_reference']==r['normalized_reference'] for o in rows):raise ValueError('Final reference overlaps development/selection')
    result=dict(schema='optical-field-lock-v1',normalization=POLICY,manifest=str(manifest_path),manifest_sha256=sha(manifest_path),prior_locks=prior_files,
        code_sha256={name:sha(ROOT/name) for name in CODE},versions=dict(numpy=np.__version__,opencv=cv2.__version__),videos=rows,
        limitations='Byte and transcript duplicates only; recompression/crops and undisclosed past use require human review. Roles and references are frozen before inference.')
    lock_path.parent.mkdir(parents=True,exist_ok=True);write_json(lock_path,result);return result

def verify(lock):
    if lock.get('schema')!='optical-field-lock-v1' or lock.get('normalization')!=POLICY:raise ValueError('Unsupported lock')
    paths={lock['manifest']:lock['manifest_sha256'],**lock['prior_locks']}
    paths.update({str(ROOT/n):h for n,h in lock['code_sha256'].items()})
    for r in lock['videos']:paths.update({r['video']:r['video_sha256'],r['reference']:r['reference_sha256']})
    for p,h in paths.items():
        if sha(p)!=h:raise ValueError('Frozen file changed: '+p)
    if lock['versions']!=dict(numpy=np.__version__,opencv=cv2.__version__):raise ValueError('Runtime versions changed')

def aggregate(rows):
    total=sum(r['reference_units'] for r in rows);edits=sum(r['edits'] for r in rows)
    return dict(recordings=len(rows),reference_units=total,edits=edits,cer=edits/total if total else None,
        substitutions=sum(r['substitutions'] for r in rows),insertions=sum(r['insertions'] for r in rows),deletions=sum(r['deletions'] for r in rows),
        exact=sum(r['exact'] for r in rows),failed=sum(r['status']=='FAILED' for r in rows),review=sum(r['status']=='REVIEW' for r in rows),
        silent_errors=sum(r['edits']>0 and r['status']=='OK' for r in rows),correct_but_review=sum(r['exact'] and r['status']=='REVIEW' for r in rows))

def run(lock_path,output):
    lock_path=Path(lock_path).resolve();lock_bytes=lock_path.read_bytes();lock=json.loads(lock_bytes);verify(lock)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'lock.json').write_bytes(lock_bytes);write_json(output/'status.json',{'status':'RUNNING','lock_sha256':hashlib.sha256(lock_bytes).hexdigest()})
    rows=[]
    try:
        for item in lock['videos']:
            folder=output/item['id'];folder.mkdir();shared_error='';begin=time.perf_counter()
            try:info,t,b=read_trace(item['video'],tuple(item['roi']),*item['range_seconds'])
            except (ValueError,OSError,cv2.error) as exc:shared_error=str(exc)
            decode_seconds=time.perf_counter()-begin
            for method in METHODS:
                start=time.perf_counter();result=None;error=shared_error
                if not error:
                    try:result=analyze_trace(t,b,info['fps'],threshold_method=method,**item['options'])
                    except (ValueError,cv2.error) as exc:error=str(exc)
                text=result['text'] if result else '';normalized=normalize(text)
                row=dict(id=item['id'],group_id=item['group_id'],role=item['role'],method=method,status=result['status'] if result else 'FAILED',
                    **score(item['normalized_reference'],normalized),warnings=len(result['warnings']) if result else 0,error=error,
                    decode_seconds=decode_seconds,analysis_seconds=time.perf_counter()-start)
                rows.append(row);(folder/(method+'.txt')).write_text(text,encoding='utf-8')
                write_json(folder/(method+'.json'),dict(metrics=row,reference=item['normalized_reference'],hypothesis=normalized,analysis=result))
        verify(lock)
        if lock_path.read_bytes()!=lock_bytes:raise ValueError('Lock changed during run')
        summary=[];group_summary=[]
        for role in sorted({r['role'] for r in rows}):
            for method in METHODS:
                subset=[r for r in rows if r['role']==role and r['method']==method]
                summary.append(dict(role=role,method=method,**aggregate(subset)))
                for group in sorted({r['group_id'] for r in subset}):group_summary.append(dict(role=role,method=method,group_id=group,**aggregate([r for r in subset if r['group_id']==group])))
        for name,values in [('recordings',rows),('summary',summary),('groups',group_summary)]:
            write_json(output/(name+'.json'),values)
            with (output/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
        status='COMPLETE_WITH_FAILURES' if any(r['status']=='FAILED' for r in rows) else 'COMPLETE'
        write_json(output/'status.json',dict(status=status,lock_sha256=hashlib.sha256(lock_bytes).hexdigest(),files_unchanged=True))
        lines=['# 動画一括評価','', '正規化：濁点を独立単位に分解、空白とモード括弧を除外。句読点・小数点は保持。旧音声評価のCERと直接比較しない。',
               '失敗は空の本文として全削除に計上。参考本文では採点しない。警告数は誤り数ではない。rehearsalは動作試験であり実撮影・独立評価ではない。','',
               '|区分|方式|件数|CER|完全一致|失敗|警告なしの誤り|正解だが要確認|','|---|---|---:|---:|---:|---:|---:|---:|']
        lines += [f"|{r['role']}|{r['method']}|{r['recordings']}|{r['cer']:.2%}|{r['exact']}|{r['failed']}|{r['silent_errors']}|{r['correct_but_review']}|" for r in summary]
        (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return summary
    except Exception as exc:
        write_json(output/'status.json',dict(status='ABORTED',error=str(exc)));raise

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('freeze');a.add_argument('manifest');a.add_argument('lock')
    a=s.add_parser('verify');a.add_argument('lock')
    a=s.add_parser('run');a.add_argument('lock');a.add_argument('output')
    a=p.parse_args()
    if a.action=='freeze':freeze(a.manifest,a.lock)
    elif a.action=='verify':verify(json.loads(Path(a.lock).read_text(encoding='utf-8')))
    else:
        result=run(a.lock,a.output)
        if any(r['failed'] for r in result):return 2
    print('PASS');return 0

if __name__=='__main__':raise SystemExit(main())
