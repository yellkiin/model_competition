#!/usr/bin/env python3
"""Generate the template-level standalone requirements.tex from manifests."""
import argparse
from pathlib import Path
from environment_contract import load_catalog, read_json, validate_needs, ENV_DIR
from environment_reports import render_tex

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(render_tex(load_catalog(),validate_needs(read_json(ENV_DIR/'基础需求.json'))),encoding='utf8')
    return 0
if __name__=='__main__':raise SystemExit(main())
