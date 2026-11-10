"""Isolated, cancellable recognition worker. No Streamlit calls here."""
import json
import sys
import os,shutil,threading
from pathlib import Path


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def run(folder):
    try:
        import torch
        from production import VERSION, CHECKPOINT, verify_release, recognize
        from predict import classify_features
        from flexible_roi import extract_flexible
        verify_release()
        if os.environ.get('MORSE_CLOUD')=='1':
            import splitter
            splitter.FFMPEG=Path(shutil.which('ffmpeg') or 'ffmpeg')
            torch.set_num_threads(1)
            # A disconnected browser must not leave an unbounded cloud job running.
            watchdog=threading.Timer(900,lambda:os._exit(124))
            watchdog.daemon=True;watchdog.start()
        request = json.loads((folder/'request.json').read_text(encoding='utf-8'))
        save(folder/'progress.json', {'fraction': 0., 'stage': 'モデルを読み込んでいます'})
        checkpoint = torch.load(CHECKPOINT, map_location='cpu', weights_only=False)
        def progress(value):
            save(folder/'progress.json', {'fraction': float(value)*.85, 'stage': '動画を読み取っています'})
        times, features, meta = extract_flexible(request['path'], request['roi'], progress)
        save(folder/'progress.json', {'fraction': .85, 'stage': '文字を判定しています'})
        result = (classify_features(times, features, checkpoint, request['unit']/1000, True)
                  if request['isolated'] else recognize(times, features, checkpoint))
        result.update(version=VERSION, recognition_mode=request['mode'],
                      source=str(Path(request['path']).resolve()), roi=request['roi'], preprocessing=meta,
                      warning='認識結果は要確認です。可変ROI・実天候での精度は未確認。候補スコアは正解率ではありません。')
        save(folder/'result.json', result)
    except Exception as exc:
        save(folder/'error.json', {'message': str(exc)})
        raise


if __name__ == '__main__':
    run(Path(sys.argv[1]))
