"""Extract source-identifiable optical crops; originals are never modified."""
from pathlib import Path
import hashlib,json,subprocess,sys
import cv2,numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/optical_ml_20261013'
SOURCE=ROOT/'optical-batch-test/splits/20261012_173941'
FFMPEG=ROOT/'work/video_test_tools/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()

def main():
 manifest=json.loads((SOURCE/'split_manifest.json').read_text(encoding='utf-8'))
 assert manifest['status']=='complete' and len(manifest['outputs'])==65
 (OUT/'original_crops').mkdir(parents=True,exist_ok=True)
 records=[]
 x,y,w,h=manifest['roi'];cx=x+w//2;cy=y+h//2
 for i,c in enumerate(manifest['outputs']):
  p=SOURCE/c['file'];dest=OUT/'original_crops'/f'{c["id"]}.npz'
  # Preserve timestamps while decoding. No global frame-index / nominal-fps repair.
  cap=cv2.VideoCapture(str(p));frames=[];times=[]
  while True:
   ok,f=cap.read()
   if not ok:break
   times.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000)
   crop=f[cy-64:cy+64,cx-64:cx+64]
   frames.append(cv2.resize(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),(64,64),interpolation=cv2.INTER_AREA))
  expected=round(cap.get(cv2.CAP_PROP_FRAME_COUNT));cap.release()
  if len(frames)!=expected or len(frames)<3 or np.any(np.diff(times)<=0):raise ValueError(f'Invalid decode: {p}')
  times=np.asarray(times)-times[0]
  np.savez_compressed(dest,frames=np.array(frames),times=times)
  records.append(dict(id=c['id'],label=c['labels'],class_index=i,file=str(p),sha256=sha(p),crop_file=str(dest),frames=len(frames),duration=float(times[-1]),source_recording=manifest['source']['path'],source_interval=[c['start'],c['end']]))
  print(f'extract {i+1}/65',flush=True)
 (OUT/'sources.json').write_text(json.dumps(dict(manifest_sha256=sha(SOURCE/'split_manifest.json'),source_manifest=str(SOURCE/'split_manifest.json'),crop_xywh=[cx-64,cy-64,128,128],records=records),ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
