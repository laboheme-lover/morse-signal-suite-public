from pathlib import Path
import json
import cv2
import numpy as np
from optical_video.core import LATIN
from morse_table import MORSE_TABLE

def generate(path,patterns,fps=30,dot_frames=9,noise=0,invert=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    events=[];states=[False]*dot_frames*3
    for p in patterns:
        for j,symbol in enumerate(p):
            a=len(states);states.extend([True]*(dot_frames*(1 if symbol=='.' else 3)))
            events.append(dict(start_seconds=a/fps,end_seconds=len(states)/fps,symbol=symbol))
            states.extend([False]*(dot_frames if j<len(p)-1 else dot_frames*3))
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*('mp4v' if path.suffix=='.mp4' else 'MJPG')),fps,(160,120))
    if not writer.isOpened():raise RuntimeError('Synthetic video encoder unavailable')
    rng=np.random.default_rng(12345)
    try:
        for on in states:
            frame=np.full((120,160,3),35,dtype=np.float32)
            frame[40:80,60:100]=220 if (on!=invert) else 30
            if noise:frame+=rng.normal(0,noise,frame.shape)
            writer.write(np.clip(frame,0,255).astype(np.uint8))
    finally:writer.release()
    truth=dict(patterns=patterns,events=events,fps=fps,dot_seconds=dot_frames/fps,roi=[60,40,40,40],synthetic=True,noise_std=noise,invert=invert)
    path.with_suffix('.json').write_text(json.dumps(truth,indent=2),encoding='utf-8')
    return truth

if __name__=='__main__':
    patterns=[MORSE_TABLE['イ'],MORSE_TABLE['（'],LATIN['W'],LATIN['F'],LATIN['P'],MORSE_TABLE['）'],MORSE_TABLE['ロ']]
    generate(Path(__file__).parent/'samples/mixed_30fps.avi',patterns)
