"""Synthetic central flashing light, independent fixed Wabun codes: KA + dakuten + RA."""
from pathlib import Path
import cv2,numpy as np
r=Path(__file__).resolve().parents[1]/'test-data'
states=[(False,7)]
for code in ['.-..','..','...']:
    for i,c in enumerate(code):
        states.append((True,1 if c=='.' else 3))
        states.append((False,1 if i<len(code)-1 else 3))
states.append((False,7))
for fps in [30,15]:
    p=r/f'light_{fps}fps.mp4';writer=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'mp4v'),fps,(160,120))
    assert writer.isOpened()
    try:
        for on,units in states:
            frame=np.full((120,160,3),16,np.uint8)
            if on:frame[40:80,60:100]=235
            for _ in range(round(units*.6*fps)):writer.write(frame)
    finally:writer.release()
    assert p.stat().st_size>1000
    capture=cv2.VideoCapture(str(p));rows=[];index=0
    while True:
        success,frame=capture.read()
        if not success:break
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2YUV)[:,:,0]
        rows.append(f'{index/fps:.9f}\t{gray[48:72:2,68:92:2].mean():.6f}')
        index+=1
    capture.release()
    p.with_suffix('.tsv').write_text('\n'.join(rows),encoding='utf-8')
print('Created two MP4 fixtures: がら, dot 600 ms, 30 / 15 fps')
