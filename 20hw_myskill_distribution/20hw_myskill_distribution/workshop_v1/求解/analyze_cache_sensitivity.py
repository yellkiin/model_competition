"""Check and summarize the deliberately non-official 3x3 L2 study."""

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "求解/正式实验/L2参数敏感性_非官方"


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    grid = rows(OUT / "逐配置最优.csv")
    official = {(r["case"], int(r["cores"])): r for r in rows(ROOT / "求解/问题三/结果/逐例官方评估.csv")}
    assert len(grid) == 54
    groups = defaultdict(list)
    for row in grid:
        case = row["case"]
        cap = int(row["capacity_bytes"])
        bandwidth = int(row["bandwidth_bytes_per_cycle"])
        assert cap in (262144, 1048576, 4194304)
        assert bandwidth in (60, 250, 500)
        receipt = json.loads((ROOT / row["receipt"]).read_text(encoding="utf-8"))
        assert receipt["status"] == "PASS" and receipt["independent_validation"]["status"] == "PASS"
        groups[case].append(row)
        if cap == 1048576 and bandwidth == 250:
            ref = official[(case, 5)]
            assert int(row["makespan_cycles"]) == int(ref["makespan_cycles"])
            assert row["candidate"] == ref["candidate"]
    assert len(groups) == 6
    summary = {"status": "PASS", "study": "non_official_parameter_sensitivity", "grid_rows": len(grid),
               "official_default_crosscheck": "all six default 1 MiB/250-byte-per-cycle outcomes match the formal five-core rows",
               "cases": {}}
    for case, group in sorted(groups.items()):
        assert len(group) == 9
        by_pair = {(int(r["capacity_bytes"]), int(r["bandwidth_bytes_per_cycle"])): r for r in group}
        assert len(by_pair) == 9
        baseline = int(by_pair[(1048576, 250)]["makespan_cycles"])
        times = [int(r["makespan_cycles"]) for r in group]
        rates = [float(r["hit_rate"]) for r in group]
        cap_gain = baseline / int(by_pair[(4194304, 250)]["makespan_cycles"])
        bw_gain = baseline / int(by_pair[(1048576, 500)]["makespan_cycles"])
        summary["cases"][case] = {
            "default_cycles": baseline, "min_cycles": min(times), "max_cycles": max(times),
            "min_hit_rate": min(rates), "max_hit_rate": max(rates),
            "selected_candidates": sorted({r["candidate"] for r in group}),
            "capacity_gain_4mib_vs_1mib_at_250": cap_gain,
            "bandwidth_gain_500_vs_250_at_1mib": bw_gain,
        }
    (OUT / "统计验证.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
