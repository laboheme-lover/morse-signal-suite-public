from pathlib import Path
from datetime import datetime
import sys,json
import streamlit as st
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import splitter as s
from light_source import suggest
from trace_cache import read_cached
from browser_preview import make_preview
from roi_editor import edit_roi,validate_roi
st.set_page_config(page_title='光モールス動画の分割',layout='wide')
st.title('光モールス試験動画の分割')
st.write('①プレビュー → ②光源の範囲と送信条件を指定 → ③検出状態の確認 → ④分割保存')
st.info('AndroidからPCへ動画をコピーしてください。送信時と同じバッチ・開始位置・終了位置・短点時間を選びます。元動画は変更しません。')
with st.expander('使い方：光源の自動提案から分割保存まで',expanded=False):
 st.markdown("""
### 基本の手順

1. **動画を指定する**：AndroidからPCへコピーした動画のフルパスを入力します。大きな動画でも静止画で確認できます。動きも確認したい場合は「軽量な動画プレビューを表示（選択位置から15秒）」をオンにします。
2. **光源を探す**：「点滅する光源の範囲を自動提案」を押します。探索が終わると、光源候補を囲む緑枠と、明るい場面のプレビューが表示されます。
3. **緑枠を調整する**：静止画上で枠の内側をドラッグすると移動、四隅・辺の白い四角をドラッグするとサイズ変更できます。「新しい範囲を描く」で光源を囲み直すこともできます。小さな光源は表示倍率を2～8倍にしてスクロールで探してください。「この緑枠を解析に適用」を押すと解析範囲が更新されます。左X・上Y・幅・高さでの数値指定も可能です。プレビュー位置を変え、消灯時も確認してから「プレビューで点滅と光源の範囲を確認しました」にチェックします。
4. **送信条件を合わせる**：撮影時と同じ原稿版・送信バッチ・開始位置・終了位置・短点時間を選びます。複数の送信単位を撮影した場合は、Androidで送った順に選びます。「開始前の光モールスから送信範囲を自動連携」は、送信側でも自動連携をオンにした動画だけで使います。
5. **解析する**：まず「厳密検査（従来方式）」で「動画を解析して分割できるか確認」を押します。初回は動画全体の読み取りに時間がかかります。同じ動画・光源範囲なら、読み取り結果を再利用して条件を再検査できます。
6. **結果を確認して保存する**：「分割可能」の件数、点灯・消灯の明るさの差、区間一覧を確認します。新しい保存先フォルダを指定し、「検査済み区間を分割して保存」を押します。前後0.5秒の余白を付けた無音MP4、原稿TXT、記録JSONを保存します。元動画は変更しません。

### うまく読めない場合

- **明るさの差が不足**：まず光源範囲を小さく調整します。暗い背景を広く含めると、小さなライトの明るさが平均されて薄まります。感度の基準を下げる前に、範囲を見直してください。
- **自動提案が外れる**：探索は動画の一部の場面を使うため、短い送信や動く光源では見つからない場合があります。点灯しているプレビュー位置を選び、手動で範囲を指定してください。
- **件数・点滅時間が一致しない**：バッチ、送信順、範囲、短点時間を確認します。前後に別の送信を含む場合は「動画の解析時間も指定」で対象を絞り、前後に1秒以上の消灯を残します。
- **厳密検査を通らない区間も調べたい**：「10秒休止で候補分割（要確認）」を使えます。候補は原稿との対応が未確認です。区間を確認し、必要なら読み飛ばす区間を選択してください。候補保存では原稿TXTを付けません。
- **フレーム時刻のエラー**：確認できる先頭時刻の誤りは自動補正します。なおエラーが出る場合は、メッセージと動画のパスを控えて時刻情報を調べてください。途中の欠落は自動で埋めません。

### 今回の改善例

1634.mp4では、光源を囲む範囲を絞ることで、点灯・消灯の明るさの差が約1.6から83.7となり、65件すべての点滅数・時間・10秒休止が厳密検査を通りました。**光源の位置や適切な範囲は動画ごとに異なります。**
""")
 st.info('「分割可能」は区切りと原稿の点滅列との整合を確認した結果です。独立した文字認識モデルの正解率を示すものではありません。')
path=st.text_input('動画ファイルのフルパス（MP4など）')
if not path:st.stop()
try:meta=s.info(path)
except Exception as e:st.error(str(e));st.stop()
st.caption(f"{meta['width']}×{meta['height']} / {meta['fps']:.2f} fps / 約{meta['duration']/60:.1f}分")
source_key=json.dumps(s.identity(path),sort_keys=True)
if st.session_state.get('roi_source')!=source_key:
 st.session_state['roi_source']=source_key
 for k,val in [('roi_x',meta['width']//3),('roi_y',meta['height']//3),('roi_w',meta['width']//3),('roi_h',meta['height']//3),('preview_sec',min(6.,max(0.,meta['duration']-1/meta['fps']))),('roi_reviewed',False)]:st.session_state[k]=val
 st.session_state.pop('roi_suggestion',None)
 st.session_state.pop('preview_roi_error',None)
def narrow_preview_source():
 try:
  start=float(st.session_state['preview_sec'])
  with st.spinner('選択位置から15秒間の点滅を調べています…'):
   proposed=suggest(path,start_seconds=start,end_seconds=start+15)
  for k,val in zip(['roi_x','roi_y','roi_w','roi_h'],proposed['roi']):st.session_state[k]=val
  st.session_state['preview_sec']=proposed['preview_seconds'];st.session_state['roi_reviewed']=False
  st.session_state['roi_suggestion']=proposed;st.session_state.pop('preview_roi_error',None)
 except Exception as e:st.session_state['preview_roi_error']=str(e)
if st.button('点滅する光源の範囲を自動提案'):
 try:
  with st.spinner('動画の複数の場面から点滅する場所を探索しています…'):
   proposed=suggest(path,st.progress(0.).progress)
  for k,val in zip(['roi_x','roi_y','roi_w','roi_h'],proposed['roi']):st.session_state[k]=val
  st.session_state['preview_sec']=proposed['preview_seconds'];st.session_state['roi_reviewed']=False
  st.session_state['roi_suggestion']=proposed
 except Exception as e:st.error(str(e))
if st.session_state.get('roi_suggestion'):
 st.info('点滅が強い場所を提案しました。反射光や別の光源の可能性もあるため、緑枠と拡大画像を確認してください。')
st.caption('小さなライトは、その周囲だけを囲んでください。広い背景を含めると点灯・消灯の差が薄まります。')
sec=st.number_input('プレビュー位置（秒）',0.,max(0.,meta['duration']-1/meta['fps']),step=.1,key='preview_sec')
st.button('この15秒プレビューから点滅範囲を絞り込む',on_click=narrow_preview_source)
if st.session_state.get('preview_roi_error'):st.warning(st.session_state['preview_roi_error'])
pending=st.session_state.pop('pending_roi',None)
if pending and pending['source']==source_key:
 for k,val in zip(['roi_x','roi_y','roi_w','roi_h'],validate_roi(pending['roi'],meta['width'],meta['height'])):st.session_state[k]=val
 st.session_state['roi_reviewed']=False
 st.session_state.pop('checked',None)
def roi_changed():
 st.session_state['roi_reviewed']=False
 st.session_state.pop('checked',None)
c1,c2,c3,c4=st.columns(4)
x=c1.number_input('光源範囲 左X',0,meta['width']-2,key='roi_x',on_change=roi_changed)
y=c2.number_input('光源範囲 上Y',0,meta['height']-2,key='roi_y',on_change=roi_changed)
st.session_state['roi_w']=min(st.session_state['roi_w'],meta['width']-int(x))
st.session_state['roi_h']=min(st.session_state['roi_h'],meta['height']-int(y))
w=c3.number_input('範囲の幅',2,meta['width']-int(x),key='roi_w',on_change=roi_changed)
h=c4.number_input('範囲の高さ',2,meta['height']-int(y),key='roi_h',on_change=roi_changed)
roi=[int(x),int(y),int(w),int(h)]
if st.checkbox('軽量な動画プレビューを表示（選択位置から15秒）',key='light_video_preview'):
 try:
  with st.spinner('ブラウザー用の短いプレビューを準備しています…'):
   clip=make_preview(path,sec)
  st.video(str(clip))
  st.caption(f'元動画の {sec:.2f} 秒から最大15秒の無音・縮小プレビューです。プレーヤーの0秒はこの開始位置に対応します。解析と分割保存には元動画を使用します。')
 except Exception as e:st.warning(str(e)+' 静止画プレビューと解析は引き続き利用できます。')
try:
 picture=s.preview(path,sec)
 context=json.dumps([source_key,sec])
 event=edit_roi(picture,roi,context)
 if isinstance(event,dict) and event.get('context')==context and event.get('event')!=st.session_state.get('roi_editor_event'):
  selected=validate_roi(event.get('roi'),meta['width'],meta['height'])
  st.session_state['roi_editor_event']=event['event']
  st.session_state['pending_roi']={'source':source_key,'roi':selected}
  st.rerun()
 st.caption('緑枠を動かす・縮める →「この緑枠を解析に適用」→ 拡大画像を確認 → 確認チェックを入れて解析。2～8倍表示では画像内をスクロールできます。')
 st.image(picture[int(y):int(y+h),int(x):int(x+w)],caption='選択した光源範囲の拡大',width=320)
except Exception as e:st.error(str(e));st.stop()
reviewed=st.checkbox('プレビューで点滅と光源の範囲を確認しました',key='roi_reviewed')
auto_header=st.checkbox('開始前の光モールスから送信範囲を自動連携（0.4.0以降・試験機能）')
if auto_header:
 st.info('送信側で自動連携をオンにした動画のみ対応します。原稿版・順序・速度・誤読チェックを検証し、本文だけを分割します。従来動画はチェックを外して手動指定してください。')
 profile='sentence';batch=s.corpus(profile)['batches'][0];batch_ids=[batch['id']];first=1;last=len(batch['cases']);unit=300
else:
 profile=st.selectbox('送信アプリの原稿版',['sentence','full'],format_func=lambda p:'全文原稿・10＋2バッチ／休止10秒' if p=='full' else '単文・44＋20バッチ（複数選択対応）')
 batches=s.corpus(profile)['batches']
 multiple=st.checkbox('複数の送信単位を連続撮影した動画')
 if multiple:
  indices=st.multiselect('Androidで送信した順に選択',range(len(batches)),format_func=lambda i:batches[i]['name'])
  if not indices:st.info('送信順と同じ順番に選択してください。');st.stop()
  batch_ids=[batches[i]['id'] for i in indices]
  batch=s.selected_batch('selection_queue',profile,batch_ids)
  st.write('送信順：'+' → '.join(batches[i]['name'] for i in indices))
 else:
  idx=st.selectbox('送信バッチ',range(len(batches)),format_func=lambda i:batches[i]['name']);batch=batches[idx];batch_ids=[batch['id']]
 c1,c2,c3=st.columns(3)
 first=c1.number_input('開始位置（1から）',1,len(batch['cases']),1,key='first_'+','.join(batch_ids))
 last=c2.number_input('終了位置',int(first),len(batch['cases']),len(batch['cases']),key='last_'+','.join(batch_ids)+str(first))
 unit=c3.selectbox('短点時間（ms）',[300,450,600])
 st.dataframe([{'位置':i+1,'ID':c['id'],'原稿':c['labels']} for i,c in enumerate(batch['cases'])][int(first)-1:int(last)],hide_index=True)
video_start=0.;video_end=None
if not auto_header and st.checkbox('動画の解析時間も指定（前後に1秒以上の消灯を含める）'):
 c1,c2=st.columns(2)
 video_start=c1.number_input('動画内の開始秒',0.,float(meta['duration']),0.,.1)
 video_end=c2.number_input('動画内の終了秒',0.,float(meta['duration']),float(meta['duration']),.1)
contrast=st.slider('必要な点灯・消灯の明るさの差（0〜255の輝度）',8,100,20,help='小さくすると暗い信号を通しやすくなりますが、雑音も拾いやすくなります。合格は認識精度の保証ではありません。')
mode=st.radio('分割方式',['strict','pause_candidates'],format_func=lambda m:'厳密検査（従来方式）' if m=='strict' else '10秒休止で候補分割（要確認）')
if mode=='pause_candidates':st.warning('約10秒（8秒以上）の消灯を区切り候補にします。フレーム間隔の異常は記録して続行しますが、欠落した点滅は補いません。原稿番号と正解文は自動付与しません。異常区間は保存対象から除外できます。')
key=json.dumps([s.identity(path),roi,batch['id'],first,last,unit,contrast,mode,profile,batch_ids,auto_header,video_start,video_end],sort_keys=True)
if st.button('動画を解析して分割できるか確認',disabled=not reviewed):
 st.session_state.pop('checked',None)
 progress=st.progress(0.)
 try:
  result,t,v=s.analyze(path,roi,batch['id'],int(first),int(last),unit,contrast,progress.progress,mode=mode,profile=profile,batch_ids=batch_ids,auto_header=auto_header,video_start=video_start,video_end=video_end,trace_reader=read_cached)
  st.session_state['checked']=(key,result)
  st.session_state['trace']={'秒':t[::max(1,len(t)//4000)],'輝度':v[::max(1,len(v)//4000)]}
 except Exception as e:
  st.error(str(e))
  if auto_header:
   st.info('自動連携は、送信時に連携信号を付けた動画だけで使えます。手動指定で続ける場合は、上の「開始前の光モールスから送信範囲を自動連携」のチェックを外し、送信したバッチ・順番・短点時間を指定して再解析してください。複数の単文を撮影した場合は「複数の送信単位を連続撮影した動画」をオンにします。連携信号が動画に残っている場合は、解析時間を本文の範囲に限定してください。原稿は自動では割り当てません。')
checked=st.session_state.get('checked')
if checked and checked[0]==key and reviewed:
 result=checked[1]
 if result['metadata'].get('brightness_cache_hit'):st.caption('前回の輝度読み取り結果を再利用しました。現在の送信条件で再検査しています。')
 if result.get('optical_header'):
  st.success('自動連携成功：短点 '+str(result['unit_ms'])+' ms／送信順：'+' → '.join(result['batch_ids']))
  st.caption('開始前の連携信号は本文・認識評価の対象から除外しています。')
 for correction in result['metadata'].get('timestamp_corrections',[]):
  st.info(f"先頭フレームの時刻を補正しました：{correction['raw_seconds']:.6f}秒 → {correction['corrected_seconds']:.6f}秒。映像の補間や欠落の埋め合わせは行っていません。")
 review=result['quality']=='REVIEW'
 if review:
  st.warning(f"候補 {len(result['clips'])}区間（予定 {result['expected_count']}件）。点灯・消灯の輝度差 {result['contrast']:.1f}。原稿との対応は未確認です。")
  for warning in result['warnings']:st.write(warning)
  st.write(f"フレーム間隔の最大値：{result['frame_interval_max']*1000:.1f} ms／異常 {len(result['timing_anomalies'])}か所")
  st.dataframe(result['pauses'])
 else:st.success(f"分割可能：{len(result['clips'])}件。点灯・消灯の輝度差 {result['contrast']:.1f}。10秒休止・点滅数・時間の整合を確認しました。")
 st.caption('原稿の点滅列との照合は誤分割防止のためです。機械学習モデルの認識精度を評価したものではありません。')
 st.line_chart(st.session_state['trace'],x='秒',y='輝度')
 st.dataframe([{'ID':c['id'],'開始秒':round(c['start'],3),'終了秒':round(c['end'],3),'注意':'／'.join(c.get('issues',[]))} for c in result['clips']])
 skip=st.multiselect('読み飛ばす区間（保存しない）',[c['id'] for c in result['clips']]) if review else []
 allow=st.checkbox('原稿対応と点滅品質が未確認の候補として保存します') if review else False
 st.write('前後0.5秒の余白を付けた無音MP4と記録JSONを保存します。候補分割では原稿TXTを付けず、除外区間と異常を記録します。厳密検査では原稿TXTも保存します。')
 output=st.text_input('保存先（新しいフォルダ）',str(s.ROOT/'splits'/datetime.now().strftime('%Y%m%d_%H%M%S')))
 if st.button('候補区間を分割して保存' if review else '検査済み区間を分割して保存',disabled=review and not allow):
  try:
   p=st.progress(0.);folder=s.export(result,output,p.progress,allow_review=allow,skip_ids=skip);st.success('保存しました：'+str(folder))
  except Exception as e:st.error(str(e))
elif checked:st.warning('条件が変更されました。もう一度解析してください。')
