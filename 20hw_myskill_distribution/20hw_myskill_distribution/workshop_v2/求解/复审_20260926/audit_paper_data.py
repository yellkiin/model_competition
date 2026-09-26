"""Fail-closed numerical review of recorded data; never runs the solver.

csv mode checks recorded CSVs against TeX tables. tables mode independently
recomputes the published tables and cross_question.csv, with explicitly narrower
scope. Neither mode proves evaluator correctness or PDF rendering quality.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean, median

CASES = {f"case_{i:03d}" for i in range(1, 101)}
CORES = set(range(1, 6))
GRID_CASES = {"case_001", "case_004", "case_006", "case_044", "case_046", "case_080"}
CAPS = (262144, 1048576, 4194304)
BWS = (60, 250, 500)


class AuditError(ValueError):
    """Invalid, missing or inconsistent evidence; must not become a PASS."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def number(value: object, *, integer: bool = False, minimum: float = 0) -> int | float:
    text = str(value).strip() if value is not None else ""
    # TeX display integers use commas; CSV integer-valued decimals are also allowed.
    require(bool(text), "Missing numeric value")
    require("," not in text or bool(re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+(\.\d+)?", text)),
            f"Invalid thousands separators: {text!r}")
    try:
        d = Decimal(text.replace(",", ""))
    except InvalidOperation as exc:
        raise AuditError(f"Invalid number: {text!r}") from exc
    require(d.is_finite(), f"Non-finite number: {text!r}")
    require(d >= Decimal(str(minimum)), f"Number below {minimum}: {text!r}")
    if integer:
        require(d == d.to_integral_value(), f"Non-integer value: {text!r}")
        return int(d)
    value = float(d)
    require(math.isfinite(value), f"Number exceeds float range: {text!r}")
    return value


def boolean(value: object) -> bool:
    v = str(value).strip().lower()
    require(v in {"true", "false"}, f"Invalid boolean: {value!r}")
    return v == "true"


def case_id(value: str) -> str:
    case = value if value.startswith("case_") else "case_" + value
    require(case in CASES, f"Unexpected case: {case}")
    return case


def unique(rows: list[dict], fields: tuple[str, ...], expected: set | None = None) -> dict:
    out = {}
    for r in rows:
        try:
            key = tuple(r[f] for f in fields)
        except KeyError as exc:
            raise AuditError(f"Missing key: {exc}") from exc
        require(key not in out, f"Duplicate key {key}")
        out[key] = r
    if expected is not None:
        require(set(out) == expected,
                f"Coverage mismatch; missing={sorted(expected-set(out))[:8]}, "
                f"extra={sorted(set(out)-expected)[:8]}")
    return out


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames),
                f"Missing/duplicate CSV columns: {path}")
        rows = list(reader)
        require(all(None not in r and None not in r.values() for r in rows),
                f"Malformed CSV row: {path}")
        return rows


def tex_rows(text: str) -> list[list[str]]:
    found = []
    for line in text.splitlines():
        if re.match(r"^\s*\d+\s*&", line):
            require(line.rstrip().endswith(("\\\\", "\\\\*")), f"Incomplete table row: {line}")
            found.append([c.strip() for c in re.sub(r"\\\\\*?\s*$", "", line).split("&")])
    return found


def parse_main_tables(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    rows, seen_blocks = [], set()
    for block in re.findall(r"\\begin\{longtable\}.*?\\end\{longtable\}", text, re.S):
        match = re.search(r"\\label\{tab:appendix_q([123])_n([1-5]+)\}", block)
        require(match is not None, "Unrecognized appendix table")
        q, ns = int(match[1]), tuple(map(int, match[2]))
        require((q, ns) not in seen_blocks, f"Repeated table block q{q} {ns}")
        seen_blocks.add((q, ns))
        for cells in tex_rows(block):
            require(len(cells) == 1 + 2 * len(ns), f"Wrong column count: {cells}")
            for j, n in enumerate(ns):
                rows.append(dict(case=case_id(cells[0]), q=q, n=n,
                                 makespan=number(cells[1+2*j], integer=True, minimum=1),
                                 added_copy_bytes=number(cells[2+2*j], integer=True)))
    require(seen_blocks == {(q, ns) for q in (1, 2, 3) for ns in ((1, 2), (3, 4), (5,))},
            "Missing/extra main appendix block")
    return unique(rows, ("q", "case", "n"), {(q, c, n) for q in (1, 2, 3) for c in CASES for n in CORES})


def parse_pair_table(path: Path) -> dict:
    rows = []
    for cells in tex_rows(path.read_text(encoding="utf-8")):
        require(len(cells) == 7, f"Wrong pair column count: {cells}")
        r = dict(case=case_id(cells[0]), n=number(cells[1], integer=True, minimum=1),
                 without_l2=number(cells[2], integer=True, minimum=1),
                 with_l2=number(cells[3], integer=True, minimum=1),
                 without_l2_added_bytes=number(cells[4], integer=True),
                 with_l2_added_bytes=number(cells[5], integer=True), hit_rate=number(cells[6]))
        require(r["hit_rate"] <= 1, "Hit rate exceeds 1")
        rows.append(r)
    return unique(rows, ("case", "n"), {(c, n) for c in CASES for n in CORES})


def validate_main_csv(rows: list[dict], q: int) -> dict:
    normalized = []
    for r in rows:
        require(r.get("status") == "ok", f"q{q}: invalid status at {r.get('case')}")
        require(number(r.get("q"), integer=True) == q, f"Wrong question in q{q}")
        item = dict(case=case_id(r["case"]), q=q, n=number(r["n"], integer=True, minimum=1))
        for field in ("makespan", "added_copy_bytes", "spill_added_copy_bytes"):
            item[field] = number(r.get(field), integer=True, minimum=1 if field == "makespan" else 0)
        require(item["spill_added_copy_bytes"] <= item["added_copy_bytes"], "Spill exceeds total extra COPY")
        normalized.append(item)
    return unique(normalized, ("q", "case", "n"), {(q, c, n) for c in CASES for n in CORES})


def validate_pairs_csv(rows: list[dict]) -> dict:
    normalized = []
    for r in rows:
        require(boolean(r.get("same_plan")), f"same_plan is false for {r.get('case')}")
        item = dict(case=case_id(r["case"]), n=number(r["n"], integer=True, minimum=1))
        for f in ("with_l2", "without_l2", "with_l2_added_bytes", "without_l2_added_bytes"):
            item[f] = number(r.get(f), integer=True, minimum=0 if f.endswith("bytes") else 1)
        item["hit_rate"] = number(r.get("hit_rate"))
        require(item["hit_rate"] <= 1, "Hit rate exceeds 1")
        ratio = number(r.get("cache_speedup"))
        require(abs(ratio-item["without_l2"]/item["with_l2"]) <= 1e-9, "Stored cache ratio differs")
        normalized.append(item)
    return unique(normalized, ("case", "n"), {(c, n) for c in CASES for n in CORES})


def relation(a: list[int], b: list[int]) -> dict:
    require(len(a) == len(b), "Unaligned comparison")
    return dict(improved=sum(y < x for x, y in zip(a, b)),
                same=sum(y == x for x, y in zip(a, b)),
                worse=sum(y > x for x, y in zip(a, b)))


def compute(main: dict, pairs: dict) -> dict:
    for c in CASES:
        require(main[1,c,1]["makespan"] == main[2,c,1]["makespan"], "Different single-core reference")
        require(main[1,c,1]["added_copy_bytes"] == main[2,c,1]["added_copy_bytes"], "Different baseline COPY")
    stats = {}
    for q in (1, 2, 3):
        for n in sorted(CORES):
            group = [main[q,c,n] for c in sorted(CASES)]
            ratios = [main[1,c,1]["makespan"]/main[q,c,n]["makespan"] for c in sorted(CASES)]
            stats[f"q{q}_n{n}"] = dict(count=len(group), mean_speedup=mean(ratios),
                median_speedup=median(ratios), min_speedup=min(ratios), max_speedup=max(ratios),
                mean_added_copy_bytes=mean(r["added_copy_bytes"] for r in group),
                median_added_copy_bytes=median(r["added_copy_bytes"] for r in group))
    cache = {}
    for n in sorted(CORES):
        group = [pairs[c,n] for c in sorted(CASES)]
        ratios = [r["without_l2"]/r["with_l2"] for r in group]
        for c in CASES:
            r = pairs[c,n]
            require(r["with_l2"] == main[3,c,n]["makespan"], f"Q3-pair cycle mismatch: {c}/{n}")
            require(r["with_l2_added_bytes"] == main[3,c,n]["added_copy_bytes"], f"Q3-pair COPY mismatch: {c}/{n}")
        cache[str(n)] = dict(count=len(group), mean_ratio=mean(ratios), median_ratio=median(ratios),
            mean_hit_rate=mean(r["hit_rate"] for r in group),
            **relation([r["without_l2"] for r in group], [r["with_l2"] for r in group]))
    comparisons = {}
    for qa, qb, field in ((1,2,"makespan"),(1,2,"added_copy_bytes"),(2,3,"makespan")):
        comparisons[f"q{qb}_vs_q{qa}_{field}"] = relation(
            [main[qa,c,5][field] for c in sorted(CASES)], [main[qb,c,5][field] for c in sorted(CASES)])
    ratios12 = [main[1,c,5]["makespan"]/main[2,c,5]["makespan"] for c in sorted(CASES)]
    return dict(displayed_configurations=len(main), displayed_cache_pairs=len(pairs),
                main_stats=stats, cache_stats=cache, comparisons_n5=comparisons,
                q1_over_q2_n5=dict(mean=mean(ratios12), median=median(ratios12)))


def check_summary_tables(folder: Path, result: dict) -> int:
    checked = 0
    for q in (1,2,3):
        rows = tex_rows((folder/f"q{q}_means.tex").read_text(encoding="utf-8"))
        require(len(rows) == 5, "Summary does not have five rows")
        seen = set()
        for row in rows:
            require(len(row) == 6, "Malformed means table")
            n = number(row[0], integer=True, minimum=1)
            require(n in CORES and n not in seen, "Invalid/duplicate summary core")
            seen.add(n)
            s = result["main_stats"][f"q{q}_n{n}"]
            expected = [s["count"], s["mean_speedup"], s["median_speedup"], s["min_speedup"], s["max_speedup"]]
            for i, (v, e) in enumerate(zip(row[1:], expected)):
                require(abs(number(v)-e) <= (0 if i == 0 else 0.0000500001), f"Summary mismatch q{q} n{n}: {v} vs {e}")
            checked += 1
    rows = tex_rows((folder/"q3_pairs.tex").read_text(encoding="utf-8"))
    require(len(rows) == 5, "Pair summary does not have five rows")
    seen = set()
    for row in rows:
        require(len(row) == 8, "Malformed pair summary")
        n = number(row[0], integer=True, minimum=1)
        require(n in CORES and n not in seen, "Invalid/duplicate pair summary core")
        seen.add(n)
        s = result["cache_stats"][str(n)]
        expected = [s["count"],s["mean_ratio"],s["median_ratio"],s["improved"],s["same"],s["worse"],s["mean_hit_rate"]]
        for i, (v, e) in enumerate(zip(row[1:], expected)):
            # Pair appendix rounds each individual hit rate to six decimal places.
            tol = 0.0000505001 if i == 6 else (0.0000500001 if i in (1,2) else 0)
            require(abs(number(v)-e) <= tol, f"Pair summary mismatch n{n}: {v} vs {e}")
        checked += 1
    return checked


def check_cross(rows: list[dict], main: dict) -> dict:
    indexed = unique(rows, ("case",), {(c,) for c in CASES})
    spills = {q: [] for q in (1,2,3)}
    for (c,), r in indexed.items():
        for q in (1,2,3):
            require(number(r[f"q{q}_makespan"],integer=True,minimum=1) == main[q,c,5]["makespan"], "Cross-table cycle mismatch")
            require(number(r[f"q{q}_added_bytes"],integer=True) == main[q,c,5]["added_copy_bytes"], "Cross-table COPY mismatch")
            sp = number(r[f"q{q}_spill_bytes"],integer=True)
            require(sp <= main[q,c,5]["added_copy_bytes"], "Spill exceeds total extra COPY")
            if "spill_added_copy_bytes" in main[q,c,5]:
                require(sp == main[q,c,5]["spill_added_copy_bytes"], "CSV Spill differs across files")
            spills[q].append(sp)
        for qa,qb in ((1,2),(2,3)):
            expected = main[qa,c,5]["makespan"]/main[qb,c,5]["makespan"]
            require(abs(number(r[f"q{qa}_to_q{qb}_ratio"])-expected) <= 1e-9, "Cross-table ratio mismatch")
    return {f"q{q}": dict(zero_count=sum(v == 0 for v in x), positive_count=sum(v>0 for v in x), mean=mean(x)) for q,x in spills.items()}


def check_grid(rows: list[dict], main: dict) -> dict:
    normalized = []
    for r in rows:
        mode = r.get("mode")
        require(mode in {"fixed_plan","bounded_readaptation"}, f"Unknown grid mode: {mode}")
        require(r.get("status") == r.get("response_status") == "ok" and boolean(r.get("audit_ok")), "Invalid grid status")
        require(number(r.get("q"),integer=True) == 3 and number(r.get("n"),integer=True) == 5, "Unexpected grid configuration")
        c = case_id(r["case"])
        cap = number(r["capacity_bytes"],integer=True,minimum=1)
        bw = number(r["bandwidth_bytes_per_cycle"],integer=True,minimum=1)
        cycle = number(r["makespan_cycles"],integer=True,minimum=1)
        require(number(r["summary_makespan_cycles"],integer=True) == cycle, "Grid summary cycle mismatch")
        equal_plan = boolean(r.get("plan_equal_to_main"))
        if mode == "fixed_plan":
            require(equal_plan, "Fixed-plan record changes the plan")
            if cap == 1048576 and bw == 250:
                require(cycle == main[3,c,5]["makespan"], "Default grid differs from Q3 main")
        hit, miss = [number(r[k],integer=True) for k in ("cache_hit_bytes","cache_miss_bytes")]
        rate = number(r["byte_hit_rate"])
        require(rate <= 1 and abs(rate-(hit/(hit+miss) if hit+miss else 0)) <= 1e-9, "Grid hit-rate mismatch")
        total, part, spill = [number(r[k],integer=True) for k in ("added_copy_bytes","partition_added_copy_bytes","spill_added_copy_bytes")]
        require(total == part+spill, "Grid COPY decomposition mismatch")
        normalized.append(dict(case=c,mode=mode,cap=cap,bw=bw,cycle=cycle,hit_rate=rate))
    expected = {(c,"fixed_plan",cap,bw) for c in GRID_CASES for cap in CAPS for bw in BWS}
    expected |= {(c,"bounded_readaptation",cap,bw) for c in GRID_CASES for cap,bw in ((262144,60),(4194304,500))}
    index = unique(normalized,("case","mode","cap","bw"),expected)
    return dict(records=len(index),fixed=sum(r["mode"]=="fixed_plan" for r in normalized),
                readapted=sum(r["mode"]=="bounded_readaptation" for r in normalized),
                examples={c:[index[c,"fixed_plan",cap,bw]["cycle"] for bw in BWS]
                          for c,cap in (("case_080",262144),("case_044",1048576))})


def check_anytime(rows: list[dict]) -> dict:
    seen, selected = set(), []
    for r in rows:
        key = (case_id(r["case"]), number(r["q"],integer=True),
               number(r["n"],integer=True,minimum=1), number(r["seconds"]))
        require(key not in seen, f"Duplicate anytime record: {key}")
        seen.add(key)
        require(key[1] in (0,1,2,3) and key[2] in CORES, "Unexpected anytime configuration")
        require(key[1] != 0 or key[2] == 1, "The q0 reference is single-core")
        has = boolean(r["has_solution"])
        if key[1:] == (1,5,30):
            selected.append(dict(case=key[0],has_solution=has))
    unique(selected,("case",),{(c,) for c in CASES})
    return dict(rows=len(selected), distinct_cases=len({r["case"] for r in selected}),
                has_solution=sum(r["has_solution"] for r in selected))


def audit(workspace: Path, mode: str) -> dict:
    table = workspace/"论文/章节内容/数据表"
    data = workspace/"求解/规范化数据"
    used = [table/n for n in ("appendix_results.tex","appendix_pairs.tex","q1_means.tex","q2_means.tex","q3_means.tex","q3_pairs.tex")]
    used.append(data/"combined/cross_question.csv")
    if mode == "csv":
        used.extend(data/"combined"/f"appendix_q{q}.csv" for q in (1,2,3))
        used.extend([data/"combined/pairs.csv",data/"combined/anytime.csv",data/"studies/cache_parameter_grid.csv"])
    missing = [str(p.relative_to(workspace)) for p in used if not p.is_file()]
    require(not missing, f"Missing input files: {missing}")
    main, pairs = parse_main_tables(used[0]), parse_pair_table(used[1])
    limits = ["No official evaluator or solver rerun.","No PDF compilation, page or hyperlink verification.",
              "Numeric agreement is not evidence of same-plan byte identity."]
    if mode == "csv":
        actual = {}
        for q in (1,2,3):
            actual.update(validate_main_csv(read_csv(data/"combined"/f"appendix_q{q}.csv"),q))
        for k,r in main.items():
            require(all(r[f] == actual[k][f] for f in ("makespan","added_copy_bytes")),f"Main TeX/CSV mismatch: {k}")
        actual_pairs = validate_pairs_csv(read_csv(data/"combined/pairs.csv"))
        for k,r in pairs.items():
            require(all(r[f] == actual_pairs[k][f] for f in ("with_l2","without_l2","with_l2_added_bytes","without_l2_added_bytes")),f"Pair TeX/CSV mismatch: {k}")
            require(abs(r["hit_rate"]-actual_pairs[k]["hit_rate"]) <= .0000005001,f"Pair hit-rate mismatch: {k}")
        main,pairs = actual,actual_pairs
    else:
        limits += ["Table mode: original appendix CSVs, same_plan flags and full raw response files were not checked.",
                   "Table mode: anytime.csv and parameter-grid CSV were not checked.",
                   "Individual hit rates were read at their printed six-decimal precision."]
    result = compute(main,pairs)
    result["summary_rows_checked"] = check_summary_tables(table,result)
    result["spill_n5"] = check_cross(read_csv(data/"combined/cross_question.csv"),main)
    if mode == "csv":
        result["grid"] = check_grid(read_csv(data/"studies/cache_parameter_grid.csv"),main)
        result["anytime_q1_n5_30"] = check_anytime(read_csv(data/"combined/anytime.csv"))
    result.update(status="PASS_SCOPED",mode=mode,limitations=limits,
                  inputs=[dict(path=str(p.relative_to(workspace)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in used])
    return result


def markdown(result: dict) -> str:
    lines = ["# 独立数值复核", "", f"状态：{result['status']}；模式：{result['mode']}。", ""]
    if result["status"] == "FAIL":
        lines += ["本次核验未通过，不生成成功结论。", "", result["error"]]
    else:
        lines += [f"主表展示配置：{result['displayed_configurations']}；配对记录：{result['displayed_cache_pairs']}；核对正文统计行：{result['summary_rows_checked']}。", "",
                  "| 核数 | 第一问均值 | 第二问均值 | 第三问均值 |", "|---:|---:|---:|---:|"]
        for n in sorted(CORES):
            lines.append(f"| {n} | " + " | ".join(f"{result['main_stats'][f'q{q}_n{n}']['mean_speedup']:.4f}" for q in (1,2,3))+" |")
        lines += ["", "## 计算结果", "", "```json", json.dumps({k:result[k] for k in ("comparisons_n5","q1_over_q2_n5","cache_stats","spill_n5")},ensure_ascii=False,indent=2), "```"]
        for optional in ("grid","anytime_q1_n5_30"):
            if optional in result:
                lines += ["",f"{optional}：",json.dumps(result[optional],ensure_ascii=False)]
        lines += ["", "## 核验边界", ""] + ["- "+s for s in result["limitations"]]
    return "\n".join(lines)+"\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace",type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument("--mode",choices=("csv","tables"),default="csv")
    parser.add_argument("--output-dir",type=Path)
    args = parser.parse_args(argv)
    out = args.output_dir or args.workspace/"求解/复审_20260926/数值核验"
    try:
        result = audit(args.workspace,args.mode)
        code = 0
    except (AuditError,OSError,KeyError,ValueError) as exc:
        result = dict(status="FAIL",mode=args.mode,error=f"{type(exc).__name__}: {exc}")
        code = 2
    out.mkdir(parents=True,exist_ok=True)
    (out/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (out/"report.md").write_text(markdown(result),encoding="utf-8")
    print(result["status"])
    if code:
        print(result["error"],file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
