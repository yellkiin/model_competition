"""Read BibTeX's actual file-open trace, including inputs absent from XeLaTeX .fls.

TeX Live/Kpathsea emits this trace with KPATHSEA_DEBUG=4. A bibliography run
without an understood trace is not evidence of its inputs and fails closed.
No bibliography metadata or scientific relevance is certified here.
"""
from __future__ import annotations

import re
from pathlib import Path

from build_academic_figure_asset_index import sha


def auxiliary_inputs(main: Path) -> set[Path]:
    """Follow the generated AUX chain using the same working directory as TeX."""
    cwd = main.parent.resolve()
    visited: set[Path] = set()

    def visit(path: Path, stack: set[Path]) -> None:
        path = path.resolve()
        if path in stack:
            raise ValueError('Cyclic auxiliary input: ' + str(path))
        if path in visited:
            return
        text = path.read_text(encoding='utf-8-sig')
        visited.add(path)
        for raw in re.findall(r'\\@input\s*\{([^{}]+)\}', text):
            visit(cwd / raw, stack | {path})

    visit(main.with_suffix('.aux'), set())
    return visited


def bibliography_requested(main: Path) -> bool:
    return any(re.search(r'\\bibdata\s*\{', p.read_text(encoding='utf-8-sig'))
               for p in auxiliary_inputs(main))


def read_open_trace(text: str, cwd: Path) -> list[Path]:
    """Accept successful read opens; ignore searches, failed opens and writes.

    Windows TeX Live's fsyscp wrapper appends a codepage annotation (normally
    ` []`) to the path. POSIX Kpathsea reports a plain fopen path instead.
    Greedy filename capture keeps spaces, commas and parentheses in paths.
    """
    paths = []
    pattern = re.compile(
        r'^kdebug:(?P<api>fsyscp_)?x?fopen\((?P<path>.*), '
        r'(?P<mode>r[b+]*)\) => (?P<handle>\S+)\s*$')
    for line in text.splitlines():
        match = pattern.fullmatch(line.strip())
        if not match or match['handle'].lower() in {'0', '0x0', '(nil)', 'null'}:
            continue
        raw = match['path']
        if match['api']:
            # The annotation is emitted by fsyscp_fopen, not part of the name.
            raw = re.sub(r' \[[^\[\]]*\]$', '', raw)
        path = Path(raw.strip('"'))
        path = (cwd / path).resolve() if not path.is_absolute() else path.resolve()
        if path.suffix.lower() in {'.bib', '.bst'} and path not in paths:
            paths.append(path)
    return paths


def bibliography_inputs(root: Path, main: Path, trace_path: Path) -> list[dict]:
    root = root.resolve()
    paths = read_open_trace(trace_path.read_text(encoding='utf-8-sig'), main.parent)
    styles = [p for p in paths if p.suffix.lower() == '.bst']
    databases = [p for p in paths if p.suffix.lower() == '.bib']
    if len(styles) != 1 or not databases:
        raise ValueError('Missing BibTeX file-open evidence; use a BibTeX build '
                         'supporting KPATHSEA_DEBUG=4 and recompile')
    blg = main.with_suffix('.blg').read_text(encoding='utf-8-sig')
    declared_styles = re.findall(r'^The style file: (.+)\s*$', blg, re.M)
    declared_databases = re.findall(r'^Database file #\d+: (.+)\s*$', blg, re.M)
    for declared, opened in ((declared_styles, styles), (declared_databases, databases)):
        if len(declared) != len(opened):
            raise ValueError('BibTeX log and actual opened inputs differ')
        for raw, actual in zip(declared, opened):
            label = Path(raw.strip().strip('"'))
            # BLG often uses the requested basename, even when Kpathsea found
            # it elsewhere. A path-qualified label must match that full path.
            if (label.name.casefold() != actual.name.casefold() or
                    (label.parent != Path('.') and (main.parent / label).resolve() != actual)):
                raise ValueError('BibTeX log/input mismatch: ' + raw)
    return [{'path': p.relative_to(root).as_posix() if p.is_relative_to(root) else p.as_posix(),
             'scope': 'project' if p.is_relative_to(root) else 'external',
             'kind': 'database' if p.suffix.lower() == '.bib' else 'style',
             'sha256': sha(p)} for p in paths]


def input_paths(root: Path, rows: list[dict]) -> set[Path]:
    result = set()
    for row in rows:
        path = Path(row['path'])
        if row['scope'] == 'project':
            path = (root / path).resolve()
            path.relative_to(root.resolve())
        elif row['scope'] == 'external' and path.is_absolute():
            path = path.resolve()
            if path.is_relative_to(root.resolve()):
                raise ValueError('Local bibliography input marked external')
        else:
            raise ValueError('Invalid bibliography input scope/path')
        result.add(path)
    return result


def generated_outputs(root: Path, main: Path) -> dict[str, str]:
    paths = auxiliary_inputs(main)
    paths.update(p for suffix in ('.gmcmlayout', '.gmcmprose', '.gmcmevaluation', '.bbl', '.blg')
                 if (p := main.with_suffix(suffix)).is_file())
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(paths)}
