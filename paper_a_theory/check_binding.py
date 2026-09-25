"""Check theory package wiring in disposable synthetic workspaces.

These are document-installation checks, not ORION tests or experiments. No
original graphs, evaluator or optimisation methods are imported or executed.
"""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
from bind_theory import inspect_binding, install


def git(root: Path, *args: str) -> str:
    done = subprocess.run(['git', '-C', str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=30)
    return done.stdout.decode('utf-8').strip()


def main() -> None:
    checked = []
    with tempfile.TemporaryDirectory(prefix='orion-theory-package-check-') as td:
        root = Path(td)
        repo = root / 'source copy'
        repo.mkdir()
        impl = repo / 'renamed_implementation'
        impl.mkdir()
        (impl / 'entry.py').write_text('# synthetic source; never executed\n', encoding='utf-8')
        git(repo, 'init')
        git(repo, 'config', 'user.name', 'Theory package check')
        git(repo, 'config', 'user.email', 'theory-check@example.invalid')
        git(repo, 'add', 'renamed_implementation/entry.py')
        git(repo, 'commit', '-m', 'Synthetic source for path binding only')
        commit = git(repo, 'rev-parse', 'HEAD')
        (repo / 'original_problem.docx').write_bytes(b'synthetic placeholder, not a problem document')
        (repo / 'official copy').mkdir()
        (repo / 'config.txt').write_text('synthetic configuration, not used', encoding='utf-8')
        (repo / 'literature').mkdir()
        results = repo / 'new_results_location'
        results.mkdir()
        protected = results / 'existing_result.txt'
        protected.write_text('preserve exactly\n', encoding='utf-8')
        workspace = root / 'new paper workspace'
        workspace.mkdir()
        agents = workspace / 'AGENTS.md'
        agents.write_text('existing writing agent must remain unchanged\n', encoding='utf-8')
        legacy = root / 'workshop_v1'
        legacy.mkdir()
        legacy_file = legacy / 'existing_paper.txt'
        legacy_file.write_text('original paper\n', encoding='utf-8')
        before = {p: p.read_bytes() for p in (protected, agents, legacy_file)}
        spec = {
            'schema_version': 1, 'binding_id': 'synthetic-binding',
            'workspace': str(workspace), 'repo_root': str(repo),
            'implementation_root': 'renamed_implementation',
            'implementation_commit': commit, 'source_mode': 'git',
            'implementation_files': ['entry.py'], 'execution_manifest': None,
            'problem_file': 'original_problem.docx', 'official_root': 'official copy',
            'config_file': 'config.txt', 'literature_root': 'literature',
            'result_runs': [{'run_id': 'synthetic-not-an-experiment', 'path': 'new_results_location', 'role': 'main'}],
        }
        binding = inspect_binding(spec, root, commit)
        assert binding['entrypoint_checks'][0]['checked_against_git']
        assert binding['status'] == 'paths_bound_semantic_and_result_review_pending'
        checked.append('explicit relocated source/result roots and selected Git text comparison')
        destination = install(binding, spec)
        assert (destination / 'THEORY_HANDOFF.md').is_file()
        assert (destination / 'package' / 'THEORY.md').is_file()
        assert all(p.read_bytes() == b for p, b in before.items())
        checked.append('new reading input created; AGENTS, old workshop and results preserved')
        try:
            inspect_binding(spec, root, commit)
        except FileExistsError:
            checked.append('existing binding is not overwritten')
        else:
            raise AssertionError('Existing binding must fail closed')
        changed = deepcopy(spec)
        changed['binding_id'] = 'changed-source'
        (impl / 'entry.py').write_text('# changed local file\n', encoding='utf-8')
        try:
            inspect_binding(changed, root, commit)
        except ValueError:
            checked.append('source text that differs from the declared commit is rejected')
        else:
            raise AssertionError('Changed source must not silently pass')
        (impl / 'entry.py').write_text('# synthetic source; never executed\n', encoding='utf-8')
        pending = deepcopy(spec)
        pending['binding_id'] = 'methods-before-results'
        pending['result_runs'] = []
        result = inspect_binding(pending, root, commit)
        assert result['result_runs'] == []
        checked.append('method-only preparation accepts no results and retains review-pending state')
        forbidden = deepcopy(pending)
        forbidden['workspace'] = str(legacy)
        try:
            inspect_binding(forbidden, root, commit)
        except ValueError:
            checked.append('legacy workshop_v1 cannot be the new output workspace')
        else:
            raise AssertionError('Legacy workspace must be preserved')
        assert all(p.read_bytes() == b for p, b in before.items())
    print(json.dumps({
        'status': 'passed', 'checks': checked,
        'scope': 'synthetic document-input installation and preservation only',
        'original_solver_calls': 0, 'original_evaluator_calls': 0,
        'performance_experiments': 0, 'mathematical_or_result_validation': False,
        'native_windows_execution': False,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
