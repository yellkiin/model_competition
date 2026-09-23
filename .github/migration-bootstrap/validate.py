"""One-time target-repository validation; no upstream Agent or problem data execution."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest

root = Path.cwd().resolve()
agent = root / '各种建模agent/华为杯整合Agent'
lib = root / '各种建模agent/hwb-math-modeling-skills/数模资料/优秀论文索引/近期论文原文'
sys.path.insert(0, str(agent))
report = {'repository': 'yellkiin/model_competition', 'base_commit': 'f48de9dde7f8b7eb028c01824c3521e3662f06a6', 'python': platform.python_version(), 'workflow_run': os.environ.get('GITHUB_RUN_ID'), 'unit_tests': []}
for directory, pattern in [(agent / 'huaweicup_agent/tests', 'test_*.py'), (lib, 'test_library.py')]:
    suite = unittest.TestLoader().discover(str(directory), pattern=pattern)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report['unit_tests'].append({'directory': str(directory.relative_to(root)), 'run': result.testsRun, 'skipped': [reason for _, reason in result.skipped], 'failures': len(result.failures), 'errors': len(result.errors)})
    assert result.wasSuccessful(), 'Unit tests failed'
from huaweicup_agent.bridge import GUIDES, guide_records, paper_records
report['role_guides'] = {role: guide_records(role) for role in GUIDES}
assert all(item['exists'] for items in report['role_guides'].values() for item in items), report['role_guides']
subprocess.run([sys.executable, str(lib / 'library.py'), '--download', '--write-report'], check=True)
report['paper_library'] = json.loads((lib / 'verification.json').read_text())
assert len(paper_records()) == 103
assert sum(p['status'] == 'downloaded' for p in paper_records()) == 12
with tempfile.TemporaryDirectory() as tmp:
    work = str(Path(tmp) / 'demo')
    subprocess.run([sys.executable, 'tools/huaweicup.py', 'demo', work], check=True)
    subprocess.run([sys.executable, 'tools/huaweicup.py', 'audit', work], check=True)
    rejected = subprocess.run([sys.executable, 'tools/huaweicup.py', 'audit', work, '--final'])
    assert rejected.returncode != 0, 'Synthetic draft must not pass final audit'
report['demo'] = 'executed synthetic experiment, plot, TeX source and audit; final audit rejected rehearsal'
report['remote_tex_compile'] = 'not run; local XeLaTeX migration rehearsal compiled and rendered separately'
report['status'] = 'passed'
report['limitations'] = ['No actual LLM contest solve', 'No live Crossref fact verification', 'No upstream backend execution', 'No 2024/2025 full PDFs', 'No independent award verification']
(agent / 'huaweicup_agent/docs/repository_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
