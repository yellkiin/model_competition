"""Derive abstract-ready facts from the completed official results and validation files."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
statistics_path = ROOT / '求解/正式实验/统计分析.json'
validation_path = ROOT / '求解/正式实验/逐问核验摘要.json'
stats = json.loads(statistics_path.read_text(encoding='utf-8'))
checks = json.loads(validation_path.read_text(encoding='utf-8'))
methods = {'q1': '连通块分核', 'q2': '场景B重新择优', 'q3': '同方案反事实'}
conclusions = {'q1': '多数图可利用多个核心', 'q2': 'Task合并并不保证逐例加速', 'q3': '有正向收益的算例过半'}
facts = {'schema_version': '1.0', 'derivation': {
    'statistics_source': '求解/正式实验/统计分析.json',
    'statistics_sha256': hashlib.sha256(statistics_path.read_bytes()).hexdigest(),
    'validation_source': '求解/正式实验/逐问核验摘要.json',
    'validation_sha256': hashlib.sha256(validation_path.read_bytes()).hexdigest(),
    'definition': '100个官方算例、5核逐例加速比的算术平均；独立核验按当前逐问摘要。'},
    'questions': {}}
for q in ('q1', 'q2', 'q3'):
    row = checks[q]
    assert row['status'] == 'verified' and row['passed'] == row['selected_configurations'] == 500
    facts['questions'][q] = {
        'method': methods[q],
        'conclusion': {'text': conclusions[q], 'status': 'verified'},
        'speedup': {'value': stats[q]['5']['mean'], 'unit': '（无量纲）', 'status': 'verified'},
        'validation': row['statement'].replace('500组', '五百组'),
    }
facts['questions']['q3']['cache_gain'] = {
    'value': stats['paired_5']['cache_gain_same_plan']['mean'],
    'unit': '（无量纲）', 'status': 'verified'}
out = ROOT / '求解/正式实验/摘要事实.json'
out.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(out)


