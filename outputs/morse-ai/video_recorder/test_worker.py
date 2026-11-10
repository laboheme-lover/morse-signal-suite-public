import json, subprocess, sys, tempfile, pathlib
import cv2
base=pathlib.Path(__file__).resolve().parent
worker=base/'capture_worker.py'
def check(args,stdin):
 p=subprocess.run([sys.executable,'-B','-X','utf8',str(worker),*args],input=stdin,text=True,encoding='utf-8',capture_output=True,timeout=10)
 return [json.loads(x) for x in p.stdout.splitlines()]
with tempfile.TemporaryDirectory(prefix='worker_test_',dir=base) as tmp:
 args=['--test-no','CHECK','--output',tmp,'--source',str(base.parent/'optical_video/samples/mixed_30fps.avi')]
 messages=check(args,'STOP\n')
 folders=list(pathlib.Path(tmp).glob('Test_*'))
 assert len(folders)==1
 assert json.loads((folders[0]/'recording.json').read_text(encoding='utf-8'))['status']=='CANCELLED'
 messages=check(['--test-no','../bad','--output',tmp],'')
 assert messages[-1]['event']=='error'
 messages=check(['--test-no','CHECK','--output',tmp,'--source',str(pathlib.Path(tmp)/'missing.avi')],'')
 assert messages[-1]['event']=='error'
 assert len(list(pathlib.Path(tmp).glob('Test_*')))==2
completed=[]
for meta_path in (base/'test_outputs').glob('*/recording.json'):
 meta=json.loads(meta_path.read_text(encoding='utf-8'))
 if meta['status']!='COMPLETE':continue
 times=[json.loads(x)['captured_seconds'] for x in (meta_path.parent/'frame_times.jsonl').read_text().splitlines()]
 assert len(times)==meta['frames'] and all(a<=b for a,b in zip(times,times[1:]))
 cap=cv2.VideoCapture(str(meta_path.parent/'video.avi'));count=0
 while cap.read()[0]:count+=1
 cap.release();assert count==meta['frames'];completed.append(count)
assert completed
print('PASS cancellation, invalid number, missing source, unique paths, saved video frames and timestamps:',completed)
