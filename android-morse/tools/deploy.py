"""Deploy only to an explicitly selected, authorized Android device."""
from pathlib import Path
import argparse, datetime, hashlib, json, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--serial', help='adb device serial; required when multiple devices exist')
parser.add_argument('--check', action='store_true', help='list devices without installation')
parser.add_argument('--test', action='store_true', help='run Android file-decoding integration tests after installing')
args = parser.parse_args()
cfg = json.loads((ROOT/'.toolchain/environment.json').read_text(encoding='utf-8'))
adb = str(Path(cfg['sdk'])/'platform-tools/adb.exe')
apk = ROOT/'dist/wabun-signal-0.5.0-debug.apk'
report = ROOT/'test-results'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
report.mkdir(parents=True, exist_ok=True)
events = []
def run(*command, binary=False):
    p = subprocess.run([adb, *command], capture_output=True, timeout=120)
    value = p.stdout if binary else p.stdout.decode('utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8', errors='replace') or str(value))
    return value
try:
    listing = run('devices', '-l')
    print(listing)
    if args.check:
        sys.exit(0)
    devices = [line.split()[0] for line in listing.splitlines()[1:]
               if len(line.split()) >= 2 and line.split()[1] == 'device']
    if args.serial:
        if args.serial not in devices:
            raise RuntimeError('Selected device is not connected/authorized.')
        serial = args.serial
    elif len(devices) == 1:
        serial = devices[0]
    else:
        raise RuntimeError('Connect and authorize one device, or specify --serial. No installation performed.')
    expected = (ROOT/'dist/SHA256SUMS.txt').read_text().split()[0]
    if hashlib.sha256(apk.read_bytes()).hexdigest() != expected:
        raise RuntimeError('APK checksum mismatch; rebuild and verify before deploying.')
    def device(*cmd, **kw):
        return run('-s', serial, *cmd, **kw)
    model = device('shell', 'getprop', 'ro.product.model').strip()
    events.append({'device': serial, 'model': model, 'sha256': expected})
    print('Installing on', model)
    events.append({'install': device('install', '-r', str(apk))})
    if args.test:
        test_apk = ROOT/'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'
        events.append({'test_install': device('install', '-r', '-t', str(test_apk))})
        test_output = device('shell', 'am', 'instrument', '-w', '-r', 'jp.local.wabun.test/jp.local.wabun.DeviceSmokeTest')
        (report/'instrumentation.txt').write_text(test_output, encoding='utf-8')
        if 'WABUN_SMOKE_PASS 31 checks' not in test_output:
            raise RuntimeError('Android integration test failed; see instrumentation.txt')
        events.append({'integration_tests': 'passed', 'checks': 31})
    fixtures = ROOT/'test-data'
    device('shell', 'mkdir', '-p', '/sdcard/Download/WabunTest')
    for f in sorted(list(fixtures.glob('*.wav'))+list(fixtures.glob('*.mp4'))):
        device('push', str(f), '/sdcard/Download/WabunTest/'+f.name)
    events.append({'launch': device('shell', 'am', 'start', '-W', '-n', 'jp.local.wabun/.MainActivity')})
    (report/'launch.png').write_bytes(device('exec-out', 'screencap', '-p', binary=True))
    events.append({'status': 'installed_and_launch_requested', 'note': 'Camera, microphone, phone-call and recognition accuracy require manual tests.'})
    print('Installed. Test WAV/MP4 files: Downloads/WabunTest. Report:', report)
except Exception as exc:
    events.append({'status': 'failed', 'error': str(exc)})
    print('Deployment could not complete:', exc)
    sys.exit(1)
finally:
    (report/'deployment.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')





