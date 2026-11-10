"""Experimental variable-size optical ROI adapter; frozen inference unchanged."""
import cv2,numpy as np
from predict import extract_features,splitter
from dataset import features

def crop_for_model(frame,roi):
 x,y,w,h=map(int,roi);height,width=frame.shape[:2]
 if min(x,y)<0 or min(w,h)<2 or x+w>width or y+h>height:raise ValueError('光源範囲が動画の外です。')
 cw,ch=int(round(w*3.2)),int(round(h*3.2));left=int(round(x+w/2-cw/2));top=int(round(y+h/2-ch/2))
 if left>=0 and top>=0 and left+cw<=width and top+ch<=height:
  gray=cv2.cvtColor(frame[top:top+ch,left:left+cw],cv2.COLOR_BGR2GRAY)
  return cv2.resize(gray,(64,64),interpolation=cv2.INTER_AREA),False
 gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
 transform=np.array([[cw/64,0,left+(cw/64-1)/2],[0,ch/64,top+(ch/64-1)/2]],dtype=np.float32)
 return cv2.warpAffine(gray,transform,(64,64),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_REPLICATE),True

def extract_flexible(path,roi,progress=None):
 meta=splitter.info(path);x,y,w,h=map(int,roi)
 if w==40 and h==40 and x+20>=64 and y+20>=64 and x+84<=meta['width'] and y+84<=meta['height']:
  t,f,m=extract_features(path,roi,progress);m.update(roi=roi,roi_adapter='legacy_40px',edge_padding=False);return t,f,m
 before=splitter.identity(path);cap=cv2.VideoCapture(str(path));values=[];times=[];padded=False
 try:
  while True:
   ok,frame=cap.read()
   if not ok:break
   crop,edge=crop_for_model(frame,roi);padded|=edge
   values.append(features(crop[None])[0]);times.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000)
   if progress and len(times)%300==0:progress(min(.99,len(times)/meta['frames']))
 finally:cap.release()
 if before!=splitter.identity(path) or len(times)!=meta['frames'] or len(times)<3:raise ValueError('動画全体を安定して読み取れませんでした。')
 if times[0]>=times[1]:times[0]=splitter.verify_initial_timestamp(path,times[:3],meta['fps'])[0][0]
 times,_=splitter.correct_initial_timestamp(times,meta['fps'])
 if not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('時刻が不正です。')
 meta.update(roi=list(roi),roi_adapter='scaled_neighborhood_experimental',edge_padding=padded)
 if progress:progress(1.)
 return times,np.asarray(values),meta
