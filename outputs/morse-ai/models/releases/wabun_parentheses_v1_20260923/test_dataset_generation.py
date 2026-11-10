import csv
from collections import Counter
import json
from pathlib import Path
import unittest
from generate_dataset import build_plan, split_counts, generate_dataset, validate_dataset
from esc50_manager import ESC50Manager
import test_esc50


class DatasetGenerationTests(unittest.TestCase):
    def test_counts_and_reproducible_plan(self):
        for count in (10,300):
            plan=build_plan(count)
            self.assertEqual(len(plan),65*count)
            self.assertEqual(plan,build_plan(count))
            self.assertNotEqual(plan,build_plan(count,seed=77))
            self.assertEqual(len({r['sample_id'] for r in plan}),len(plan))
            self.assertEqual(len({r['seed'] for r in plan}),len(plan))
            counts=Counter(r['label'] for r in plan)
            self.assertEqual(set(counts.values()),{count})
            for split in ('train','validation','test'):
                pool=[r for r in plan if r['split']==split]
                self.assertEqual({r['noise_type'] for r in pool},{'clean','white','esc50'})
                self.assertEqual({r['snr_db'] for r in pool if r['noise_type']!='clean'},{20,10,5,0,-5})
        self.assertEqual(split_counts(300),{'train':210,'validation':45,'test':45})
        self.assertEqual(split_counts(10,0),{'train':7,'validation':2,'test':1})
        self.assertEqual(split_counts(10,1),{'train':7,'validation':1,'test':2})

    def test_generation_validation_and_tampering(self):
        fixture=test_esc50.ESC50Tests()
        fixture.setUp()
        try:
            root=fixture.root/'dataset'
            report=generate_dataset(root,10,44,fixture.root,labels=['イ','モ'])
            self.assertEqual(report['samples'],20)
            self.assertEqual(report['split_counts'],{'train':14,'validation':3,'test':3})
            self.assertEqual(json.loads((root/'dataset_config.json').read_text(encoding='utf-8'))['status'],'complete')
            with self.assertRaises(FileExistsError):
                generate_dataset(root,10,44,fixture.root,labels=['イ','モ'])
            with (root/'metadata.csv').open(encoding='utf-8-sig',newline='') as file:
                reader=csv.DictReader(file); fields=reader.fieldnames; rows=list(reader)
            rows[0]['morse_code']='invalid'
            with (root/'metadata.csv').open('w',encoding='utf-8-sig',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=fields); writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'Label/code mismatch'):
                validate_dataset(root,ESC50Manager(fixture.root))
        finally:
            fixture.tearDown()

    def test_invalid_plan(self):
        for n in (0,9,-1,10.5):
            with self.assertRaises(ValueError):
                build_plan(n)
        for labels in ([],['イ','イ'],['A']):
            with self.assertRaises(ValueError):
                build_plan(10,labels=labels)


if __name__=='__main__':
    unittest.main()
