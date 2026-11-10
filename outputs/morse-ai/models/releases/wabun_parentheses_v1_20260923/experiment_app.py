"""Live M1--M4 experimental comparison; no training or production replacement."""
from pathlib import Path
import sys,hashlib,io,json,tempfile,time
import numpy as np
import soundfile as sf
import librosa
import streamlit as st
import altair as alt
import pandas as pd
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'phase8_quality'))
from wabun_runtime_pipeline import evaluate,METHODS,LABELS
import evaluate_new as runner
from stress_frontend import synth
from analyze_saved_errors import ui_review,sha
from wabun_runtime_policy import normalize_reference
from evaluate_recording import edit_alignment
from experimental_audio_io import load_upload

st.set_page_config(page_title='音声処理の実験比較',layout='wide')
st.title('音声処理の実験比較')
st.caption('丸括弧内も和文として解釈します。欧文への自動切替は行いません。')
st.caption('評価用M1〜M4を、同じ音声・同じ重みで比較します。通常アプリの推論設定やモデルは変更しません。')
st.warning('実験機能です。合成音声での改善は実録音での性能を保証しません。予測確率は正解率ではありません。')

@st.cache_resource
def resources():
    runner.verify_frozen()
    return runner.load_models()

def wav_bytes(x):
    stream=io.BytesIO();sf.write(stream,x,16000,format='WAV',subtype='PCM_16');return stream.getvalue()

source=st.radio('入力', ['サンプル','音声ファイル'],horizontal=True)
audio=None;identity=None
if source=='サンプル':
    sample=st.selectbox('サンプル',['音程が揺れる「スセソ」','ゆっくりした「ヘイハ」','丸括弧付き和文「サ（ヘイ）シ」'])
    settings={'音程が揺れる「スセソ」':('スセソ',.08,'wobble60'),
              'ゆっくりした「ヘイハ」':('ヘイハ',.19,'stable'),'丸括弧付き和文「サ（ヘイ）シ」':('サ（ヘイ）シ',.08,'control_spike')}
    signal,dot,profile=settings[sample];audio,_,_=synth(signal,dot,profile,41);identity=hashlib.sha256(audio.tobytes()).hexdigest()
else:
    upload=st.file_uploader('音声（WAV / MP3 / FLAC、0.5〜120秒）',type=['wav','mp3','flac'],max_upload_size=20)
    if upload:
        try:
            payload=upload.getvalue();identity=hashlib.sha256(payload).hexdigest();audio=load_upload(payload,Path(upload.name).suffix.lower())
        except Exception as exc:
            st.error('音声を読み込めませんでした：'+str(exc))
model_name=st.selectbox('モデル',['M1','M2','M3','M4'],index=2)
methods=st.multiselect('比較する処理',METHODS,default=['baseline','combined'],format_func=lambda x:LABELS[x])
if 'guarded' in methods:
    st.warning('補正ガードの自動切り戻しは検証用です。合成検証で一部モデルの総誤りが増えたため、通常利用への採用は保留しています。')
reference_input=st.text_area('正解本文（任意・和文）',help='入力しなければ認識結果だけを表示します。正解は推論に使用せず、処理後の採点にだけ使用します。括弧内も和文です。採点用本文では括弧・句読点を除きます。')
if audio is not None:st.audio(wav_bytes(audio),format='audio/wav')
st.caption('速度補正はモデル入力の音量変化データを短点100 ms基準へ伸縮します。原音と区間の時刻は維持します。音程追従は検出した音程を700 Hzへ変換します。')
key=('wabun-parentheses-v1',identity,model_name,tuple(methods))
if st.button('比較を実行',disabled=audio is None or not methods,type='primary'):
    try:
        with st.spinner('同じ音声で比較しています…'):
            runner.verify_frozen()
            models,cfg,labels=resources();start=time.perf_counter()
            outputs,detectors=evaluate(audio,{model_name:models[model_name]},cfg,labels,methods)
            saved=dict(text_policy='wabun-parentheses-v1',input_sha256=identity,model=model_name,model_sha256=sha(ROOT/f'phase6_wabun65/runs/{model_name.lower()}_wabun65_20260922/best.pt'),
                elapsed_seconds=time.perf_counter()-start,duration_seconds=len(audio)/16000,outputs={},detectors=detectors)
            for (method,name),(text,segments,warnings,error) in outputs.items():
                saved['outputs'][method]=dict(text=text,segments=segments,warnings=warnings,error=error)
            st.session_state['experiment_result']=(key,saved)
    except Exception as exc:st.error('比較処理に失敗しました：'+str(exc))

stored=st.session_state.get('experiment_result')
if stored and stored[0]==key:
    saved=stored[1];reference=None
    if reference_input.strip():
        try:reference=normalize_reference(reference_input)
        except ValueError as exc:st.error('正解本文を採点できません：'+str(exc))
    summary=[]
    for method,data in saved['outputs'].items():
        meta=saved['detectors'][method]
        row={'処理':LABELS[method],'認識本文':data['text'],'状態':'失敗' if data['error'] else '完了',
             '要確認区間':sum(ui_review(r) for r in data['segments']),'推定短点（ms）':round(meta['dot_seconds']*1000,2) if 'dot_seconds' in meta else None}
        if reference is not None:
            metric,_=edit_alignment(reference,data['text']);row['編集距離']=metric['edit_distance'];row['CER']=metric['cer']
        summary.append(row)
    st.subheader('比較結果');st.dataframe(summary,hide_index=True)
    st.caption(f"処理時間：{saved['elapsed_seconds']:.2f}秒。全文を対象にした結果です。失敗時の本文は空として採点します。")
    chosen=st.selectbox('詳しく見る処理',list(saved['outputs']),format_func=lambda x:LABELS[x])
    data=saved['outputs'][chosen];meta=saved['detectors'][chosen]
    if 'guard' in meta:
        st.caption('補正ガードの選択：'+LABELS[meta['guard']['selected_method']]+'。選択は正解文を使わず、音と観測符号から判断します。')
    st.text(data['text'] or '（本文なし）')
    if data['error']:st.error(data['error'])
    for warning in data['warnings']:st.warning(warning)
    if 'track_hz' in meta:
        st.subheader('追跡した音程')
        frame=pd.DataFrame({'時刻（秒）':meta['track_seconds'],'音程（Hz）':meta['track_hz']})
        chart=alt.Chart(alt.InlineData(values=frame.to_dict('records'))).mark_line().encode(
            x=alt.X('時刻（秒）:Q',scale=alt.Scale(domain=[0,saved['duration_seconds']])),
            y=alt.Y('音程（Hz）:Q',scale=alt.Scale(domain=[min(meta['track_hz'])-25,max(meta['track_hz'])+25])),
            tooltip=['時刻（秒）:Q','音程（Hz）:Q']).properties(height=260)
        st.altair_chart(chart,width='stretch')
        st.caption('無音区間の音程は前後の値から補間しています。')
    rows=data['segments']
    if rows:
        st.dataframe([dict(区間=r['index'],開始秒=round(r['start_seconds'],3),終了秒=round(r['end_seconds'],3),文字=r['text_prediction'],
                           予測確率=round(r['confidence'],4),要確認=ui_review(r),時間倍率=r.get('feature_time_scale',1.)) for r in rows],hide_index=True)
        i=st.selectbox('原音を確認する区間',range(len(rows)),format_func=lambda i:f"{i+1}：{rows[i]['text_prediction'] or rows[i].get('prosign','制御符号')}")
        r=rows[i];st.audio(wav_bytes(audio[r['start_sample']:r['end_sample']]),format='audio/wav')
        st.dataframe(r.get('display_candidates',r.get('top_k',[])),hide_index=True)
        if r.get('review_reason'):st.warning(r['review_reason'])
    export=dict(saved,reference=reference,comparison_summary=summary)
    st.download_button('比較結果をJSON保存',json.dumps(export,ensure_ascii=False,indent=2),'experimental_comparison.json','application/json')
elif stored:
    st.info('入力または設定が変わりました。「比較を実行」で新しい結果を計算してください。')
