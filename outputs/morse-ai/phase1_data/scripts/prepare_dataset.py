"""Publish a frozen read-only view of audited existing datasets; does not copy WAVs."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from src.common import ROOT,read_csv,load_config
from src.metadata_manager import prepare_existing
from src.test_protection import freeze_or_verify

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path);args=p.parse_args()
    cfg=load_config(args.config);rows=read_csv(ROOT/'reports/dataset_audit.csv')
    freeze_or_verify(rows,cfg)
    prepare_existing(rows,cfg)
    print('Split indices created/verified without changing existing WAVs.')
