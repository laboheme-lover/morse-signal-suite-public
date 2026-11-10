import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse,json
from src.common import load_config
from src.verification import verify
from src.visualization import plot_reports

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path);parser.add_argument('--figures',action='store_true');args=parser.parse_args()
    result=verify(load_config(args.config))
    if args.figures:plot_reports()
    print(json.dumps(result,indent=2),flush=True)
    if not result['targets_met']:raise SystemExit(1)
