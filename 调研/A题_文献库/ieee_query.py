# -*- coding: utf-8 -*-
"""Run a bounded IEEE Xplore metadata/full-text check for A-question literature.

The key is read at runtime from the IEEE_API_KEY environment variable and is
never printed or written to output. Only Open Access records are sent to the
official full-text endpoint.
"""
from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any

import requests


OUT_DIR = Path(__file__).resolve().parent
FULLTEXT_DIR = OUT_DIR / "ieee_fulltext"
SEARCH_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
FULLTEXT_URL = "https://ieeexploreapi.ieee.org/api/v1/search/document/{article_number}/fulltext"

# Each group is deliberately narrow. max_records is kept below the API limit
# so the result remains reviewable and does not become a general web crawl.
QUERY_GROUPS = [
    {
        "id": "memory_constrained_dag",
        "query": '("memory constrained" OR "memory-constrained") AND (DAG OR "directed acyclic graph") AND scheduling',
        "note": "memory-constrained DAG scheduling",
        "start_year": 2018,
        "end_year": 2026,
    },
    {
        "id": "communication_contention",
        "query": '("communication contention" OR "bandwidth contention") AND (scheduling OR "graph scheduling")',
        "note": "communication and shared-bandwidth contention",
        "start_year": 2018,
        "end_year": 2026,
    },
    {
        "id": "acyclic_graph_partitioning",
        "query": '("acyclic partitioning" OR "DAG partitioning") AND (graph OR hypergraph)',
        "note": "acyclic graph partitioning",
        "start_year": 2010,
        "end_year": 2026,
    },
    {
        "id": "neural_network_multicore",
        "query": '("neural network" OR DNN) AND (multicore OR "multi-core") AND scheduling',
        "note": "neural-network multicore scheduling",
        "start_year": 2015,
        "end_year": 2026,
    },
    {
        "id": "tensor_memory_scheduling",
        "query": '("tensor graph" OR "computational graph") AND (memory OR cache) AND scheduling',
        "note": "tensor graph memory/cache scheduling",
        "start_year": 2015,
        "end_year": 2026,
    },
    {
        "id": "npu_accelerator_scheduling",
        "query": '("neural network accelerator" OR NPU) AND ("task scheduling" OR "graph scheduling")',
        "note": "accelerator task/graph scheduling",
        "start_year": 2015,
        "end_year": 2026,
    },
    {
        "id": "hypergraph_partitioning",
        "query": '("hypergraph partitioning") AND (DAG OR acyclic OR scheduling OR communication)',
        "note": "hypergraph partitioning with DAG/communication relevance",
        "start_year": 2010,
        "end_year": 2026,
    },
    {
        "id": "known_a_references",
        "query": '"10.1109/71.993206" OR "10.1109/CCGRID.2017.101" OR "10.1109/TPDS.2005.64" OR "10.1109/TCAD.2021.3059569"',
        "note": "known A01/A02 and contention DOI checks",
        "start_year": None,
        "end_year": None,
    },
]

EXCLUDE_TERMS = (
    "task offloading",
    "computation offloading",
    "mobile cloud",
    "vehicular edge",
    "iot offloading",
    "edge offloading",
    "serverless",
    "datacenter",
    "edge computing",
    "edge-cloud",
    "cloud communication",
    "cloud analytics",
    "function-as-a-service",
    "multi-tenancy",
    "public and private clouds",
    "cloud workflow",
    "offloading",
    "vehicular",
    "v2v",
    "earth observation satellite",
    "container computing",
    "gpu clusters",
    "ai clusters",
    "wireless jamming",
    "containers",
    "edge deployment",
    "edge deployed",
    "sign language",
    "big data applications",
    "matrix completion",
    "quantum circuits",
)
POSITIVE_TERMS = (
    "dag", "directed acyclic", "acyclic", "graph partition", "hypergraph",
    "multicore", "multi-core", "neural network", "dnn", "tensor", "cache",
    "memory", "bandwidth", "communication", "scheduling", "accelerator",
)
KNOWN_A_DOIS = {
    "10.1109/71.993206".lower(),
    "10.1109/CCGRID.2017.101".lower(),
    "10.1109/TPDS.2005.64".lower(),
    "10.1109/TCAD.2021.3059569".lower(),
}


def _api_key() -> str:
    return os.environ.get("IEEE_API_KEY", "")


def _authors(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        nested = raw.get("authors") or raw.get("author") or raw.get("items")
        if nested is not None:
            return _authors(nested)
        return str(raw.get("full_name") or raw.get("name") or "")
    if isinstance(raw, list):
        names = []
        for item in raw:
            if isinstance(item, dict):
                names.append(str(item.get("full_name") or item.get("name") or ""))
            else:
                names.append(str(item))
        return ", ".join(x for x in names if x)
    return ""


def _access_type(article: dict[str, Any]) -> str:
    for key in ("accessType", "access_type", "accessTypeName", "access", "access_type_name"):
        value = article.get(key)
        if value:
            if isinstance(value, dict):
                value = value.get("value") or value.get("name") or value.get("type") or ""
            return str(value)
    if article.get("open_access") is True or article.get("is_open_access") is True:
        return "Open Access"
    return ""


def _is_open_access(value: str) -> bool:
    normalized = value.lower().replace("_", " ").replace("-", " ")
    return "open access" in normalized or normalized.strip() in {"open", "openaccess"}


def _url_list(article: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = article.get(key)
        if isinstance(value, str) and value.startswith("http"):
            values.append(value)
        elif isinstance(value, list):
            values.extend(x for x in value if isinstance(x, str) and x.startswith("http"))
    return sorted(set(values))


def _score(article: dict[str, Any]) -> tuple[int, bool]:
    text = " ".join(str(article.get(k, "")) for k in ("title", "abstract", "publication_title")).lower()
    excluded = any(term in text for term in EXCLUDE_TERMS)
    score = sum(1 for term in POSITIVE_TERMS if term in text)
    if "neural network" in text or "dnn" in text:
        score += 2
    if "dag" in text or "directed acyclic" in text:
        score += 2
    return score, excluded


def _format_article(article: dict[str, Any], group_id: str, query: str, rank: int) -> dict[str, Any]:
    score, excluded = _score(article)
    title = str(article.get("title", "")).strip()
    abstract = str(article.get("abstract", "")).strip()
    access = _access_type(article)
    return {
        "title": title,
        "authors": _authors(article.get("authors", [])),
        "year": article.get("publication_year", ""),
        "venue": article.get("publication_title", ""),
        "doi": article.get("doi", "") or "",
        "url": article.get("html_url", "") or article.get("abstract_url", ""),
        "pdf_urls": _url_list(article, "pdf_url"),
        "method": "IEEE Xplore Metadata API",
        "relevance": "high" if score >= 5 else "medium" if score >= 3 else "low",
        "limitations": "; ".join([
            "metadata/abstract screening only",
            "excluded by offloading/cloud filter" if excluded else "full method requires paper review",
        ]),
        "priority": 1 if score >= 5 and not excluded else 2 if score >= 3 and not excluded else 3,
        "source_evidence": {
            "source": "IEEE Xplore Metadata API",
            "endpoint": "/api/v1/search/articles",
            "query_group": group_id,
            "query": query,
            "rank": rank,
            "article_number": article.get("article_number", "") or "",
            "abstract": abstract[:1200],
            "index_terms": article.get("index_terms", {}),
            "access_type": access,
            "article_fields": sorted(article.keys()),
        },
        "license_note": "Metadata is from IEEE Xplore. Full text is recorded only when the API marks it Open Access and the official endpoint permits retrieval.",
        "_article": article,
    }


def _request(session: requests.Session, url: str, params: dict[str, Any]) -> tuple[int | None, Any, str | None, str]:
    """Return status, parsed body, safe error class, and content type."""
    try:
        response = session.get(url, params=params, timeout=60)
    except requests.RequestException as exc:
        return None, None, type(exc).__name__, ""
    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        return response.status_code, None, "HTTPError", content_type
    if "json" in content_type.lower():
        try:
            return response.status_code, response.json(), None, content_type
        except ValueError:
            return response.status_code, None, "InvalidJSON", content_type
    return response.status_code, response.content, None, content_type


def _fulltext(session: requests.Session, candidate: dict[str, Any]) -> dict[str, Any]:
    article = candidate["_article"]
    article_number = str(article.get("article_number", ""))
    access = str(candidate["source_evidence"].get("access_type", ""))
    result = {
        "attempted": False,
        "endpoint": "/api/v1/search/document/{article_number}/fulltext",
        "article_number": article_number,
        "access_type": access,
        "http_status": None,
        "content_type": "",
        "interface": "",
        "saved_file": "",
        "error_type": "",
    }
    if not article_number or not _is_open_access(access):
        result["error_type"] = "skipped_non_open_access_or_missing_article_number"
        return result
    result["attempted"] = True
    url = FULLTEXT_URL.format(article_number=article_number)
    status, body, error_type, content_type = _request(session, url, {"apikey": _api_key(), "format": "xml"})
    result.update({"http_status": status, "content_type": content_type, "error_type": error_type or ""})
    lower_type = content_type.lower()
    if "pdf" in lower_type:
        result["interface"] = "PDF"
        suffix = ".pdf"
    elif "xml" in lower_type:
        result["interface"] = "XML"
        suffix = ".xml"
    elif "html" in lower_type:
        result["interface"] = "HTML"
        suffix = ".html"
    else:
        result["interface"] = "JSON" if "json" in lower_type else "unknown"
        suffix = ""
    if isinstance(body, (bytes, bytearray)) and suffix == ".xml" and len(body) <= 25_000_000 and status == 200:
        try:
            root = ET.fromstring(body)
            bodies = [x for x in root.iter() if x.tag.rsplit("}", 1)[-1] == "body"]
            if not bodies or sum(len("".join(x.itertext())) for x in bodies) < 1000:
                raise ValueError("No substantial article body")
        except (ET.ParseError, ValueError):
            result["error_type"] = "InvalidOrIncompleteXML"
            return result
        FULLTEXT_DIR.mkdir(parents=True, exist_ok=True)
        file_path = FULLTEXT_DIR / f"{article_number}{suffix}"
        file_path.write_bytes(body)
        result["saved_file"] = str(file_path)
    return result


def main() -> int:
    key = _api_key()
    if not key:
        raise SystemExit("IEEE_API_KEY unavailable")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "A-literature-ieee-query/1.0"})
    raw_groups: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in QUERY_GROUPS:
        params: dict[str, Any] = {
            "apikey": key,
            "querytext": group["query"],
            "max_records": 10,
            "start_record": 1,
            "format": "json",
        }
        if group["start_year"] is not None:
            params["start_year"] = group["start_year"]
        if group["end_year"] is not None:
            params["end_year"] = group["end_year"]
        status, body, error_type, content_type = _request(session, SEARCH_URL, params)
        articles = body.get("articles", []) if isinstance(body, dict) else []
        ranked = []
        for rank, article in enumerate(articles, start=1):
            if isinstance(article, dict):
                ranked.append((_score(article), rank, article))
        ranked.sort(key=lambda item: (item[0][1], -item[0][0], item[1]))
        selected = []
        for (_, excluded), rank, article in ranked:
            if excluded:
                continue
            formatted = _format_article(article, group["id"], group["query"], rank)
            if str(formatted["doi"]).lower() in KNOWN_A_DOIS:
                formatted["relevance"] = "high"
                formatted["priority"] = 1
                formatted["limitations"] = "known A-literature DOI; metadata/abstract screening only"
            identity = str(article.get("doi") or article.get("article_number") or formatted["title"]).lower()
            if identity in seen:
                continue
            seen.add(identity)
            selected.append(formatted)
            candidates.append(formatted)
            if len(selected) >= 10:
                break
        raw_groups.append({
            "id": group["id"],
            "note": group["note"],
            "query": group["query"],
            "start_year": group["start_year"],
            "end_year": group["end_year"],
            "http_status": status,
            "content_type": content_type,
            "error_type": error_type or "",
            "total_records": body.get("total_records") if isinstance(body, dict) else None,
            "returned_records": len(articles),
            "selected_records": len(selected),
            "selected": [x["source_evidence"]["article_number"] for x in selected],
        })
        time.sleep(1.2)

    fulltext_attempts = []
    for candidate in candidates:
        attempt = _fulltext(session, candidate)
        candidate["source_evidence"]["fulltext"] = attempt
        fulltext_attempts.append(attempt)
        candidate.pop("_article", None)
        if attempt["attempted"]:
            time.sleep(1.2)

    run = {
        "generated": date.today().isoformat(),
        "search_endpoint": "/api/v1/search/articles",
        "fulltext_endpoint": "/api/v1/search/document/{article_number}/fulltext",
        "groups": raw_groups,
        "fulltext_attempts": fulltext_attempts,
        "credential": {"source": "environment variable", "variable": "IEEE_API_KEY", "value_recorded": False},
        "notes": [
            "Searches are bounded to max_records=10 per group.",
            "Only records marked Open Access were sent to the official full-text endpoint.",
            "Locked/chargeable records were not sent to a full-text or purchase path.",
        ],
    }
    (OUT_DIR / "ieee_api_results.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    for candidate in candidates:
        candidate.pop("_article", None)
    candidates.sort(key=lambda x: (x["priority"], x["year"] or 9999, x["title"]))
    (OUT_DIR / "ieee_candidates.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "groups": len(raw_groups),
        "candidates": len(candidates),
        "fulltext_attempted": sum(1 for x in fulltext_attempts if x["attempted"]),
        "fulltext_saved": sum(1 for x in fulltext_attempts if x["saved_file"]),
        "statuses": [x["http_status"] for x in raw_groups],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
