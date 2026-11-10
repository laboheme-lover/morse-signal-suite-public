"""Streamlit UI logic tests. Browser drag gestures and hardware are separate tests."""
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

import cv2
import numpy as np
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

def app(path):
    target = ROOT / path
    # AppTest does not add the script directory in the same way as streamlit run.
    return AppTest.from_string(
        f'import sys\nsys.path.insert(0, {str(target.parent)!r})\n'
        f'from pathlib import Path\nexec(compile(Path({str(target)!r}).read_text(encoding="utf-8"), {str(target)!r}, "exec"), {{"__file__": {str(target)!r}, "__name__": "__main__"}})',
        default_timeout=120,
    ).run()

def button(at, label):
    return next(b for b in at.button if b.label == label)

class WebTests(unittest.TestCase):
    def clean(self, at):
        self.assertEqual(len(at.exception), 0, str(at.exception))

    def test_audio_sample_and_settings(self):
        at = app('outputs/morse-ai/app.py')
        self.clean(at)
        self.assertTrue(button(at, '認識する').disabled)
        at.radio[0].set_value('サンプル：イロハ').run()
        self.assertFalse(button(at, '認識する').disabled)
        button(at, '認識する').click().run()
        self.clean(at)
        self.assertEqual(len(at.error), 0, str(at.error))
        self.assertEqual(at.text_area[0].value, 'イロハ')
        self.assertGreater(len(at.dataframe), 0)
        at.slider[0].set_value(5).run()
        self.assertEqual(len(at.text_area), 0)  # stale results must be invalidated

    def test_splitter_missing_file(self):
        at = app('optical-batch-test/pc/app.py')
        self.clean(at)
        at.text_input[0].set_value(str(ROOT / '__missing__.mp4')).run()
        self.clean(at)
        self.assertGreater(len(at.error), 0)

    def test_optical_roi_confirm_and_invalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'blink.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 30, (320, 240))
            self.assertTrue(writer.isOpened())
            for i in range(120):
                frame = np.zeros((240, 320, 3), np.uint8)
                if i % 30 < 15:
                    frame[105:115, 155:165] = 255
                writer.write(frame)
            writer.release()
            at = app('optical-ml/app.py')
            at.text_input[0].set_value(str(path)).run()
            self.clean(at)
            self.assertTrue(button(at, '認識を実行').disabled)
            button(at, '点滅する光源の範囲を自動提案').click().run()
            self.clean(at)
            self.assertIn('ml_suggestion', at.session_state)
            button(at, 'この光源範囲を確認').click().run()
            self.assertFalse(button(at, '認識を実行').disabled)
            at.number_input(key='ml_x').set_value(120).run()
            self.clean(at)
            self.assertTrue(button(at, '認識を実行').disabled)

    def test_candidate_edit_and_undo(self):
        code = f'import sys\nsys.path.insert(0, {str(ROOT / "optical-ml")!r})\n' + '''
import streamlit as st
from result_editor import render_result
if 'bundle' not in st.session_state:
    st.session_state.bundle={'result': {'text':'イ', 'warning':'test fixture', 'characters':[{'text':'イ','start':0.,'end':1.,'candidates':[{'label':'イ','score':.6},{'label':'ロ','score':.4}]}]}}
render_result(st.session_state.bundle)
'''
        at = AppTest.from_string(code).run()
        at.selectbox[1].set_value(1).run()
        button(at, '選んだ候補を反映').click().run()
        self.clean(at)
        self.assertEqual(at.session_state.bundle['corrections'], {0: 'ロ'})
        self.assertEqual(at.session_state.bundle['result']['text'], 'イ')
        button(at, 'この文字を元に戻す').click().run()
        self.assertEqual(at.session_state.bundle['corrections'], {})

if __name__ == '__main__':
    if len(sys.argv) > 1:
        unittest.main()
    else:
        # Each deployed app has its own process. Their same-named modules
        # (notably predict.py) must not share Python's import cache in tests.
        codes = [subprocess.run([sys.executable, __file__, 'WebTests.' + name, '-v']).returncode
                 for name in unittest.defaultTestLoader.getTestCaseNames(WebTests)]
        sys.exit(any(codes))
