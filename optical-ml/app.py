"""Optical ML recognition with an interactive original-pixel ROI editor."""
import sys,json,os
from pathlib import Path
import streamlit as st
import torch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from production import VERSION,CHECKPOINT,verify_release,recognize
verify_release()
from predict import classify_features
from flexible_roi import extract_flexible
import splitter
from roi_editor import edit_roi,validate_roi
from light_source import suggest
st.set_page_config(page_title='光モールス機械学習・採用版',layout='wide')
st.title('光モールス機械学習・採用版')
from job_controls import start_job,show_controls
show_controls()
if os.environ.get('MORSE_CLOUD')=='1':
 from runtime import upload_video
 path=upload_video()
else:
 st.caption('PC版：5 GB・20分以内。ファイルを直接読み込みます。')
 path=st.text_input('動画ファイルのフルパス')
name='cnn'
if not path:st.stop()
try:
 from desktop_video import inspect_local
 meta=inspect_local(path)
except Exception as e:st.error(str(e));st.stop()
source=json.dumps(splitter.identity(path),sort_keys=True)
if st.session_state.get('ml_source')!=source:
 st.session_state['ml_source']=source
 for k,v in zip(('ml_x','ml_y','ml_w','ml_h'),validate_roi([930,550,40,40],meta['width'],meta['height'])):st.session_state[k]=v
 st.session_state['ml_sec']=0.;st.session_state.pop('ml_result',None)
 st.session_state.pop('ml_roi_confirmed',None)
 st.session_state.pop('ml_suggestion',None)
st.subheader('1．光源を探して範囲を確認')
if st.button('点滅する光源の範囲を自動提案',disabled=bool(st.session_state.get('ml_job'))):
 st.session_state.pop('ml_roi_confirmed',None)
 try:
  with st.spinner('点滅する光源を探しています…'):
   proposed=suggest(path,st.progress(0.).progress)
  for k,v in zip(('ml_x','ml_y','ml_w','ml_h'),validate_roi(proposed['roi'],meta['width'],meta['height'])):st.session_state[k]=v
  st.session_state['ml_sec']=max(0.,min(proposed['preview_seconds'],meta['duration']-1/meta['fps']))
  st.session_state['ml_suggestion']=proposed
  st.session_state.pop('ml_pending_roi',None)
  st.session_state.pop('ml_result',None)
 except Exception as e:
  st.session_state.pop('ml_suggestion',None)
  st.warning(f'自動提案できませんでした：{e} 点灯している時刻を選び、手動で範囲を指定してください。')
if st.session_state.get('ml_suggestion'):
 st.success('緑枠を調整し、「この光源範囲を確認」を押してください。')
pending=st.session_state.pop('ml_pending_roi',None)
if pending and pending['source']==source:
 for k,v in zip(('ml_x','ml_y','ml_w','ml_h'),validate_roi(pending['roi'],meta['width'],meta['height'])):st.session_state[k]=v
 st.session_state.pop('ml_result',None)
sec=st.number_input('プレビュー位置（秒）',0.,max(0.,meta['duration']-1/meta['fps']),step=.1,key='ml_sec')
c1,c2,c3,c4=st.columns(4)
x=c1.number_input('光源範囲 左X',0,meta['width']-2,key='ml_x');y=c2.number_input('光源範囲 上Y',0,meta['height']-2,key='ml_y')
st.session_state['ml_w']=min(st.session_state['ml_w'],meta['width']-x);st.session_state['ml_h']=min(st.session_state['ml_h'],meta['height']-y)
w=c3.number_input('範囲の幅',2,meta['width']-x,key='ml_w');h=c4.number_input('範囲の高さ',2,meta['height']-y,key='ml_h')
roi=[int(x),int(y),int(w),int(h)]
roi_key=json.dumps([source,roi])
if st.session_state.get('ml_last_roi')!=roi_key:
 st.session_state.pop('ml_roi_confirmed',None)
 st.session_state['ml_last_roi']=roi_key
try:
 picture=splitter.preview(path,sec);context=json.dumps([source,sec])
 event=edit_roi(picture,roi,context)
 if isinstance(event,dict) and event.get('context')==context and event.get('event')!=st.session_state.get('ml_roi_event'):
  st.session_state['ml_pending_roi']={'source':source,'roi':validate_roi(event.get('roi'),meta['width'],meta['height'])}
  st.session_state['ml_roi_event']=event['event'];st.rerun()
 st.caption('枠の内側をドラッグして移動、白い四角でサイズ変更。小さな光源は2～8倍表示で確認し、「この緑枠を解析に適用」を押してください。')
 st.image(picture[y:y+h,x:x+w],caption='認識に使う光源範囲の拡大',width=320)
except Exception as e:st.error(str(e));st.stop()
if st.button('この光源範囲を確認',disabled=bool(st.session_state.get('ml_job'))):
 st.session_state['ml_roi_confirmed']=roi_key
confirmed=st.session_state.get('ml_roi_confirmed')==roi_key
if confirmed:st.success('光源範囲を確認済みです。認識を実行できます。')
else:st.info('緑枠と拡大画像を確認してください。枠を動かした後は、再度確認が必要です。')
if x<1.1*w or y<1.1*h or x+2.1*w>meta['width'] or y+2.1*h>meta['height']:
 st.caption('画面端で周囲の背景が不足する場合は端の画素で補います。可能なら画面端から離れた光源を選んでください。')
mode=st.radio('認識方法',['採用版：連続電文・周期自動推定＋時間補正','補助：単文字・手動の短点時間'])
isolated=mode.startswith('補助')
unit=st.selectbox('短点時間（ms）',[300,450,600]) if isolated else None
key=json.dumps([source,VERSION,name,roi,unit,isolated])
if st.session_state.get('ml_result',{}).get('key')!=key:st.session_state.pop('ml_result',None)
if st.button('認識を実行',disabled=bool(st.session_state.get('ml_job')) or not confirmed):
 try:
  st.session_state['ml_job']=start_job(dict(path=path,roi=roi,unit=unit,isolated=isolated,mode=mode),key)
  st.session_state.pop('ml_job_notice',None)
  st.rerun()
 except Exception as e:st.error(str(e))
if st.session_state.get('ml_result'):
 from result_editor import render_result
 render_result(st.session_state['ml_result'])
