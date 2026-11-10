"""Copied to distribution root as tools_v4.py; uses only its bundled app/runtime."""
from pathlib import Path
import argparse,json,os,socket,sys,time
ROOT=Path(__file__).resolve().parent;APP=ROOT/'app'
sys.path.insert(0,str(APP));sys.path.insert(0,str(APP/'phase8_quality'))

def selftest():
    import hashlib
    package=json.loads((ROOT/'release_v4_manifest.json').read_text(encoding='utf-8'))
    for rel,expected in package['files'].items():
        p=ROOT/rel
        with p.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
        if actual!=expected:raise ValueError('同梱ファイルが変更されています：'+rel)
    import evaluate_new as runner
    runner.verify_frozen()
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(APP/'experiment_app.py'),default_timeout=90).run();assert not app.exception
    app.button[0].click().run();assert not app.exception;assert app.dataframe[0].value.iloc[1]['認識本文']=='スセソ'
    view=AppTest.from_file(str(APP/'evaluation_app.py'),default_timeout=60).run();assert not view.exception
    from batch_preflight import inspect
    report=inspect(ROOT/'examples/audio_manifest.json',ROOT/'evaluation_results/selftest_unused')
    assert len(report['recordings'])==1
    # Resource shortage is a valid environment finding; no inference batch starts.
    assert not any('件目' in e or '一覧' in e for e in report['errors']),report
    print('PASS: v4 file hashes, frozen M1-M4, experiment inference, comparison screen, example manifest',flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['check','experiment','batch']);parser.add_argument('--port',type=int)
    args,rest=parser.parse_known_args()
    if args.mode=='check':selftest();return 0
    if args.mode=='experiment':
        port=None
        for candidate in ([args.port] if args.port else range(8504,8515)):
            with socket.socket() as s:
                try:s.bind(('127.0.0.1',candidate));port=candidate;break
                except OSError:pass
        if port is None:raise RuntimeError('起動用ポートが使用中です。既存アプリを終了してください。')
        print(f'実験画面：http://127.0.0.1:{port}/',flush=True)
        from streamlit.web import cli
        sys.argv=['streamlit','run',str(APP/'experiment_app.py'),'--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true']
        return cli.main()
    from checked_batch import main as batch_main
    if rest:return batch_main(rest)
    print('1: 同梱サンプルを評価  2: 自分の音声を評価  3: 再開  4: 実行前チェックだけ')
    choice=input('番号：').strip()
    if choice=='1':
        out=ROOT/'evaluation_results'/('audio_demo_'+time.strftime('%Y%m%d_%H%M%S'))
        return batch_main(['--manifest',str(ROOT/'examples/audio_manifest.json'),'--output',str(out),'--report',str(out.parent/(out.name+'_preflight.json'))])
    if choice=='3':return batch_main(['--resume','--output',input('結果フォルダー：').strip().strip('"')])
    if choice in ('2','4'):
        manifest=input('録音一覧JSON：').strip().strip('"');out=input('新しい結果フォルダー：').strip().strip('"')
        return batch_main(['--manifest',manifest,'--output',out]+(['--check-only'] if choice=='4' else []))
    print('終了しました。');return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,AssertionError) as exc:print('確認が必要です：'+str(exc),file=sys.stderr);raise SystemExit(2)
