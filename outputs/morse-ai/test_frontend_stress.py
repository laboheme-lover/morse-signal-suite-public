import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent/'phase8_quality'))
from stress_frontend import synth
from evaluation_compare import paired

class StressTests(unittest.TestCase):
    def test_stress_view_and_profile_filter(self):
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parent
        app=AppTest.from_file(str(root/'evaluation_app.py'),default_timeout=30).run()
        folder=root/'phase8_quality/frontend_stress_v1/comparisons'
        app.multiselect[0].set_value([folder/'stress_baseline_M1_comparison.json',folder/'stress_segment_mode_v1_M1_comparison.json']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.dataframe[1].value.iloc[0]['共通件数'],192)
        app.multiselect[5].set_value(['drift100']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.dataframe[1].value.iloc[0]['共通件数'],24)

    def test_reproducible_and_new_timing(self):
        a,expected,meta=synth('サ（ヘイ）シ',.08,'jitter30',41)
        b,again,_=synth('サ（ヘイ）シ',.08,'jitter30',41)
        self.assertTrue(np.array_equal(a,b));self.assertEqual(expected,again)
        _,stable,_=synth('サ（ヘイ）シ',.08,'stable',41)
        self.assertNotEqual(expected,stable)
        self.assertTrue(all(0<=r['start_sample']<r['end_sample']<=len(a) for r in expected))

    def test_frequency_and_control_fault_scope(self):
        _,_,meta=synth('スセソ',.08,'drift100',41)
        self.assertAlmostEqual(meta['frequency_min'],600);self.assertGreater(meta['frequency_max'],799)
        for profile in ('control_notch','control_spike'):
            _,_,none=synth('スセソ',.08,profile,41);self.assertEqual(none['faults'],[])
            _,rows,meta=synth('サ（ヘイ）シ',.08,profile,41)
            self.assertTrue(meta['faults'])
            for fault in meta['faults']:
                self.assertTrue(any(r['label'] in '（）' and r['start_sample']<=fault['start_sample']<fault['end_sample']<=r['end_sample'] for r in rows))

    def test_repeated_audio_pairs_require_matching_condition(self):
        a=[dict(id=x,input_sha256='a'*64,reference='イ',reference_units=1,edits=0) for x in ('first','second')]
        b=[dict(r) for r in a];b[1]['edits']=1
        result=paired(a,b);self.assertEqual(result['共通件数'],2);self.assertEqual(result['悪化件数'],1)
        b[1]['id']='different';self.assertEqual(paired(a,b)['共通件数'],1)
        with self.assertRaises(ValueError):paired(a+a,b)

if __name__=='__main__':unittest.main()
