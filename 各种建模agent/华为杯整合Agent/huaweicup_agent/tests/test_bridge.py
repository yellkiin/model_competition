"""迁移入口与参考路由的离线回归；不运行第三方代码。"""
import csv
import tempfile
import unittest
from pathlib import Path
from huaweicup_agent.bridge import GUIDES, LIBRARY, guide_records, paper_records
from huaweicup_agent.core import initialize
from huaweicup_agent.workflow import task_prompt


class BridgeTests(unittest.TestCase):
    def test_all_eight_roles(self):
        self.assertEqual(len(GUIDES), 8)
        self.assertTrue(all(GUIDES.values()))

    def test_unknown_role(self):
        with self.assertRaises(ValueError):
            guide_records("invented")

    def test_missing_and_present(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            relative = GUIDES["researcher"][0]
            file = root / relative
            file.parent.mkdir(parents=True)
            file.write_text("guide", encoding="utf-8")
            entries = guide_records("researcher", root)
            self.assertTrue(entries[0]["exists"])
            self.assertEqual(len(entries[0]["sha256"]), 64)
            self.assertFalse(entries[1]["exists"])
            self.assertFalse(entries[0]["execute"])

    def test_paper_filter_preserves_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            directory = root / LIBRARY
            directory.mkdir(parents=True)
            fields = ["年份", "题号", "论文/队伍编号", "下载状态", "压缩包", "压缩包内路径", "SHA256", "奖项核验", "说明"]
            with (directory / "index_match.csv").open("w", encoding="utf-8-sig", newline="") as out:
                writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerow(dict(zip(fields, ["2025", "A", "title", "not_downloaded", "", "", "", "未核验", "无全文"])))
            found = paper_records(2025, "A", root)
            self.assertEqual(found[0]["status"], "not_downloaded")
            self.assertIsNone(found[0]["archive"])
            self.assertEqual(paper_records(2023, "C", root), [])

    def test_task_embeds_real_guides_not_completion(self):
        with tempfile.TemporaryDirectory() as d:
            ws = initialize(Path(d) / "workspace")
            prompt = task_prompt(ws, "modeler")
            self.assertIn("repository_guides", prompt)
            self.assertIn("host_must_read", prompt)
            self.assertIn("hwb-modeling-ideas", prompt)


if __name__ == "__main__":
    unittest.main()
