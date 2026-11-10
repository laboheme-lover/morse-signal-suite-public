"""Offline optical batch splitter. Quality gates reject uncertain boundaries."""
from pathlib import Path
import json,hashlib,math,subprocess,time,re
from array import array
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'corpus/batches.json'
FFMPEG=ROOT.parent/'work/video_test_tools/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'

class SplitError(ValueError):pass
def corpus_path(profile='full'):
 if profile not in ('full','sentence'):raise SplitError('原稿版が不正です。')
 return CORPUS if profile=='full' else ROOT/'corpus/sentence_batches.json'
def corpus(profile='full'):return json.loads(corpus_path(profile).read_text(encoding='utf-8'))
def identity(path):
 p=Path(path).resolve();s=p.stat();return dict(path=str(p),size=s.st_size,mtime_ns=s.st_mtime_ns)
def info(path):
 cap=cv2.VideoCapture(str(path))
 try:
  if not cap.isOpened():raise SplitError('動画を開けません。端末からコピーしたMP4などを指定してください。')
  fps=float(cap.get(cv2.CAP_PROP_FPS));w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
  if not 1<=fps<=240 or not 0<w<=4096 or not 0<h<=4096 or n<=0 or n/fps>36*3600:raise SplitError('対応範囲外です（4K相当・240fps・36時間以内）。')
  return dict(fps=fps,width=w,height=h,frames=n,duration=n/fps)
 finally:cap.release()
def preview(path,seconds,roi=None):
 meta=info(path);cap=cv2.VideoCapture(str(path))
 try:
  cap.set(cv2.CAP_PROP_POS_MSEC,seconds*1000);ok,frame=cap.read()
  if not ok:raise SplitError('指定した位置のプレビューを読み込めません。')
  if roi:
   x,y,w,h=roi;cv2.rectangle(frame,(x,y),(x+w,y+h),(0,255,0),max(1,meta['width']//500))
  return cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
 finally:cap.release()
def read_trace(path,roi,progress=None):
 meta=info(path);x,y,w,h=map(int,roi)
 if min(x,y)<0 or min(w,h)<2 or x+w>meta['width'] or y+h>meta['height']:raise SplitError('光源の選択範囲が画像の外にあります。')
 cap=cv2.VideoCapture(str(path));times=array('d');values=array('d');n=0;corrections=[]
 try:
  while True:
   ok,frame=cap.read()
   if not ok:break
   if frame.shape[:2]!=(meta['height'],meta['width']):raise SplitError('動画の途中で解像度が変わっています。')
   t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
   if not math.isfinite(t) or (n>=2 and t<=times[-1]):raise SplitError('フレーム時刻が不正です。固定fpsの動画へ書き出して再試行してください。')
   times.append(t);values.append(float(cv2.cvtColor(frame[y:y+h,x:x+w],cv2.COLOR_BGR2GRAY).mean()));n+=1
   if n==3 and times[0]>=times[1]:
    fixed,corrections=verify_initial_timestamp(path,times,meta['fps'])
    times[0]=fixed[0]
   if progress and n%150==0:progress(min(n/meta['frames'],.99))
   if n>240*36*3600:raise SplitError('フレーム数が対応範囲を超えました。')
  if n<3 or abs(n-meta['frames'])>1:raise SplitError('動画を最後まで読み込めませんでした。')
 finally:cap.release()
 if progress:progress(1.)
 times,negative_corrections=correct_initial_timestamp(np.array(times),meta['fps'])
 corrections.extend(negative_corrections)
 meta['timestamp_corrections']=corrections
 return meta,times,np.array(values)

def verify_initial_timestamp(path,times,fps):
 """Verify a suspect first OpenCV timestamp against independently decoded PTS.
 Never synthesize a constant-fps timeline or conceal later missing frames.
 """
 error='先頭フレームの時刻を検証できません。動画の時刻情報を確認してください。'
 command=[str(FFMPEG),'-nostdin','-hide_banner','-i',str(path),'-map','0:v:0','-vf','showinfo','-frames:v','3','-an','-fps_mode','passthrough','-f','null','-']
 try:
  run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 except (OSError,subprocess.TimeoutExpired) as exc:raise SplitError(error) from exc
 pts=[float(v) for v in re.findall(r'\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([\d.eE+-]+)',run.stderr)]
 if run.returncode or len(pts)<3 or abs(pts[0])>1e-6 or not 0<=times[0]<=4/fps or any(abs(pts[i]-times[i])>1e-5 for i in (1,2)) or not pts[0]<pts[1]<pts[2]:
  raise SplitError(error)
 fixed=np.asarray(times,dtype=float).copy();fixed[0]=pts[0]
 return fixed,[dict(frame=0,raw_seconds=float(times[0]),corrected_seconds=pts[0],reason='First OpenCV timestamp verified against FFmpeg decoded presentation timestamps')]

def correct_initial_timestamp(times,fps):
 """Repair only OpenCV's negative first HEVC timestamp; preserve other gaps."""
 times=np.asarray(times,dtype=float).copy();corrections=[]
 if len(times)>=3 and times[0]<0:
  step=times[2]-times[1];estimated=times[1]-step
  # Require the next two frames to agree with nominal frame spacing and zero
  # origin. This is not interpolation of missing image content.
  if -4/fps<=times[0]<0 and times[1]>=0 and abs(step-1/fps)<=.1/fps and abs(estimated)<=.1/fps:
   corrections.append(dict(frame=0,raw_seconds=float(times[0]),corrected_seconds=0.,reason='OpenCV negative initial timestamp; next two frames agree with zero origin'))
   times[0]=0.
  else:raise SplitError('先頭時刻が負で、自動補正条件を満たしません。時刻情報を確認してください。')
 return times,corrections
def runs(states,times,dt):
 edges=np.r_[0,np.flatnonzero(np.diff(states.astype(np.int8)))+1,len(states)]
 return [dict(on=bool(states[a]),start=float(times[a]),end=float(times[b]) if b<len(times) else float(times[-1]+dt),frames=int(b-a)) for a,b in zip(edges[:-1],edges[1:])]
def detect(times,values,cases,unit,minimum_contrast=20):
 if len(times)<3 or len(values)!=len(times) or not np.isfinite(values).all():raise SplitError('輝度データが不足しています。')
 delta=np.diff(times);dt=float(np.median(delta))
 if np.any(delta<=0) or np.max(delta)>unit*.4:raise SplitError('フレーム間隔が長すぎるか欠落があります。点滅を分割できません。')
 # Two brightness clusters; percentile initialization is robust to a few hot pixels.
 low,high=np.percentile(values,[1,99])
 for _ in range(20):
  threshold=(low+high)/2;off=values[values<=threshold];on=values[values>threshold]
  if len(on)<2 or len(off)<2:raise SplitError('分割作業は実施不可能：点灯と消灯を区別できません。光源の範囲・露出・距離を確認してください。')
  newlow=float(np.median(off));newhigh=float(np.median(on))
  if abs(newlow-low)+abs(newhigh-high)<.001:break
  low,high=newlow,newhigh
 contrast=high-low;noise=max(1,float(np.median(np.abs(off-low))*1.4826),float(np.median(np.abs(on-high))*1.4826))
 if contrast<minimum_contrast or contrast/noise<4:raise SplitError(f'分割作業は実施不可能：点灯・消灯の明るさの差が不足しています（差 {contrast:.1f}、ばらつき比 {contrast/noise:.1f}）。光源を拡大して範囲選択し、露出や撮影位置を見直してください。')
 threshold=(low+high)/2;rs=runs(values>threshold,times,dt)
 # Never fill long blackouts or invent missing pulses. Require complete recording edges.
 if rs[0]['on'] or rs[-1]['on'] or rs[0]['end']-rs[0]['start']<1 or rs[-1]['end']-rs[-1]['start']<1:
  raise SplitError('先頭または末尾の消灯を確認できません。途中で切れた録画は分割しません。')
 groups=[];current=[];gaps=[]
 for r in rs:
  if not r['on'] and r['end']-r['start']>=8:
   if current:groups.append(current);current=[];gaps.append(r['end']-r['start'])
  else:
   if r['on'] or current:current.append(r)
 if current:groups.append(current)
 # Terminal darkness is not an inter-case pause.
 for group in groups:
  while group and not group[-1]['on']:group.pop()
 if len(groups)!=len(cases):raise SplitError(f'分割作業は実施不可能：検出{len(groups)}件／指定原稿{len(cases)}件。感度不足・余分な点滅・途中停止・バッチや範囲の選択違いを確認してください。')
 clips=[]
 for i,(group,case) in enumerate(zip(groups,cases)):
  if not group:raise SplitError('信号のない区間があります。')
  if i:
   gap=group[0]['start']-groups[i-1][-1]['end']
   if not 8<=gap<=12:raise SplitError(f'{i}件目の後の休止が10秒と整合しません（{gap:.2f}秒）。')
  expected=case['pulses']
  if len(group)!=len(expected):raise SplitError(f"{case['id']}：点滅数が原稿と一致しません。分割作業は実施不可能です（検出{len(group)}区間／予定{len(expected)}区間）。")
  for r,(state,units) in zip(group,expected):
   observed=r['end']-r['start'];wanted=units*unit
   if r['on']!=state or abs(observed-wanted)>max(dt*2.5,unit*.35):raise SplitError(f"{case['id']}：点滅時間が原稿・短点時間と一致しません。感度または送信条件を確認してください。")
  clips.append(dict(id=case['id'],signal_start=group[0]['start'],signal_end=group[-1]['end'],start=max(float(times[0]),group[0]['start']-.5),end=min(float(times[-1]+dt),group[-1]['end']+.5),labels=case['labels']))
 return dict(clips=clips,contrast=contrast,noise_ratio=contrast/noise,threshold=threshold,frame_interval_max=float(np.max(delta)),quality='PASS',note='Segmentation suitability only; not a model recognition accuracy result')
def selected_batch(batch_id,profile='full',batch_ids=None):
 ids=list(batch_ids) if batch_ids is not None else [batch_id]
 catalog={b['id']:b for b in corpus(profile)['batches']}
 if not ids or len(ids)!=len(set(ids)) or any(i not in catalog for i in ids):
  raise SplitError('送信単位を重複なく選択してください。')
 return dict(id=batch_id,cases=[c for i in ids for c in catalog[i]['cases']])

def analyze(path,roi,batch_id,first,last,unit_ms,minimum_contrast=20,progress=None,mode='strict',profile='full',batch_ids=None,auto_header=False,video_start=0.,video_end=None,trace_reader=None):
 if unit_ms not in (300,450,600):raise SplitError('短点時間を300・450・600 msから選んでください。')
 before=identity(path);meta,t,v=(trace_reader or read_trace)(path,roi,progress)
 header=None
 if auto_header:
  from optical_header import decode
  header=decode(t,v,minimum_contrast);profile='sentence';batch_ids=header['batch_ids'];batch_id='selection_queue';unit_ms=header['unit_ms']
  video_start=header['body_from']
 selected=selected_batch(batch_id,profile,batch_ids)
 if auto_header:first,last=1,len(selected['cases'])
 if not 1<=first<=last<=len(selected['cases']):raise SplitError('送信範囲が不正です。')
 if video_end is None:video_end=float(t[-1])+1.
 if not 0<=video_start<video_end:raise SplitError('動画の解析範囲が不正です。')
 mask=(t>=video_start)&(t<video_end);t,v=t[mask],v[mask]
 if len(t)<3:raise SplitError('選択した動画範囲にフレームが不足しています。')
 if mode=='strict':result=detect(t,v,selected['cases'][first-1:last],unit_ms/1000,minimum_contrast)
 elif mode=='pause_candidates':
  from recovery import detect_candidates
  result=detect_candidates(t,v,selected['cases'][first-1:last],unit_ms/1000,minimum_contrast)
 else:raise SplitError('分割方式が不正です。')
 if before!=identity(path):raise SplitError('解析中に元動画が変更されました。')
 result.update(optical_header=header,video_start=video_start,video_end=video_end,source=before,metadata=meta,roi=list(roi),batch=batch_id,batch_ids=list(batch_ids) if batch_ids is not None else [batch_id],first=first,last=last,unit_ms=unit_ms,corpus_profile=profile,corpus_sha256=hashlib.sha256(corpus_path(profile).read_bytes()).hexdigest())
 return result,t,v
def export(result,output,progress=None,*,allow_review=False,skip_ids=()):
 if result['quality']!='PASS' and not (allow_review and result['quality']=='REVIEW'):raise SplitError('未確認候補の保存には明示的な確認が必要です。')
 if identity(result['source']['path'])!=result['source']:raise SplitError('検査結果が無効です。再解析してください。')
 if hashlib.sha256(corpus_path(result.get('corpus_profile','full')).read_bytes()).hexdigest()!=result['corpus_sha256']:raise SplitError('原稿が変更されました。再解析してください。')
 if not FFMPEG.is_file():raise SplitError('動画書き出し用ffmpegがありません。')
 selected=[c for c in result['clips'] if c['id'] not in skip_ids]
 if not selected:raise SplitError('保存する区間がありません。')
 output=Path(output);output.mkdir(parents=True,exist_ok=False)
 report=dict(result,status='incomplete',outputs=[],skipped=[c for c in result['clips'] if c['id'] in skip_ids])
 try:
  for i,clip in enumerate(selected):
   path=output/(clip['id']+'.mp4');pending=output/(clip['id']+'.partial.mp4')
   command=[str(FFMPEG),'-nostdin','-hide_banner','-loglevel','error','-n','-ss',str(clip['start']),'-i',result['source']['path'],'-t',str(clip['end']-clip['start']),'-map','0:v:0','-an','-c:v','libx264','-preset','ultrafast','-crf','0','-fps_mode','passthrough',str(pending)]
   run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if run.returncode:raise SplitError('動画の書き出しに失敗しました：'+run.stderr[-1000:])
   m=info(pending)
   if abs(m['duration']-(clip['end']-clip['start']))>max(.5,2/result['metadata']['fps']):raise SplitError('書き出し動画の長さが予定と一致しません。')
   pending.rename(path)
   if clip.get('labels') is not None:(output/(clip['id']+'.txt')).write_text(clip['labels'],encoding='utf-8')
   report['outputs'].append(dict(file=path.name,**clip))
   if progress:progress((i+1)/len(selected))
  if identity(result['source']['path'])!=result['source']:raise SplitError('書き出し中に元動画が変更されました。')
  report['status']='complete'
 finally:(output/'split_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return output
