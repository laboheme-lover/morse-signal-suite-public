import unittest,copy
from morse_table import MORSE_TABLE
from wabun_runtime_policy import render_body,normalize_reference
class PolicyTests(unittest.TestCase):
 def rows(self,text):return [dict(index=i,pattern=MORSE_TABLE[c],prediction=c,top_k=[dict(label=c,confidence=1.)]) for i,c in enumerate(text)]
 def test_parentheses_and_paragraph(self):
  r=self.rows('（キリサケ）リ」');before=copy.deepcopy(r);text,rows,w=render_body(r)
  self.assertEqual(text,'キリサケリ');self.assertEqual(r,before);self.assertTrue(all(x['mode']=='wabun' for x in rows));self.assertEqual(w,[])
 def test_unmatched(self):
  self.assertEqual(render_body(self.rows('（リ'))[0],'リ')
 def test_reference(self):self.assertEqual(normalize_reference('（リ、サ）'),'リサ')
 def test_repaired_pattern_restored(self):
  r=self.rows('（リ');r[0]['observed_pattern']='......';t,_,_=render_body(r);self.assertEqual(t,'□リ')
if __name__=='__main__':unittest.main()
