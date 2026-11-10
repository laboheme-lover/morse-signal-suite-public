"""Opt-in low-memory recording comparison; original batch command retained."""
from pathlib import Path
import argparse, json, re, sys
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'phase8_quality'))
from low_memory_recording_experiment import read,save,run
from intake import digest
from policy import normalize_reference
from adaptive_pipeline import METHODS
import soundfile as sf

def prepare(source,out):
    if out.exists():raise FileExistsError('出力先は新しいフォルダーを指定してください。')
    manifest=read(source);entries=[];seen=set()
    for row in manifest['recordings']:
        ident=row['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident) or ident in seen:raise ValueError('IDは重複のない半角英数字・_-にしてください。')
        seen.add(ident);audio=(source.parent/row['audio']).resolve();ref=(source.parent/row['reference']).resolve()
        info=sf.info(audio);duration=info.frames/info.samplerate
        if not .5<=duration<=1800:raise ValueError('録音は0.5〜1800秒にしてください。')
        if audio.stat().st_size>512*1024**2:raise ValueError('音声は512 MiB以下にしてください。')
        text=normalize_reference(ref.read_text(encoding='utf-8-sig'))
        if not text:raise ValueError('空の正解文は評価できません。')
        body=row['body']
        if body.get('mode') not in ('full','protocol','window'):raise ValueError('本文範囲はfull/protocol/windowから明示してください。')
        if body['mode']=='window' and not 0<=body['start_seconds']<body['end_seconds']<=duration:raise ValueError('本文範囲が不正です。')
        entries.append(dict(id=ident,audio=str(audio),audio_sha256=digest(audio),reference_path=str(ref),reference_sha256=digest(ref),reference=text,
            duration_seconds=duration,body=body,historical_body_source=str(source.resolve()),historical_body_sha256=digest(source)))
    if not entries:raise ValueError('録音一覧が空です。')
    paths=[ROOT/'phase8_quality'/x for x in ['low_memory_recording_experiment.py','low_memory_frontend.py','adaptive_pipeline.py','timing_frontend.py','experimental_frontend.py','policy.py','guarded_pipeline.py','analyze_recording_experiment.py']]+[Path(__file__)]
    save(out/'manifest.json',dict(scope='USER_RECORDING_DIAGNOSTIC_NOT_INDEPENDENT_ACCEPTANCE',models=['M1','M2','M3','M4'],methods=METHODS,
        scripts={str(p.relative_to(ROOT)):digest(p) for p in paths},recordings=entries))

def execute(out,limit=None):
    # OS releases this lock even on interrupted runs; completed files are atomic.
    import msvcrt
    lockpath=out/'execution.lock'
    with lockpath.open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('この出力先の評価がすでに実行中です。')
        try:
            h=digest(out/'manifest.json');fixed=out/'manifest_lock.json'
            if fixed.exists():
                if read(fixed)['sha256']!=h:raise ValueError('マニフェストが開始後に変更されています。新しい出力先を使ってください。')
            else:save(fixed,dict(sha256=h))
            run(out,limit)
            if len(list(out.glob('*/result.json')))==len(read(out/'manifest.json')['recordings']):
                from analyze_recording_experiment import finalize
                finalize(out)
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--manifest',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--resume',action='store_true');ap.add_argument('--limit',type=int)
    a=ap.parse_args()
    if not a.resume:
        if a.manifest is None:ap.error('--manifest is required unless --resume')
        prepare(a.manifest,a.output)
    execute(a.output,a.limit)
