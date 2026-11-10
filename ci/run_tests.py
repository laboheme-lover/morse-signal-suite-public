"""Run repository-only checks; recordings, SDKs and the development tree are not used."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SUITES = [
    ('outputs/morse-ai', 'test_morse_table.py'),
    ('optical-ml', 'test_pipeline.py'),
    ('optical-ml', 'test_adaptive_timing_v2.py'),
    ('optical-batch-test/pc', 'test_light_source.py'),
    ('ci', 'test_release.py'),
]

def main():
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update(PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1')
    failed = []
    for folder, pattern in SUITES:
        print(f'\n=== {folder}/{pattern} ===', flush=True)
        result = subprocess.run(
            [sys.executable, '-m', 'unittest', 'discover', '-s', folder, '-p', pattern, '-v'],
            cwd=ROOT, env=env, check=False,
        )
        if result.returncode:
            failed.append(f'{folder}/{pattern}')
    print('\nFAILED: ' + ', '.join(failed) if failed else '\nAll repository checks passed.', flush=True)
    return bool(failed)

if __name__ == '__main__':
    sys.exit(main())
