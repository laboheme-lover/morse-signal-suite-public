import unittest
import splitter as s
from test_splitter import trace

class MultiBatchTests(unittest.TestCase):
    def test_order_and_single65_retained(self):
        batches=s.corpus('sentence')['batches']
        ids=[batches[2]['id'],batches[0]['id'],batches[1]['id']]
        cases=s.selected_batch('selection_queue','sentence',ids)['cases']
        self.assertEqual(len(cases),67)
        self.assertEqual(cases[1:66],batches[0]['cases'])
        self.assertEqual(cases[0],batches[2]['cases'][0])
        self.assertEqual(cases[-1],batches[1]['cases'][0])
        t,v=trace(cases,gap=10)
        self.assertEqual(len(s.detect(t,v,cases,.3)['clips']),67)
    def test_invalid_queue(self):
        for ids in ([],['single65','single65'],['missing']):
            with self.assertRaises(s.SplitError):
                s.selected_batch('selection_queue','sentence',ids)

