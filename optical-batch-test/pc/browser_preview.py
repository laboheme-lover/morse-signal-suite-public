"""Small browser-compatible clips for viewing only; never used for analysis."""
import hashlib,json,subprocess,uuid
import splitter as s

def make_preview(path,seconds,duration=15.):
 before=s.identity(path);meta=s.info(path)
 start=max(0.,min(float(seconds),meta['duration']-1/meta['fps']))
 length=min(float(duration),meta['duration']-start)
 if not 0<length<=30:raise s.SplitError('プレビューの長さが不正です。')
 key=dict(source=before,start=start,length=length,version=1)
 name=hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()
 folder=s.ROOT/'cache'/'browser_previews';folder.mkdir(parents=True,exist_ok=True)
 output=folder/(name+'.mp4')
 if output.is_file() and output.stat().st_size>0:return output
 pending=folder/(name+'.'+uuid.uuid4().hex+'.mp4')
 args=[str(s.FFMPEG),'-nostdin','-hide_banner','-loglevel','error','-n','-ss',str(start),'-i',str(path),'-t',str(length),'-map','0:v:0','-an','-vf',"scale='min(960,iw)':-2",'-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(pending)]
 try:
  run=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  if run.returncode:raise s.SplitError('軽量プレビューの作成に失敗しました：'+run.stderr[-500:])
  if s.identity(path)!=before:raise s.SplitError('プレビュー作成中に元動画が変更されました。')
  if not pending.exists() or pending.stat().st_size==0:raise s.SplitError('プレビューを書き出せませんでした。')
  pending.replace(output)
 finally:
  if pending.exists():pending.unlink()
 return output
