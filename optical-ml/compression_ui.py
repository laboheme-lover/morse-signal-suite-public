"""Desktop-only export panel; encoding runs in a separate cancellable process."""
from pathlib import Path
import streamlit as st
import video_compression as vc

def render(path):
    with st.expander('Web版用に圧縮・保存（解像度を維持）'):
        st.caption('H.264で圧縮します。点滅時刻と解像度を維持し、音声は除外します。元動画は変更しません。')
        directory=st.text_input('圧縮動画の保存先フォルダ',value=str(Path(path).parent),key='compression_directory')
        if st.button('圧縮して保存',disabled=bool(st.session_state.get('compression_job')) or bool(st.session_state.get('ml_job'))):
            try:
                st.session_state.compression_job=vc.start(path,directory)
                st.session_state.pop('compression_result',None);st.session_state.pop('compression_error',None)
                st.rerun()
            except Exception as e:st.error(str(e))

        @st.fragment(run_every=1 if st.session_state.get('compression_job') else None)
        def panel():
            job=st.session_state.get('compression_job')
            if job:
                if st.button('圧縮を中断'):
                    vc.cancel(job);st.session_state.pop('compression_job');st.rerun()
                if job['process'].poll() is None:
                    st.progress(vc.progress(job),text='圧縮中です。完了後にフレーム時刻を確認します。')
                else:
                    try:
                        with st.spinner('解像度・フレーム数・点滅時刻を確認しています…'):
                            st.session_state.compression_result=vc.finish(job)
                    except Exception as e:st.session_state.compression_error=str(e)
                    st.session_state.pop('compression_job');st.rerun()
            result=st.session_state.get('compression_result')
            if result:
                st.success('圧縮動画を保存しました。')
                st.code(result['path'],language=None)
                st.write(f"容量：{result['original_bytes']/1e6:.2f} MB → {result['bytes']/1e6:.2f} MB")
                if result['web_reasons']:st.warning('Web版の条件外：'+'／'.join(result['web_reasons']))
                else:st.success('Web版の容量・時間・解像度・fpsの条件内です。保存したMP4をWeb版で選択してください。')
            if st.session_state.get('compression_error'):st.error(st.session_state.compression_error)
        panel()
