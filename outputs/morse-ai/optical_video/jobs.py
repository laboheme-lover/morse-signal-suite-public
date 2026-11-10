"""Session-owned background jobs; workers never call Streamlit."""
from pathlib import Path
import hashlib,io,json,tempfile,threading,time,zipfile,uuid
from optical_video.core import read_trace,analyze_trace,csv_text

UI_VERSION='optical-jobs-v1'
METHODS={'fixed':'固定','adaptive':'適応','change_aware':'変化点対応'}

class Cancelled(Exception):pass

class VideoJob:
    def __init__(self,key,data,suffix,input_name,roi,start,end,options,compare=False):
        self.key=key;self.token=uuid.uuid4().hex;self.cancel_event=threading.Event();self.done=threading.Event();self.lock=threading.Lock()
        self.state='running';self.progress=0.;self.stage='準備中';self.result=None;self.error='';self.temp_path=None
        self.thread=threading.Thread(target=self._run,args=(data,suffix,input_name,roi,start,end,options.copy(),compare),daemon=True)
        self.thread.start()
    def cancel(self):
        with self.lock:
            if self.state=='running':self.cancel_event.set();self.stage='中止処理中'
    def check(self):
        if self.cancel_event.is_set():raise Cancelled()
    def update(self,value,stage):
        self.check()
        with self.lock:self.progress=max(self.progress,min(.99,value));self.stage=stage
    def snapshot(self):
        with self.lock:return dict(state=self.state,progress=self.progress,stage=self.stage,result=self.result,error=self.error)
    def _run(self,data,suffix,input_name,roi,start,end,options,compare):
        result=None;error='';state='failed'
        try:
            with tempfile.TemporaryDirectory(prefix='morse_video_job_') as directory:
                self.temp_path=directory;path=Path(directory)/('input'+suffix);self.check();path.write_bytes(data)
                started=time.perf_counter()
                info,t,b=read_trace(path,roi,start,end,progress=lambda p:self.update(.7*p,'動画を読み取り中'),check_cancel=self.check)
                decode_seconds=time.perf_counter()-started;self.check()
                methods=list(METHODS) if compare else [options.pop('threshold_method','fixed')]
                options.pop('threshold_method',None)
                if compare and options.get('thresholds') is not None:raise ValueError('一括比較では手動しきい値を解除してください。')
                records=[];shared=dict(input_name=input_name,input_sha256=hashlib.sha256(data).hexdigest(),video=info,roi=list(roi),range_seconds=[start,end],options=options,decode_seconds=decode_seconds)
                for i,method in enumerate(methods):
                    self.update(.7+.29*i/len(methods),METHODS[method]+'方式を解析中');begin=time.perf_counter()
                    analysis=None;failure=''
                    try:analysis=analyze_trace(t,b,info['fps'],threshold_method=method,**options)
                    except ValueError as exc:failure=str(exc)
                    self.check()
                    if analysis:analysis.update(shared,schema='optical-video-v5',method='光信号のルール解析',options=dict(options,threshold_method=method))
                    records.append(dict(method=method,analysis=analysis,error=failure,analysis_seconds=time.perf_counter()-begin))
                result=dict(schema='optical-comparison-v1',compare=compare,shared=shared,records=records,
                            all_successful=all(r['analysis'] is not None for r in records),completed=True)
                self.check()
            state='complete'
        except Cancelled:state='cancelled'
        except Exception as exc:error=str(exc);state='failed'
        finally:
            # Publish only after temporary file cleanup. Cancellation wins publication races.
            with self.lock:
                if self.cancel_event.is_set():state='cancelled';result=None
                self.state=state;self.result=result if state=='complete' else None;self.error=error
                self.progress=1. if state=='complete' else self.progress;self.stage={'complete':'完了','cancelled':'中止しました','failed':'処理できませんでした'}[state]
            self.done.set()

def summary_rows(bundle):
    rows=[]
    for record in bundle['records']:
        r=record['analysis']
        rows.append({'方式':METHODS[record['method']],'状態':r['status'] if r else 'FAILED','本文':r['text'] if r else '',
            '文字数':len(r['text']) if r else 0,'警告数':len(r['warnings']) if r else 0,'解析秒':round(record['analysis_seconds'],3),'エラー':record['error']})
    return rows

def comparison_zip(bundle):
    if not bundle.get('completed'):raise ValueError('Incomplete comparison cannot be exported')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('comparison.json',json.dumps(bundle,ensure_ascii=False,indent=2))
        archive.writestr('summary.csv',csv_text(summary_rows(bundle)).encode('utf-8-sig'))
        for record in bundle['records']:
            if record['analysis']:
                archive.writestr(record['method']+'/text.txt',record['analysis']['text'])
                archive.writestr(record['method']+'/characters.csv',csv_text(record['analysis']['characters']).encode('utf-8-sig'))
            else:archive.writestr(record['method']+'/error.txt',record['error'])
    return stream.getvalue()
