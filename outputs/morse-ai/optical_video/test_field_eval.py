from pathlib import Path
import copy,json,tempfile,unittest
from unittest.mock import patch
from optical_video import field_eval as f
from optical_video.synthetic import generate

def fixture(base):
    generate(base/'a.avi',['.-']);(base/'a.txt').write_text('イ',encoding='utf-8')
    row=dict(id='a',video='a.avi',reference='a.txt',group_id='shoot1',role='rehearsal',source='synthetic',camera='generator',exposure='fixed',conditions='clean',roi=[60,40,40,40],range_seconds=[0,3.3],options={'dot_seconds':.3},declared_unseen=False)
    return dict(schema='optical-field-manifest-v1',source_review_completed=True,normalization=f.POLICY,prior_locks=[],videos=[row])

class FieldTests(unittest.TestCase):
    def test_normalization_and_edits(self):
        self.assertEqual(f.normalize('が (wfp) 1.2、'),f.normalize('カ゛WFP1.2、'))
        for text in ['(W','W)','((W))']:
            with self.assertRaises(ValueError):f.normalize(text)
        for a,b,want in [('ABC','ADC',(1,0,0)),('ABC','AC',(0,0,1)),('AC','ABC',(0,1,0)),('AB','',(0,0,2))]:
            s=f.score(a,b);self.assertEqual((s['substitutions'],s['insertions'],s['deletions']),want)
        self.assertEqual(f.score('A','AAAA')['cer'],3)
    def test_freeze_verify_tamper_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m=fixture(p);f.write_json(p/'manifest.json',m);lock=f.freeze(p/'manifest.json',p/'lock.json');f.verify(lock)
            with self.assertRaises(FileExistsError):f.freeze(p/'manifest.json',p/'lock.json')
            (p/'a.txt').write_text('ロ',encoding='utf-8')
            with self.assertRaises(ValueError):f.verify(lock)
    def test_groups_duplicates_unseen_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m=fixture(p)
            variants=[];v=copy.deepcopy(m);v['videos']=[];variants.append(v)
            v=copy.deepcopy(m);v['videos'][0]['role']='final';variants.append(v)
            v=copy.deepcopy(m);v['videos'].append(dict(v['videos'][0],id='b'));variants.append(v)
            v=copy.deepcopy(m);v['videos'].append(dict(v['videos'][0],id='b',role='selection'));variants.append(v)
            v=copy.deepcopy(m);v['videos'][0]['id']='../escape';variants.append(v)
            for v in variants:
                f.write_json(p/'manifest.json',v)
                with self.assertRaises(ValueError):f.freeze(p/'manifest.json',p/'lock.json')
    def test_prior_lock_blocks_reused_final(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m=fixture(p);f.write_json(p/'old.json',m);f.freeze(p/'old.json',p/'old.lock.json')
            m['prior_locks']=['old.lock.json'];m['videos'][0].update(role='final',group_id='other',declared_unseen=True)
            f.write_json(p/'new.json',m)
            with self.assertRaises(ValueError):f.freeze(p/'new.json',p/'new.lock.json')
    def test_three_methods_failure_denominator_and_groups(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m=fixture(p);(p/'bad.mp4').write_bytes(b'broken')
            m['videos'].append(dict(m['videos'][0],id='bad',video='bad.mp4',group_id='shoot2'))
            f.write_json(p/'manifest.json',m);f.freeze(p/'manifest.json',p/'lock.json')
            with patch('optical_video.field_eval.read_trace',wraps=f.read_trace) as reader:summary=f.run(p/'lock.json',p/'out');self.assertEqual(reader.call_count,2)
            self.assertEqual(len(summary),3)
            for r in summary:self.assertEqual((r['reference_units'],r['failed'],r['exact'],r['cer']),(2,1,1,.5))
            self.assertEqual(len(json.loads((p/'out/groups.json').read_text())),6)
            self.assertEqual(json.loads((p/'out/status.json').read_text())['status'],'COMPLETE_WITH_FAILURES')
            with self.assertRaises(FileExistsError):f.run(p/'lock.json',p/'out')
    def test_midrun_mutation_aborts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);f.write_json(p/'manifest.json',fixture(p));f.freeze(p/'manifest.json',p/'lock.json')
            original=f.analyze_trace
            def mutate(*a,**kw):
                (p/'a.txt').write_text('ロ',encoding='utf-8');return original(*a,**kw)
            with patch('optical_video.field_eval.analyze_trace',side_effect=mutate):
                with self.assertRaises(ValueError):f.run(p/'lock.json',p/'out')
            self.assertEqual(json.loads((p/'out/status.json').read_text())['status'],'ABORTED')

if __name__=='__main__':unittest.main()
