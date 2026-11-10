import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import json
from src.common import load_config
from src.dataset_audit import audit
from src.test_protection import freeze_or_verify

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    cfg = load_config(args.config)
    rows, summary = audit(cfg)
    summary['frozen_test_files'] = freeze_or_verify(rows, cfg)
    print(json.dumps(summary, indent=2), flush=True)
    if summary['errors'] or summary['leakage_errors']: raise SystemExit(1)
