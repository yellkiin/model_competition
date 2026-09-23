"""Run the documented output-only physical-model adaptation."""
from pathlib import Path
import runpy
import sys

RUNTIME = Path(__file__).resolve().parent/'runtime'
sys.path.insert(0, str(RUNTIME))
module = sys.argv.pop(1)
if module not in ('d_experiments', 'd_data'):
    raise ValueError('Expected d_experiments or d_data')
runpy.run_module('research_fd.'+module, run_name='__main__')
