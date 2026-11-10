from pathlib import Path
import json,struct,hashlib
import torch
from scipy.signal import butter
R=Path(__file__).resolve().parents[1];src=R.parent/'outputs/morse-ai/models/releases/wabun_parentheses_v1_20260923'
p=src/'phase6_wabun65/runs/m3_wabun65_20260922/best.pt';sha=hashlib.sha256(p.read_bytes()).hexdigest()
assert sha==json.loads((src/'release_manifest.json').read_text(encoding='utf-8'))['files'][p.relative_to(src).as_posix()]
c=torch.load(p,map_location='cpu',weights_only=True);d=R/'app/src/main/assets'
with (d/'audio_m3.bin').open('wb') as f:
 f.write(struct.pack('>i',0x4d330001))
 for label in sorted(c['labels'],key=c['labels'].get):
  b=label.encode('utf-8');f.write(struct.pack('>H',len(b))+b)
 for a in c['state_dict'].values():
  a=a.numpy().astype('>f4');f.write(struct.pack('>i',a.size)+a.tobytes())
 f.write(butter(4,[300,1400],btype='bandpass',fs=16000,output='sos').astype('>f8').tobytes())
with (d/'audio_filters.bin').open('wb') as f:
 ns=[512,1024,2048,4096,8192,16384];f.write(struct.pack('>i',len(ns)))
 for n in ns:
  bins=[i for i in range(n//2+1) if 300<=i*16000/n<=1500];f.write(struct.pack('>iii',n,min(bins),len(bins)))
  for i in bins:f.write(butter(4,[i*16000/n-100,i*16000/n+100],btype='bandpass',fs=16000,output='sos').astype('>f8').tobytes())
(d/'audio_model.json').write_text(json.dumps({'version':'M3-wabun-parentheses-v1','source_sha256':sha,'config':c['config'],'runtime':'Java CPU float32 CNN+BiGRU; float64 DSP','model_sha256':hashlib.sha256((d/'audio_m3.bin').read_bytes()).hexdigest(),'filters_sha256':hashlib.sha256((d/'audio_filters.bin').read_bytes()).hexdigest()},ensure_ascii=False,indent=2),encoding='utf-8')
print('Exported adopted M3 and deterministic segmentation filters')
