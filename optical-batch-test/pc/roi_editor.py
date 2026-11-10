"""Local interactive ROI editor; coordinates always refer to original pixels."""
import base64
from pathlib import Path
import cv2
import streamlit.components.v1 as components

_editor=components.declare_component('optical_roi_editor',path=str(Path(__file__).parent/'roi_editor_frontend'))

def validate_roi(rect,width,height):
    if not isinstance(rect,(list,tuple)) or len(rect)!=4:raise ValueError('範囲が不正です。')
    x,y,w,h=[int(round(float(v))) for v in rect]
    w=max(2,min(w,width));h=max(2,min(h,height))
    return [max(0,min(x,width-w)),max(0,min(y,height-h)),w,h]

def edit_roi(rgb,roi,context):
    ok,jpg=cv2.imencode('.jpg',cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,92])
    if not ok:raise ValueError('範囲選択画像を作成できません。')
    return _editor(image='data:image/jpeg;base64,'+base64.b64encode(jpg).decode('ascii'),
                   roi=roi,width=rgb.shape[1],height=rgb.shape[0],context=context,
                   key='interactive_optical_roi',default=None)
