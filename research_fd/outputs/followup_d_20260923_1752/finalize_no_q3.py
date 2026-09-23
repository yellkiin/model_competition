"""Write truthful status artifacts and reports when no joint Q3 plan was validated."""
from __future__ import annotations
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def get(path):
    return json.loads((HERE/path).read_text(encoding="utf-8"))

def put(path,value):
    (HERE/path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")

def md(path,text):
    (HERE/path).write_text(text.rstrip()+"\n",encoding="utf-8")

def main():
    if (HERE/"q3_joint_plan.json").exists():
        current=get("q3_joint_plan.json")
        if isinstance(current.get("jobs"),list) and current["jobs"]:
            raise SystemExit("A real Q3 joint plan exists; run independent validation and Q4 instead")
    q1=get("q1_summary.json")
    q1check=get("q1_validation.json")
    q2=list(csv.DictReader((HERE/"q2_comparison.csv").open(encoding="utf-8")))
    by={r["method"]:r for r in q2}
    q2log=get("q2_search_log.json")
    witness=get("witness_iterations.json")
    diagnosis=get("q3_diagnostic.json")
    for name in ("q2_baseline_export","q2_fast_export","q2_energy_export"):
        result=get(f"{name}/validation.json")
        if not result["transport_valid"] or result["issues"]:
            raise SystemExit(f"independent Q2 validation failed: {name}")
    assert q1check["status"]=="passed"
    q3={"status":"NO_VALIDATED_JOINT_PLAN","formal_result":None,
        "reason":"All recorded finite task-slot models returned INFEASIBLE; this does not prove the unrestricted official Q3 infeasible.",
        "attempt_count":len(witness),"frozen_q3":None,"formal_q4":None}
    put("q3_joint_plan.json",q3)
    put("q3_status.json",{**q3,"iterations":witness})
    for level in ("60s","15s","10s","ray7_5m"):
        path=f"radio_validation_{level}.json"
        if not (HERE/path).exists():
            put(path,{"status":"NOT_RUN_NO_JOINT_CANDIDATE","numerical_result":None,
                      "reason":"No CP-SAT joint incumbent was available for radio validation."})
    with (HERE/"relay_tasks.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f)
        w.writerow(["status","site","departure_s","ready_s","stop_s","returned_s","energy_kwh"])
        w.writerow(["NO_VALIDATED_JOINT_PLAN",None,None,None,None,None,None])
    for groups in (2,3):
        for policy in ("strict","duplicate"):
            put(f"partition_{groups}_{policy}.json",{"status":"NOT_RUN_NO_FROZEN_Q3",
                "formal_result":None,"groups":groups,"policy":policy})
    def fm(x): return f"{float(x):.6f}"
    q1rows=q1["reserve_sensitivity"]
    wrows=[]
    for x in witness:
        source=x.get("source_plan", "q2_candidate_fast.json" if x["iteration"]<10 else "q2_candidate_energy.json")
        source="energy" if "energy.json" in source else "fast"
        wrows.append(f"| {x['iteration']} | {source} | {x['window_s']} | {x['relay_task_slots']} | {x.get('site_count',13)} | {x['radio_blocks']} | {x['status']} |")
    md("RESULTS.md",f"""# D 题四问深化实验：执行结果

输入为 `research_fd/outputs/d_official.json`，地形为正式 DEM；所有本轮代码和结果保存在本目录。Q1、Q2 是正式输入下已执行结果。Q3 尚无通过资源和通信双重验证的联合方案，因此 Q4 不报正式数值。

## 问题一

45 个机型—服务区安全载荷已重算；额定体积作为每批约束单独检查，不把体积臆造为统一的质量换算。逐区计数状态 DP 采用架次、能耗、累计作业时间词典序。

| 返航余量 | 精确最少架次 | 运输能耗 kWh | 累计作业时间 s |
|---:|---:|---:|---:|
"""+"\n".join(f"| {int(r['reserve']*100)}% | {r['trips']} | {fm(r['transport_energy_kwh'])} | {fm(r['cumulative_work_s'])} |" for r in q1rows)+f"""

20% 余量时，B/S008 安全质量上限为 28.801789 kg，C/S008 为 58.905354 kg。80 箱逐箱覆盖、载荷/体积/往返能量检查通过；S002、S003、S008 的独立全位掩码 DP 在三档余量下与计数状态 DP 一致。详见 `q1_capacity_45.csv`、`q1_batches.csv`、`q1_validation.json`。

## 问题二

独立复核确认原 26 趟基线 80 箱恰交一次、硬/软迟到 0、实体机和电池无冲突、质量/体积/往返能量满足。新候选同样经独立物理和时间复核，`issues=0`。数值属于有限随机邻域找到的可行解，**未证明全局最优**。

| 方案 | 架次 | 工期 s | 运输能耗 kWh | 硬/软迟到 |
|---|---:|---:|---:|---:|
| 原基线 | 26 | {fm(by['baseline']['makespan_s'])} | {fm(by['baseline']['energy_kwh'])} | 0/0 |
| 固定资源顺序 DAG 重排 | 26 | {fm(by['dag_compressed']['makespan_s'])} | {fm(by['dag_compressed']['energy_kwh'])} | 0/0 |
| 最短工期档案 | 26 | {fm(by['candidate_fast']['makespan_s'])} | {fm(by['candidate_fast']['energy_kwh'])} | 0/0 |
| 最低运输能耗档案 | 26 | {fm(by['candidate_energy']['makespan_s'])} | {fm(by['candidate_energy']['energy_kwh'])} | 0/0 |

最低能耗方案工期比原基线长，已保留以呈现能耗—工期取舍。搜索 {q2log['rounds']} 轮，尝试两架次换箱 {q2log['attempts']['pair']} 次、三架次换箱 {q2log['attempts']['triple']} 次、机型与实体资源联合插入 {q2log['attempts']['type_insert']} 次、资源顺序插入 {q2log['attempts']['order_insert']} 次。旧节能/较快候选数值只作比较线索，本轮只以实际保存和复核的候选报告成绩。逐箱交付和机身/电池时间表在 `q2_fast_export/`、`q2_energy_export/`。

## 问题三

相对轨迹缓存和可变长度任务槽已执行。13 驻点合并块模型为 110 块、最多 16 槽；全 88 驻点及逐采样拆块也实际执行。各次有限模型状态如下。这里的 `INFEASIBLE` 只针对列出的驻点、块、槽数、启动窗口、固定路线与保守整数时间模型，不能外推为题目原始连续问题无解。

| 次 | Q2 路线 | 启动窗口 ±s | 任务槽 | 驻点 | 块/需求 | CP-SAT 状态 |
|---:|---|---:|---:|---:|---:|---|
"""+"\n".join(wrows)+f"""

固定最短工期 Q2 时刻约 2640 s 有一个 30 s 诊断时间格至少需要 3 个同时驻点，而正式库存仅 2 架中继；这只是固定时刻的空间下界。空通信要求控制模型可行；移除中继机/电池资源约束的诊断模型可行（不计正式成绩），表明资源占用是当前表示下的主要瓶颈。细节见 `q3_diagnostic.json` 和 `witness_iterations.json`。

没有联合 incumbent，所以未执行 60/15/10 s 和 7.5 m 的候选验证，`q3_joint_plan.json` 与对应验证 JSON 均是明确的 null/status 记录，不包含虚构计划或能耗。`relay_tasks.csv` 也只有状态行。

## 问题四

无冻结的正式 Q3 计划，2/3 组 strict/duplicate 均为 `NOT_RUN_NO_FROZEN_Q3`，资源数、独立运行代价及 partition-aware 成绩均为空值，见四个 `partition_*.json`。
""")
    md("METHODS.md","""# 方法和可复核边界

## 正式输入与物理引擎

统一读取 `research_fd/outputs/d_official.json` 和封存的正式适配 runtime。正式 DEM 决定地形峰值、飞行高度和通信遮挡。合成实例参数没有进入正式计算。运输能耗按当前正式引擎的水平续航插值与爬升势能之和计算，服务和装卸计入时间；电池返回后按正式充电曲线占用至满电。所有最终 Q2 候选经 `export_validate_plan.py` 独立重算覆盖、库存、时间区间和路径物理。

## Q1：安全载荷与精确组批

每个机型—节点求满足额定质量、体积和往返能量上限的最大质量；任意实际箱组合仍独立检查体积。对每个服务点按相同质量和体积的箱类型压缩状态，用 DP 穷举可行动作，词典序最小化架次、能耗、作业时间。三处代表节点另做箱编号位掩码精确 DP 校验。该问题独立分区，不含全局机身排班或交付期限，因此不能把 Q1 的 18 趟直接当作 Q2 可行架次。

## Q2：连续时间资源 DAG 与有限邻域

把每架实体机和每块实体电池的任务顺序分别固定为有向边，边长取上一任务的机身/电池实际占用时间；加上每条路线的释放时刻，用 DAG 最长路得到该顺序下的最早启动时间。循环或超出硬期限的顺序被拒绝。两架次移动/交换货箱、三架次循环换箱后，正式路径引擎重算访问顺序、质量、体积、能耗、各箱抵达、补能占用。机型变化时同时重新插入新机型实体机与电池序列。搜索维护零迟到下工期和能耗两个档案，种子 20260923、时限 180 s；有限邻域结果无全局最优性证明。

## Q3：相对通信块与任务槽

每条固定运输路线在相对起飞时刻坐标计算直连和候选驻点接入余量；相同空间射线只算一次。无直连的连续采样且驻点集合相同者合为块，另执行逐采样拆块对照。CP-SAT 给每架 R01/R02 设置少量可选任务槽；每槽选驻点、离仓时间、到站/setup、服务结束和返仓时间。服务长度决定悬停及通信能耗、返仓 SOC 与单调充电表的完成时间。机身按任务槽次序无重叠，六组能源组件用 cumulative 限制。运输路线固定，但实体机/电池顺序保留，启动时间在 ±300、±600、±1200 s 内按整秒连续选取。硬期限、实际库存、正式链路预算与能量余量未放宽；后续放开软期限的尝试明确标注。

模型对飞行时间、能耗和充电采取保守整数舍入；`INFEASIBLE` 仅是该有限且偏保守表示的结论。仅在取得 incumbent 后才执行 60→15→10 s、15→7.5 m 的数值复核并加入断联 witness。此轮未取得 incumbent，故没有细网格验证数据。资源放松诊断单独标注，不能当作正式可行解。

## Q4 门槛

仅对独立复核通过的 frozen Q3 联合计划计算服务区超图、strict/duplicate 的两/三组资源。由于本轮没有这样的计划，四个 Q4 文件只报告未运行状态和 null。旧合成或旧近似分组结果不替代正式 Q4。
""")
    md("COMMANDS.md","""# 已执行命令（PowerShell，仓库根目录）

虚拟环境解释器均为 `research_fd/.venv/Scripts/python.exe`；执行前已按任务要求 `git fetch origin`、切换并快进到 `research/d-four-questions-20260923`。

```powershell
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q1_exact.py
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q1_validate.py
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q2_search.py --seconds 180
& research_fd/.venv/Scripts/python.exe research_fd/outputs/review/export_validate_plan.py --input research_fd/outputs/d_official.json --plan research_fd/outputs/official_pareto_cpsat/energy_cap_1.json --out research_fd/outputs/followup_d_20260923_1752/q2_baseline_export --skip-radio --runtime research_fd/outputs/runtime
& research_fd/.venv/Scripts/python.exe research_fd/outputs/review/export_validate_plan.py --input research_fd/outputs/d_official.json --plan research_fd/outputs/followup_d_20260923_1752/q2_candidate_fast.json --out research_fd/outputs/followup_d_20260923_1752/q2_fast_export --skip-radio --runtime research_fd/outputs/runtime
& research_fd/.venv/Scripts/python.exe research_fd/outputs/review/export_validate_plan.py --input research_fd/outputs/d_official.json --plan research_fd/outputs/followup_d_20260923_1752/q2_candidate_energy.json --out research_fd/outputs/followup_d_20260923_1752/q2_energy_export --skip-radio --runtime research_fd/outputs/runtime
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 90
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 90 --allow-soft
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_diagnose.py
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8 --all-sites
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8 --split-blocks
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --plan research_fd/outputs/followup_d_20260923_1752/q2_candidate_energy.json --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8
& research_fd/.venv/Scripts/python.exe research_fd/outputs/followup_d_20260923_1752/q3_compact.py --seconds 120 --allow-soft --single-window 1200 --slots-per-aircraft 8 --all-sites --split-blocks
```

各命令对应日志和模型状态文件均在本目录；`q3_diagnose.py` 中的资源放松只用于失败定位。没有执行独立 Q4 求解，因为正式 Q3 冻结门槛未达到。
""")

if __name__=="__main__": main()
