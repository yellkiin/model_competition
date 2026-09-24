"""Fixed AI-tool disclosure generation shared by the paper builders and audits."""
from __future__ import annotations

from pathlib import Path
import json

AI_KEY = "ai_tool_disclosure"
AI_REFERENCE_TYPE = "ai_tool"
AI_DISCLOSURE = {
    "tool_name": "DeepSeek",
    "version": "DeepSeek-V4.1-Flash",
    "organization": "深度求索（DeepSeek）",
    "date": "2026-09-23",
}


AI_TEXT = 'DeepSeek，DeepSeek-V4.1-Flash，深度求索（DeepSeek），2026-09-23。'
AI_TEX_HOOK = r'\AtEndEnvironment{thebibliography}{\bibitem{ai_tool_disclosure}' + AI_TEXT + '}'


def disclosure_record(key: str = AI_KEY, *, usages: list[dict] | None = None) -> dict:
    return {
        "key": key,
        "reference_type": AI_REFERENCE_TYPE,
        "ai_disclosure": dict(AI_DISCLOSURE),
        "usage_status": "adopted" if usages else "template_only",
        "sources": [],
        "usages": list(usages or []),
    }


def ensure_evidence_record(manifest_path: Path, key: str = AI_KEY) -> bool:
    """Idempotently append the generated disclosure record to evidence.

    Existing ordinary evidence must already carry the explicit reference_type;
    this helper never upgrades legacy records or invents an AI-use assertion.
    """
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    evidence_path = (manifest_path.parent / manifest['references_evidence_path']).resolve()
    evidence_path.relative_to(manifest_path.parent)
    evidence = json.loads(evidence_path.read_text(encoding='utf-8-sig'))
    if evidence.get('schema_version') != '1.1':
        raise ValueError('旧文献证据须按1.1补齐显式类型与真实使用记录；不得直接沿用旧审核')
    records = evidence.get('references', [])
    legacy = [row.get('key', '<unknown>') for row in records if 'reference_type' not in row]
    if legacy:
        raise ValueError('文献证据缺少 reference_type（需明确 ordinary 或 ai_tool）：' + ','.join(legacy))
    ai = [row for row in records if row.get('reference_type') == AI_REFERENCE_TYPE]
    if len(ai) > 1:
        raise ValueError('文献证据中重复的AI工具披露记录')
    changed = False
    if ai:
        if ai[0].get('ai_disclosure') != AI_DISCLOSURE or ai[0].get('key') != AI_KEY:
            raise ValueError('已有AI工具披露记录的固定字段或保留键不正确')
        if records[-1] is not ai[0]:
            raise ValueError('已有AI工具披露记录必须位于证据列表末尾')
    else:
        records.append(disclosure_record(key))
        evidence['references'] = records
        evidence['schema_version'] = '1.1'
        changed = True
    if changed:
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    return changed
