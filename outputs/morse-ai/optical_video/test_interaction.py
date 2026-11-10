from pathlib import Path
import unittest
from optical_video.interaction import valid_roi,review_points

class InteractionTests(unittest.TestCase):
    def test_roi_validation(self):
        self.assertEqual(valid_roi([0,0,1080,1920],1080,1920),[0,0,1080,1920])
        for r in ([0,0,0,3],[-1,0,2,3],[0,0,1081,2],[True,0,1,1],None):self.assertIsNone(valid_roi(r,1080,1920))
    def test_anchors_and_jump_keep_result(self):
        self.assertEqual(review_points({'exposure_changes':[{'time_seconds':2.5}],'diagnostics':[{'start_seconds':float('nan')}]}),[(2.5,'明暗の基準変化 ')])
        from streamlit.testing.v1 import AppTest
        from optical_video.testing import finish_ui_job
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'video_app.py'),default_timeout=30).run()
        app.checkbox[0].check().run()
        next(n for n in app.number_input if n.label=='解析開始（秒）').set_value(1.).run()
        next(b for b in app.button if b.label=='解析する').click().run();finish_ui_job(app)
        self.assertFalse(app.exception)
        before=app.text_area[0].value
        point=next(s for s in app.selectbox if s.label=='映像で確認する警告時刻').value[0]
        next(b for b in app.button if b.label=='選択した警告時刻へ移動').click().run()
        self.assertFalse(app.exception);self.assertEqual(app.slider[0].value,point)
        self.assertEqual(app.text_area[0].value,before)

if __name__=='__main__':unittest.main()
