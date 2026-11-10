from pathlib import Path
import base64,hashlib,json,tempfile
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from optical_video.core import preview,analyze_video,csv_text
from optical_video.change_points import VERSION
from optical_video.jobs import VideoJob,UI_VERSION,METHODS,summary_rows,comparison_zip
from optical_video.interaction import valid_roi,review_points
from streamlit.components.v1 import declare_component

roi_picker=declare_component('optical_roi_picker',path=str(Path(__file__).parent/'roi_component'))

def jump_preview(seconds,maximum):
    st.session_state['optical_preview_time']=min(maximum,max(0.,seconds))

@st.fragment(run_every=.5)
def job_monitor(key):
    job=st.session_state.get('optical_job')
    if job is None:return
    snapshot=job.snapshot()
    st.progress(snapshot['progress'],text=snapshot['stage'])
    st.caption('進捗は処理段階の目安です。残り時間を示すものではありません。')
    if snapshot['state']=='running':
        if st.button('中止する',key='cancel_optical_job'):
            job.cancel();st.info('中止を要求しました。実行中の処理区間が終わるまでお待ちください。')
        return
    if st.session_state.get('optical_job_handled')!=job.token:
        st.session_state['optical_job_handled']=job.token
        if snapshot['state']=='complete' and job.key==key:
            st.session_state['optical_bundle']=snapshot['result'];st.session_state['optical_key']=key
        st.session_state['optical_job_message']=snapshot['stage']+('：'+snapshot['error'] if snapshot['error'] else '')
        st.rerun()

def main():
    st.title('動画の点滅からモールスを読む')
    st.caption('光信号のルール解析・試作版｜固定カメラ・固定光源向け。音声やCNNは使用しません。')
    uploaded=st.file_uploader('動画（MP4 / AVI、200 MiB以下）',type=['mp4','avi'])
    sample=Path(__file__).parent/'samples'/'mixed_30fps.avi'
    use_sample=st.checkbox('合成サンプルを使用',value=False)
    if uploaded is None and not use_sample:
        job=st.session_state.get('optical_job')
        if job:job.cancel()
        st.session_state.pop('optical_bundle',None)
        st.info('動画を選び、プレビューを見ながら光源を囲む範囲を指定してください。');return
    data=sample.read_bytes() if use_sample else uploaded.getvalue()
    if len(data)>200*1024**2:st.error('200 MiBを超えています。');return
    suffix='.avi' if use_sample else Path(uploaded.name).suffix
    with tempfile.TemporaryDirectory(prefix='morse_video_') as td:
        path=Path(td)/('input'+suffix);path.write_bytes(data)
        try:info,frame=preview(path)
        except (ValueError,cv2.error) as exc:st.error(str(exc));return
        st.write(f"{info['width']} × {info['height']} / {info['fps']:.2f} fps / {info['duration_seconds']:.2f}秒")
        source_id=hashlib.sha256(data).hexdigest()
        if st.session_state.get('optical_source_id')!=source_id:
            st.session_state['optical_source_id']=source_id
            for k in ('optical_preview_time','roi_x','roi_y','roi_w','roi_h','roi_selection'):st.session_state.pop(k,None)
        maximum=max(0.01,info['duration_seconds']-1/info['fps'])
        time=st.slider('プレビュー時刻（秒）',0.,maximum,0.,key='optical_preview_time')
        _,frame=preview(path,time)
        with st.expander('緑枠を移動・サイズ変更して光源範囲を指定',expanded=True):
            defaults=[min(60,info['width']-1),min(40,info['height']-1),min(40,info['width']-min(60,info['width']-1)),min(40,info['height']-min(40,info['height']-1))]
            current=[st.session_state.get(k,v) for k,v in zip(('roi_x','roi_y','roi_w','roi_h'),defaults)]
            ok,png=cv2.imencode('.png',cv2.cvtColor(frame,cv2.COLOR_RGB2BGR))
            context=json.dumps([source_id,time])
            selection=roi_picker(image='data:image/png;base64,'+base64.b64encode(png).decode(),width=info['width'],height=info['height'],roi=current,context=context,key='picker_'+source_id,default=None)
            if selection and selection.get('context')==context and selection.get('event')!=st.session_state.get('roi_selection') and valid_roi(selection.get('roi'),info['width'],info['height']):
                for k,v in zip(('roi_x','roi_y','roi_w','roi_h'),selection['roi']):st.session_state[k]=v
                st.session_state['roi_selection']=selection['event']
                st.rerun()
            st.caption('緑枠の内側をドラッグで移動、白い四角をドラッグでサイズ変更。「この緑枠を解析に適用」で反映。表示倍率2～8倍と数値入力も使えます。')
        cols=st.columns(4)
        x=cols[0].number_input('左 X',0,info['width']-1,defaults[0],key='roi_x')
        y=cols[1].number_input('上 Y',0,info['height']-1,defaults[1],key='roi_y')
        for k,limit in [('roi_w',info['width']-int(x)),('roi_h',info['height']-int(y))]:
            if k in st.session_state and not 1<=st.session_state[k]<=limit:st.session_state[k]=max(1,min(limit,st.session_state[k]))
        w=cols[2].number_input('幅',1,info['width']-int(x),min(40,info['width']-int(x)),key='roi_w')
        h=cols[3].number_input('高さ',1,info['height']-int(y),min(40,info['height']-int(y)),key='roi_h')
        roi=tuple(map(int,(x,y,w,h)));cv2.rectangle(frame,(x,y),(x+w-1,y+h-1),(0,255,0),1)
        st.image(frame,caption='緑の枠が解析する光源領域です。座標は元画像の画素単位です。',width=min(800,info['width']*3))
        cols=st.columns(2)
        start=cols[0].number_input('解析開始（秒）',0.,info['duration_seconds'],0.)
        end=cols[1].number_input('解析終了（秒）',0.,info['duration_seconds'],info['duration_seconds'])
        auto=st.checkbox('短点長を自動推定',True)
        dot=st.number_input('短点長（秒、自動推定OFF時）',.01,10.,.3,step=.01,disabled=auto)
        invert=st.checkbox('明暗を反転（暗くなる信号）')
        mixed=st.checkbox('括弧符号で国際モールスへ切替',True)
        method=st.selectbox('点灯判定方式',['固定しきい値（従来）','適応しきい値（実験的）','変化点対応（実験的）'])
        compare=st.checkbox('3方式を一括比較する')
        if compare:st.caption('同じ動画・光源範囲・解析時間・短点設定で比較します。動画の読み取りは1回です。手動しきい値は比較時には使いません。')
        adaptive=not method.startswith('固定')
        if method.startswith('適応'):st.warning('実験的な方式です。徐々に暗くなる動画では改善しましたが、急に暗くなる動画で、誤った文字を警告なしで出力する例が確認されています。固定方式の結果や元映像と照合してください。')
        if method.startswith('変化点'):st.warning('明暗の基準が急変する場所を検出し、前後を分けて解析する実験方式です。変化点付近は正しく見えても要確認とします。検出できない変化もあります。')
        manual=st.checkbox('しきい値を手動指定',disabled=adaptive or compare)
        thresholds=st.slider('消灯側・点灯側しきい値',0,255,(80,170),disabled=not manual or adaptive or compare)
        gap_manual=st.checkbox('文字間隔を手動指定')
        gap=st.number_input('文字区切りの消灯時間（秒）',.01,30.,.6,disabled=not gap_manual)
        selected_method='change_aware' if method.startswith('変化点') else ('adaptive' if adaptive else 'fixed')
        options=dict(dot_seconds=None if auto else dot,invert=invert,mixed=mixed,thresholds=list(thresholds) if manual and not adaptive and not compare else None,character_gap_seconds=gap if gap_manual else None,threshold_method=selected_method)
        key=hashlib.sha256((VERSION+UI_VERSION).encode()+data+json.dumps([roi,start,end,options,compare]).encode()).hexdigest()
        job=st.session_state.get('optical_job')
        if st.session_state.get('optical_key')!=key:st.session_state.pop('optical_bundle',None)
        if job and job.key!=key:job.cancel()
        busy=job is not None and not job.done.is_set()
        if st.button('解析する',type='primary',disabled=busy):
            st.session_state.pop('optical_bundle',None);st.session_state.pop('optical_job_message',None)
            st.session_state['optical_job']=VideoJob(key,data,suffix,sample.name if use_sample else uploaded.name,roi,start,end,options,compare)
            st.rerun()
        job_monitor(key)
        if st.session_state.get('optical_job_message'):st.caption(st.session_state['optical_job_message'])
        bundle=st.session_state.get('optical_bundle')
        if bundle is None:return
        if bundle['compare']:
            st.subheader('3方式の比較')
            st.dataframe(summary_rows(bundle),hide_index=True)
            st.caption('文章が一致しても正解の保証にはなりません。警告数は誤認識数ではありません。解析秒は共通の動画読込時間を除く目安です。')
            successful=[r for r in bundle['records'] if r['analysis']]
            texts={r['analysis']['text'] for r in successful}
            if len(successful)==3 and len(texts)==1:st.info('3方式の本文は一致しています。')
            else:st.warning('本文に差があるか、解析できなかった方式があります。元映像と照合してください。')
            st.download_button('比較結果をZIPで保存',comparison_zip(bundle),'optical_comparison.zip','application/zip')
            choice=st.selectbox('詳細を見る方式',list(METHODS),format_func=METHODS.get)
            record=next(r for r in bundle['records'] if r['method']==choice)
        else:record=bundle['records'][0]
        result=record['analysis']
        if result is None:st.error(record['error']);return
        st.subheader('認識した文章')
        st.text_area('本文',result['text'],disabled=True)
        if not result['text']:st.write('参考結果：'+result['candidate_text'])
        st.write(f"状態：{result['status']} / 短点 {result['dot_seconds']:.3f}秒 / {result['frames_per_dot']:.1f}フレーム／短点")
        st.caption('OKは現在の検査で警告が出なかったという意味で、文章の正しさや全文の読み取りを保証しません。露出が暗くなる動画では、文字の欠落を検知できないことがあります。')
        for warning in result['warnings']:st.warning(warning)
        points=review_points(result)
        if points:
            selected=st.selectbox('映像で確認する警告時刻',points,format_func=lambda p:f'{p[0]:.3f}秒：{p[1]}')
            st.button('選択した警告時刻へ移動',on_click=jump_preview,args=(selected[0],maximum))
            _,warning_frame=preview(path,selected[0]);cv2.rectangle(warning_frame,(x,y),(x+w-1,y+h-1),(0,255,0),1)
            st.image(warning_frame,caption=f'警告位置 {selected[0]:.3f}秒（上部プレビューへ移動して前後を確認できます）',width=min(600,info['width']*2))
        if result.get('exposure_changes'):
            with st.expander('明暗の基準が変化した時刻',expanded=True):st.dataframe(result['exposure_changes'],hide_index=True)
        if result.get('exposure_suspicions'):
            with st.expander('変化点を確定できないため確認が必要な時刻',expanded=True):st.dataframe(result['exposure_suspicions'],hide_index=True)
        if result.get('diagnostics'):
            with st.expander('信号の見落としが疑われる時間帯',expanded=True):
                st.dataframe([{k:r[k] for k in ('start_seconds','end_seconds','reason')} for r in result['diagnostics']],hide_index=True)
                st.caption('該当時刻の映像と明るさを確認してください。原因の断定や欠落文字の補完はしていません。')
        trace=pd.DataFrame(result['trace']).set_index('time_seconds')
        trace['消灯しきい値']=trace['threshold_off'];trace['点灯しきい値']=trace['threshold_on'];trace['点灯判定（0/255）']=trace['on'].astype(int)*255
        st.subheader('明るさと点灯判定')
        st.line_chart(trace[['signal','消灯しきい値','点灯しきい値','点灯判定（0/255）']])
        st.caption('signalは解析用輝度です。明暗反転時は255−元の輝度。元の値もJSONに保存します。')
        st.subheader('短点・長点と文字の対応')
        st.dataframe(result['characters'],hide_index=True)
        if result['characters']:
            index=st.selectbox('確認する文字区間',range(len(result['characters'])))
            row=result['characters'][index];_,detail=preview(path,row['start_seconds'])
            cv2.rectangle(detail,(x,y),(x+w-1,y+h-1),(0,255,0),1)
            st.image(detail,caption=f"{row['start_seconds']:.3f}秒 / {row['pattern']} / {row['review_reason']}",width=min(600,info['width']*2))
        with st.expander('点灯・消灯の時間一覧'):st.dataframe(result['events'],hide_index=True)
        for label,content,name,mime in [('本文TXT',result['text'],'optical_result.txt','text/plain'),('文字CSV',csv_text(result['characters']).encode('utf-8-sig'),'optical_characters.csv','text/csv'),('詳細JSON',json.dumps(result,ensure_ascii=False,indent=2),'optical_result.json','application/json')]:
            st.download_button(label,content,name,mime)

if __name__=='__main__':main()
