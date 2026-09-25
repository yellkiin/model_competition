"""Project-local defaults. The desktop source is read-only external input."""
from __future__ import annotations
from pathlib import Path
from common import read

DEFAULT_DATA_ROOT = r'C:\Users\LEGION\Desktop\数据'


def project_paths(project='.', home=None, repo=None, data_root=None):
    project = Path(project).expanduser().resolve()
    def local(value, default):
        p = Path(value).expanduser() if value else project / default
        return (p if p.is_absolute() else project / p).resolve()
    agent = local(home, 'ORION_Paper_Agent')
    cache = local(repo, '.orion_paper_cache/repository')
    # Never interpret the Windows default as a relative directory on other OSes.
    source = str(data_root) if data_root is not None else DEFAULT_DATA_ROOT
    return dict(project_root=str(project), agent_root=str(agent), repo_cache=str(cache),
                local_data_root=source)


def session_home(project='.', home=None):
    return Path(project_paths(project, home=home)['agent_root'])


def template_candidates(project='.', explicit=None):
    root = Path(project).resolve()
    candidates = [Path(explicit).resolve()] if explicit else []
    candidates += [root, root/'20hw_myskill_distribution',
                   root/'20hw_myskill_distribution/20hw_myskill_distribution']
    seen = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if (p/'AGENTS.md').is_file() and (p/'华为杯_求解规范/tools/workshop.py').is_file():
            yield p


def load_session(home):
    return read(Path(home)/'.orion_paper/SESSION.json')
