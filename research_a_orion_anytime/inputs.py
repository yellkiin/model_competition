"""Minimal existing-input admission for the Windows run.

The delivered module was empty. This path reuses locally available official
inputs without changing them; it performs no content fingerprints or tests.
Missing inputs fail explicitly instead of being silently accepted.
"""
from pathlib import Path
import time


def ensure(official, cases, archive=None, restore=False, deadline=float('inf')):
    root = Path(official)
    for case in cases:
        if time.time() >= deadline:
            raise TimeoutError('Input loading reached the campaign deadline')
        path = root / 'data' / f'{case}.json'
        try:
            with path.open('rb') as stream:
                prefix = stream.read(128)
        except FileNotFoundError:
            raise FileNotFoundError(f'Required official A input is missing: {path}') from None
        if not prefix.strip() or prefix.startswith(b'version https://git-lfs.github.com/spec/v1'):
            raise FileNotFoundError(f'Required official A input is empty or an LFS pointer: {path}; provide the existing extracted A attachment directory')