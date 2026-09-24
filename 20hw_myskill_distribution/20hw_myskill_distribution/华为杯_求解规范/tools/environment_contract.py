"""Strict environment contracts; bootstrap requires only the Python standard library."""
from __future__ import annotations
import json
import re
from pathlib import Path
from workspace_schema import errors

ENV_DIR = Path(__file__).resolve().parent.parent / '环境'
STATES = ('unexamined', 'satisfied', 'missing', 'installing', 'failed', 'blocked', 'not_applicable', 'unresolved')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate(data, name):
    problems = errors(data, read_json(ENV_DIR / (name + '.schema.json')))
    if problems:
        raise ValueError(name + ': ' + '; '.join(problems[:15]))
    return data


def load_catalog():
    data = validate(read_json(ENV_DIR / '软件目录.json'), '软件目录')
    ids = [p['id'] for p in data['providers']]
    caps = [c['id'] for c in data['capabilities']]
    if len(set(ids)) != len(ids) or len(set(caps)) != len(caps):
        raise ValueError('Duplicate capability/provider')
    for cap in data['capabilities']:
        if not set(cap['providers']) <= set(ids):
            raise ValueError('Unknown provider')
    for p in data['providers']:
        if p['artifact'] is not None:
            artifact_schema = read_json(ENV_DIR / '软件目录.schema.json')['properties']['python']['properties']['artifact']
            if errors(p['artifact'], artifact_schema):
                raise ValueError('Invalid download artifact')
        for pkg in p['packages']:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*(?:(?:==|>=|<=|<|>|~=)[0-9][A-Za-z0-9.*+-]*(?:,(?:==|>=|<=|<|>|~=)[0-9][A-Za-z0-9.*+-]*)*)?', pkg['requirement']):
                raise ValueError('Unsafe package requirement')
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', pkg['module']):
                raise ValueError('Unsafe module')
    return data


def validate_needs(data):
    validate(data, '软件需求')
    ids = [r['capability'] for r in data['requirements']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate requirement')
    return data


def active(row):
    return row['necessity'] == 'required' or (row['necessity'] == 'conditional' and row['enabled'])


def merge_needs(current, additions):
    validate_needs(additions)
    by_id = {r['capability']: dict(r) for r in current['requirements']}
    for row in additions['requirements']:
        prior = by_id.get(row['capability'])
        if prior and row != prior:
            row = dict(row, sources=list(dict.fromkeys(prior['sources'] + row['sources'])))
        by_id[row['capability']] = row
    return validate_needs({'schema_version': '1.0', 'requirements': list(by_id.values())})
