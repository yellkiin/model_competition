import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("paper_library", Path(__file__).with_name("library.py"))
library = importlib.util.module_from_spec(spec)
spec.loader.exec_module(library)


class LibraryTests(unittest.TestCase):
    def test_safe_names(self):
        for value in ["../a.pdf", "/a.pdf", "C:a.pdf", "a\\b.pdf", ""]:
            with self.assertRaises(ValueError):
                library.safe_member(value)
        library.safe_member("2023/A/A23100070049.pdf")

    def test_reject_html(self):
        with self.assertRaises(ValueError):
            library.validate_pdf(b"<html>Not PDF</html>", {}, False)

    def test_pdf_hash_validation(self):
        data = b"%PDF-1.4\nfixture\n%%EOF\n"
        record = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                  "git_blob_sha": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
        library.validate_pdf(data, record, False)
        record["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            library.validate_pdf(data, record, False)

    def test_missing_parser_is_not_success(self):
        data = b"%PDF-1.4\nfixture\n%%EOF\n"
        record = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                  "git_blob_sha": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
        with patch.object(library.shutil, "which", return_value=None):
            with self.assertRaises(ValueError):
                library.validate_pdf(data, record, True)

    def test_no_overwrite(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "manifest.json").write_text(json.dumps({"archive": {"file": "a.zip"}}))
            (root / "a.zip").write_bytes(b"keep")
            with patch.object(library, "validate_index"):
                with self.assertRaises(FileExistsError):
                    library.download(root)
            self.assertEqual((root / "a.zip").read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
