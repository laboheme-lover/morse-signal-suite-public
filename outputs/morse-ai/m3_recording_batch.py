"""Portable adopted-M3 batch; frozen historical runners are unchanged."""
from pathlib import Path
import argparse,hashlib,json,sys,msvcrt
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P/'phase8_quality'))
from batch_preflight import inspect,display
from adopted_m3 import M3Single,RELEASE
from evaluate_new import infer,select_body
from audio_preprocessing import load_audio
from morse_segmentation import segment_morse
from morse_table import REVERSE_TABLE
from wabun_runtime_policy import render_body,normalize_reference,VERSION
from evaluate_recording import edit_alignment

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):
 p=Path(p);t=p.with_suffix('.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8');t.replace(p)
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--resume',action='store_true');ap.add_argument('--check-only',action='store_true');ap.add_argument('--report',type=Path);ap.add_argument('--limit',type=int);a=ap.parse_args(argv)
 if not a.resume and a.manifest is None:ap.error('--manifest is required')
 out=a.output.resolve();report=inspect(a.manifest or out/'manifest.json',out,a.resume);display(report)
 if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 if report['status']!='READY':return 2
 if a.check_only:return 0
 if not a.resume:
  rows=[]
  for e in read(a.manifest)['recordings']:
   audio=(a.manifest.resolve().parent/e['audio']).resolve();ref=(a.manifest.resolve().parent/e['reference']).resolve()
   rows.append(dict(id=e['id'],audio=str(audio),reference_path=str(ref),audio_sha256=digest(audio),reference_sha256=digest(ref),normalized_reference=normalize_reference(ref.read_text(encoding='utf-8-sig')),body=e['body']))
  out.mkdir(parents=True);save(out/'manifest.json',dict(model='M3',frontend='baseline',policy=VERSION,release_manifest_sha256=digest(RELEASE/'release_manifest.json'),code_hashes={str(f.relative_to(P)):digest(f) for f in [Path(__file__),P/'wabun_runtime_policy.py',P/'adopted_m3.py',P/'phase8_quality/evaluate_new.py',P/'morse_segmentation.py',P/'recognition_policy.py']},recordings=rows));(out/'manifest.sha256').write_text(digest(out/'manifest.json'),encoding='ascii')
 with (out/'execution.lock').open('a+b') as lock:
  lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:raise ValueError('この出力先は実行中です。')
  try:
   assert digest(out/'manifest.json')==(out/'manifest.sha256').read_text();manifest=read(out/'manifest.json')
   if manifest.get('model')!='M3' or manifest.get('policy')!=VERSION:raise ValueError('再開できるのはv5のM3和文評価フォルダーだけです。')
   assert digest(RELEASE/'release_manifest.json')==manifest['release_manifest_sha256']
   for rel,h in manifest['code_hashes'].items():assert digest(P/rel)==h
   model=M3Single();count=0
   for e in manifest['recordings']:
    assert digest(e['audio'])==e['audio_sha256'] and digest(e['reference_path'])==e['reference_sha256']
    dest=out/e['id']/'result.json'
    if dest.exists():
     assert digest(dest)==dest.with_suffix('.sha256').read_text();continue
    if a.limit is not None and count>=a.limit:break
    count+=1;text='';error='';rows=[]
    try:
     audio=load_audio(e['audio']);detected,meta=segment_morse(audio)
     for i,r in enumerate(detected):r.update(index=i,rule_prediction=REVERSE_TABLE.get(r['pattern'],'?'))
     body=select_body(detected,e['body']);_,rows,_=infer(body,audio,model.model,model.model_config,model.labels);text,rows,warnings=render_body(rows)
    except (ValueError,OSError,RuntimeError) as exc:error=str(exc)
    metric,alignment=edit_alignment(e['normalized_reference'],text)
    dest.parent.mkdir(exist_ok=True);save(dest,dict(id=e['id'],model='M3',frontend='baseline',policy=VERSION,reference=e['normalized_reference'],hypothesis=text,status='FAILED' if error else 'OK',error=error,metrics=metric,segments=rows,alignment=alignment));dest.with_suffix('.sha256').write_text(digest(dest),encoding='ascii');print(e['id'],metric['edit_distance'],'edits',flush=True)
   results=[read(out/e['id']/'result.json') for e in manifest['recordings'] if (out/e['id']/'result.json').exists()];units=sum(r['metrics']['reference_units'] for r in results);edits=sum(r['metrics']['edit_distance'] for r in results)
   save(out/'summary.json',dict(model='M3',policy=VERSION,completed=len(results)==len(manifest['recordings']),recordings=len(results),reference_units=units,edits=edits,cer=edits/units if units else None,failures=sum(r['status']=='FAILED' for r in results)))
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except (ValueError,OSError,RuntimeError,AssertionError) as e:print('評価を停止しました：'+str(e));raise SystemExit(2)
