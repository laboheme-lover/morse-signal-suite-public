"""Session-scoped process lifecycle; cancelled results are never adopted."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def start_job(request, key):
    folder = Path(tempfile.mkdtemp(prefix='optical_recognition_'))
    (folder/'request.json').write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
    with (folder/'worker.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('recognition_job.py')), str(folder)],
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return {'process': process, 'folder': folder, 'key': key}


def stop_job(job):
    process = job['process']
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return None


def show_controls():
    import streamlit as st

    @st.fragment(run_every=1 if st.session_state.get('ml_job') else None)
    def panel():
        job = st.session_state.get('ml_job')
        if not job:
            if st.session_state.get('ml_job_notice'):
                st.info(st.session_state['ml_job_notice'])
            return
        st.info('認識処理中です。中断すると今回の途中結果を破棄します。')
        if st.button('認識を中断', type='primary', key='ml_cancel_job'):
            stop_job(job)
            st.session_state.pop('ml_job', None)
            st.session_state['ml_job_notice'] = '認識を中断しました。設定を確認して再実行できます。中断位置からの再開ではなく、最初から解析します。'
            st.rerun()
        if job['process'].poll() is None:
            progress = read_json(job['folder']/'progress.json') or {'fraction': 0., 'stage': '処理を準備しています'}
            st.progress(progress['fraction'], text=progress['stage'])
            st.caption('進捗バーは工程の目安です。アプリの画面を閉じるだけでは解析は止まりません。')
        else:
            result = read_json(job['folder']/'result.json')
            error = read_json(job['folder']/'error.json')
            if job['process'].returncode == 0 and result is not None:
                st.session_state['ml_result'] = {'key': job['key'], 'result': result}
                st.session_state['ml_job_notice'] = '認識が完了しました。設定を変更していた場合は、実行時の設定に戻して結果を確認してください。'
            else:
                st.session_state['ml_job_notice'] = '認識できませんでした：' + (error['message'] if error else f"処理が終了しました（コード {job['process'].returncode}）。")
            st.session_state.pop('ml_job', None)
            st.rerun()
    panel()
