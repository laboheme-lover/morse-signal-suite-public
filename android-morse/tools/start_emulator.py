from pathlib import Path
import json, os, subprocess, argparse
ROOT=Path(__file__).resolve().parents[1];T=ROOT/'.toolchain'
cfg=json.loads((T/'environment.json').read_text(encoding='utf-8'))
parser=argparse.ArgumentParser();parser.add_argument('--visible',action='store_true');args=parser.parse_args()
env=os.environ.copy();env.update(ANDROID_HOME=cfg['sdk'],ANDROID_USER_HOME=str(T/'android-user'),ANDROID_AVD_HOME=str(T/'avd'),ANDROID_EMULATOR_HOME=str(T/'android-user'))
emulator=Path(cfg['sdk'])/'emulator/emulator.exe'
if not (T/'avd/Wabun_API35.avd').exists():raise SystemExit('Wabun_API35 virtual device has not been prepared.')
cmd=[str(emulator),'-avd','Wabun_API35','-no-audio','-no-boot-anim','-gpu','software','-no-snapshot','-camera-back','none','-camera-front','none','-memory','2048']
if not args.visible:cmd.append('-no-window')
with (T/'emulator.log').open('w',encoding='utf-8') as f:
    p=subprocess.Popen(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
(T/'emulator.pid').write_text(str(p.pid))
print('Virtual device starting. Use deploy.py --serial emulator-5554 --test after Android boots.')
