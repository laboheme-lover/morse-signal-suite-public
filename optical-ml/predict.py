"""Experimental optical inference: selected ROI -> character gaps -> classifier.

Classification confidence is NOT a calibrated correctness probability.
No language model, reference correction or international-mode switching.
"""
import argparse,json,sys
from pathlib import Path
import cv2,numpy as np,torch
from model import MODELS
from dataset import features,tensorize
from extract import ROOT,OUT
sys.path.insert(0,str(ROOT/'optical-batch-test/pc'))
import splitter

def extract_features(path,roi,progress=None):
 before=splitter.identity(path);meta=splitter.info(path);x,y,w,h=map(int,roi);cx=x+w//2;cy=y+h//2
 # Input convention: 128x128 neighborhood with a 40x40 central emitter ROI.
 if w!=40 or h!=40 or cx-64<0 or cy-64<0 or cx+64>meta['width'] or cy+64>meta['height']:
  raise ValueError('学習版v1は幅40・高さ40画素の光源範囲を使います。周囲128画素が画像内に収まる位置を指定してください。')
 cap=cv2.VideoCapture(str(path));values=[];times=[]
 try:
  while True:
   ok,f=cap.read()
   if not ok:break
   frame=cv2.resize(cv2.cvtColor(f[cy-64:cy+64,cx-64:cx+64],cv2.COLOR_BGR2GRAY),(64,64),interpolation=cv2.INTER_AREA)
   values.append(features(frame[None])[0]);times.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000)
   if progress and len(times)%300==0:progress(min(.99,len(times)/meta['frames']))
 finally:cap.release()
 if splitter.identity(path)!=before:raise ValueError('解析中に元動画が変更されました。')
 if len(times)!=meta['frames'] or len(times)<3:raise ValueError('動画の全フレームを読み取れませんでした。')
 if times[0]>=times[1]:times[0]=splitter.verify_initial_timestamp(path,times[:3],meta['fps'])[0][0]
 times,fixes=splitter.correct_initial_timestamp(times,meta['fps'])
 if not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('時刻が不正です。')
 if progress:progress(1.)
 return times,np.asarray(values),meta

def classify_features(times,f,checkpoint,unit=.3,isolated=False):
 if len(times)<3 or not np.isfinite(f).all() or not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('時刻または輝度が不正です。')
 if not .1<=unit<=1. or np.diff(times).max()>unit*.4:raise ValueError('短点時間に対してフレーム間隔が大きすぎます。')
 signal=f[:,0]-f[:,2];low,high=np.percentile(signal,[5,95])
 # Sparse continuous recordings can have less than 5% lit frames.
 if high-low<5:low,high=np.percentile(signal,[1,99])
 if high-low<5:raise ValueError('光の変化が小さく、認識を保留します。')
 for _ in range(15):
  a=signal[signal<=(low+high)/2];b=signal[signal>(low+high)/2]
  if min(len(a),len(b))<2:raise ValueError('点灯・消灯を分けられません。')
  low,high=np.median(a),np.median(b)
 rs=splitter.runs(signal>(low+high)/2,times,float(np.median(np.diff(times))))
 intervals=[];start=None;end=None
 for r in rs:
  if r['on']:
   if start is None:start=r['start']
   end=r['end']
  elif r['end']-r['start']>=2*unit and start is not None:
   intervals.append((start,end));start=end=None
 if start is not None:intervals.append((start,end))
 if isolated:intervals=[(times[0],times[-1]+1/30)]
 model=MODELS[checkpoint['model']]();model.load_state_dict(checkpoint['state_dict']);model.eval();torch.set_num_threads(4)
 results=[]
 for a,b in intervals:
  left=max(times[0],a-.5);right=min(times[-1],b+.5)
  if right<=left:continue
  grid=np.arange(left,right,1/30)
  arr=np.stack([np.interp(grid,times,f[:,i]) for i in range(4)],axis=1)
  inp=torch.from_numpy(tensorize(arr,len(arr)/30))[None]
  with torch.no_grad():prob=model(inp).softmax(1)[0];top=prob.topk(3)
  candidates=[dict(label=checkpoint['classes'][int(i)],score=float(p)) for p,i in zip(top.values,top.indices)]
  results.append(dict(start=float(a),end=float(b),text=candidates[0]['label'],candidates=candidates,review=True))
 return dict(text=''.join(r['text'] for r in results),characters=results,model=checkpoint['model'],contrast=float(high-low),status='EXPERIMENTAL_REVIEW',warning='同一65元動画の加工データで学習した開発版。新しい実録画・実天候での性能は未検証。候補スコアは正解率ではありません。')

def main():
 p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('--roi',type=int,nargs=4,required=True);p.add_argument('--model',default='cnn',choices=MODELS);p.add_argument('--unit',type=float,default=.3);p.add_argument('--isolated',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
 dest=Path(a.output)
 if dest.exists():raise FileExistsError('出力は新しいファイルを指定してください。')
 ckpt=torch.load(OUT/'models'/f'{a.model}.pt',weights_only=False,map_location='cpu')
 t,f,m=extract_features(a.video,a.roi);r=classify_features(t,f,ckpt,a.unit,a.isolated);r.update(source=str(Path(a.video).resolve()),roi=a.roi)
 dest.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(r['text'])

if __name__=='__main__':main()
