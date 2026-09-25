"""Exercise PR42's actual read-only source sync and package_inputs interface.

Run in a disposable authorised Git checkout (the packaging workflow). Fetches
only fixed source objects, the original question/config and our theory directory.
No workshop is started; no solver, evaluator, templates or manuscripts are run.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from extend_workbench_profile import extend

PEER = 'eb2bb14d67a8d2770e276b77411f779f43f94b49'
PROBLEM = '题目/A题/通用神经网络处理器下的多核调度问题.docx'
CONFIG = '题目/A题/通用神经网络处理器下的多核调度问题  附件/data/config.txt'


def git(repo: Path, *args: str) -> bytes:
    p = subprocess.run(['git', '-C', str(repo), *args], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    return p.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    current = git(repo, 'rev-parse', 'HEAD').decode().strip()
    try:
        git(repo, 'cat-file', '-e', PEER + '^{commit}')
    except subprocess.CalledProcessError:
        git(repo, 'fetch', '--filter=blob:none', '--depth=1', '--no-tags', 'origin', PEER)
    with tempfile.TemporaryDirectory(prefix='theory-pr42-interface-') as td:
        root = Path(td)
        modules = root / 'fixed_pr42_modules'
        modules.mkdir()
        for name in ('common.py', 'sources.py', 'install.py'):
            (modules / name).write_bytes(git(repo, 'show', PEER + ':paper_a_workbench/' + name))
        sys.path.insert(0, str(modules))
        sources = importlib.import_module('sources')
        installer = importlib.import_module('install')
        home = root / 'temporary_paper_home'
        home.mkdir()
        # PR42 installation creates this folder before package_inputs is used.
        (home / '题目').mkdir()
        agents = home / 'AGENTS.md'
        agents.write_text('preserved synthetic agent entry\n', encoding='utf-8')
        original_agents = agents.read_bytes()
        profile = {
            'schema': 1, 'repository': 'yellkiin/model_competition', 'batch_size': 4,
            'active_publication': None, 'method_selection': 'preserve existing method choice',
            'sources': [
                {'id': 'problem', 'ref': PEER, 'paths': [PROBLEM], 'required': True},
                {'id': 'official_config', 'ref': PEER, 'paths': [CONFIG], 'required': True},
            ],
        }
        old = deepcopy(profile)
        augmented = extend(profile, current)
        assert profile == old and augmented['sources'][:-1] == profile['sources']
        assert augmented['active_publication'] == profile['active_publication']
        assert augmented['method_selection'] == profile['method_selection']
        p = root / 'SOURCE_PROFILE.with_theory.json'
        p.write_text(json.dumps(augmented, ensure_ascii=False, indent=2), encoding='utf-8')
        lock, snapshot = sources.sync(repo, p, home, fetch=False, metadata_only=False, workers=1, lfs=False)
        assert not lock['errors']
        assert all(row['status'] == 'present' for row in lock['files'])
        for row in lock['files']:
            if row['source'] == 'theory_pr38_v1':
                assert row['revision'] == current
        packaged = installer.package_inputs(home, snapshot)
        archive = next(Path(f) for f in packaged['inputs'] if f.endswith('.zip'))
        question = next(Path(f) for f in packaged['inputs'] if f.endswith('.docx'))
        with zipfile.ZipFile(archive) as z:
            expected = 'theory_pr38_v1/paper_a_theory/THEORY.md'
            assert expected in z.namelist()
            assert z.read(expected) == git(repo, 'show', current + ':paper_a_theory/THEORY.md')
        assert question.read_bytes() == git(repo, 'show', PEER + ':' + PROBLEM)
        assert agents.read_bytes() == original_agents
        receipt = {
            'status': 'passed', 'peer_workbench_commit': PEER,
            'theory_source_commit': current,
            'source_files_present': len(lock['files']),
            'native_source_path': 'theory_pr38_v1/paper_a_theory/THEORY.md',
            'theory_in_original_workflow_input_zip': True,
            'original_question_copied_exactly': True,
            'original_profile_and_agent_entry_preserved': True,
            'publication_and_method_selection_preserved': True,
            'source_sync_and_package_inputs_executed': True,
            'workshop_started': False, 'new_solver_or_evaluator_calls': 0,
            'scope': 'PR42 native source and input-file routing, not final manuscript or Windows installation',
        }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
