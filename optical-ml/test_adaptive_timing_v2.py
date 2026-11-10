import unittest
import numpy as np
from adaptive_timing_v2 import estimate_unit

class TimingTests(unittest.TestCase):
    def trace(self,unit):
        intervals=[]
        for code in ((1,3),(3,1,1),(1,1,3,1))*8:
            for i,pulse in enumerate(code):intervals.extend([(True,pulse*unit),(False,(3 if i==len(code)-1 else 1)*unit)])
        ends=np.cumsum([duration for _,duration in intervals]);t=np.arange(0,ends[-1],1/30)
        idx=np.minimum(np.searchsorted(ends,t,side='right'),len(intervals)-1)
        on=np.array([s for s,_ in intervals])[idx]
        f=np.column_stack([20+100*on,20+110*on,np.full(len(t),20),20+10*on])
        return t,f
    def test_periods(self):
        for unit in (.182,.3,.5,.667):
            t,f=self.trace(unit);self.assertLess(abs(estimate_unit(t,f)['unit_seconds']-unit),.018)
    def test_brightness_offset(self):
        t,f=self.trace(.24);self.assertLess(abs(estimate_unit(t,f*.4+30)['unit_seconds']-.24),.018)
    def test_reject_flat(self):
        with self.assertRaises(ValueError):estimate_unit(np.arange(100)/30,np.ones((100,4)))
    def test_one_frame_drops(self):
        t,f=self.trace(.3)
        f[20::43,0]=20;f[20::43,1]=20
        self.assertLess(abs(estimate_unit(t,f)['unit_seconds']-.3),.018)
    def test_reject_bad_time(self):
        t,f=self.trace(.3);t[2]=t[1]
        with self.assertRaises(ValueError):estimate_unit(t,f)

if __name__=='__main__':unittest.main()
