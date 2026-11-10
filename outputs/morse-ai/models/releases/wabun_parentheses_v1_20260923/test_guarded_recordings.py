import copy, json, tempfile, unittest
from pathlib import Path
import sys
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'phase8_quality'))
from guarded_pipeline import guard
from recording_experiment import infer_recording
from batch_recordings import prepare,execute

def row(text='イ',pattern='.-'):
    return dict(start_sample=1600,end_sample=3200,index=0,pattern=pattern,text_prediction=text,review_reason='')

class GuardTests(unittest.TestCase):
    def fixtures(self):
        return {('baseline','M1'):('イ',[row()],[],''),('combined_mode','M1'):('ロ',[row('ロ')],[],'')},{'combined_mode':dict(timing_fit_loss=.3,tracked_min_hz=700,tracked_max_hz=710)}
    def test_irregular_stable_falls_back_without_reference(self):
        outputs,detectors=self.fixtures();before=copy.deepcopy(outputs)
        result,meta=guard(outputs,detectors,'M1')
        self.assertEqual(result[0],'イ');self.assertTrue(meta['guard']['fallback']);self.assertTrue(result[1][0]['review_reason']);self.assertEqual(outputs,before)
    def test_changed_codes_do_not_trigger_irregular_guard(self):
        outputs,detectors=self.fixtures();outputs[('combined_mode','M1')][1][0]['pattern']='--'
        result,meta=guard(outputs,detectors,'M1');self.assertFalse(meta['guard']['fallback']);self.assertEqual(result[0],'ロ')
    def test_pitch_variation_keeps_tracking(self):
        outputs,detectors=self.fixtures();detectors['combined_mode']['tracked_max_hz']=800
        self.assertFalse(guard(outputs,detectors,'M1')[1]['guard']['fallback'])
    def test_ambiguous_and_failure(self):
        outputs,detectors=self.fixtures();detectors['combined_mode']['timing_ambiguous']=True
        self.assertTrue(guard(outputs,detectors,'M1')[1]['guard']['fallback'])
        outputs[('baseline','M1')]=('',[],[],'failed');outputs[('combined_mode','M1')]=('',[],[],'failed')
        result,meta=guard(outputs,detectors,'M1');self.assertEqual(result[3],'failed');self.assertFalse(meta['guard']['fallback'])
    def test_silent_file_retains_all_failures(self):
        outputs,meta,timing=infer_recording(np.zeros(16000),{'M1':None},{},[],{'mode':'full'})
        self.assertEqual(len(outputs),6);self.assertTrue(all(r['error'] for r in outputs.values()))
    def test_batch_manifest_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);sf.write(p/'a.wav',np.zeros(16000),16000);(p/'ref.txt').write_text('イ',encoding='utf-8')
            source=p/'input.json';entry=dict(id='one',audio='a.wav',reference='ref.txt',body={'mode':'full'})
            source.write_text(json.dumps({'recordings':[entry]}),encoding='utf-8');prepare(source,p/'out')
            stored=json.loads((p/'out/manifest.json').read_text(encoding='utf-8'));self.assertEqual(stored['recordings'][0]['reference'],'イ')
            source.write_text(json.dumps({'recordings':[entry,entry]}),encoding='utf-8')
            with self.assertRaises(ValueError):prepare(source,p/'duplicate')
    def test_guard_app(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(ROOT/'experiment_app.py'),default_timeout=60).run()
        app.multiselect[0].set_value(['baseline','guarded']).run();app.button[0].click().run();self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value),2)
        app.selectbox[2].set_value('guarded').run();self.assertFalse(app.exception)
        self.assertTrue(any('補正ガードの選択' in c.value for c in app.caption))
    def test_resume_rejects_manifest_change(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'manifest.json').write_text('{}',encoding='utf-8');(p/'manifest_lock.json').write_text('{"sha256":"invalid"}',encoding='utf-8')
            with patch('batch_recordings.run') as mocked:
                with self.assertRaises(ValueError):execute(p)
                mocked.assert_not_called()
    def test_concurrent_output_lock(self):
        import msvcrt
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            with (p/'execution.lock').open('w+b') as handle:
                handle.write(b'0');handle.flush();handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                try:
                    with patch('batch_recordings.run') as mocked:
                        with self.assertRaises((OSError,RuntimeError)):execute(p)
                        mocked.assert_not_called()
                finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':unittest.main()
