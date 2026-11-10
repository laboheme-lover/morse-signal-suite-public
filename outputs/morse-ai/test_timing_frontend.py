import sys,unittest,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent/'phase8_quality'))
from timing_frontend import estimate_unit,segment_timing
from stress_frontend import synth
from morse_table import MORSE_TABLE

class TimingTests(unittest.TestCase):
    def test_saved_problem_case(self):
        folder=Path(__file__).resolve().parent/'phase8_quality/timing_experiment_v1/development/frontend_stress_v1_kana_d80_stable_seed41_clean'
        detector=json.loads((folder/'timing_v1_detector.json').read_text(encoding='utf-8'))
        self.assertLess(abs(detector['dot_seconds']-.08),.006)
        for model in ('M1','M2','M3','M4'):
            output=json.loads((folder/('timing_v1_'+model+'.json')).read_text(encoding='utf-8'))
            self.assertEqual(output['text'],'スセソ')

    def test_viewer_new_validation(self):
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parent;folder=root/'phase8_quality/timing_experiment_v1/held/comparisons'
        app=AppTest.from_file(str(root/'evaluation_app.py'),default_timeout=30).run()
        app.multiselect[0].set_value([folder/'timing_held_baseline_M1_comparison.json',folder/'timing_held_timing_v1_M1_comparison.json']).run()
        self.assertFalse(app.exception);self.assertEqual(app.dataframe[1].value.iloc[0]['共通件数'],108)
        self.assertEqual(app.dataframe[1].value.iloc[0]['改善件数'],11)
        self.assertEqual(app.dataframe[1].value.iloc[0]['悪化件数'],0)

    def test_long_majority(self):
        unit,_=estimate_unit([.08]*2+[.24]*12,[.08]*10+[.24]*3)
        self.assertAlmostEqual(unit,.08)
    def test_all_long_with_short_gaps(self):
        unit,_=estimate_unit([.3]*8,[.1]*6+[.3])
        self.assertAlmostEqual(unit,.1)
    def test_ambiguous_equal_durations(self):
        unit,meta=estimate_unit([.24]*4,[.24]*3)
        self.assertTrue(meta['timing_ambiguous']);self.assertAlmostEqual(unit,.24)
    def test_audio_regression(self):
        for dot in (.08,.16):
            audio,_,_=synth('スセソ',dot,'stable',41)
            rows,meta=segment_timing(audio)
            self.assertEqual([r['pattern'] for r in rows],[MORSE_TABLE[c] for c in 'スセソ'])
            self.assertLess(abs(meta['dot_seconds']-dot),.006)
    def test_invalid(self):
        for x,g in [([],[]),([0,.1],[.1]),([np.nan,.1],[.1]),([.1,.2],[-1])]:
            with self.assertRaises(ValueError):estimate_unit(x,g)
        with self.assertRaises(ValueError):segment_timing(np.zeros(16000))
if __name__=='__main__':unittest.main()
