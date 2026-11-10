from pathlib import Path
import io,threading,unittest,zipfile
from unittest.mock import patch
from optical_video.jobs import VideoJob,comparison_zip,summary_rows
from optical_video.core import read_trace,analyze_trace

SAMPLE=Path(__file__).parent/'samples/mixed_30fps.avi'
def job(compare=True,data=None):return VideoJob('test',SAMPLE.read_bytes() if data is None else data,'.avi','sample.avi',(60,40,40,40),0,None,{'threshold_method':'fixed'},compare)
def completed(j):
    if not j.done.wait(20):raise AssertionError('Job timed out')
    if Path(j.temp_path).exists():raise AssertionError('Temporary directory leaked')
    return j.snapshot()

class JobTests(unittest.TestCase):
    def test_shared_decode_matches_individual_and_export(self):
        with patch('optical_video.jobs.read_trace',wraps=read_trace) as reader:
            snapshot=completed(job());self.assertEqual(reader.call_count,1)
        self.assertEqual(snapshot['state'],'complete');bundle=snapshot['result']
        info,t,b=read_trace(SAMPLE,(60,40,40,40))
        for record in bundle['records']:
            expected=analyze_trace(t,b,info['fps'],threshold_method=record['method'])
            self.assertEqual(record['analysis']['text'],expected['text'])
            self.assertEqual(record['analysis']['events'],expected['events'])
        with zipfile.ZipFile(io.BytesIO(comparison_zip(bundle))) as z:
            self.assertIn('comparison.json',z.namelist());self.assertEqual(z.read('fixed/text.txt').decode(),'イWFPロ')
    def test_cancel_decode_cleanup_then_restart(self):
        entered=threading.Event();release=threading.Event()
        def blocked(*args,**kwargs):
            entered.set();release.wait(10);kwargs['check_cancel']();return read_trace(*args,**kwargs)
        with patch('optical_video.jobs.read_trace',side_effect=blocked):
            j=job();self.assertTrue(entered.wait(5));j.cancel();release.set();s=completed(j)
        self.assertEqual(s['state'],'cancelled');self.assertIsNone(s['result'])
        self.assertEqual(completed(job())['state'],'complete')
    def test_cancel_during_method_no_partial_result(self):
        entered=threading.Event();release=threading.Event()
        def blocked(*args,**kwargs):
            result=analyze_trace(*args,**kwargs);entered.set();release.wait(10);return result
        with patch('optical_video.jobs.analyze_trace',side_effect=blocked):
            j=job();self.assertTrue(entered.wait(5));j.cancel();release.set();s=completed(j)
        self.assertEqual(s['state'],'cancelled');self.assertIsNone(s['result'])
    def test_failure_is_retained_and_bad_input_cleans(self):
        def fail_one(*args,**kwargs):
            if kwargs['threshold_method']=='adaptive':raise ValueError('intentional fixture failure')
            return analyze_trace(*args,**kwargs)
        with patch('optical_video.jobs.analyze_trace',side_effect=fail_one):s=completed(job())
        self.assertEqual(len(s['result']['records']),3);self.assertFalse(s['result']['all_successful'])
        self.assertEqual(summary_rows(s['result'])[1]['状態'],'FAILED')
        self.assertEqual(completed(job(data=b'not video'))['state'],'failed')
    def test_read_progress_is_monotone_and_cancellable(self):
        values=[]
        read_trace(SAMPLE,(60,40,40,40),progress=values.append)
        self.assertEqual(values,sorted(values));self.assertEqual(values[-1],1.)
    def test_cancel_mid_decode_releases_video_handle(self):
        import cv2
        from optical_video.jobs import Cancelled
        cap=cv2.VideoCapture(str(SAMPLE));counter=[0]
        def check():
            counter[0]+=1
            if counter[0]>=20:raise Cancelled()
        with patch('optical_video.core.cv2.VideoCapture',return_value=cap):
            with self.assertRaises(Cancelled):read_trace(SAMPLE,(60,40,40,40),check_cancel=check)
        self.assertFalse(cap.isOpened())
    def test_settings_change_cancels_and_hides_stale_output(self):
        from streamlit.testing.v1 import AppTest
        from optical_video.testing import finish_ui_job
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'video_app.py'),default_timeout=30).run()
        app.checkbox[0].check().run()
        entered=threading.Event();release=threading.Event()
        def blocked(*args,**kwargs):entered.set();release.wait(10);kwargs['check_cancel']();return read_trace(*args,**kwargs)
        with patch('optical_video.jobs.read_trace',side_effect=blocked):
            app.button[0].click().run();self.assertTrue(entered.wait(5))
            app.number_input[0].set_value(1).run();release.set();finish_ui_job(app)
        self.assertFalse(app.exception);self.assertEqual(len(app.text_area),0)
        self.assertEqual(app.session_state['optical_job'].snapshot()['state'],'cancelled')
    def test_ui_comparison_and_cancel(self):
        from streamlit.testing.v1 import AppTest
        from optical_video.testing import finish_ui_job
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'video_app.py'),default_timeout=30).run()
        app.checkbox[0].check().run()
        next(c for c in app.checkbox if c.label=='3方式を一括比較する').check().run()
        app.button[0].click().run();finish_ui_job(app);self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value),3);self.assertEqual(app.text_area[0].value,'イWFPロ')
        entered=threading.Event();release=threading.Event()
        def blocked(*args,**kwargs):entered.set();release.wait(10);kwargs['check_cancel']();return read_trace(*args,**kwargs)
        with patch('optical_video.jobs.read_trace',side_effect=blocked):
            app.button[0].click().run();self.assertTrue(entered.wait(5));self.assertEqual(len(app.text_area),0)
            next(b for b in app.button if b.label=='中止する').click().run();release.set();finish_ui_job(app)
        self.assertEqual(len(app.text_area),0);self.assertEqual(app.session_state['optical_job'].snapshot()['state'],'cancelled')

if __name__=='__main__':unittest.main()
