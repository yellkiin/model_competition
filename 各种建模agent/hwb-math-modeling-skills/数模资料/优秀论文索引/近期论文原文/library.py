"""核验或重取固定版本的12篇PDF。默认只检查，不改索引，不解压到仓库。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import urllib.request
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
INDEX_FIELDS = ["年份", "题号", "论文/队伍编号", "培养单位代码(编号解析)", "来源"]
SOURCE_PREFIX = "https://raw.githubusercontent.com/zhanwen/MathModel/cd5be91735ebf11d5ee52eb170e86a6d07131977/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_member(name: str) -> None:
    parts = PurePosixPath(name)
    if not name or parts.is_absolute() or ".." in parts.parts or "\\" in name or ":" in name:
        raise ValueError("非法ZIP相对路径")


def validate_pdf(data: bytes, record: dict, check_pages: bool = True) -> None:
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
        raise ValueError("不是完整PDF")
    if len(data) != record["bytes"] or sha256(data) != record["sha256"]:
        raise ValueError("PDF大小或SHA256不符")
    git_hash = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if git_hash != record["git_blob_sha"]:
        raise ValueError("源Git blob不符")
    if check_pages:
        executable = shutil.which("pdfinfo")
        if executable is None:
            raise ValueError("缺少pdfinfo；安装poppler-utils后再核验页数")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            path.write_bytes(data)
            result = subprocess.run([executable, str(path)], capture_output=True,
                                    text=True, timeout=30, check=True)
        count = next((int(line.split(":", 1)[1]) for line in result.stdout.splitlines()
                      if line.startswith("Pages:")), None)
        if count != record["pages"]:
            raise ValueError("PDF页数不符")


def validate_index(root: Path, manifest: dict) -> None:
    original = root.parent / "优秀论文索引.csv"
    raw = original.read_bytes()
    if sha256(raw) != manifest["index"]["sha256"]:
        raise ValueError("现有论文索引与迁移源版本不同；必须先重新对齐，不能覆盖")
    with original.open(encoding="utf-8-sig", newline="") as stream:
        originals = list(csv.DictReader(stream))
    expected = {}
    for number, row in enumerate(originals, 2):
        if int(row["年份"]) in manifest["recent_years"]:
            key = (row["年份"], row["题号"], row["论文/队伍编号"])
            if key in expected:
                raise ValueError("原始索引有重复身份")
            expected[key] = (number, row)
    with (root / "index_match.csv").open(encoding="utf-8-sig", newline="") as stream:
        matches = list(csv.DictReader(stream))
    if len(matches) != len(expected) or len(matches) != 103:
        raise ValueError("近年索引计数不符")
    papers = {r["paper_id"]: r for r in manifest["papers"]}
    seen = set()
    for row in matches:
        key = (row["年份"], row["题号"], row["论文/队伍编号"])
        if key not in expected or key in seen:
            raise ValueError("对照表身份错误/重复")
        seen.add(key)
        number, source = expected[key]
        if int(row["上游CSV行号"]) != number or any(row[f] != source[f] for f in INDEX_FIELDS):
            raise ValueError("索引行号或内容不符")
        paper = papers.get(key[2])
        if paper is None:
            if row["下载状态"] != "not_downloaded" or row["压缩包内路径"] or row["SHA256"]:
                raise ValueError("未下载记录被错误标成已有全文")
        elif (row["下载状态"] != "downloaded" or row["压缩包内路径"] != paper["archive_member"]
              or row["SHA256"] != paper["sha256"] or row["压缩包"] != manifest["archive"]["file"]):
            raise ValueError("PDF与索引映射不符")


def verify(root: Path = ROOT, check_index: bool = True, check_pages: bool = True) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    safe_member(manifest["archive"]["file"])
    archive = root / manifest["archive"]["file"]
    data = archive.read_bytes()
    if len(data) != manifest["archive"]["bytes"] or sha256(data) != manifest["archive"]["sha256"]:
        raise ValueError("ZIP字节数或SHA256不符")
    papers = manifest["papers"]
    expected = {r["archive_member"]: r for r in papers}
    if len(expected) != 12 or len({r["sha256"] for r in papers}) != 12:
        raise ValueError("论文重复或数量不符")
    with ZipFile(archive) as z:
        if len(z.namelist()) != 12 or set(z.namelist()) != set(expected):
            raise ValueError("ZIP清单不符")
        for info in z.infolist():
            safe_member(info.filename)
            record = expected[info.filename]
            if info.file_size != record["bytes"]:
                raise ValueError("ZIP条目大小不符")
            validate_pdf(z.read(info), record, check_pages)
        if z.testzip() is not None:
            raise ValueError("ZIP CRC不符")
    if check_index:
        validate_index(root, manifest)
    return {"status": "passed", "paper_count": 12, "physical_pages": sum(r["pages"] for r in papers),
            "archive_sha256": manifest["archive"]["sha256"], "archive_bytes": len(data),
            "local_index_checked": check_index, "pdf_pages_checked": check_pages,
            "reading_status": "integrity_only_not_fulltext_reviewed",
            "award_status": "not_independently_verified"}


def download(root: Path = ROOT) -> None:
    """从清单锁定的公共源重取；拒绝覆盖。只运行本脚本，不执行下载的内容。"""
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    validate_index(root, manifest)
    safe_member(manifest["archive"]["file"])
    target = root / manifest["archive"]["file"]
    if target.exists():
        raise FileExistsError("论文包已存在；用 --verify-only 核验，不覆盖")
    with tempfile.TemporaryDirectory(dir=root) as temp:
        candidate = Path(temp) / "papers.zip"
        with ZipFile(candidate, "w", compression=ZIP_DEFLATED, compresslevel=6) as z:
            for record in manifest["papers"]:
                if not record["source_url"].startswith(SOURCE_PREFIX):
                    raise ValueError("不在固定公共来源内")
                with urllib.request.urlopen(record["source_url"], timeout=45) as response:
                    data = response.read(record["bytes"] + 1)
                validate_pdf(data, record)
                safe_member(record["archive_member"])
                info = ZipInfo(record["archive_member"], (2026, 9, 23, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 2175008768
                z.writestr(info, data, compresslevel=6)
        result = candidate.read_bytes()
        if sha256(result) != manifest["archive"]["sha256"] or len(result) != manifest["archive"]["bytes"]:
            raise ValueError("重建论文包与原迁移包不同，不发布")
        # 仅创建，不覆盖竞态中出现的已有文件。
        with target.open("xb") as stream:
            stream.write(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--verify-only", action="store_true")
    modes.add_argument("--download", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    if args.download:
        download()
    report = verify()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.write_report:
        (ROOT / "verification.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
