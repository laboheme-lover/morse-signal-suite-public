"""Pause-based candidate splitting; never certifies recognition or fills missing frames."""
import numpy as np
from splitter import SplitError, runs


def detect_candidates(times, values, cases, unit, minimum_contrast=20):
    t = np.asarray(times, dtype=float)
    v = np.asarray(values, dtype=float)
    if len(t) < 3 or len(t) != len(v) or not np.isfinite(t).all() or not np.isfinite(v).all():
        raise SplitError('時刻・輝度データが不正です。')
    delta = np.diff(t)
    if np.any(delta <= 0):
        raise SplitError('時刻が逆転または重複しています。候補分割も実施できません。')
    dt = float(np.median(delta))
    low, high = np.percentile(v, [1, 99])
    for _ in range(20):
        threshold = (low + high) / 2
        off, on = v[v <= threshold], v[v > threshold]
        if min(len(off), len(on)) < 2:
            raise SplitError('点灯と消灯を区別できません。')
        lo, hi = float(np.median(off)), float(np.median(on))
        if abs(lo-low) + abs(hi-high) < .001:
            break
        low, high = lo, hi
    contrast = float(high-low)
    noise = max(1., float(np.median(abs(off-low))*1.4826), float(np.median(abs(on-high))*1.4826))
    if contrast < minimum_contrast or contrast/noise < 4:
        raise SplitError(f'明るさの差が不足しています（差 {contrast:.1f}）。光源範囲を確認してください。')
    threshold = float((low+high)/2)
    rs = runs(v > threshold, t, dt)
    # A long timestamp hole is not evidence of continuous darkness. A separator
    # requires actual dark observations no more than 120 ms apart (300 ms unit).
    gaps = []
    separators = []
    for r in rs:
        if r['on'] or r['end']-r['start'] < 8:
            continue
        overlaps = (t[:-1] < r['end']) & (t[1:] > r['start'])
        maximum = float(delta[overlaps].max()) if overlaps.any() else 0.
        observed = maximum <= unit*.4
        record = dict(r, duration_seconds=r['end']-r['start'],
                      max_frame_interval=maximum, usable_boundary=observed,
                      approx_10_seconds=8 <= r['end']-r['start'] <= 12)
        gaps.append(record)
        if observed:
            separators.append(r)
    intervals = []
    start = float(t[0])
    for r in separators:
        intervals.append((start, r['start']))
        start = r['end']
    intervals.append((start, float(t[-1]+dt)))
    anomalies = [dict(start_seconds=float(t[i]), end_seconds=float(t[i+1]),
                      duration_seconds=float(delta[i])) for i in np.flatnonzero(delta > unit*.4)]
    clips = []
    for a, b in intervals:
        lit = np.flatnonzero((t >= a) & (t < b) & (v > threshold))
        if not len(lit):
            continue
        begin, end = float(t[lit[0]]), float(t[min(lit[-1]+1, len(t)-1)])
        affected = [g for g in anomalies if g['start_seconds'] < end and g['end_seconds'] > begin]
        issues = []
        if affected:
            issues.append(f'フレーム間隔超過 {len(affected)}か所。点滅精度は未確認')
        if begin-t[0] < 1 or t[-1]-end < 1:
            issues.append('録画端の余白不足／途中で切れた可能性')
        clips.append(dict(id=f'candidate_{len(clips)+1:03}', signal_start=begin,
                          signal_end=end, start=max(float(t[0]), begin-.5),
                          end=min(float(t[-1]+dt), end+.5), labels=None,
                          issues=issues, timing_anomaly_count=len(affected)))
    if not clips:
        raise SplitError('点灯区間がありません。')
    warnings = ['候補分割です。原稿との対応・点滅数・点滅時間・認識精度は保証しません。']
    if len(clips) != len(cases):
        warnings.append(f'検出 {len(clips)}区間／予定 {len(cases)}件。原稿番号を自動割当しません。')
    else:
        warnings.append('件数は予定と一致しますが、原稿番号は目視確認が必要です。')
    for gap in gaps:
        if not gap['usable_boundary']:
            warnings.append(f"{gap['start']:.2f}秒付近の消灯は時刻欠落を含むため区切りに使いません。")
    return dict(clips=clips, contrast=contrast, noise_ratio=contrast/noise,
                threshold=threshold, frame_interval_max=float(delta.max()),
                quality='REVIEW', mode='pause_candidates', warnings=warnings,
                pauses=gaps, timing_anomalies=anomalies, expected_count=len(cases),
                expected_ids=[c['id'] for c in cases],
                note='Unverified pause-based candidates; no reference text assigned; no missing frames interpolated')
