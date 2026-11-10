import unittest
from optical_video.evaluate_coverage_stress import cases,distance,schedule,score
from morse_table import MORSE_TABLE

class BenchmarkTests(unittest.TestCase):
    def test_complete_coverage_and_no_duplicate_cases(self):
        roster=cases();self.assertEqual(len({c['name'] for c in roster}),len(roster))
        for fps in (30,60):
            c=next(c for c in roster if c['name']==f'wabun65_{fps}')
            self.assertEqual(len(c['patterns']),65);self.assertEqual(set(c['patterns']),set(MORSE_TABLE.values()))
            c=next(c for c in roster if c['name']==f'international38_{fps}')
            self.assertEqual(len(c['expected']),38)
    def test_time_ground_truth(self):
        states,events=schedule(['.-','-'],9,30)
        self.assertEqual(len(events),3)
        self.assertAlmostEqual(events[0]['start_seconds'],.9)
        self.assertAlmostEqual(events[0]['end_seconds'],1.2)
        for event in events:
            self.assertTrue(states[round(event['start_seconds']*30):round(event['end_seconds']*30)].all())
    def test_rejections_stay_in_score_and_errors_not_hidden(self):
        spec={'name':'a','category':'stress','expected':'イロ','patterns':['.-','.-.-']}
        truth={'patterns':spec['patterns'],'events':[]}
        s=score(spec,truth,None,'no contrast',1.)
        self.assertEqual((s['edits'],s['cer'],s['pattern_edits']),(2,1.,2))
        result=dict(text='イ',candidate_text='イ',status='OK',characters=[{'pattern':'.-'}],events=[])
        self.assertTrue(score(spec,truth,result,'',0.)['unflagged_error'])
        result['status']='REVIEW';self.assertFalse(score(spec,truth,result,'',0.)['unflagged_error'])
    def test_sequence_distance(self):
        self.assertEqual(distance(['.-','--'],['.-','..']),1)
        self.assertEqual(distance('アイウ','アイ'),1)
        self.assertEqual(distance('','ア'),1)

if __name__=='__main__':unittest.main()
