"""Create a NEW PR42 SOURCE_PROFILE with one pinned theory source.

Only the output JSON is written. Existing sources, active_publication, algorithm
and result selections remain unchanged. No network, sync, solving or installation.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys


def extend(profile: dict, commit: str, source_id: str = 'theory_pr38_v1') -> dict:
    if not isinstance(profile, dict) or profile.get('schema') != 1:
        raise ValueError('Expected the inspected PR42 SOURCE_PROFILE schema 1')
    if profile.get('repository') != 'yellkiin/model_competition':
        raise ValueError('Unexpected source repository')
    if not re.fullmatch(r'[0-9a-fA-F]{40}', commit):
        raise ValueError('Resolve the theory branch to an immutable 40-character commit first')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', source_id):
        raise ValueError('Invalid source id')
    sources = profile.get('sources')
    if not isinstance(sources, list) or any(not isinstance(s, dict) for s in sources):
        raise ValueError('Expected a list of source objects')
    item = {
        'id': source_id, 'ref': commit.lower(), 'paths': ['paper_a_theory'],
        'required': True, 'text_only': True,
        'role': 'mandatory theory input before manuscript drafting; not a result publication',
    }
    existing = [s for s in sources if s.get('id') == source_id]
    if existing:
        if len(existing) == 1 and existing[0] == item:
            return deepcopy(profile)
        raise ValueError('Theory source id already has different settings; reconcile in a new local profile explicitly')
    result = deepcopy(profile)
    result['sources'].append(item)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--theory-commit', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--source-id', default='theory_pr38_v1')
    args = p.parse_args()
    try:
        source = args.profile.resolve()
        target = args.out.resolve()
        if source == target:
            raise ValueError('Use a new local profile filename, not the original profile')
        profile = json.loads(source.read_text(encoding='utf-8-sig'))
        result = extend(profile, args.theory_commit, args.source_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(target)
        print('Existing publication and source selections preserved; run PR42 sync with this new profile.')
        return 0
    except (OSError, ValueError) as exc:
        print(f'Profile extension stopped: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
