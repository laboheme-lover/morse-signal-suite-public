"""Experimental offline local-percentile thresholds; no reference-dependent tuning."""
import math
import numpy as np
from scipy.ndimage import percentile_filter

VERSION='optical-video-v3-adaptive'

def local_thresholds(signal,fps,window_seconds,global_off,global_on):
    if not math.isfinite(window_seconds) or not .2<=window_seconds<=30:
        raise ValueError('適応窓は0.2〜30秒にしてください。')
    size=max(3,int(round(window_seconds*fps))|1)
    # Centered windows use future frames: this is an offline-video method, not live inference.
    low=percentile_filter(signal,10,size=size,mode='nearest')
    high=percentile_filter(signal,90,size=size,mode='nearest')
    reliable=(high-low)>=15.
    off=np.where(reliable,low+.35*(high-low),global_off)
    on=np.where(reliable,low+.65*(high-low),global_on)
    return off,on,reliable
