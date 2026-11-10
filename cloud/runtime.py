"""Bounded, session-private upload storage for the public demo."""
import hashlib, json, math, os, shutil, subprocess, tempfile, threading
from pathlib import Path

MAX_BYTES=50*1024*1024
MAX_SECONDS=120

def configure():
    os.environ['MORSE_CLOUD']='1'
    os.environ.setdefault('OMP_NUM_THREADS','1')
    os.environ.setdefault('MKL_NUM_THREADS','1')

def inspect_media(path,kind):
    tool=shutil.which('ffprobe')
    if not tool:raise ValueError('動画・音声検査用のffprobeがインストールされていません。')
    try:
        p=subprocess.run([tool,'-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,timeout=20,check=True)
        data=json.loads(p.stdout)
        duration=float(data['format']['duration'])
        if not math.isfinite(duration) or not 0<duration<=MAX_SECONDS:raise ValueError('公開版は120秒以内のファイルに対応します。')
        streams=[s for s in data['streams'] if s.get('codec_type')==kind]
        if not streams:raise ValueError('選択した形式の信号が見つかりません。')
        if kind=='video':
            s=streams[0];w=int(s['width']);h=int(s['height'])
            numerator,denominator=map(float,s.get('avg_frame_rate','0/1').split('/'))
            fps=numerator/denominator if denominator else 0
            if w*h>1920*1080 or not 1<=fps<=60:raise ValueError('公開版の動画はフルHD相当・60fps以下にしてください。')
        return data
    except (subprocess.SubprocessError,KeyError,TypeError,json.JSONDecodeError):
        raise ValueError('ファイルの形式・長さを検査できませんでした。') from None

def store_upload(payload,suffix,state,kind):
    if not payload or len(payload)>MAX_BYTES:raise ValueError('ファイルは50 MB以内にしてください。')
    digest=hashlib.sha256(payload).hexdigest()
    old=state.get('cloud_'+kind)
    if old and old['digest']==digest and Path(old['path']).exists():return old['path']
    # TemporaryDirectory owns its own random folder; no user filename is used as a path.
    folder=Path(tempfile.mkdtemp(prefix='morse_cloud_'))
    path=folder/('input'+suffix)
    try:
        path.write_bytes(payload);inspect_media(path,kind)
    except Exception:
        shutil.rmtree(folder);raise
    timer=threading.Timer(1800,shutil.rmtree,args=(folder,),kwargs={'ignore_errors':True});timer.daemon=True;timer.start()
    if old:shutil.rmtree(Path(old['path']).parent,ignore_errors=True)
    state['cloud_'+kind]={'digest':digest,'path':str(path)}
    return str(path)

def upload_video():
    import streamlit as st
    st.info('公開試用版：動画はクラウドに送信して処理します。50 MB・120秒・フルHD相当・60fpsまで。機密情報を含む動画は送信しないでください。')
    st.caption('一時ファイルは約30分後に削除します。無料サービスの休止・再起動で結果が失われることがあります。')
    up=st.file_uploader('光モールス動画をアップロード',type=['mp4','mov'],disabled=bool(st.session_state.get('ml_job')))
    if up is None:return ''
    try:return store_upload(up.getvalue(),Path(up.name).suffix.lower(),st.session_state,'video')
    except ValueError as e:st.error(str(e));return ''
