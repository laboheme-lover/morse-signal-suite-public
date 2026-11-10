"""Seeded image-space augmentation, persisted features and reproducible recipes.

All splits share 65 source clips: these are augmentation-development splits,
NOT an independent recording test. Weather is an artificial image effect.
"""
from pathlib import Path
import json,sys,hashlib,subprocess
import cv2,numpy as np
from extract import ROOT,OUT,FFMPEG

CONDITIONS=['clean','fast','slow','dim','bright','rain','fog','static_light','sensor_noise','timing_jitter','mixed']

def augment(frames,times,condition,seed,stress=False):
 rng=np.random.default_rng(seed);p={'condition':condition,'seed':seed,'stress':stress}
 speed=float(rng.uniform(1.25,1.65) if condition=='fast' else rng.uniform(.60,.85) if condition=='slow' else rng.uniform(.90,1.10))
 if stress and condition=='fast':speed=2.2
 if stress and condition=='slow':speed=.45
 mapped=times/speed
 if condition in ('timing_jitter','mixed'):
  intervals=np.diff(mapped)*rng.uniform(.65 if stress else .8,1.35 if stress else 1.2,len(times)-1)
  mapped=np.r_[0,np.cumsum(intervals)]
 target=np.arange(0,mapped[-1],1/30)
 idx=np.searchsorted(mapped,target);idx=np.clip(idx,1,len(mapped)-1)
 idx-=abs(target-mapped[idx-1])<abs(target-mapped[idx])
 a=frames[idx].astype(np.float32)
 gain=float(rng.uniform(.25,.55) if condition=='dim' else rng.uniform(1.4,2.1) if condition=='bright' else rng.uniform(.8,1.2))
 if stress and condition=='dim':gain=.1
 a*=gain;p.update(speed=speed,gain=gain,output_fps=30)
 if condition in ('fog','mixed'):
  transmission=float(rng.uniform(.35,.65) if not stress else .15)
  sigma=float(rng.uniform(.6,1.5) if not stress else 2.5)
  a=np.array([cv2.GaussianBlur(f,(0,0),sigma) for f in a])*transmission+145*(1-transmission)
  p.update(fog_transmission=transmission,fog_blur_sigma=sigma)
 if condition in ('static_light','mixed'):
  yy,xx=np.mgrid[:64,:64];lx=float(rng.uniform(5,59));ly=float(rng.uniform(5,59));sigma=float(rng.uniform(2,7));strength=float(rng.uniform(65,160))
  if stress:lx=ly=32.;strength=220.;sigma=10.
  lamp=strength*np.exp(-((xx-lx)**2+(yy-ly)**2)/(2*sigma*sigma))
  a+=lamp[None];p.update(lamp_xy=[lx,ly],lamp_sigma=sigma,lamp_strength=strength)
 if condition in ('rain','mixed'):
  density=9 if stress else int(rng.integers(2,6));p['rain_streaks_per_frame']=density
  for f in a:
   rain=np.zeros((64,64),np.float32)
   for _ in range(density):
    x,y=rng.integers(0,64,2);cv2.line(rain,(int(x),int(y)),(int(x+3),int(y+rng.integers(5,18))),float(rng.uniform(40,130)),1)
   # Synthetic scattering streaks and occasional partial attenuation, not real rainfall.
   f+=cv2.GaussianBlur(rain,(3,3),.5)
   if rng.random()<(.2 if stress else .06):f[22:42,22:42]*=rng.uniform(.2,.7)
 if condition in ('sensor_noise','mixed'):
  sigma=float(rng.uniform(4,12) if not stress else 25);a+=rng.normal(0,sigma,a.shape);p['noise_sigma']=sigma
 a=np.clip(a,0,255).astype(np.uint8)
 # Variable dark margins prevent fixed crop boundaries becoming class identifiers.
 before=int(rng.integers(0,10));after=int(rng.integers(0,10))
 a=np.concatenate([np.repeat(a[:1],before,axis=0),a,np.repeat(a[-1:],after,axis=0)])
 p.update(extra_margin_frames=[before,after]);return a,p

def features(a):
 center=a[:,22:42,22:42].astype(np.float32)
 background=np.concatenate([a[:,:12].reshape(len(a),-1),a[:,-12:].reshape(len(a),-1)],axis=1)
 return np.stack([center.mean((1,2)),np.percentile(center,90,axis=(1,2)),np.median(background,axis=1),a.mean((1,2))],axis=1).astype(np.float32)

def tensorize(f,duration,steps=256):
 signal=f[:,:2]-f[:,2,None]
 low=np.percentile(signal,5,axis=0);span=np.maximum(np.percentile(signal,95,axis=0)-low,5.)
 normalized=np.clip((signal-low)/span,-1,2)
 channels=np.column_stack([normalized,f[:,2]/255,f[:,0]/255,np.full(len(f),duration/12)])
 grid=np.linspace(0,len(f)-1,steps)
 return np.stack([np.interp(grid,np.arange(len(f)),channels[:,i]) for i in range(5)]).astype(np.float32)

def preview_video(a,path):
 run=subprocess.run([str(FFMPEG),'-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','gray','-s','64x64','-r','30','-i','pipe:0','-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],input=a.tobytes(),capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if run.returncode:raise RuntimeError(run.stderr.decode(errors='replace'))

def main():
 sources=json.loads((OUT/'sources.json').read_text(encoding='utf-8'))['records']
 (OUT/'dataset').mkdir(exist_ok=True);(OUT/'preview').mkdir(exist_ok=True)
 records=[];raw=[];offsets=[0];X=[];Y=[];splits=[];conditions=[]
 counts={'train':8,'validation':2,'test_augmented':2,'stress':1}
 for c in sources:
  z=np.load(c['crop_file']);frames,times=z['frames'],z['times']
  for split_i,(split,n) in enumerate(counts.items()):
   for ci,condition in enumerate(CONDITIONS):
    for rep in range(n):
     seed=202610130+split_i*1000000+c['class_index']*1000+ci*20+rep
     a,p=augment(frames,times,condition,seed,stress=split=='stress')
     f=features(a);X.append(tensorize(f,len(a)/30));Y.append(c['class_index']);splits.append(split_i);conditions.append(ci)
     raw.append(f);offsets.append(offsets[-1]+len(f))
     records.append(dict(index=len(X)-1,split=split,source_id=c['id'],source_sha256=c['sha256'],class_index=c['class_index'],label=c['label'],frames=len(a),duration=len(a)/30,parameters=p))
     if c['class_index']==1 and split=='test_augmented' and rep==0:preview_video(a,OUT/'preview'/f'{condition}.mp4')
  print(f'augment {c["class_index"]+1}/65',flush=True)
 np.savez_compressed(OUT/'dataset/features.npz',x=np.stack(X),y=np.array(Y),split=np.array(splits),condition=np.array(conditions),raw=np.concatenate(raw),offsets=np.array(offsets))
 with (OUT/'dataset/manifest.jsonl').open('w',encoding='utf-8') as f:
  for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 config=dict(conditions=CONDITIONS,split_names=list(counts),variants_per_class_condition=counts,total=len(X),classes=[c['label'] for c in sources],input_shape=[5,256],source_recordings=1,independent_test=False,warning='All splits derive from the same 65 source clips. Weather effects are artificial. No claim of real-weather or new-recording generalization.')
 (OUT/'dataset/config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
 print(config['total'],flush=True)

if __name__=='__main__':main()
