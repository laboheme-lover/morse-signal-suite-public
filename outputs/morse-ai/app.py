"""Milestone 10: local Streamlit interface for continuous Wabun recognition."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import numpy as np
import streamlit as st
import torch
from audio_preprocessing import load_audio
from generate_morse_audio import generate_morse_audio
from adopted_m3 import M3SequencePredictor

st.set_page_config(page_title='和文モールス認識',page_icon='📻',layout='wide')

@st.cache_resource
def get_predictor():
    torch.set_num_threads(1)
    return M3SequencePredictor()

def wav_bytes(audio,sample_rate=16000):
    import soundfile as sf
    stream=io.BytesIO();sf.write(stream,audio,sample_rate,format='WAV',subtype='PCM_16')
    return stream.getvalue()

def result_json(result):
    clean={k:v for k,v in result.items() if k!='segments'}
    clean['segments']=[{k:v for k,v in row.items() if k not in ('audio','mel')} for row in result['segments']]
    return json.dumps(clean,ensure_ascii=False,indent=2)

st.title('和文モールス認識')
st.caption('採用モデル：M3 ／ 前処理：baseline ／ 丸括弧内も和文')
st.caption('音声を文字ごとに分け、認識候補を確認できます。処理はこのPC内で行います。')
with st.sidebar:
    st.header('認識設定')
    auto_gap=True;gap=.2;auto_frequency=True;frequency=700.;shift=False;mixed=False
    top_k=st.slider('候補数',1,5,3)
    threshold=st.slider('要確認にする予測確率の下限',0.,1.,.8,.05)
    st.caption('採用構成の周波数・文字間隔は自動推定です。丸括弧内も和文として読みます。')
    st.caption('予測確率は正しさの保証ではありません。低確率や方式間の不一致を「要確認」にします。')

source=st.radio('音声の入力方法',['ファイルをアップロード','サンプル：イロハ','サンプル：イ（ヤチツ）ロ'],horizontal=True)
payload=None;name='';suffix='.wav'
if source=='ファイルをアップロード':
    uploaded=st.file_uploader('WAV / MP3を選択',type=['wav','mp3'])
    if uploaded is not None:
        payload=uploaded.getvalue();name=uploaded.name;suffix=Path(name).suffix.lower()
else:
    letters='イロハ' if source=='サンプル：イロハ' else 'イ（ヤチツ）ロ'
    payload=wav_bytes(np.concatenate([generate_morse_audio(c,padding=.15) for c in letters]))
    name=source
if payload is not None:
    st.audio(payload,format='audio/mpeg' if suffix=='.mp3' else 'audio/wav')
    st.caption(name)
options=dict(top_k=top_k,low_confidence=threshold,mixed_mode=mixed,
             frequency_hz=None if auto_frequency else frequency,target_frequency_hz=700. if shift else None,
             character_gap_seconds=None if auto_gap else gap)
fingerprint=hashlib.sha256(b'adopted-M3-baseline-wabun-v1'+(payload or b'')+json.dumps(options,sort_keys=True).encode()).hexdigest()
if st.session_state.get('result_key')!=fingerprint:
    st.session_state.pop('recognition',None)
if st.button('認識する',type='primary',disabled=not payload):
    st.session_state.pop('recognition',None)
    try:
        with st.spinner('音声を分割して認識しています…'):
            predictor=get_predictor()
            with tempfile.TemporaryDirectory(prefix='morse_upload_') as temporary:
                path=Path(temporary)/('input'+suffix);path.write_bytes(payload)
                audio=load_audio(path,predictor.single.config)
            if len(audio)>16000*1800:raise ValueError('音声は30分以内に分けてください。')
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=1):
                result=predictor.predict_audio(audio,include_details=True,**options)
            result['text_policy']='wabun-parentheses-v1: parentheses retained, no international switch'
            result['input_name']=name;result['input_sha256']=hashlib.sha256(payload).hexdigest()
            st.session_state['recognition']=result;st.session_state['result_key']=fingerprint
    except Exception as exc:
        st.error(f'認識できませんでした：{exc}')
        st.info('音声の形式、無音でないこと、周波数と文字間隔の設定を確認してください。')

result=st.session_state.get('recognition')
if result is None:
    st.info('音声を選んで「認識する」を押してください。サンプル音声でも試せます。')
else:
    st.subheader('認識結果')
    st.text_area('CNNの認識文字列',value=result['text'],height=140,disabled=True)
    cols=st.columns(3)
    cols[0].metric('認識文字数',result['character_count'])
    cols[1].metric('平均予測確率',f"{result['mean_confidence']:.1%}" if result['mean_confidence'] is not None else '—')
    cols[2].metric('要確認',result['review_count'])
    for message in result['warnings']:st.warning(message)
    if result['review_count']:st.warning('要確認の文字があります。音声と候補を確認してください。')
    st.caption('丸括弧は和文の記号として表示します。手続符号は本文に表示しません。□は未対応符号のため要確認です。前置きが残る場合があります。')
    a,b=st.columns(2)
    a.download_button('認識文を保存',result['text'],file_name='morse_transcript.txt',mime='text/plain')
    b.download_button('詳細JSONを保存',result_json(result),file_name='morse_result.json',mime='application/json')
    with st.expander('ルール方式との比較'):
        st.text(result['rule_text'])
        st.caption('参考用の別方式です。CNN出力をこの文字列で置き換えてはいません。')
    st.subheader('文字ごとの確認')
    only_review=st.checkbox('要確認の区間だけ表示')
    rows=[r for r in result['segments'] if not only_review or r['needs_review']]
    st.dataframe([{'番号':r['index']+1,'開始（秒）':round(r['start_seconds'],3),'終了（秒）':round(r['end_seconds'],3),
                   '文字':r.get('prosign',r['text_prediction']),'予測確率':round(r['confidence'],4),
                   '状態':'⚠ 要確認' if r['needs_review'] else ('手続符号' if r['kind']=='prosign' else '—')} for r in rows],hide_index=True)
    if rows:
        selection=st.selectbox('詳細を見る区間',range(len(rows)),format_func=lambda i:f"{rows[i]['index']+1}: {rows[i].get('prosign',rows[i]['text_prediction'])}（{rows[i]['start_seconds']:.2f}秒）")
        row=rows[selection]
        left,right=st.columns(2)
        with left:
            st.write('候補')
            st.dataframe([{'順位':c['rank'],'文字':c['display_label'],'元の和文ラベル':c['label'],'予測確率':c['probability']} for c in row['display_candidates']],hide_index=True)
            if 'audio' in row:st.audio(wav_bytes(row['audio'],result['sample_rate']),format='audio/wav')
            if row['error']:st.error(row['error'])
            if row.get('review_reason'):st.warning(row['review_reason'])
            st.caption(f"モード: {row['mode']} / 符号: {row['pattern']}")
        with right:
            if 'mel' in row:
                os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'.cache/matplotlib'))
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                import librosa.display
                fig,ax=plt.subplots(figsize=(7,3),layout='constrained')
                mesh=librosa.display.specshow(row['mel'],sr=result['sample_rate'],hop_length=128,x_axis='time',y_axis='mel',ax=ax)
                ax.set_title('Mel spectrogram (display only)');fig.colorbar(mesh,ax=ax,format='%+2.0f dB')
                st.pyplot(fig);plt.close(fig)
