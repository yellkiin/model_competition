"""Compatibility entry point for the independent, fail-closed recorded-data audit.

Historical reports remain unchanged. New runs write to 复审_20260926/数值核验.
"""
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "复审_20260926"))
    from audit_paper_data import main
    raise SystemExit(main())
