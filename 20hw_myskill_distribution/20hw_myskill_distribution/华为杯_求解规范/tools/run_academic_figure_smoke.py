#!/usr/bin/env python3
"""Compatibility entrypoint for v2 execution. Use run_academic_figure.py arguments.

The retired v1 --stage prepare/render workflow no longer writes review records.
For DEMO runs pass an explicit runtime, plan, figure-id and --allow-demo.
"""

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

from run_academic_figure import main
if __name__ == '__main__':
    raise SystemExit(main())
