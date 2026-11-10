from pathlib import Path
from optical_video.field_eval import freeze,run,write_json,POLICY
from optical_video.synthetic import generate
from morse_table import MORSE_TABLE

def main():
    base=Path(__file__).parent/'field_rehearsal';base.mkdir(exist_ok=False)
    rows=[]
    for ident,text,patterns,dot in [('clean','イ',['.-'],9),('mixed','イWFPロ',[MORSE_TABLE[c] for c in 'イ（ヤチツ）ロ'],9),('low_fps','イ',['.-'],3),('broken','イ',[],9)]:
        path=base/(ident+'.avi')
        if ident=='broken':path.write_bytes(b'intentional corrupt fixture');duration=3.
        else:
            generate(path,patterns,dot_frames=dot)
            import cv2
            cap=cv2.VideoCapture(str(path));duration=cap.get(cv2.CAP_PROP_FRAME_COUNT)/30;cap.release()
        (base/(ident+'.txt')).write_text(text,encoding='utf-8')
        rows.append(dict(id=ident,video=path.name,reference=ident+'.txt',group_id=ident,role='rehearsal',declared_unseen=False,
            source='generated fixture, not real recording',camera='synthetic',exposure='fixed',conditions=ident,roi=[60,40,40,40],range_seconds=[0,duration],options={'dot_seconds':dot/30}))
    write_json(base/'manifest.json',dict(schema='optical-field-manifest-v1',normalization=POLICY,source_review_completed=True,prior_locks=[],videos=rows))
    freeze(base/'manifest.json',base/'lock.json');summary=run(base/'lock.json',base/'results')
    assert all((r['reference_units'],r['exact'],r['failed'],r['review'],r['edits'])==(8,2,1,1,2) for r in summary),summary
    print('PASS: 4 fixtures x 3 methods; expected failure retained, low-fps candidate excluded')

if __name__=='__main__':main()
