"""Execute a recorded local Python step only inside an explicitly DEMO workspace."""
import argparse
import json
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
    from workspace_context import bounded
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--script', required=True)
    p.add_argument('args', nargs=argparse.REMAINDER)
    a = p.parse_args(); root = Path.cwd().resolve()
    manifest = json.loads((root/'工作区清单.json').read_text(encoding='utf-8-sig'))
    if manifest.get('purpose') != 'demo':
        raise SystemExit('This entry only accepts purpose=demo; it never calls finish.')
    script = bounded(root, a.script)
    script.relative_to(root/'求解')
    if script.suffix != '.py':
        raise SystemExit('Python DEMO source required')
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), *(a.args[1:] if a.args[:1] == ['--'] else a.args)]
    runpy.run_path(str(script), run_name='__main__')
