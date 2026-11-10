"""Pinned production selection; verify inference files against evaluated copies."""
from pathlib import Path
import hashlib

VERSION = 'optical-cnn-adaptive-v2-20261013'
HERE = Path(__file__).resolve().parent
RELEASE = HERE / 'releases' / VERSION
CHECKPOINT = RELEASE / 'cnn.pt'

def verify_release():
    files = {name: HERE / name for name in
             ('adaptive_timing_v2.py', 'predict.py', 'dataset.py', 'model.py', 'extract.py')}
    files['splitter.py'] = HERE.parent / 'optical-batch-test/pc/splitter.py'
    for name, live in files.items():
        if hashlib.sha256(live.read_bytes()).digest() != hashlib.sha256((RELEASE/name).read_bytes()).digest():
            raise RuntimeError(f'採用版と処理が異なります。再確認が必要です: {name}')
    expected = (RELEASE/'cnn.sha256').read_text().strip()
    if hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest() != expected:
        raise RuntimeError('採用モデルの整合性確認に失敗しました。')

def recognize(times, features, checkpoint):
    from adaptive_timing_v2 import classify_adaptive
    result = classify_adaptive(times, features, checkpoint, normalize_input=True)
    result.update(version=VERSION, status='REVIEW_REQUIRED',
                  warning='採用版の結果です。候補スコアは正解率ではありません。実天候・可変ROIでの性能は未確認です。')
    return result
