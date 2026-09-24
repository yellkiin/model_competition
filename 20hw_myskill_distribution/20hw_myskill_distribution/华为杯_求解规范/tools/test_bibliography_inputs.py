"""Behavior tests for actual bibliography inputs, not bibliography truth claims."""
import tempfile
import unittest
from pathlib import Path

from bibliography_inputs import (auxiliary_inputs, bibliography_inputs,
                                 bibliography_requested, generated_outputs,
                                 input_paths, read_open_trace)


class BibliographyInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.main = self.root / 'paper.tex'
        self.main.write_text('isolated test', encoding='utf-8')
        self.main.with_suffix('.aux').write_text('\\bibdata{reference}\n', encoding='utf-8')
        self.bib = self.root / 'reference.bib'
        self.bib.write_text('% non-scientific fixture\n', encoding='utf-8')
        self.bst = self.root / 'gmcm.bst'
        self.bst.write_text('% style fixture\n', encoding='utf-8')
        self.main.with_suffix('.blg').write_text(
            'The style file: gmcm.bst\nDatabase file #1: reference.bib\n', encoding='utf-8')
        self.trace = self.root / 'trace.log'
        self.trace.write_text(
            'kdebug:fsyscp_xfopen(gmcm.bst [], rb) => 0x123\n'
            'kdebug:fsyscp_xfopen(reference.bib [], rb) => 0x456\n', encoding='utf-8')

    def test_exact_opened_inputs_and_hash_change(self):
        rows = bibliography_inputs(self.root, self.main, self.trace)
        self.assertEqual([r['path'] for r in rows], ['gmcm.bst', 'reference.bib'])
        self.assertEqual(input_paths(self.root, rows), {self.bst, self.bib})
        self.bib.write_text('% changed\n', encoding='utf-8')
        self.assertNotEqual(rows, bibliography_inputs(self.root, self.main, self.trace))

    def test_search_or_failed_open_is_not_read_evidence(self):
        self.trace.write_text('kdebug:returning from search(reference.bib) => ./reference.bib\n'
            'kdebug:fopen(reference.bib, r) => (nil)\n'
            'kdebug:fopen(gmcm.bst, r) => 0x0\n'
            'kdebug:fopen(reference.bib, wb) => 0x123\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Missing BibTeX'):
            bibliography_inputs(self.root, self.main, self.trace)

    def test_missing_database_trace_fails(self):
        self.trace.write_text('kdebug:fopen(gmcm.bst, r) => 0x123\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            bibliography_inputs(self.root, self.main, self.trace)

    def test_multiple_databases_and_missing_one_fails(self):
        second = self.root / 'extra.bib'
        second.write_text('% additional database\n', encoding='utf-8')
        with self.main.with_suffix('.blg').open('a', encoding='utf-8') as f:
            f.write('Database file #2: extra.bib\n')
        with self.assertRaisesRegex(ValueError, 'differ'):
            bibliography_inputs(self.root, self.main, self.trace)
        with self.trace.open('a', encoding='utf-8') as f:
            f.write('kdebug:fopen(extra.bib, r) => 0x789\n')
        self.assertEqual(len(bibliography_inputs(self.root, self.main, self.trace)), 3)

    def test_trace_handles_spaces_commas_parentheses_and_windows_annotation(self):
        for name in ('directory (x), y/my file.bib', '中文目录/资料.bib', 'a [b].bst'):
            actual = self.root / name
            for api, suffix in (('fopen', ''), ('fsyscp_xfopen', ' []')):
                text = f'kdebug:{api}({name}{suffix}, rb) => 0x123\n'
                self.assertEqual(read_open_trace(text, self.root), [actual])

    def test_external_database_records_actual_absolute_path(self):
        with tempfile.TemporaryDirectory() as external:
            path = Path(external).resolve() / 'reference.bib'
            path.write_text('% external input\n', encoding='utf-8')
            self.trace.write_text('kdebug:fopen(gmcm.bst, r) => 0x1\n'
                                 f'kdebug:fopen({path.as_posix()}, r) => 0x2\n', encoding='utf-8')
            rows = bibliography_inputs(self.root, self.main, self.trace)
            self.assertEqual(rows[1]['scope'], 'external')
            self.assertEqual(rows[1]['path'], path.as_posix())
            self.assertEqual(input_paths(self.root, rows), {self.bst, path})

    def test_missing_or_mismatched_inputs_fail(self):
        self.main.with_suffix('.blg').write_text(
            'The style file: gmcm.bst\nDatabase file #1: wrong.bib\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            bibliography_inputs(self.root, self.main, self.trace)
        self.main.with_suffix('.blg').write_text(
            'The style file: gmcm.bst\nDatabase file #1: reference.bib\n', encoding='utf-8')
        self.bib.unlink()
        with self.assertRaises(OSError):
            bibliography_inputs(self.root, self.main, self.trace)

    def test_nested_aux_bibliography_and_hashes(self):
        self.main.with_suffix('.aux').write_text('\\@input{child.aux}\n', encoding='utf-8')
        child = self.root / 'child.aux'
        child.write_text('\\bibdata{reference}\n', encoding='utf-8')
        self.assertTrue(bibliography_requested(self.main))
        before = generated_outputs(self.root, self.main)
        self.assertIn('child.aux', before)
        child.write_text('\\bibdata{other}\n', encoding='utf-8')
        self.assertNotEqual(before, generated_outputs(self.root, self.main))

    def test_missing_and_cyclic_aux_fail(self):
        self.main.with_suffix('.aux').write_text('\\@input{missing.aux}\n', encoding='utf-8')
        with self.assertRaises(OSError):
            auxiliary_inputs(self.main)
        self.main.with_suffix('.aux').write_text('\\@input{paper.aux}\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            auxiliary_inputs(self.main)

    def test_prose_measurement_streams_are_bound_to_compile_evidence(self):
        for suffix in ('.gmcmprose', '.gmcmevaluation'):
            path = self.main.with_suffix(suffix)
            path.write_text('format|18pt|702pt|455pt|12\n', encoding='utf8')
            before = generated_outputs(self.root, self.main)
            self.assertIn(path.name, before)
            path.write_text('tampered measurement\n', encoding='utf8')
            self.assertNotEqual(before, generated_outputs(self.root, self.main))

    def test_no_bibtex_manual_bibliography(self):
        self.main.with_suffix('.aux').write_text('\\bibcite{key}{1}\n', encoding='utf-8')
        self.assertFalse(bibliography_requested(self.main))

    def test_forged_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            input_paths(self.root, [{'path': '../outside.bib', 'scope': 'project'}])
        with self.assertRaises(ValueError):
            input_paths(self.root, [{'path': self.bib.as_posix(), 'scope': 'external'}])


if __name__ == '__main__':
    unittest.main()
