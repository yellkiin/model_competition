"""Fetch known public manuscript URLs; preserve PDF bytes and record provenance.

Usage: python download_papers.py catalog.json --workers 4
Requires requests and PyMuPDF (fitz). Does not obtain credentials or bypass access controls.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import fitz
import requests

ROOT = Path(__file__).resolve().parent


def public_url(url):
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in {"apikey", "api_key", "token", "cltoken", "auth"}]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def inspect_pdf(data, title):
    if not data.lstrip().startswith(b"%PDF-"):
        raise ValueError("Response is not a PDF (HTML/login/error responses are rejected)")
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass or not len(doc):
            raise ValueError("Encrypted or empty PDF")
        text = " ".join(doc[i].get_text() for i in range(min(2, len(doc))))
        words = set(re.findall(r"[a-z0-9]+", title.lower())) - {"a", "an", "the", "and", "of", "for", "with", "to", "in", "on"}
        found = set(re.findall(r"[a-z0-9]+", text.lower()))
        overlap = len(words & found) / max(1, len(words))
        return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "pages": len(doc), "title_token_overlap": round(overlap, 3),
                "pdf_validation": "PDF header and all-page renderability; title tokens in first two pages",
                "text_extractable": bool(text.strip())}


def fetch_one(paper):
    identifier = paper["id"]
    filename = paper.get("pdf_filename", f"{identifier}_{paper['year']}.pdf")
    if Path(filename).name != filename:
        raise ValueError("PDF filename must not contain directory components")
    path = ROOT / "pdf" / filename
    result = {"id": identifier, "checked_at": datetime.now(timezone.utc).isoformat(), "attempts": []}
    if path.exists():
        data = path.read_bytes()
        result.update(inspect_pdf(data, paper["title"]))
        result.update(status="downloaded", local_path=path.relative_to(ROOT).as_posix(), reused=True)
        return result
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; AcademicLiteratureCollector/1.0)"
    for url in paper.get("pdf_urls", []):
        attempt = {"url": public_url(url)}
        try:
            with session.get(url, timeout=(15, 65), stream=True) as response:
                attempt["http_status"] = response.status_code
                attempt["resolved_url"] = public_url(response.url)
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_content(1024 * 128):
                    size += len(chunk)
                    if size > 60 * 1024 * 1024:
                        raise ValueError("Single manuscript exceeds 60 MiB limit")
                    chunks.append(chunk)
                data = b"".join(chunks)
            info = inspect_pdf(data, paper["title"])
            if info["text_extractable"] and info["title_token_overlap"] < 0.65 and not paper.get("allow_visual_title_check"):
                raise ValueError(f"Title mismatch: overlap={info['title_token_overlap']}")
            if info["title_token_overlap"] < 0.65:
                info["title_check"] = "manual_visual_review_required"
            with fitz.open(stream=data, filetype="pdf") as doc:
                # Validate every page parses/renders, without altering the downloaded file.
                for page in doc:
                    page.get_pixmap(matrix=fitz.Matrix(0.15, 0.15), alpha=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            result["attempts"].append(attempt)
            result.update(info)
            result.update(status="downloaded", local_path=path.relative_to(ROOT).as_posix(),
                          download_url=public_url(url), resolved_url=attempt["resolved_url"])
            print(f"{identifier}: downloaded {len(data)} bytes / {info['pages']} pages", flush=True)
            return result
        except Exception as exc:
            # Keep exception class only: request exception strings may include signed URLs.
            attempt["error_type"] = type(exc).__name__
            if isinstance(exc, ValueError):
                attempt["detail"] = str(exc)
            result["attempts"].append(attempt)
    result["status"] = "not_downloaded"
    print(f"{identifier}: unavailable after {len(result['attempts'])} attempts", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--log", type=Path, default=ROOT / "download_log.json")
    args = parser.parse_args()
    papers = json.loads(args.catalog.read_text(encoding="utf-8-sig"))
    previous = {}
    if args.log.exists():
        previous = {r["id"]: r for r in json.loads(args.log.read_text(encoding="utf-8"))}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.workers, 5))) as pool:
        for result in pool.map(fetch_one, papers):
            old = previous.get(result["id"], {})
            if result.get("reused"):
                result = {**old, **result, "attempts": old.get("attempts", [])}
            elif old:
                result["attempts"] = old.get("attempts", []) + result["attempts"]
            previous[result["id"]] = result
            args.log.parent.mkdir(parents=True, exist_ok=True)
            args.log.write_text(json.dumps(list(previous.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"downloaded": sum(r["status"] == "downloaded" for r in previous.values()), "total": len(previous)}))


if __name__ == "__main__":
    main()
