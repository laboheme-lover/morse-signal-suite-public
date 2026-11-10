"""Run/check the existing low-memory batch without modifying frozen runners."""
from pathlib import Path
import argparse,json,sys
from batch_preflight import inspect,display

def main(argv=None):
    ap=argparse.ArgumentParser(description='省メモリ一括評価：実行前チェック付き')
    ap.add_argument('--manifest',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--resume',action='store_true');ap.add_argument('--check-only',action='store_true');ap.add_argument('--report',type=Path);ap.add_argument('--limit',type=int)
    a=ap.parse_args(argv)
    if not a.resume and a.manifest is None:ap.error('新規評価には --manifest が必要です。')
    report=inspect(a.manifest or a.output/'manifest.json',a.output,a.resume);display(report)
    if a.report:
        a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if report['status']!='READY':return 2
    if a.check_only:return 0
    try:
        from batch_recordings_low_memory import prepare,execute
        if not a.resume:prepare(a.manifest,a.output)
        execute(a.output,a.limit)
    except (ValueError,OSError,RuntimeError,AssertionError) as exc:
        print('評価を停止しました：'+str(exc),file=sys.stderr);print('入力・コード・出力先を確認してください。元の結果は削除していません。',file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
