"""Reproducible synthetic load test; child-process Windows peak working set."""
from pathlib import Path
import ctypes,json,subprocess,sys,time
import cv2
import numpy as np
from optical_video.jobs import VideoJob

OUT=Path(__file__).parent/'load_evaluation'

def memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('peak','working','qpp','qp','qnp','qn','page','peakpage')]
    c=Counters();c.cb=ctypes.sizeof(c)
    kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=ctypes.c_void_p
    psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):raise ctypes.WinError()
    return dict(working_mib=c.working/1024**2,peak_mib=c.peak/1024**2)

def worker(name,cancel):
    path=OUT/(name+'.mp4');baseline=memory();begin=time.perf_counter()
    job=VideoJob('load',path.read_bytes(),'.mp4',path.name,(60,40,40,40),0,None,dict(dot_seconds=.3),True)
    requested=None
    while not job.done.wait(.01):
        if cancel and job.snapshot()['progress']>=.035 and requested is None:
            requested=time.perf_counter();job.cancel()
    finished=time.perf_counter();s=job.snapshot()
    result=dict(case=name,cancel=cancel,file_mib=path.stat().st_size/1024**2,elapsed_seconds=finished-begin,
        baseline=baseline,memory=memory(),state=s['state'],error=s['error'],temporary_cleaned=not Path(job.temp_path).exists(),
        cancellation_seconds=None if requested is None else finished-requested)
    if not cancel:
        assert s['state']=='complete',s
        result['methods']=[dict(method=r['method'],text_length=len(r['analysis']['text']),only_i=set(r['analysis']['text'])=={'イ'},seconds=r['analysis_seconds']) for r in s['result']['records']]
        result['decode_seconds']=s['result']['shared']['decode_seconds']
        assert all(r['only_i'] for r in result['methods'])
    else:assert s['state']=='cancelled' and s['result'] is None and requested is not None
    assert result['temporary_cleaned']
    print(json.dumps(result))

def main():
    OUT.mkdir(exist_ok=True);cases=[('1080p30_60s',1920,1080,30,60),('1080p60_60s',1920,1080,60,60),('360p30_600s',640,360,30,600)]
    rows=[]
    for name,w,h,fps,duration in cases:
        path=OUT/(name+'.mp4')
        if not path.exists():
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h));assert writer.isOpened()
            dark=np.full((h,w,3),30,np.uint8);light=dark.copy();light[40:80,60:100]=220
            # Complete .- characters every 8 dot units, with initial/trailing silence.
            dot=round(.3*fps);cycles=(duration*fps-6*dot)//(8*dot)
            try:
                for i in range(duration*fps):
                    k=i-3*dot;phase=k%(8*dot)
                    on=0<=k<cycles*8*dot and (phase<dot or 2*dot<=phase<5*dot)
                    writer.write(light if on else dark)
            finally:writer.release()
        print('Generated '+name,flush=True)
        for cancel in ([False,True] if name=='1080p60_60s' else [False]):
            p=subprocess.run([sys.executable,'-B','-X','utf8','-m','optical_video.benchmark_load','--worker',name,str(int(cancel))],capture_output=True,text=True,encoding='utf-8',check=True)
            row=json.loads(p.stdout);row.update(width=w,height=h,fps=fps,duration_seconds=duration);rows.append(row);print(json.dumps(row),flush=True)
            (OUT/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    if '--worker' in sys.argv:worker(sys.argv[2],bool(int(sys.argv[3])))
    else:main()
