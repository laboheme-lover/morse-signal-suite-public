import unittest
import numpy as np
from morse_segmentation import segment_morse
from evaluate_recording import canonical_reference,edit_alignment
from analyze_recording_body import select_body


class RecordingTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(canonical_reference('ジュウデン、400。 ツカッタ'),'シ゛ユウテ゛ン400ツカツタ')

    def test_edit_counts(self):
        for ref,hyp,expected in [('ABC','ADC',(1,0,0)),('ABC','ABXC',(0,1,0)),('ABC','AC',(0,0,1))]:
            m,_=edit_alignment(ref,hyp)
            self.assertEqual((m['substitutions'],m['insertions'],m['deletions']),expected)

    def test_segment_known_signal(self):
        sr=16000;dot=.08;parts=[np.zeros(sr//2)]
        patterns=['--.','..-.','..-','-']
        for pattern in patterns:
            for k,symbol in enumerate(pattern):
                n=round(sr*dot*(1 if symbol=='.' else 3))
                parts.append(.5*np.sin(2*np.pi*600*np.arange(n)/sr))
                parts.append(np.zeros(round(sr*dot*(1 if k<len(pattern)-1 else 3))))
        parts.append(np.zeros(sr//2))
        segments,info=segment_morse(np.concatenate(parts))
        self.assertEqual([s['pattern'] for s in segments],patterns)
        self.assertAlmostEqual(info['dot_seconds'],dot,delta=.01)

    def test_rule_assisted_scope(self):
        rows=[{'pattern':p,'rule_prediction':r} for p,r in
              [('....','ヌ'),('-..---','?'),('--.','リ'),('.-.-..','」'),('...-.','?')]]
        self.assertEqual(select_body(rows),[rows[2]])
        with self.assertRaises(ValueError):select_body(rows[:-1])

    def test_silence_rejected(self):
        with self.assertRaises(ValueError):segment_morse(np.zeros(16000))


if __name__=='__main__':unittest.main()
