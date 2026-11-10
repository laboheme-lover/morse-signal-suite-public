from pathlib import Path
import sys,struct,json,subprocess
import numpy as np
import torch
import cv2
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R.parent/'optical-ml'))
from model import OpticalCNN
from dataset import tensorize,features
from adaptive_timing_v2 import estimate_unit
from adaptive_timing_v2 import classify_adaptive
release=R.parent/'optical-ml/releases/optical-cnn-adaptive-v2-20261013'
ck=torch.load(release/'cnn.pt',map_location='cpu',weights_only=False)
m=OpticalCNN();m.load_state_dict(ck['state_dict']);m.eval();torch.set_num_threads(4)
z=np.load(R.parent/'outputs/optical_ml_20261013/dataset/features.npz')
ids=np.linspace(0,len(z['x'])-1,130,dtype=int);x=z['x'][ids]
with torch.no_grad():logits=m(torch.from_numpy(x)).numpy()
raw=z['raw'][:127];duration=len(raw)/30
t=np.arange(0,30,1/30);on=np.zeros(len(t))
for a,b in [(1,1.3),(1.6,2.5),(3.4,3.7),(4,4.3),(4.6,5.5),(6.4,7.3),(7.6,7.9),(8.2,9.1),(10,10.3),(10.6,11.5)]:on[(t>=a)&(t<b)]=1
f=np.column_stack([20+200*on,25+210*on,np.full(len(t),10),15+30*on]);unit=estimate_unit(t,f)['unit_seconds']
start,end=1.,2.5;scale=.3/unit;left=max(t[0],start-.5/scale);right=min(t[-1],end+.5/scale)
grid=np.arange(left*scale,right*scale,1/30);arr=np.stack([np.interp(grid,t*scale,f[:,i]) for i in range(4)],axis=1)
expected=tensorize(arr,len(arr)/30)
stream_expected=classify_adaptive(t,f,ck)['text']
folder=R/'core-tests/optical-build';folder.mkdir(exist_ok=True)
with (folder/'fixture.bin').open('wb') as out:
 out.write(struct.pack('>i',len(x)))
 for a,b in zip(x,logits):out.write(a.astype('>f4').tobytes());out.write(b.astype('>f4').tobytes())
 out.write(struct.pack('>i',len(raw)));out.write(raw.astype('>f8').tobytes());out.write(struct.pack('>d',duration));out.write(tensorize(raw,duration).astype('>f4').tobytes())
 out.write(struct.pack('>i',len(t)))
 for a,b in zip(t,f):out.write(struct.pack('>d',a));out.write(b.astype('>f8').tobytes())
 out.write(struct.pack('>ddd',unit,start,end));out.write(expected.astype('>f4').tobytes())
 b=stream_expected.encode('utf-8');out.write(struct.pack('>H',len(b))+b)
 cap=cv2.VideoCapture(str(R/'test-data/cnn_offcenter.mp4'));vf=[]
 while True:
  ok,frame=cap.read()
  if not ok:break
  patch=cv2.resize(cv2.cvtColor(frame[176:304,384:512],cv2.COLOR_BGR2GRAY),(64,64),interpolation=cv2.INTER_AREA);vf.append(features(patch[None])[0])
 cap.release();vf=np.asarray(vf);vt=np.arange(len(vf))/30
 expected_video=classify_adaptive(vt,vf,ck)['text']
 out.write(struct.pack('>i',len(vf)))
 for a,b in zip(vt,vf):out.write(struct.pack('>d',a));out.write(b.astype('>f8').tobytes())
 b=expected_video.encode('utf-8');out.write(struct.pack('>H',len(b))+b)
cfg=json.loads((R/'.toolchain/environment.json').read_text(encoding='utf-8'));java=Path(cfg['java'])/'bin'
names=['OpticalCnn','OpticalMath','OpticalReceiver','MorseCodec','JapaneseNumbers','SendProgress','LightRegion','LightTracker']
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(folder),*[str(R/'app/src/main/java/jp/local/wabun'/f'{n}.java') for n in names],str(R/'core-tests/OpticalCnnTest.java')],check=True)
p=subprocess.run([str(java/'java.exe'),'-Dfile.encoding=UTF-8','-cp',str(folder),'OpticalCnnTest',str(R/'app/src/main/assets/optical_cnn.bin'),str(folder/'fixture.bin')],capture_output=True,text=True,encoding='utf-8')
(folder/'result.txt').write_text(p.stdout+p.stderr,encoding='utf-8');print(p.stdout+p.stderr);sys.exit(p.returncode)

