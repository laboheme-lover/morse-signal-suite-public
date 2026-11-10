import unittest,tempfile,json
from pathlib import Path
import numpy as np,cv2
import splitter as s

def trace(cases,unit=.3,gap=10,low=20,high=230):
 states=[(False,5.)]
 for i,c in enumerate(cases):
  states.extend((on,u*unit) for on,u in c['pulses'])
  states.append((False,gap if i+1<len(cases) else 5.))
 total=sum(d for _,d in states);t=np.arange(round(total*30))/30
 v=np.full(len(t),float(low));start=0.
 for on,d in states:
  v[(t>=start-1e-8)&(t<start+d-1e-8)]=high if on else low;start+=d
 return t,v
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.cases=s.corpus()['batches'][0]['cases'][:3]
 def test_all_corpus_cases(self):
  c=s.corpus();self.assertEqual([len(b['cases']) for b in c['batches']],[65]+[5]*4+[4]*6+[10]*2)
  old=json.loads((s.ROOT/'archive/v0.1.0/batches.json').read_text(encoding='utf-8'))
  self.assertEqual([r for b in c['batches'] for r in b['cases']],[r for b in old['batches'] for r in b['cases']])
  self.assertEqual(len({r['id'] for b in c['batches'] for r in b['cases']}),129)
  for b in c['batches']:
   for r in b['cases']:
    self.assertNotIn('□',r['labels']);self.assertTrue(r['pulses'][0][0]);self.assertTrue(r['pulses'][-1][0])
    self.assertEqual(r['units'],sum(u for _,u in r['pulses']))
    self.assertNotIn('<',r['labels']);self.assertNotIn('＞',r['labels'])
 def test_three_speeds(self):
  for unit in (.3,.45,.6):
   t,v=trace(self.cases,unit);r=s.detect(t,v,self.cases,unit)
   self.assertEqual(len(r['clips']),3)
   self.assertEqual([c['id'] for c in r['clips']],[c['id'] for c in self.cases])
 def test_low_contrast(self):
  t,v=trace(self.cases,low=100,high=109)
  with self.assertRaisesRegex(s.SplitError,'明るさの差'):s.detect(t,v,self.cases,.3)
 def test_static(self):
  t,v=trace(self.cases)
  with self.assertRaises(s.SplitError):s.detect(t,np.ones(len(t))*30,self.cases,.3)
 def test_wrong_count(self):
  t,v=trace(self.cases)
  with self.assertRaisesRegex(s.SplitError,'指定原稿'):s.detect(t,v,self.cases[:2],.3)
 def test_wrong_speed(self):
  t,v=trace(self.cases)
  with self.assertRaises(s.SplitError):s.detect(t,v,self.cases,.6)
 def test_wrong_gap(self):
  t,v=trace(self.cases,gap=14)
  with self.assertRaisesRegex(s.SplitError,'休止'):s.detect(t,v,self.cases,.3)
 def test_incomplete(self):
  t,v=trace(self.cases);a=np.flatnonzero(v>100)[0]
  with self.assertRaises(s.SplitError):s.detect(t[a:]-t[a],v[a:],self.cases,.3)
 def test_missing_frames(self):
  t,v=trace(self.cases);t[50:]+=.3
  with self.assertRaisesRegex(s.SplitError,'フレーム'):s.detect(t,v,self.cases,.3)
 def test_noise(self):
  t,v=trace(self.cases);v+=np.random.default_rng(4).normal(0,2,len(v))
  self.assertEqual(s.detect(t,v,self.cases,.3)['quality'],'PASS')
 def test_real_video_export(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);p=d/'fixture.mp4';t,v=trace(self.cases)
   out=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'mp4v'),30,(96,64));self.assertTrue(out.isOpened())
   for value in v:
    frame=np.full((64,96,3),20,dtype=np.uint8);frame[20:44,32:64]=round(value);out.write(frame)
   out.release()
   image=s.preview(p,6,[32,20,32,24]);self.assertEqual(image.shape,(64,96,3))
   result,_,_=s.analyze(p,[32,20,32,24],'single65',1,3,300)
   folder=s.export(result,d/'split');manifest=json.loads((folder/'split_manifest.json').read_text(encoding='utf-8'))
   self.assertEqual(manifest['status'],'complete');self.assertEqual(len(list(folder.glob('*.mp4'))),3)
   for clip in result['clips']:
    meta,t2,v2=s.read_trace(folder/(clip['id']+'.mp4'),[32,20,32,24])
    self.assertGreater(v2.max()-v2.min(),150)
   with self.assertRaises(FileExistsError):s.export(result,folder)
   p.write_bytes(b'changed')
   with self.assertRaises(s.SplitError):s.export(result,d/'changed')
if __name__=='__main__':unittest.main(verbosity=2)
