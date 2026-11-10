"""Create an immutable evaluation-plan snapshot, or verify its dependencies."""
from intake import PROJECT,digest
from pathlib import Path
import argparse,json

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    target=Path(__file__).with_name('future_evaluation_plan.json')
    if a.verify:
        plan=json.loads(target.read_text(encoding='utf-8'))
        failed=[p for p,h in plan['sha256'].items() if not (PROJECT/p).is_file() or digest(PROJECT/p)!=h]
        if failed:raise SystemExit('CHANGED: '+', '.join(failed))
        print('PASS: frozen model/config/code hashes match');return
    paths=['recognition_policy.py','predict_sequence.py','morse_segmentation.py','audio_preprocessing.py','mixed_morse.py','morse_table.py','evaluate_recording.py',
           'phase8_quality/policy.py','phase8_quality/intake.py','phase6_wabun65/common.py','phase7_real/evaluate.py','phase7_real/evaluate_four.py']
    for folder,name in (('phase2_m1','m1'),('phase3_m2','m2'),('phase4_m3','m3'),('phase5_m4','m4')):
        paths.extend(p.relative_to(PROJECT).as_posix() for p in (PROJECT/folder/name).glob('*.py'))
        paths.extend(f'phase6_wabun65/runs/{name}_wabun65_20260922/{f}' for f in ('best.pt','config.json','labels.json','provenance.json'))
    plan={'status':'PREPARATION_ONLY_NO_NEW_DATA','policy':'content_v2','models':['M1','M2','M3','M4'],
          'metrics':['pooled CER = sum edit distances / sum reference units','S/I/D','exact recordings / total recordings','decode failures and review counts'],
          'requirements':['Accept intake audit and manually confirm exposure/source permissions before evaluation',
          'Never train, tune thresholds or select a model using the new test results',
          'Use identical audio and preprocessing for all four models; retain all failures in the report',
          'Fresh inference required; do not reuse known-recording segmentation',
          'Freeze reference normalization and body framing before inspecting model predictions; ambiguous decimals require explicit source mode metadata',
          'New independent evaluation runner/body-framing protocol must be reviewed before the first new-data run',
          'Keep recordings from the same session/source group together; report source groups',
          'Unknown-noise evaluation requires categories or a corpus absent from training, plus provenance and clean controls'],
          'sha256':{p:digest(PROJECT/p) for p in paths}}
    with target.open('x',encoding='utf-8') as f:json.dump(plan,f,ensure_ascii=False,indent=2)
    print(target)

if __name__=='__main__':main()
