from pathlib import Path
import hashlib,json,tempfile
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from optical_video.core import preview,analyze_video,csv_text
from optical_video.change_points import VERSION

def main():
    st.title('動画の点滅からモールスを読む')
    st.caption('光信号のルール解析・試作版｜固定カメラ・固定光源向け。音声やCNNは使用しません。')
    uploaded=st.file_uploader('動画（MP4 / AVI、200 MiB以下）',type=['mp4','avi'])
    sample=Path(__file__).parent/'samples'/'mixed_30fps.avi'
    use_sample=st.checkbox('合成サンプルを使用',value=False)
    if uploaded is None and not use_sample:
        st.info('動画を選び、プレビューを見ながら光源を囲む範囲を指定してください。');return
    data=sample.read_bytes() if use_sample else uploaded.getvalue()
    if len(data)>200*1024**2:st.error('200 MiBを超えています。');return
    suffix='.avi' if use_sample else Path(uploaded.name).suffix
    with tempfile.TemporaryDirectory(prefix='morse_video_') as td:
        path=Path(td)/('input'+suffix);path.write_bytes(data)
        try:info,frame=preview(path)
        except (ValueError,cv2.error) as exc:st.error(str(exc));return
        st.write(f"{info['width']} × {info['height']} / {info['fps']:.2f} fps / {info['duration_seconds']:.2f}秒")
        time=st.slider('プレビュー時刻（秒）',0.,max(0.01,info['duration_seconds']-1/info['fps']),0.)
        _,frame=preview(path,time)
        cols=st.columns(4)
        x=cols[0].number_input('左 X',0,info['width']-1,min(60,info['width']-1))
        y=cols[1].number_input('上 Y',0,info['height']-1,min(40,info['height']-1))
        w=cols[2].number_input('幅',1,info['width']-int(x),min(40,info['width']-int(x)))
        h=cols[3].number_input('高さ',1,info['height']-int(y),min(40,info['height']-int(y)))
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
        adaptive=not method.startswith('固定')
        if method.startswith('適応'):st.warning('実験的な方式です。徐々に暗くなる動画では改善しましたが、急に暗くなる動画で、誤った文字を警告なしで出力する例が確認されています。固定方式の結果や元映像と照合してください。')
        if method.startswith('変化点'):st.warning('明暗の基準が急変する場所を検出し、前後を分けて解析する実験方式です。変化点付近は正しく見えても要確認とします。検出できない変化もあります。')
        manual=st.checkbox('しきい値を手動指定',disabled=adaptive)
        thresholds=st.slider('消灯側・点灯側しきい値',0,255,(80,170),disabled=not manual or adaptive)
        gap_manual=st.checkbox('文字間隔を手動指定')
        gap=st.number_input('文字区切りの消灯時間（秒）',.01,30.,.6,disabled=not gap_manual)
        selected_method='change_aware' if method.startswith('変化点') else ('adaptive' if adaptive else 'fixed')
        options=dict(dot_seconds=None if auto else dot,invert=invert,mixed=mixed,thresholds=list(thresholds) if manual and not adaptive else None,character_gap_seconds=gap if gap_manual else None,threshold_method=selected_method)
        key=hashlib.sha256(VERSION.encode()+data+json.dumps([roi,start,end,options]).encode()).hexdigest()
        if st.session_state.get('optical_key')!=key:st.session_state.pop('optical_result',None)
        if st.button('解析する',type='primary'):
            try:
                with st.spinner('動画を読み取り、点滅を解析しています…'):
                    result=analyze_video(path,roi,start,end,**options)
                result['input_name']=sample.name if use_sample else uploaded.name
                st.session_state['optical_result']=result;st.session_state['optical_key']=key
            except (ValueError,OSError,cv2.error) as exc:st.error(str(exc))
        result=st.session_state.get('optical_result')
        if result is None:return
        st.subheader('認識した文章')
        st.text_area('本文',result['text'],disabled=True)
        if not result['text']:st.write('参考結果：'+result['candidate_text'])
        st.write(f"状態：{result['status']} / 短点 {result['dot_seconds']:.3f}秒 / {result['frames_per_dot']:.1f}フレーム／短点")
        st.caption('OKは現在の検査で警告が出なかったという意味で、文章の正しさや全文の読み取りを保証しません。露出が暗くなる動画では、文字の欠落を検知できないことがあります。')
        for warning in result['warnings']:st.warning(warning)
        if result.get('exposure_changes'):
            with st.expander('明暗の基準が変化した時刻',expanded=True):st.dataframe(result['exposure_changes'],hide_index=True)
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
