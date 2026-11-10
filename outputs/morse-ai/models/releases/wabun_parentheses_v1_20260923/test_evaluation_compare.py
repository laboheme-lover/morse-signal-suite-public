import copy
import json
from pathlib import Path
import unittest
from evaluation_compare import SCHEMA, load_bundle, paired, aggregate
from phase8_quality.analyze_saved_errors import ideal, diagnose, ui_review, confusion

ROOT=Path(__file__).resolve().parent

class ComparisonTests(unittest.TestCase):
    def bundle(self):
        return dict(schema=SCHEMA,name='test',scope='synthetic-noise-diagnostic',scoring_policy='test',rows=[
            dict(id='a',model='M1',input_sha256='a'*64,reference='イロ',hypothesis='イハ',reference_units=2,edits=1,status='OK')])

    def test_validation(self):
        b=self.bundle();self.assertEqual(load_bundle(json.dumps(b))['rows'][0]['edits'],1)
        for bad in ([],{},dict(b,rows=b['rows']*2)):
            with self.assertRaises(ValueError):load_bundle(json.dumps(bad))
        b['rows'][0]['edits']=0
        with self.assertRaises(ValueError):load_bundle(json.dumps(b))

    def test_pairing_uses_input_and_reference(self):
        a=self.bundle()['rows']; b=copy.deepcopy(a); b[0]['hypothesis']='イロ';b[0]['edits']=0
        self.assertEqual(paired(a,b)['改善件数'],1)
        b[0]['input_sha256']='b'*64
        self.assertEqual(paired(a,b)['共通件数'],0)
        b[0]['input_sha256']='a'*64;b[0]['reference']='イハ'
        self.assertEqual(paired(a,b)['共通件数'],0)
        with self.assertRaises(ValueError):paired(a*2,a)

    def test_weighted_cer(self):
        r=self.bundle()['rows'][0];r['evaluation']='test'
        other=dict(r,reference_units=8,edits=0)
        self.assertEqual(aggregate([r,other])[0]['CER'],.1)

    def test_segmentation_evidence(self):
        expected=ideal('イロ',.08)
        observed=[dict(e,prediction=e['label']) for e in expected]
        self.assertEqual(diagnose(expected,observed)['class_error'],0)
        merged=[dict(observed[0],end_sample=observed[-1]['end_sample'])]
        self.assertEqual(diagnose(expected,merged)['merged'],1)
        self.assertEqual(diagnose(expected,observed[:1])['missing'],1)
        first=observed[0];middle=(first['start_sample']+first['end_sample'])//2
        split=[dict(first,end_sample=middle),dict(first,start_sample=middle),observed[1]]
        self.assertEqual(diagnose(expected,split)['split'],1)
        observed[0]['prediction']='ハ'
        self.assertEqual(diagnose(expected,observed)['class_error_with_correct_pattern'],1)

    def test_warning_boundary_and_controls(self):
        r=dict(kind='character',confidence=.8,disagrees_with_rule=False,text_prediction='イ')
        self.assertFalse(ui_review(r));r['confidence']=.799;self.assertTrue(ui_review(r))
        r['kind']='mode_control';self.assertFalse(ui_review(r))
        c=confusion([dict(edits=1,alert=True),dict(edits=1,alert=False),dict(edits=0,alert=True),dict(edits=0,alert=False)],'alert')
        self.assertEqual([c[k] for k in ('TP','FN','FP','TN')],[1,1,1,1])

    def test_saved_data(self):
        folder=ROOT/'phase8_quality/saved_error_analysis'
        total=0
        for p in folder.glob('M?_comparison.json'):
            b=load_bundle(p.read_bytes());self.assertEqual(len(b['rows']),366);total+=len(b['rows'])
            self.assertEqual(paired(b['rows'],b['rows'])['共通件数'],366)
        self.assertEqual(total,1464)
        pilot=load_bundle((folder/'pilot_M1_comparison.json').read_bytes())
        expanded=load_bundle((folder/'M1_comparison.json').read_bytes())
        self.assertEqual(len(pilot['rows']),11)
        self.assertEqual(paired(pilot['rows'],expanded['rows'])['共通件数'],0)
        clean=json.loads((ROOT/'phase8_quality/noise_expanded/multi_mode_d80_clean_oNone_sNone/M1.json').read_text(encoding='utf-8'))
        d=diagnose(ideal('イ（ヤチ）ロ（12）ハ',.08),clean['segments'])
        self.assertFalse(any(v for k,v in d.items() if k!='matched'))

    def test_streamlit(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(ROOT/'evaluation_app.py'),default_timeout=30).run()
        self.assertEqual(len(at.exception),0)
        self.assertGreaterEqual(len(at.dataframe),3)
        at.multiselect[1].set_value([]).run()
        self.assertEqual(len(at.exception),0)
        self.assertTrue(any('該当' in x.value for x in at.warning))
        at.multiselect[0].set_value([]).run()
        self.assertEqual(len(at.exception),0)

if __name__=='__main__':unittest.main()
