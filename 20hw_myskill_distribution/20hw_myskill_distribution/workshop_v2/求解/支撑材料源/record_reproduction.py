"""Register the completed response-only recomputation without claiming full solving."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

W = Path(__file__).resolve().parents[2]
P = W.parents[1]
OUT = P / ".orion_paper_cache/reproduction_20260926"
REPORT = OUT / "reproduction_report.json"
SOURCE = W / "提交附件/支撑材料文件/其他支撑材料/复现程序/reproduce.py"
PYTHON = W / ".venv/Scripts/python.exe"


def main():
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    receipt = dict(
        kind="selected_response_recomputation",
        status="completed_response_only",
        official_solver_or_evaluator_invoked=False,
        command=[str(PYTHON), "-B", str(SOURCE), "--package-root", str(W / "提交附件"),
                 "--output", str(OUT)],
        process_exit_code=0,
        report=report,
        outputs=[str(OUT / name) for name in ("recomputed_main.csv", "recomputed_pairs.csv",
                                                "recomputed_means.csv", "mean_speedup.svg",
                                                "reproduction_report.json")],
        output_recorded_at_utc=datetime.fromtimestamp(REPORT.stat().st_mtime, timezone.utc).isoformat(),
        scope="Read 1400 selected official responses and 500 same-plan Q3/Q2 responses; recomputed values and compared reference cycle counts. No independent solver rerun or full package audit.",
    )
    (OUT / "REPRODUCTION_RECORD.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    internal = W / "求解/验收输出/支撑材料"
    internal.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPORT, internal / "reproduction_report.json")
    shutil.copy2(OUT / "REPRODUCTION_RECORD.json", internal / "响应重算记录.json")
    manifest_path = W / "求解/支撑材料清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    command = "python 支撑材料文件/其他支撑材料/复现程序/reproduce.py --output <独立输出目录>"
    validate = ("import json,pathlib; d=json.loads(pathlib.Path('响应重算/reproduction_report.json').read_text(encoding='utf-8')); "
                "assert d['main_configurations']==1400 and d['paired_configurations']==500 and "
                "d['baseline_cases']==100 and not d['comparison_mismatches']")
    for q in manifest["questions"]:
        q["run_verification"] = dict(status="pending", command=command,
                                     record_path="求解/验收输出/支撑材料/响应重算记录.json",
                                     verified_at=receipt["output_recorded_at_utc"])
        q["reproduction"] = dict(
            commands=[dict(purpose="solve", argv=["{python}", "../../其他支撑材料/复现程序/reproduce.py",
                                                    "--output", "响应重算"]),
                      dict(purpose="validate", argv=["{python}", "-c", validate])],
            outputs=[dict(path="响应重算/reproduction_report.json",
                          expected_path="求解/验收输出/支撑材料/reproduction_report.json",
                          comparison="json")],
        )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "counts": {k: report[k] for k in
                      ("main_configurations", "paired_configurations", "baseline_cases")},
                      "mismatches": len(report["comparison_mismatches"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
