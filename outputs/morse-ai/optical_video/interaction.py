"""Validated UI coordinates and review anchors, independent from decoding."""
import math

def valid_roi(value,width,height):
    if not isinstance(value,(list,tuple)) or len(value)!=4:return None
    if any(type(v) is not int for v in value):return None
    x,y,w,h=value
    return value if 0<=x<x+w<=width and 0<=y<y+h<=height else None

def review_points(result):
    points=[]
    for field,label,time_key in [('exposure_changes','明暗の基準変化','time_seconds'),('exposure_suspicions','明暗変化の疑い','time_seconds'),('diagnostics','信号見落としの疑い','start_seconds'),('characters','文字の要確認','start_seconds')]:
        for row in result.get(field,[]):
            if field=='characters' and not row.get('review_reason'):continue
            t=row.get(time_key)
            if isinstance(t,(int,float)) and math.isfinite(t) and t>=0:points.append((float(t),label+' '+row.get('review_reason','')))
    return sorted(set(points))
