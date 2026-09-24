#!/usr/bin/env python3
"""Read-only v2 DEMO render gate. Never fills review observations or changes PASS."""

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

from pathlib import Path
import argparse,json
from audit_visual_plan import audit
from build_academic_figure_asset_index import safe,write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',type=Path,default=Path('.'))
    p.add_argument('--runtime',choices=['codex','claude'],required=True)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();root=a.project_root.resolve()
    result=audit(safe(root,str(a.plan)),'render',root,None,allow_demo=True,runtime=a.runtime)
    write_json(safe(root,str(a.report)),result)
    print(json.dumps({'status':result['status'],'failures':result['failures']},ensure_ascii=False))
    return int(result['status']!='PASS')
if __name__ == '__main__':
    raise SystemExit(main())
