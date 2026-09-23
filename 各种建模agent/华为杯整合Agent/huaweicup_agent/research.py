"""公开文献元数据检索与人工核验后的入库；搜索命中不等于读过原文。"""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .core import Workspace, stamp, validate_sources


def search_crossref(query: str, limit: int = 8, opener=urlopen) -> list[dict]:
    """固定 HTTPS 主机，不获取任意用户 URL；不传赛题附件或秘密。"""
    if not query.strip() or len(query) > 500 or not 1 <= limit <= 20:
        raise ValueError("query 需为 1–500 字；limit 需为 1–20")
    url = "https://api.crossref.org/works?" + urlencode({"query.bibliographic": query, "rows": limit})
    request = Request(url, headers={"User-Agent": "HuaweiCupWorkbench/0.1 (metadata research)"})
    with opener(request, timeout=20) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("元数据响应超出大小限制")
    items = json.loads(raw)["message"]["items"]
    return [{"id": f"candidate_{i + 1}", "title": (r.get("title") or ["无题名"])[0],
             "doi": r.get("DOI", ""), "url": r.get("URL", ""),
             "read_status": "metadata", "verified_by": "", "locator": "",
             "retrieved_at": stamp(), "kind": "paper"} for i, r in enumerate(items)]


def add_source(ws: Workspace, source: dict) -> None:
    current = ws.read("sources.json")
    errors = validate_sources(current + [source])
    if errors:
        raise ValueError("; ".join(errors))
    ws.write("sources.json", current + [source])


def eligible_sources(ws: Workspace) -> list[dict]:
    """只有已定位且有人复核的非目录来源可被自动写作引用。"""
    sources = ws.read("sources.json")
    errors = validate_sources(sources)
    if errors:
        raise ValueError("; ".join(errors))
    return [s for s in sources if s.get("read_status") in {"abstract", "fulltext"}
            and s.get("verified_by") and s.get("kind") not in {"directory", "search_result"}]
