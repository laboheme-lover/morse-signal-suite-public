"""Encode known fixtures using optional test-only ffmpeg, then test actual decoder."""
from pathlib import Path
import argparse,json,subprocess
import cv2
from optical_video.core import preview,analyze_video
from optical_video.synthetic import generate

OUT=Path(__file__).parent/'compatibility_evaluation'

def run(ffmpeg):
    OUT.mkdir(exist_ok=True);source=OUT/'source.avi';generate(source,['.-'])
    def encode(name,args):
        target=OUT/name
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(source),*args,str(target)],check=True)
        return target
    h264=encode('h264.mp4',['-c:v','libx264','-pix_fmt','yuv420p'])
    portrait=encode('portrait_1080x1920.mp4',['-vf','scale=1080:1920','-c:v','libx264','-pix_fmt','yuv420p'])
    mp4v=encode('mpeg4.mp4',['-c:v','mpeg4'])
    rotated=OUT/'rotation90.mp4'
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-display_rotation','90','-i',str(h264),'-c','copy',str(rotated)],check=True)
    vfr=encode('variable_timing.mp4',['-vf','setpts=if(gte(N\,40)\,PTS+0.2/TB\,PTS)','-fps_mode','vfr','-c:v','libx264'])
    oversized=encode('over_limit.mp4',['-vf','scale=1922:1080','-c:v','libx264'])
    broken=OUT/'broken.mp4';broken.write_bytes(b'not a video')
    unsupported=OUT/'unknown_codec.mp4';unsupported.write_bytes(h264.read_bytes().replace(b'avc1',b'zzzz'))
    rows=[]
    for path,roi,dimensions in [(source,(60,40,40,40),(160,120)),(mp4v,(60,40,40,40),(160,120)),(h264,(60,40,40,40),(160,120)),(portrait,(405,640,270,640),(1080,1920)),(rotated,(40,60,40,40),(120,160))]:
        info,frame=preview(path,1.)
        assert (info['width'],info['height'])==dimensions,(path,info)
        assert frame.shape[:2]==(dimensions[1],dimensions[0])
        result=analyze_video(path,roi,dot_seconds=.3)
        assert result['text']=='イ',(path,result['text'])
        rows.append(dict(file=path.name,expected='イ',actual=result['text'],status='PASS',video=info))
    for path in (vfr,oversized,broken,unsupported):
        try:analyze_video(path,(60,40,40,40),dot_seconds=.3)
        except ValueError as exc:rows.append(dict(file=path.name,status='EXPECTED_REJECTION',message=str(exc)))
        else:raise AssertionError('Invalid video accepted: '+str(path))
    (OUT/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(rows,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ffmpeg',required=True);run(p.parse_args().ffmpeg)
