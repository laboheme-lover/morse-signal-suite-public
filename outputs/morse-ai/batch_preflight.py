"""Japanese preflight checks for the optional low-memory recording batch."""
from pathlib import Path
import ctypes,json,math,re,shutil,sys,tempfile
import soundfile as sf
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'phase8_quality'))
from policy import normalize_reference
GIB=1024**3;MIB=1024**2

def available_memory():
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ['total','available','total_page','available_page','total_virtual','available_virtual','extended']]
    status=Status();status.length=ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):raise ctypes.WinError()
    return status.available

def estimate(durations):
    # Conservative start thresholds calibrated from recorded process peaks,
    # not claims of guaranteed upper bounds or measurements on the user's PC.
    return dict(memory_bytes=int(.75*GIB+max(durations,default=0)*2.5*MIB),
                disk_bytes=int(256*MIB+sum(durations)*128*1024))

def inspect(source,out,resume=False,resources=None,probe=True):
    source=Path(source);out=Path(out).resolve();errors=[];entries=[];durations=[];ids=set();audio_paths=set()
    try:
        if resume:
            if not out.is_dir():raise ValueError('再開する結果フォルダーがありません。')
            data=json.loads((out/'manifest.json').read_text(encoding='utf-8-sig'));base=out
        else:
            if out.exists():raise ValueError('新規評価の出力先は、まだ存在しないフォルダーにしてください。')
            data=json.loads(source.read_text(encoding='utf-8-sig'));base=source.resolve().parent
        rows=data['recordings']
        if not isinstance(rows,list) or not rows:raise ValueError('録音一覧が空、または配列ではありません。')
        for index,row in enumerate(rows,1):
            try:
                ident=row['id']
                if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident) or ident in ids:raise ValueError('IDは重複しない半角英数字・ハイフン・下線の1〜80文字にしてください。')
                ids.add(ident);audio=(base/row['audio']).resolve();ref=(base/row['reference_path' if resume else 'reference']).resolve()
                if audio in audio_paths:raise ValueError('同じ音声パスが複数指定されています。')
                audio_paths.add(audio)
                if not audio.is_file():raise ValueError('音声ファイルが見つかりません。')
                if audio.suffix.lower() not in ('.wav','.mp3','.flac'):raise ValueError('音声形式はWAV／MP3／FLACにしてください。')
                if audio.stat().st_size>512*MIB:raise ValueError('音声容量が512 MiBを超えています。')
                info=sf.info(audio);duration=info.frames/info.samplerate
                if not .5<=duration<=1800:raise ValueError('音声の長さは0.5秒〜30分にしてください。')
                if not ref.is_file():raise ValueError('正解文ファイルが見つかりません。')
                if not normalize_reference(ref.read_text(encoding='utf-8-sig')):raise ValueError('正規化後の正解文が空です。')
                body=row['body']
                if not isinstance(body,dict):raise ValueError('本文範囲はmodeを含むオブジェクトで指定してください。')
                mode=body.get('mode')
                if mode not in ('full','window','protocol'):raise ValueError('本文範囲はfull／window／protocolから指定してください。')
                if mode=='window':
                    a,b=body.get('start_seconds'),body.get('end_seconds')
                    if not all(type(v) in (float,int) and math.isfinite(v) for v in (a,b)) or not 0<=a<b<=duration:raise ValueError('本文の開始・終了時刻が音声の範囲外、または不正です。')
                completed=resume and (out/ident/'result.json').is_file()
                entries.append(dict(id=ident,duration_seconds=duration,bytes=audio.stat().st_size,completed=completed))
                if not completed:durations.append(duration)
            except (KeyError,ValueError,TypeError,OSError,RuntimeError,UnicodeError) as exc:errors.append(f'{index}件目：{exc}')
    except (KeyError,ValueError,TypeError,OSError,UnicodeError) as exc:errors.append('一覧の確認：'+str(exc))
    parent=out if out.exists() else out.parent
    while not parent.exists() and parent!=parent.parent:parent=parent.parent
    try:
        if not parent.is_dir():raise ValueError('保存先の親パスがフォルダーではありません。')
        if probe:
            with tempfile.TemporaryFile(dir=parent):pass
        resources=resources if resources is not None else dict(available_memory_bytes=available_memory(),free_disk_bytes=shutil.disk_usage(parent).free)
    except (OSError,ValueError) as exc:errors.append('保存先・環境の確認：'+str(exc));resources={}
    need=estimate(durations)
    if resources.get('available_memory_bytes',0)<need['memory_bytes']:errors.append('空きメモリが開始判定の目安に足りません。他のアプリを閉じるか、短い録音に分けて再確認してください。')
    if resources.get('free_disk_bytes',0)<need['disk_bytes']:errors.append('保存先の空き容量が開始判定の目安に足りません。容量を確保するか、別の保存先を指定してください。')
    return dict(status='READY' if not errors else 'BLOCKED',errors=errors,recordings=entries,resources=resources,estimated_start_requirements=need,
        estimation_note='保守的な開始判定の目安です。最大使用量や完走を保証する値ではありません。ファイル全体の復号と推論は実行時に検証します。')

def display(report):
    print('実行前チェック：'+('実行可能' if report['status']=='READY' else '実行を停止'))
    for message in report['errors']:print('・'+message)
    for name,key in [('空きメモリ','available_memory_bytes'),('保存先の空き容量','free_disk_bytes')]:print(f"{name}：{report['resources'].get(key,0)/GIB:.2f} GiB")
    print(f"開始判定の目安：メモリ{report['estimated_start_requirements']['memory_bytes']/GIB:.2f} GiB／保存容量{report['estimated_start_requirements']['disk_bytes']/GIB:.2f} GiB")
    print(report['estimation_note'])
