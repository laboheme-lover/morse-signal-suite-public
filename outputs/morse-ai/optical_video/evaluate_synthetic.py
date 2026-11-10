from pathlib import Path
import json,platform,time
import cv2,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from morse_table import MORSE_TABLE
from optical_video.core import analyze_video,csv_text
from optical_video.synthetic import generate

root=Path(__file__).parent;out=root/'evaluation';out.mkdir(exist_ok=False)
results=[]
for name,fps,frames,noise,invert,extension in [('clean30',30,9,0,False,'.avi'),('clean60',60,9,0,False,'.avi'),('noise30',30,9,20,False,'.avi'),('inverse_mp4',30,9,8,True,'.mp4'),('low_resolution',30,3,0,False,'.avi')]:
    patterns=[MORSE_TABLE[c] for c in 'イロハニホヘト']
    path=out/(name+extension);truth=generate(path,patterns,fps,frames,noise,invert)
    start=time.perf_counter();r=analyze_video(path,(60,40,40,40),invert=invert);elapsed=time.perf_counter()-start
    assert [c['pattern'] for c in r['characters']]==patterns
    pulses=[e for e in r['events'] if e['on']]
    error=max(abs(a[k]-b[k]) for a,b in zip(pulses,truth['events']) for k in ('start_seconds','end_seconds'))
    assert len(pulses)==len(truth['events']) and error<=1/fps+1e-6
    assert r['text']==('' if frames<5 else 'イロハニホヘト')
    result=dict(case=name,fps=fps,frames_per_dot=frames,noise_std=noise,inverted=invert,text=r['text'],candidate_text=r['candidate_text'],status=r['status'],patterns_exact=True,max_boundary_error_seconds=error,processing_seconds=elapsed,video_seconds=r['video']['duration_seconds'])
    results.append(result)
    (out/(name+'_result.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    if name=='noise30':
        trace=r['trace'];t=[e['time_seconds'] for e in trace]
        fig,ax=plt.subplots(figsize=(12,4));ax.plot(t,[e['signal'] for e in trace],label='ROI brightness')
        ax.axhline(r['threshold_on'],color='orange',linestyle='--',label='ON threshold');ax.axhline(r['threshold_off'],color='green',linestyle='--',label='OFF threshold')
        ax.step(t,[255*int(e['on']) for e in trace],where='post',alpha=.4,label='Detected ON/OFF')
        ax.set(xlim=(0,8),xlabel='Time (seconds)',ylabel='Brightness (0-255)',title='Synthetic optical Morse: noisy video (first 8 seconds)');ax.legend(loc='upper right');fig.tight_layout();fig.savefig(out/'brightness_preview.png',dpi=140);plt.close(fig)
(out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'results.csv').write_bytes(csv_text(results).encode('utf-8-sig'))
(out/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),opencv=cv2.__version__,numpy=np.__version__,platform=platform.platform(),synthetic_only=True),indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
