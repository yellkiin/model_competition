"""从仓库根目录运行 python tools/huaweicup.py --help。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import Workspace, initialize, load, save
from .workflow import ROLES, task_prompt, log_ai


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="华为杯宿主 Agent + 可追溯研究工作台")
    sub = parser.add_subparsers(dest="command", required=True)
    assets = sub.add_parser("assets", help="按角色定位本仓库指南，不执行上游服务")
    assets.add_argument("role", choices=ROLES)
    assets.add_argument("--check", action="store_true")
    papers = sub.add_parser("papers", help="查询近年索引与已下载论文，不冒充全文阅读")
    papers.add_argument("--year", type=int)
    papers.add_argument("--problem", choices=list("ABCDEF"))
    init = sub.add_parser("init", help="创建空白工作区，拒绝覆盖")
    init.add_argument("workspace")
    init.add_argument("--mode", choices=["rehearsal", "competition"], default="rehearsal")
    for command in ("seal", "status", "snapshot", "render"):
        sub.add_parser(command).add_argument("workspace")
    prompt = sub.add_parser("prompt", help="生成一个宿主 agent 角色交接任务")
    prompt.add_argument("workspace")
    prompt.add_argument("role", choices=ROLES)
    plot = sub.add_parser("plot", help="按 JSON 规格绘制真实 CSV 数据")
    plot.add_argument("workspace")
    plot.add_argument("specification")
    record = sub.add_parser("record", help="登记真实文件及其全部依赖，不是执行它")
    record.add_argument("workspace")
    record.add_argument("path")
    record.add_argument("--depends", nargs="+", required=True)
    source = sub.add_parser("source-add")
    source.add_argument("workspace")
    source.add_argument("json_file")
    search = sub.add_parser("search", help="Crossref 元数据检索；不是全文阅读")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.add_argument("--output", default="crossref_candidates.json")
    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("workspace")
    compile_cmd.add_argument("--tex", default="paper/draft.tex")
    compile_cmd.add_argument("--trusted-tex", action="store_true")
    audit_cmd = sub.add_parser("audit")
    audit_cmd.add_argument("workspace")
    audit_cmd.add_argument("--final", action="store_true")
    audit_cmd.add_argument("--pdf", default="build/draft.pdf")
    freeze_cmd = sub.add_parser("freeze")
    freeze_cmd.add_argument("workspace")
    freeze_cmd.add_argument("--pdf", default="build/draft.pdf")
    freeze_cmd.add_argument("--filename", required=True)
    freeze_cmd.add_argument("--rehearsal", action="store_true")
    demo = sub.add_parser("demo", help="真实执行合成实验、绘图、写作；不调用模型 API")
    demo.add_argument("workspace")
    demo.add_argument("--compile", action="store_true")
    ai = sub.add_parser("log-ai")
    ai.add_argument("workspace")
    ai.add_argument("--tool", required=True)
    ai.add_argument("--model", required=True)
    ai.add_argument("--purpose", required=True)
    ai.add_argument("--outputs", nargs="+", required=True)
    args = parser.parse_args(argv)
    try:
        value, code = dispatch(args)
        if value is not None:
            print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
        return code
    except Exception as exc:
        # CLI 以非零退出，保留错误类型；库函数仍正常抛异常供调用者处理。
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def dispatch(args):
    command = args.command
    if command == "assets":
        from .bridge import guide_records
        records = guide_records(args.role)
        ok = all(record["exists"] for record in records)
        return {"ok": ok, "guides": records}, 2 if args.check and not ok else 0
    if command == "papers":
        from .bridge import paper_records
        return paper_records(args.year, args.problem), 0
    if command == "init":
        return str(initialize(args.workspace, args.mode).root), 0
    if command == "demo":
        from .demo import run_demo
        return str(run_demo(args.workspace, args.compile).root), 0
    if command == "search":
        from .research import search_crossref
        target = Path(args.output)
        if target.exists():
            raise ValueError("搜索结果输出文件已存在，拒绝覆盖")
        result = search_crossref(args.query, args.limit)
        save(target, result)
        return result, 0
    ws = Workspace(args.workspace)
    if command == "seal":
        return ws.seal(), 0
    if command == "snapshot":
        return ws.snapshot(), 0
    if command == "prompt":
        return task_prompt(ws, args.role), 0
    if command == "record":
        ws.record(args.path, args.depends)
    elif command == "source-add":
        from .research import add_source
        add_source(ws, load(Path(args.json_file)))
    elif command == "log-ai":
        log_ai(ws, args.tool, args.model, args.purpose, args.outputs)
    elif command == "plot":
        from .visuals import plot_csv
        return plot_csv(ws, args.specification), 0
    elif command == "render":
        from .publication import render
        render(ws)
    elif command == "compile":
        from .publication import compile_tex
        return compile_tex(ws, args.tex, args.trusted_tex), 0
    elif command in {"audit", "status"}:
        from .audit import audit
        report = audit(ws, getattr(args, "final", False), getattr(args, "pdf", "build/draft.pdf"))
        return report, 0 if report["ok"] else 2
    elif command == "freeze":
        from .audit import freeze
        return freeze(ws, args.pdf, args.filename, args.rehearsal), 0
    return {"ok": True, "command": command}, 0


if __name__ == "__main__":
    raise SystemExit(main())
