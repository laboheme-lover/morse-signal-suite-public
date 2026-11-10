from pathlib import Path
import csv,hashlib,io,json,math
import cv2
import numpy as np
from morse_table import MORSE_TABLE,REVERSE_TABLE,DIGITS

# International code table, matching mixed_morse.INTERNATIONAL (tested).
LATIN=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',['.-','-...','-.-.','-..','.','..-.','--.','....','..','.---','-.-','.-..','--','-.','---','.--.','--.-','.-.','...','-','..-','...-','.--','-..-','-.--','--..']))
INTERNATIONAL_REVERSE={v:k for k,v in (LATIN|DIGITS|{'.':'.-.-.-',',':'--..--'}).items()}

def metadata(cap):
    fps=cap.get(cv2.CAP_PROP_FPS);width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not math.isfinite(fps) or not 1<=fps<=60 or not 0<width<=1920 or not 0<height<=1080 or not 0<count<=36000 or count/fps>600:
        raise ValueError('対応範囲外または不正な動画情報です（最大1080p・60fps・10分）。')
    return dict(fps=fps,width=width,height=height,frame_count=count,duration_seconds=count/fps)

def preview(path,seconds=0):
    cap=cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():raise ValueError('動画を開けません。対応するコーデックを確認してください。')
        info=metadata(cap)
        cap.set(cv2.CAP_PROP_POS_FRAMES,min(int(seconds*info['fps']),info['frame_count']-1))
        ok,frame=cap.read()
        if not ok:raise ValueError('プレビューフレームを読めません。')
        return info,cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
    finally:cap.release()

def read_trace(path,roi,start=0,end=None):
    path=Path(path)
    if path.stat().st_size>200*1024**2:raise ValueError('動画は200 MiB以下にしてください。')
    cap=cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():raise ValueError('動画を読み込めません。')
        info=metadata(cap);fps=info['fps'];end=info['duration_seconds'] if end is None else end
        x,y,w,h=roi
        if any(type(v) is not int for v in roi) or not (0<=x<x+w<=info['width'] and 0<=y<y+h<=info['height']):raise ValueError('ROIが画像範囲外です。')
        if not all(math.isfinite(v) for v in (start,end)) or not 0<=start<end<=info['duration_seconds']+1e-6:raise ValueError('解析時刻が不正です。')
        values=[];times=[];pts=[];n=0
        while True:
            ok,frame=cap.read()
            if not ok:break
            if n>=36000 or frame.shape[:2]!=(info['height'],info['width']):raise ValueError('フレーム数超過または解像度が途中で変化しました。')
            stamp=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if not math.isfinite(stamp):raise ValueError('動画の時刻情報が不正です。')
            pts.append(stamp)
            t=n/fps
            if start<=t<end:
                values.append(float(cv2.cvtColor(frame[y:y+h,x:x+w],cv2.COLOR_BGR2GRAY).mean()));times.append(t)
            n+=1
        if n!=info['frame_count']:raise ValueError('動画を最後まで読めませんでした（フレーム数不一致）。')
        delta=np.diff(pts)
        if len(delta) and (np.any(delta<=0) or np.max(np.abs(delta-1/fps))>max(.002,.1/fps)):
            raise ValueError('固定fpsと整合する時刻情報が得られません。可変fpsまたは時刻非対応の動画です。')
        if len(values)<3:raise ValueError('解析範囲が短すぎます。')
        return info,np.array(times),np.array(values)
    finally:cap.release()

def runs(states,times,dt):
    edges=np.r_[0,np.flatnonzero(np.diff(states.astype(int)))+1,len(states)]
    return [dict(on=bool(states[a]),start_seconds=float(times[a]),end_seconds=float(times[b-1]+dt),duration_seconds=float((b-a)*dt),frames=int(b-a)) for a,b in zip(edges[:-1],edges[1:])]

def decode(characters,mixed=True):
    inside=False;warnings=[]
    for r in characters:
        p=r['pattern'];r['mode']='international' if inside else 'wabun';r['kind']='character';r['text']=''
        if r['review_reason']:r['text']='□';continue
        if mixed and p in (MORSE_TABLE['（'],MORSE_TABLE['）']):
            opening=p==MORSE_TABLE['（'];r['kind']='mode_control'
            if opening==inside:r['review_reason']='括弧の入れ子／対応不足';warnings.append(r['review_reason'])
            inside=opening
        elif p in ('-..---','...-.'):
            r['kind']='prosign'
            if inside:warnings.append('欧文モードが閉じる前の手続符号')
            inside=False
        else:
            r['text']=(INTERNATIONAL_REVERSE if inside and mixed else REVERSE_TABLE).get(p,'□')
            if r['text']=='□':r['review_reason']='未対応の符号'
    if inside:warnings.append('欧文モードの閉じ括弧がありません。')
    return ''.join(r['text'] for r in characters),warnings

def analyze_trace(times,brightness,fps,*,dot_seconds=None,thresholds=None,invert=False,mixed=True,character_gap_seconds=None):
    times=np.asarray(times);brightness=np.asarray(brightness,dtype=float)
    if len(times)!=len(brightness) or len(times)<3 or not np.isfinite(brightness).all():raise ValueError('輝度列が不正です。')
    signal=255-brightness if invert else brightness
    low,high=np.percentile(signal,[5,95]);contrast=float(high-low)
    if contrast<15:raise ValueError('明暗差が不足しています。光源の範囲や解析時間を確認してください。')
    off,on=(float(low+.35*contrast),float(low+.65*contrast)) if thresholds is None else thresholds
    if not 0<=off<on<=255:raise ValueError('しきい値は0≦消灯側＜点灯側≦255としてください。')
    state=bool(signal[0]>=on);states=[]
    for value in signal:
        if value>=on:state=True
        elif value<=off:state=False
        states.append(state)
    events=runs(np.array(states),times,1/fps);pulses=[r['duration_seconds'] for r in events if r['on']]
    if not pulses or all(states):raise ValueError('点灯と消灯の両方が必要です。')
    if dot_seconds is None:
        a,b=min(pulses),max(pulses)
        for _ in range(20):
            short=[v for v in pulses if abs(v-a)<=abs(v-b)];long=[v for v in pulses if abs(v-a)>abs(v-b)]
            if not short or not long:raise ValueError('短点長を一意に推定できません。手動設定してください。')
            a,b=float(np.median(short)),float(np.median(long))
        if not 2.3<=b/a<=3.7:raise ValueError('短点・長点の比率が不明です。短点長を手動設定してください。')
        dot_seconds=a
    if not math.isfinite(dot_seconds) or dot_seconds<=0:raise ValueError('短点長は正の値にしてください。')
    gap=2*dot_seconds if character_gap_seconds is None else character_gap_seconds
    if not math.isfinite(gap) or gap<=0:raise ValueError('文字間隔が不正です。')
    warnings=[];characters=[];current=[]
    def finish():
        if not current:return
        reasons=[]
        for p in current:
            ratio=p['duration_seconds']/dot_seconds
            p['symbol']='.' if ratio<2 else '-'
            if abs(ratio-(1 if ratio<2 else 3))>max(.5,1/(fps*dot_seconds)):reasons.append('点灯時間が基準から外れています')
        first,last=current[0],current[-1]
        if first['start_seconds']==events[0]['start_seconds'] or last['end_seconds']==events[-1]['end_seconds']:reasons.append('解析範囲の端で点灯が途切れています')
        characters.append(dict(index=len(characters),start_seconds=first['start_seconds'],end_seconds=last['end_seconds'],pattern=''.join(p['symbol'] for p in current),review_reason=' / '.join(dict.fromkeys(reasons))))
        current.clear()
    for event in events:
        if event['on']:current.append(event)
        elif event['duration_seconds']>=gap:finish();event['gap_kind']='word' if event['duration_seconds']>=6*dot_seconds else 'character'
        else:event['gap_kind']='within_character'
    finish()
    candidate,mode_warnings=decode(characters,mixed);warnings.extend(mode_warnings)
    frames_per_dot=dot_seconds*fps
    if frames_per_dot<5:warnings.append('短点あたり5フレーム未満です。本文は確定せず参考結果として表示します。')
    elif frames_per_dot<8:warnings.append('短点あたり8フレーム未満です。境界の誤差に注意してください。')
    review=any(r['review_reason'] for r in characters) or bool(warnings)
    return dict(status='REVIEW' if review else 'OK',text=candidate if frames_per_dot>=5 else '',candidate_text=candidate,characters=characters,events=events,warnings=warnings,
        dot_seconds=float(dot_seconds),frames_per_dot=float(frames_per_dot),threshold_off=float(off),threshold_on=float(on),contrast=contrast,
        trace=[dict(time_seconds=float(t),brightness=float(v),signal=float(s),on=bool(b)) for t,v,s,b in zip(times,brightness,signal,states)])

def analyze_video(path,roi,start=0,end=None,**options):
    info,times,values=read_trace(path,roi,start,end)
    result=analyze_trace(times,values,info['fps'],**options)
    result.update(schema='optical-video-v1',method='光信号のルール解析',input_name=Path(path).name,input_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),video=info,roi=list(roi),range_seconds=[start,end],options=options)
    return result

def csv_text(rows):
    stream=io.StringIO(newline='')
    if rows:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return stream.getvalue()
