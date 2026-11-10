"""Disk-to-disk H.264 export. Never buffers the video file in memory."""
import json, math, os, shutil, subprocess, time, uuid
from pathlib import Path
import cv2
from desktop_video import inspect_local

def ffmpeg_path():
    from predict import splitter
    tool=shutil.which('ffmpeg')
    if tool:return tool
    if Path(splitter.FFMPEG).is_file():return str(splitter.FFMPEG)
    raise ValueError('FFmpegが見つかりません。FFmpegをインストールしてPATHに追加してください。')

def web_reasons(meta,size):
    reasons=[]
    if size>300*1024**2:reasons.append('300 MBを超えています')
    if meta['duration']>300:reasons.append('5分を超えています（別途分割が必要です）')
    if meta['width']*meta['height']>1920*1080:reasons.append('フルHD相当を超えています')
    if not 1<=meta['fps']<=60:reasons.append('フレームレートがWeb版の範囲外です')
    return reasons

def start(source,directory):
    source=Path(source).resolve();meta=inspect_local(source)
    if meta['width']%2 or meta['height']%2:raise ValueError('解像度維持のH.264圧縮には縦横とも偶数の画素数が必要です。')
    directory=Path(directory).expanduser().resolve()
    if not directory.is_dir():raise ValueError('既存の保存先フォルダを指定してください。')
    token=time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    dest=directory/(source.stem+'_web_'+token+'.mp4')
    partial=dest.with_name(dest.stem+'.partial.mp4');log=dest.with_suffix('.compression.log')
    command=[ffmpeg_path(),'-nostdin','-hide_banner','-n','-i',str(source),'-map','0:v:0','-an','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-threads','4','-fps_mode','passthrough','-enc_time_base','-1','-movflags','+faststart','-progress','pipe:1',str(partial)]
    with log.open('w',encoding='utf-8') as f:
        process=subprocess.Popen(command,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    stat=source.stat()
    return dict(process=process,source=source,dest=dest,partial=partial,log=log,meta=meta,identity=(stat.st_size,stat.st_mtime_ns))

def cancel(job):
    p=job['process']
    if p.poll() is None:
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
    job['partial'].unlink(missing_ok=True)

def progress(job):
    with job['log'].open('rb') as f:
        f.seek(max(0,job['log'].stat().st_size-16384));text=f.read().decode('utf-8',errors='replace')
    values=[x.split('=',1)[1] for x in text.splitlines() if x.startswith('out_time_us=')]
    try:return min(.99,max(0,float(values[-1])/1e6/job['meta']['duration']))
    except (ValueError,IndexError):return 0.

def verify_timing(source,dest):
    a=cv2.VideoCapture(str(source));b=cv2.VideoCapture(str(dest));count=0;delta=0.
    try:
        while True:
            x=a.grab();y=b.grab()
            if x!=y:raise ValueError('圧縮前後のフレーム数が一致しません。')
            if not x:break
            diff=abs(a.get(cv2.CAP_PROP_POS_MSEC)-b.get(cv2.CAP_PROP_POS_MSEC))/1000
            if not math.isfinite(diff):raise ValueError('フレーム時刻が不正です。')
            delta=max(delta,diff);count+=1
            if diff>.002:raise ValueError('圧縮前後のフレーム時刻が一致しません。')
    finally:a.release();b.release()
    if count<3:raise ValueError('動画を検証できませんでした。')
    return count,delta

def finish(job):
    if job['process'].poll() is None:raise ValueError('まだ圧縮中です。')
    try:
        if job['process'].returncode!=0:raise ValueError('圧縮に失敗しました。ログ：'+str(job['log']))
        stat=job['source'].stat()
        if (stat.st_size,stat.st_mtime_ns)!=job['identity']:raise ValueError('処理中に元動画が変更されました。')
        meta=inspect_local(job['partial'])
        if (meta['width'],meta['height'])!=(job['meta']['width'],job['meta']['height']):raise ValueError('解像度が変わっています。')
        count,delta=verify_timing(job['source'],job['partial'])
        if count!=job['meta']['frames']:raise ValueError('全フレームを検証できませんでした。')
        if job['dest'].exists():raise ValueError('保存先が既に存在します。上書きしません。')
        job['partial'].rename(job['dest'])
        result=dict(path=str(job['dest']),source=str(job['source']),original_bytes=stat.st_size,bytes=job['dest'].stat().st_size,frames=count,timestamp_max_delta_seconds=delta,meta=meta,web_reasons=web_reasons(meta,job['dest'].stat().st_size))
        job['dest'].with_suffix('.compression.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return result
    finally:
        job['partial'].unlink(missing_ok=True)
