"""面向真实赛题的声明式 CSV 绘图；数据、规格和实现一起登记来源。"""
from __future__ import annotations

import csv
import math
import re
import shutil
from pathlib import Path

from .core import Workspace


def plot_csv(ws: Workspace, specification: str) -> list[str]:
    spec = ws.read(specification)
    data_name, kind = spec["data"], spec["kind"]
    source = ws.path(data_name)
    if kind not in {"line", "scatter", "bar"}:
        raise ValueError("支持 line/scatter/bar；其他图由可审计的独立适配器实现")
    name = spec["name"]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name):
        raise ValueError("图名必须为 ASCII 标识符")
    if not all(spec.get(key) for key in ("xlabel", "ylabel", "x", "y")):
        raise ValueError("必须提供轴字段、标签和单位说明")
    errors = ws.input_errors()
    if errors:
        raise ValueError("; ".join(errors))
    if data_name in ws.read("artifacts.json"):
        ws.require_fresh([data_name])
    elif data_name not in ws.read("input_manifest.json")["files"]:
        raise ValueError("图数据必须为已封存输入或已登记产物")
    if source.stat().st_size > 20_000_000:
        raise ValueError("CSV 超过 20 MB；请先登记可复现的聚合结果")
    with source.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("CSV 为空")
    group_key = spec.get("group")
    groups = sorted({r[group_key] if group_key else "data" for r in rows})
    if len(groups) > 12:
        raise ValueError("分组超过 12 个；请拆成明确的科学问题")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    try:
        for group in groups:
            selected = [r for r in rows if not group_key or r[group_key] == group]
            x = [float(r[spec["x"]]) for r in selected]
            y = [float(r[spec["y"]]) for r in selected]
            if not all(math.isfinite(v) for v in x + y):
                raise ValueError("图数据包含 NaN/Inf")
            if kind == "line" and any(b <= a for a, b in zip(x, x[1:])):
                raise ValueError("折线横轴必须严格递增；禁止把无序重复连成趋势")
            if kind == "bar" and len(groups) != 1:
                raise ValueError("多组柱状图需专用适配器，避免柱子重叠误导")
            getattr(ax, {"line": "plot", "scatter": "scatter", "bar": "bar"}[kind])(x, y, label=group)
        ax.set_xlabel(spec["xlabel"])
        ax.set_ylabel(spec["ylabel"])
        if len(groups) > 1:
            ax.legend()
        if kind == "bar":
            ax.set_ylim(bottom=min(0, ax.get_ylim()[0]))
        fig.tight_layout()
        generator = "code/workbench_visuals.py"
        shutil.copyfile(Path(__file__), ws.path(generator))
        output = []
        for extension in ("pdf", "png"):
            target = f"figures/{name}.{extension}"
            fig.savefig(ws.path(target), dpi=200)
            ws.record(target, [data_name, specification, generator], "figure")
            output.append(target)
        return output
    finally:
        plt.close(fig)
