"""USB recording worker. Captures only when GUI launches it; no audio."""
import argparse,datetime,json,os,queue,re,sys,threading,time,uuid
from pathlib import Path
import cv2

def emit(event,**kw):print(json.dumps(dict(event=event,**kw),ensure_ascii=False),flush=True)
def reserve(root,test_no):
 if not re.fullmatch(r'[\w-]{1,40}',test_no):raise ValueError('テストNo.は40文字以内の文字・数字・ハイフン・下線にしてください。')
 root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
 dest=root/('Test_'+test_no+'_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]);dest.mkdir();return dest

def run(a):
 dest=reserve(a.output,a.test_no);meta=dict(test_no=a.test_no,camera_index=a.camera,requested_fps=a.fps,requested_size=[a.width,a.height],audio_recorded=False,status='PREPARING',test_source=bool(a.source));cap=None;writer=None;log=None;count=0;times=[];q=queue.Queue();start=None
 def commands():
  for line in sys.stdin:q.put(line.strip().upper())
  q.put('STOP')
 threading.Thread(target=commands,daemon=True).start()
 emit('preparing',directory=str(dest))
 (dest/'recording.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 try:
  cap=cv2.VideoCapture(a.source if a.source else a.camera,cv2.CAP_ANY if a.source else cv2.CAP_DSHOW)
  if not cap.isOpened():raise RuntimeError('カメラを開けません。カメラ番号、USB接続、他アプリの使用状況を確認してください。')
  if not a.source:
   cap.set(cv2.CAP_PROP_FRAME_WIDTH,a.width);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,a.height);cap.set(cv2.CAP_PROP_FPS,a.fps)
  ok,frame=cap.read()
  if not ok:raise RuntimeError('カメラから画像を取得できません。')
  height,width=frame.shape[:2];fps=cap.get(cv2.CAP_PROP_FPS);fps=fps if 1<=fps<=120 else a.fps
  meta.update(actual_size=[width,height],video_fps=fps,codec='MJPG',time_basis='perf_counter seconds since START; timestamp after each frame read')
  writer=cv2.VideoWriter(str(dest/'video.partial.avi'),cv2.VideoWriter_fourcc(*'MJPG'),fps,(width,height))
  if not writer.isOpened():raise RuntimeError('動画の保存先またはコーデックを利用できません。')
  emit('ready',directory=str(dest),width=width,height=height,fps=fps)
  if q.get()!='START':meta['status']='CANCELLED';return
  start=time.perf_counter();meta['started_at']=datetime.datetime.now().astimezone().isoformat();meta['status']='RECORDING';emit('recording')
  log=(dest/'frame_times.jsonl').open('w',encoding='utf-8')
  while True:
   try:
    if q.get_nowait()=='STOP':break
   except queue.Empty:pass
   ok,frame=cap.read();stamp=time.perf_counter()-start
   if not ok:raise RuntimeError('録画中に画像の取得が止まりました。USB接続を確認してください。')
   if frame.shape[:2]!=(height,width):raise RuntimeError('録画中に画像サイズが変化しました。')
   writer.write(frame);log.write(json.dumps(dict(frame=count,captured_seconds=stamp))+'\n');times.append(stamp);count+=1
   if count%30==0:log.flush()
   if a.source:time.sleep(1/fps)
  writer.release();writer=None;log.close();log=None
  if count==0:raise RuntimeError('録画フレームがありません。')
  check=cv2.VideoCapture(str(dest/'video.partial.avi'));ok,_=check.read();frames=int(check.get(cv2.CAP_PROP_FRAME_COUNT));check.release()
  if not ok or frames!=count:raise RuntimeError('保存動画の読み直し確認に失敗しました。部分ファイルを保持します。')
  (dest/'video.partial.avi').rename(dest/'video.avi');elapsed=time.perf_counter()-start;actual=(count-1)/(times[-1]-times[0]) if count>1 and times[-1]>times[0] else None
  meta.update(status='COMPLETE',frames=count,elapsed_seconds=elapsed,video_seconds=count/fps,measured_capture_fps=actual,ended_at=datetime.datetime.now().astimezone().isoformat())
  meta['timing_warning']=actual is None or abs(actual/fps-1)>.1
  if meta['timing_warning']:meta['warning']='取得速度と動画の固定FPSに差があります。モールスの時間評価にはframe_times.jsonlも確認してください。'
  emit('done',directory=str(dest),frames=count,timing_warning=meta['timing_warning'])
 except Exception as exc:
  meta.update(status='FAILED',frames=count,error=str(exc));emit('error',message=str(exc),directory=str(dest))
 finally:
  if writer is not None:writer.release()
  if cap is not None:cap.release()
  if log is not None:log.close()
  (dest/'recording.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
def preview(a):
 q=queue.Queue()
 def commands():
  for line in sys.stdin:q.put(line.strip().upper())
  q.put('STOP')
 threading.Thread(target=commands,daemon=True).start()
 target=Path(a.preview_path);target.parent.mkdir(parents=True,exist_ok=True)
 cap=cv2.VideoCapture(a.source if a.source else a.camera,cv2.CAP_ANY if a.source else cv2.CAP_DSHOW)
 try:
  if not cap.isOpened():raise RuntimeError('カメラを開けません。番号とUSB接続を確認してください。')
  cap.set(cv2.CAP_PROP_FRAME_WIDTH,a.width);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,a.height)
  while True:
   try:
    if q.get_nowait()=='STOP':break
   except queue.Empty:pass
   ok,frame=cap.read()
   if not ok:raise RuntimeError('プレビュー画像を取得できません。')
   ok,data=cv2.imencode('.jpg',frame)
   if not ok:raise RuntimeError('プレビュー画像を作成できません。')
   tmp=target.with_suffix('.tmp');tmp.write_bytes(data.tobytes());os.replace(tmp,target)
   emit('preview_frame');time.sleep(.1)
 finally:
  cap.release()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--test-no');p.add_argument('--output');p.add_argument('--preview-path');p.add_argument('--camera',type=int,default=0);p.add_argument('--width',type=int,default=640);p.add_argument('--height',type=int,default=480);p.add_argument('--fps',type=float,default=30);p.add_argument('--source');a=p.parse_args()
 try:
  if a.preview_path:preview(a)
  elif a.test_no and a.output:run(a)
  else:raise ValueError('test-no and output are required')
 except Exception as e:emit('error',message=str(e));raise SystemExit(2)
