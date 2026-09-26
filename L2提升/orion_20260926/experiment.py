"""Portable entry point using the delivered frozen research dependencies."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent / '_frozen'))
    runpy.run_module('research_a_orion_unified.l2_refine_20260926.experiment', run_name='__main__')
