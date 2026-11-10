"""Suggest a blinking ROI from temporal contrast, without consulting references."""
import cv2
import numpy as np
from splitter import info, identity, SplitError

def locate(samples, width, height):
 a=np.asarray(samples,dtype=np.float32)
 if a.ndim!=3 or len(a)<8:raise SplitError('光源探索用の画像が不足しています。')
 # Static lamps have little temporal contrast; isolated hot pixels are smoothed.
 spread=np.percentile(a,95,axis=0)-np.percentile(a,10,axis=0)
 score=cv2.GaussianBlur(spread,(5,5),0)
 iy,ix=np.unravel_index(np.argmax(score),score.shape)
 if score[iy,ix]<10:raise SplitError('点滅する光源候補が見つかりません。手動で範囲を指定してください。')
 sx=width/a.shape[2];sy=height/a.shape[1]
 rw=min(width,max(24,round(10*sx)));rh=min(height,max(24,round(10*sy)))
 x=max(0,min(width-rw,round((ix+.5)*sx-rw/2)))
 y=max(0,min(height-rh,round((iy+.5)*sy-rh/2)))
 patch=a[:,max(0,iy-2):iy+3,max(0,ix-2):ix+3].mean(axis=(1,2))
 return dict(roi=[x,y,rw,rh],sample_index=int(np.argmax(patch)),score=float(score[iy,ix]))

def suggest(path,progress=None,start_seconds=0.,end_seconds=None):
 before=identity(path);m=info(path)
 end_seconds=min(m['duration']-1/m['fps'],m['duration'] if end_seconds is None else float(end_seconds))
 if not 0<=start_seconds<end_seconds:raise SplitError('光源探索の時間範囲が不正です。')
 cap=cv2.VideoCapture(str(path));frames=[];seconds=[]
 try:
  # Sample the entire recording; never assume that transmission starts immediately.
  for i,sec in enumerate(np.linspace(start_seconds,end_seconds,64)):
   cap.set(cv2.CAP_PROP_POS_MSEC,float(sec*1000));ok,f=cap.read()
   if ok:
    gray=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY)
    frames.append(cv2.resize(gray,(480,max(2,round(m['height']*480/m['width']))),interpolation=cv2.INTER_AREA));seconds.append(float(sec))
   if progress:progress((i+1)/64)
 finally:cap.release()
 if identity(path)!=before:raise SplitError('光源探索中に動画が変更されました。')
 result=locate(frames,m['width'],m['height']);result['preview_seconds']=seconds.pop(result.pop('sample_index'));result['source']=before
 return result
