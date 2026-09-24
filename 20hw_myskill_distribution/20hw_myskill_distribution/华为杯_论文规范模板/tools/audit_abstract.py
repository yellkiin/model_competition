#!/usr/bin/env python3
"""Audit a Huawei Cup Chinese abstract before paper generation."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / "华为杯_求解规范/tools"))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import json
import re
from pathlib import Path
from typing import Any


from paper_contract import chinese_number, commands, strip_comments
MIN_VISIBLE_CHARACTERS = 800
MAX_VISIBLE_CHARACTERS = 1600

FORBIDDEN_STYLE_PATTERNS = {
    "background_filler": r"^(?:随着|近年来|伴随着).{0,45}(?:发展|进步|提高|关注)",
    "empty_intensifier": r"非常|极其|十分|很强的|很高的|显著优秀",
    "self_praise": r"优秀的|出色的|创新性地|全新的算法|重要的理论意义",
    "unsupported_priority_claim": r"首次提出|首次建立|填补.{0,12}空白",
    "vague_result_claim": r"结果表明模型有效|得到了最优解(?!为)|结果非常准确",
}

FORBIDDEN_DELIVERY_PATTERNS = {
    "delivery_inventory": r"最终交付|交付文件|提交附件|支撑材料|文件清单|交付清单",
    "source_or_index_inventory": r"完整源码|源代码|结果索引|哈希|SHA-?256|可复现事实链",
    "file_format_inventory": r"\.(?:json|csv|xlsx|txt|pdf|docx|drawio)\b|JSON 文件|CSV 文件|文本文件",
    "figure_inventory": r"\d+\s*张.{0,12}(?:科研图|图表|图片|流程图)|图表数量|流程图数量",
}

METHOD_WORDS = re.compile(r"模型|规划|算法|方法|策略|方程|网络|回归|优化|分解|分析|搜索|滤波|聚类|博弈|统计|定理|判据|关系式|证明|[A-Z][A-Z0-9-]{1,}")
VALIDATION_WORDS = re.compile(r"独立验证|交叉验证|灵敏度|敏感性|稳健性|鲁棒性|误差|约束校验|独立重算|情景比较|消融|证明|反例|解析检验|一致性")
PROGRESSION_WORDS = re.compile(r"基于问题[一二三四五六七八九十]|在(?:问题[一二三四五六七八九十]|前一问|前述模型)基础上|进一步|引入.{0,20}约束|扩展为|推广至|继承")
INNOVATION_WORDS = re.compile(r"创新点(?:在于|为)|创新(?:在于|之处)|贡献(?:在于|为)")
COMPARISON_WORDS = re.compile(r"相比|相较|较基线|提升|降低|减少|缩短|改进")

# Each group requires one term, not an optimization vocabulary for every task.
ABSTRACT_TYPE_TERMS = {
    "optimization": (("模型", "规划"), ("目标函数", "为目标", "最小化", "最大化"), ("约束",)),
    "statistics": (("指标", "统计量", "分布"), ("统计", "分析", "检验"), ("差异", "关联", "趋势", "特征")),
    "prediction": (("模型", "分类器"), ("特征", "输入"), ("预测", "分类", "识别"), ("验证", "误差", "准确率", "召回率", "F1")),
    "mechanism": (("假设", "机理", "守恒"), ("方程", "关系式", "模型"), ("推导", "辨识", "求解"), ("边界", "量纲", "验证", "成立条件")),
    "simulation": (("模型", "过程"), ("仿真", "模拟", "采样"), ("场景", "参数", "分布"), ("验证", "收敛", "误差", "一致性")),
    "evaluation": (("指标", "准则"), ("评价", "评分", "排序", "决策"), ("权重", "偏好", "标准"), ("敏感性", "稳定性", "一致性", "验证")),
    "interpretation": (("特征", "机制", "因素"), ("解释", "归因", "分析"), ("贡献", "作用", "关联", "影响"), ("消融", "扰动", "验证", "证据", "边界")),
    "theory": (("假设", "条件"), ("推导", "证明"), ("命题", "定理", "关系式", "判据", "界"), ("成立条件", "边界", "适用范围", "反例")),
}
QUALITATIVE_TYPES = {"mechanism", "interpretation", "theory"}
METHOD_TERMS = ("采用", "运用", "依据")
RESULT_TERMS = ("得到", "获得", "证明", "揭示", "给出")


def audit_problem_paragraph(paragraph: str, chapter: dict[str, Any]) -> dict[str, Any]:
    kind = chapter.get("abstract_type")
    if not isinstance(kind, str):
        kind = None
    mode = chapter.get("abstract_result_mode", "quantitative")
    groups = ABSTRACT_TYPE_TERMS.get(kind, ())
    missing = [list(group) for group in groups if not any(term in paragraph for term in group)]
    result_markers = list(re.finditer("|".join(RESULT_TERMS), paragraph))
    result_clause = paragraph[result_markers[0].end():] if result_markers else ""
    count = len(numeric_tokens(result_clause))
    mode_ok = mode in ("quantitative", "analytic") or (mode == "qualitative" and kind in QUALITATIVE_TYPES)
    result_ok = count >= 1 if mode == "quantitative" else (
        visible_character_count(result_clause) >= 15
        and bool(re.search(r"条件|边界|关系|判据|成立|影响|机制|作用|不成立|不支持", result_clause))
    )
    return {
        "ok": bool(groups) and not missing and mode_ok and result_ok
        and any(term in paragraph for term in METHOD_TERMS) and bool(result_markers),
        "abstract_type": kind, "result_mode": mode, "missing_term_groups": missing,
        "numeric_results": count, "valid_type": kind in ABSTRACT_TYPE_TERMS,
        "valid_result_mode": mode_ok,
    }

NUMBER_RE = re.compile(
    r"(?<![A-Za-z_0-9.^])(?:[+-]?\d+(?:\.\d+)?(?:\s*(?:×|x)\s*10(?:\^\{?[+-]?\d+\}?)?)?)(?![0-9.])",
    re.IGNORECASE,
)
UNIT_RE = re.compile(
    r"^\s*(?:%|％|（无量纲）|\(无量纲\)|"
    r"[A-Za-zµμΩ°]+(?:[/·][A-Za-z0-9µμΩ°²³^{}+-]+)*|"
    r"亿元|万元|千米|厘米|毫米|千克|毫秒|微秒|分钟|小时|百分点|"
    r"元|秒|天|米|吨|克|瓦|度|个|组|次|台|条|对|项|类|名|位|分|"
    r"周期|字节|节点|样本|算例|帧|批次)"
)


def remove_comments(text: str) -> str:
    return strip_comments(text)


def simplify_tex(text: str) -> str:
    text = remove_comments(text)

    def replace_si(match: re.Match[str]) -> str:
        unit = re.sub(r"\\([A-Za-z]+)", r"\1", match.group(2))
        return f"{match.group(1)} {unit}"

    text = re.sub(
        r"\\SI\s*\{([^{}]+)\}\s*\{([^{}]+)\}",
        replace_si,
        text,
    )
    text = re.sub(r"\\(?:num|textbf|mbox|mathrm|operatorname)\s*\{([^{}]*)\}", r"\1", text)
    text = text.replace(r"\%", "%").replace(r"\times", "×").replace(r"\pm", "±")
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", text)
    text = text.replace("$", " ").replace("{", "").replace("}", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def visible_character_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def problem_count(manifest: dict[str, Any]) -> int:
    return sum(1 for chapter in manifest.get("chapters", []) if chapter.get("role") == "problem")


def problem_marker(index: int) -> str:
    return chinese_number(index)


def numeric_tokens(text: str) -> list[re.Match[str]]:
    return [match for match in NUMBER_RE.finditer(text) if not is_reference_number(text, match)]


def is_reference_number(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 8): match.start()]
    return bool(re.search(r"(?:问题|第|表|图|公式|式|附录)\s*$", before))


def missing_unit_values(text: str) -> list[str]:
    missing = []
    for match in numeric_tokens(text):
        after = text[match.end(): match.end() + 24]
        if not UNIT_RE.match(after):
            missing.append(match.group(0))
    return missing


def decimal_precisions(text: str) -> list[int]:
    precisions = []
    for match in numeric_tokens(text):
        mantissa = re.match(r"\d+(?:\.(\d+))?", match.group(0))
        if mantissa and mantissa.group(1):
            precisions.append(len(mantissa.group(1)))
    return precisions


def extract_problem_paragraphs(plain: str, expected_count: int) -> tuple[dict[int, str], list[int]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", plain) if part.strip()]
    found: dict[int, str] = {}
    misplaced: list[int] = []
    for index in range(1, expected_count + 1):
        numeral = problem_marker(index)
        marker = re.compile(rf"针对问题(?:{re.escape(numeral)}|{index})(?:\s*[，,：:])")
        for paragraph in paragraphs:
            match = marker.search(paragraph)
            if match:
                found[index] = paragraph
                if match.start() != 0:
                    misplaced.append(index)
                break
    return found, misplaced


def normalize_keyword(value: Any) -> str:
    return re.sub(r"[\s\-_]+", "", str(value)).casefold()


def audit_abstract_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    root = manifest_path.parent
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def add(code: str, ok: bool, **details: Any) -> None:
        item = {"code": code, "ok": ok, **details}
        checks.append(item)
        if not ok:
            failures.append(item)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        add("manifest_readable", False, error=str(exc))
        return {"status": "FAIL", "manifest": str(manifest_path), "checks": checks, "failures": failures}

    abstract_raw_path = manifest.get("abstract_tex_path")
    abstract_path = (root / str(abstract_raw_path)).resolve() if abstract_raw_path else root
    try:
        abstract_path.relative_to(root.resolve())
        abstract_inside_root = True
    except ValueError:
        abstract_inside_root = False
    add(
        "abstract_fragment_exists_and_is_tex",
        abstract_inside_root and abstract_path.is_file() and abstract_path.suffix.lower() == ".tex",
        path=str(abstract_path),
    )
    if failures:
        return {"status": "FAIL", "manifest": str(manifest_path), "checks": checks, "failures": failures}

    raw = abstract_path.read_text(encoding="utf-8-sig")
    clean_raw = remove_comments(raw)
    plain = simplify_tex(raw)
    compact_plain = re.sub(r"\s+", "", plain)
    count = visible_character_count(plain)

    unescaped_percent_lines = [
        index
        for index, line in enumerate(raw.splitlines(), start=1)
        if re.search(r"(?<!\\)%", line) and not line.lstrip().startswith("%")
    ]
    add(
        "percent_signs_are_tex_escaped",
        not unescaped_percent_lines,
        lines=unescaped_percent_lines,
        message="摘要正文中的百分号必须写成 \\%，否则 LaTeX 会把同行后文当作注释。",
    )

    forbidden_structure = []
    for pattern in (
        r"\\keywords\b",
        r"\\section\b",
        r"\\begin\s*\{abstract\}",
        r"\\end\s*\{abstract\}",
        r"关键词\s*[：:]",
    ):
        forbidden_structure.extend(re.findall(pattern, clean_raw))
    forbidden_structure = sorted(set(forbidden_structure))
    add(
        "fragment_excludes_keywords_and_document_structure",
        not forbidden_structure,
        matches=forbidden_structure,
        message="摘要 fragment 只含摘要正文；关键词由 manifest 唯一生成。",
    )
    placeholders = sorted(set(re.findall(r"【[^】]*】|\[TODO\]|TODO|TBD|待补|待填", clean_raw, re.IGNORECASE)))
    add("abstract_has_no_placeholders", not placeholders, matches=placeholders)
    add(
        "visible_character_target",
        MIN_VISIBLE_CHARACTERS <= count <= MAX_VISIBLE_CHARACTERS,
        actual=count,
        minimum=MIN_VISIBLE_CHARACTERS,
        maximum=MAX_VISIBLE_CHARACTERS,
    )

    sentences = [part.strip() for part in re.split(r"[。！？]", plain) if part.strip()]
    first_sentence = sentences[0] if sentences else ""
    problem_chapters = [c for c in manifest.get("chapters", []) if c.get("role") == "problem"]
    needs_numbers = any(c.get("abstract_result_mode", "quantitative") == "quantitative" for c in problem_chapters)
    opening_ok = (first_sentence.startswith("本文针对")
                  and any(word in first_sentence for word in ("建立", "构建", "推导", "提出"))
                  and any(word in first_sentence for word in METHOD_TERMS)
                  and any(word in first_sentence for word in RESULT_TERMS))
    opening_numbers = numeric_tokens(first_sentence)
    add(
        "opening_sentence_is_result_led",
        opening_ok and (bool(opening_numbers) or not needs_numbers),
        sentence=first_sentence,
        required=["本文针对", "建立/构建/推导/提出", "采用/运用/依据", "得到/获得/证明/揭示/给出"],
    )

    expected_problems = problem_count(manifest)
    add("problem_chapters_detected", expected_problems > 0, actual=expected_problems)
    problem_paragraphs, misplaced = extract_problem_paragraphs(plain, expected_problems)
    paragraph_positions = [plain.find(problem_paragraphs[index]) for index in sorted(problem_paragraphs)]
    all_markers = re.findall(r'针对问题([一二三四五六七八九十百千零]+|[0-9]+)[，,：:]', compact_plain)
    add('problem_markers_exact_once_in_order', all_markers == [problem_marker(i) for i in range(1, expected_problems+1)], actual=all_markers)
    add(
        "one_ordered_paragraph_per_problem",
        len(problem_paragraphs) == expected_problems
        and not misplaced
        and paragraph_positions == sorted(paragraph_positions),
        expected=expected_problems,
        found=sorted(problem_paragraphs),
        positions=paragraph_positions,
        markers_not_at_paragraph_start=misplaced,
    )
    for index in range(1, expected_problems + 1):
        paragraph = problem_paragraphs.get(index, "")
        chapter = problem_chapters[index - 1]
        review = audit_problem_paragraph(paragraph, chapter)
        paragraph_ok = review.pop("ok")
        add(
            f"problem_{index}_model_method_result_loop",
            bool(paragraph) and paragraph_ok,
            **review,
        )
        if index >= 2 and chapter.get("depends_on_previous") is True:
            add(
                f"problem_{index}_progression",
                bool(PROGRESSION_WORDS.search(paragraph)),
                message="仅已声明依赖前问的问题须说明真实递进关系，不为独立问题虚构依赖。",
            )

    try:
        bold_phrases = [simplify_tex(c.argument) for c in commands(clean_raw, ('textbf',))]
    except ValueError as exc:
        bold_phrases = []
        add('bold_commands_parseable', False, error=str(exc))
    bold_lengths_ok = all(2 <= visible_character_count(value) <= 40 and
                          not re.search(r'[。！？；]', value) for value in bold_phrases)
    bold_method_count = sum(bool(METHOD_WORDS.search(value)) for value in bold_phrases)
    add('key_methods_are_selectively_bold', bool(bold_phrases) and bold_lengths_ok,
        phrases=bold_phrases, method_phrase_count=bold_method_count,
        message='逐问四类短加粗；没有固定八处上限，禁止整句整段加粗。')

    # Validation belongs to the corresponding problem. An abstract ending is
    # not a place for limitations, future work, delivery or engineering logs.
    parts = [p.strip() for p in re.split(r'\n\s*\n+', plain) if p.strip()]
    allowed = set(problem_paragraphs.values())
    extra = [p for p in parts[1:] if p not in allowed and not INNOVATION_WORDS.search(p)]
    add('no_separate_validation_or_limitation_closing', not extra, paragraphs=extra)
    innovation_sentences = [s for s in sentences if INNOVATION_WORDS.search(s)]
    innovation_text = '。'.join(innovation_sentences)
    add('innovation_is_explicit_and_evidence_backed',
        1 <= len(innovation_sentences) <= 2 and
        (bool(COMPARISON_WORDS.search(innovation_text)) or not needs_numbers) and
        (bool(numeric_tokens(innovation_text)) or not needs_numbers),
        sentence_count=len(innovation_sentences),
        message='真实方法差异与对照/解析证据，允许融入逐问段落。')
    for index, paragraph in problem_paragraphs.items():
        add(f'problem_{index}_scientific_validation_integrated', bool(VALIDATION_WORDS.search(paragraph)))
    forbidden_discussion = {
        'limitations': r'模型局限|数据不足|数据稀缺|记录稀缺|限制研究范围|研究范围限制|受限于|局限性',
        'future_work': r'未来工作|未来研究|后续研究|有待改进|待进一步|今后|进一步完善',
        'internal_checks': r'尺寸压力测试|内部验收|工程检查|构建记录|打包|编译检查|序列化|文件行数',
    }
    hits = {key: re.findall(pattern, plain) for key, pattern in forbidden_discussion.items()
            if re.search(pattern, plain)}
    add('abstract_excludes_limitations_future_and_internal_checks', not hits, matches=hits)
    from abstract_evidence import evidence_gate
    evidence = evidence_gate(manifest, root, clean_raw, problem_paragraphs, simplify_tex)
    checks.extend(evidence['checks'])
    failures.extend(evidence['failures'])

    style_hits = {
        code: sorted(set(re.findall(pattern, compact_plain)))
        for code, pattern in FORBIDDEN_STYLE_PATTERNS.items()
        if re.search(pattern, compact_plain)
    }
    add("language_is_fact_based", not style_hits, matches=style_hits)
    delivery_hits = {
        code: sorted(set(re.findall(pattern, plain, re.IGNORECASE)))
        for code, pattern in FORBIDDEN_DELIVERY_PATTERNS.items()
        if re.search(pattern, plain, re.IGNORECASE)
    }
    add("abstract_excludes_delivery_inventory", not delivery_hits, matches=delivery_hits)

    missing_units = missing_unit_values(plain)
    add("all_quantitative_values_have_units", not missing_units, values=missing_units)
    precisions = decimal_precisions(plain)
    precision_ok = all(2 <= value <= 4 for value in precisions) and len(set(precisions)) <= 1
    add(
        "decimal_precision_is_consistent",
        precision_ok,
        decimal_places=precisions,
        message="小数结果统一采用同一种 2--4 位精度；精确整数不强制补零。",
    )

    keywords = manifest.get("keywords", [])
    normalized_keywords = [normalize_keyword(value) for value in keywords] if isinstance(keywords, list) else []
    generic_keywords = [str(value) for value in keywords if normalize_keyword(value) in {"数学建模", "优化算法", "模型", "算法"}] if isinstance(keywords, list) else []
    add(
        "keywords_are_unique_and_specific",
        isinstance(keywords, list)
        and 3 <= len(keywords) <= 5
        and len(set(normalized_keywords)) == len(normalized_keywords)
        and not generic_keywords
        and all(normalized_keywords),
        count=len(keywords) if isinstance(keywords, list) else None,
        duplicates=sorted({value for value in normalized_keywords if normalized_keywords.count(value) > 1}),
        generic=generic_keywords,
    )

    return {
        "status": "PASS" if not failures else "FAIL",
        "manifest": str(manifest_path),
        "abstract": str(abstract_path),
        "checks": checks,
        "failures": failures,
    }


def failure_summary(report: dict[str, Any]) -> str:
    return ", ".join(item["code"] for item in report.get("failures", [])) or "unknown"


def require_abstract_pass(manifest_path: Path) -> dict[str, Any]:
    report = audit_abstract_manifest(manifest_path)
    if report["status"] != "PASS":
        raise ValueError(f"摘要审计失败: {failure_summary(report)}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit_abstract_manifest(args.manifest)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
