import json,sys,time,subprocess
from pathlib import Path
import cv2,numpy as np
import tempfile
root=Path(__file__).resolve().parents[1];out=Path(tempfile.mkdtemp(prefix='morse_20min_check_'))
p=out/'synthetic_20min.mp4'
w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'mp4v'),10,(160,160))
assert w.isOpened()
# Four-second cycles: .- (300ms / 900ms) and character silence.
for i in range(12000):
 phase=i%40
 frame=np.zeros((160,160,3),np.uint8)
 if 3<=phase<6 or 9<=phase<18:frame[60:100,60:100]=240
 w.write(frame)
w.release()
request=dict(path=str(p),roi=[60,60,40,40],unit=None,isolated=False,mode='採用版：連続電文')
(out/'request.json').write_text(json.dumps(request),encoding='utf-8')
t=time.perf_counter()
r=subprocess.run([sys.executable,str(root/'optical-ml/recognition_job.py'),str(out)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=900)
(out/'worker.log').write_text(r.stdout+r.stderr,encoding='utf-8')
assert r.returncode==0,(r.stdout+r.stderr)
result=json.loads((out/'result.json').read_text(encoding='utf-8'))
assert len(result['text'])==300
sys.path.insert(0,str(root/'optical-ml'))
from predict import extract_features
from production import recognize,CHECKPOINT
import torch
a,b,_=extract_features(p,[60,60,40,40])
legacy=recognize(a,b,torch.load(CHECKPOINT,map_location='cpu',weights_only=False))
assert legacy['text']==result['text']
assert legacy['characters']==result['characters']
report=dict(duration_seconds=1200,frames=12000,fps=10,width=160,height=160,file_bytes=p.stat().st_size,expected_characters=300,recognized_characters=len(result['text']),exact_match=result['text']=='イ'*300,correct_characters=sum(c=='イ' for c in result['text']),legacy_results_identical=True,elapsed_seconds=round(time.perf_counter()-t,2),feature_array_bytes=12000*(4*4+8),notes='Synthetic 20-minute completion test; not a real 5 GB or high-resolution performance benchmark.')
(out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
