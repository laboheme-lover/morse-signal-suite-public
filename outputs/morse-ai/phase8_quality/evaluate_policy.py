from policy import PROJECT,normalize_reference,render_body
from pathlib import Path
import sys,json,csv
sys.path.insert(0,str(PROJECT/'phase6_wabun65'))
from common import read_csv,write_csv,write_json,sha
from evaluate_recording import edit_alignment
ROOT=Path(__file__).resolve().parent

def main():
    out=ROOT/'results';out.mkdir(exist_ok=False)
    old=PROJECT/'phase7_real/unified44'
    numbers=sorted(int(p.name) for p in old.iterdir() if p.is_dir())
    assert len(numbers)==44
    write_json(out/'protocol.json',{'version':'content_v2','frozen_before_scoring':True,
        'rules':['Mode parentheses excluded','Kana size unified; dakuten separated','Japanese decimal between digits -> テン; explicit international decimal stays dot',
        'Question mark preserved in reference','Unsupported observed symbol -> □ and review, never substitute rule text','Reference 77 unchanged'],
        'scope':'Post-hoc development diagnostic on 44 known recordings; not fresh generalization evaluation',
        'model_weights_changed':False,'old_scores_overwritten':False})
    protected={};results=[];review=[];changes=[]
    for n in numbers:
        folder=out/f'{n:03d}';folder.mkdir()
        rawpath=PROJECT/f'evaluation/real_collection_baseline/{n:03d}/reference_original.txt'
        raw=rawpath.read_text(encoding='utf-8');ref=normalize_reference(raw)
        protected[str(rawpath)]=sha(rawpath)
        oldrefpath=old/f'{n:03d}/reference.txt';oldref=oldrefpath.read_text(encoding='utf-8')
        protected[str(oldrefpath)]=sha(oldrefpath)
        if oldref!=ref:changes.append({'number':n,'old_length':len(oldref),'new_length':len(ref),'old_reference':oldref,'new_reference':ref})
        (folder/'reference.txt').write_text(ref,encoding='utf-8')
        for name in ('M1','M2','M3','M4'):
            src=PROJECT/'phase7_real'/('additional_four' if n in (57,62,64,67) else 'results')/f'{n:03d}/{name}_segments.csv'
            protected[str(src)]=sha(src)
            text,rows,warnings=render_body(read_csv(src))
            metric,align=edit_alignment(ref,text)
            previous=next(r for r in read_csv(old/'recording_results.csv') if int(r['number'])==n and r['model']==name)
            metric.update(model=name,number=n,old_edits=int(previous['edit_distance']),old_reference_units=int(previous['reference_units']),
                exact=int(ref==text),review_segments=sum(r['unsupported_code'] for r in rows))
            results.append(metric)
            (folder/f'{name}.txt').write_text(text,encoding='utf-8');write_csv(folder/f'{name}_alignment.csv',align)
            for r in rows:
                if r['unsupported_code']:review.append({'number':n,'model':name,'index':r['index'],'pattern':r['pattern'],
                    'raw_prediction':r['prediction'],'raw_probability':r['confidence'],'text_prediction':r['text_prediction'],'reason':r['review_reason']})
    write_csv(out/'recording_results.csv',results);write_csv(out/'reference_changes.csv',changes);write_csv(out/'review_segments.csv',review)
    summary=[]
    for name in ('M1','M2','M3','M4'):
        rows=[r for r in results if r['model']==name];n=sum(r['reference_units'] for r in rows);d=sum(r['edit_distance'] for r in rows)
        summary.append({'model':name,'reference_units':n,'edits':d,'cer':d/n,
            **{k:sum(r[k] for r in rows) for k in ('substitutions','insertions','deletions','exact','review_segments')}})
    write_csv(out/'summary.csv',summary);write_json(out/'summary.json',summary)
    for name in ('M1','M2','M3','M4'):
        p=PROJECT/f'phase6_wabun65/runs/{name.lower()}_wabun65_20260922/best.pt'
        expected=json.loads((p.parent/'training_complete.json').read_text())['checkpoint_sha256']
        assert sha(p)==expected;protected[str(p)]=expected
    assert all(sha(p)==h for p,h in protected.items())
    write_json(out/'verification.json',{'status':'PASS','protected_sources':protected,'models_unchanged':True,'records':44})
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
