import unittest
from evaluate_model import metrics


class EvaluationTests(unittest.TestCase):
    def test_macro_f1_includes_all_classes(self):
        result=metrics([0,0,1,1],[0,1,1,2],3)
        self.assertEqual(result['samples'],4)
        self.assertEqual(result['correct'],2)
        self.assertAlmostEqual(result['accuracy'],0.5)
        self.assertAlmostEqual(result['macro_f1'],(2/3+0.5+0)/3)

    def test_invalid_predictions(self):
        for targets,predictions in (([],[]),([0,1],[0])):
            with self.assertRaises(ValueError):
                metrics(targets,predictions,2)


if __name__=='__main__':
    unittest.main()
