from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUTS = {
    "roadmap": ROOT / "求解/总体/图片",
    "q1_task": ROOT / "求解/问题一/图片",
    "q2_task": ROOT / "求解/问题二/图片",
    "q3_fifo": ROOT / "求解/问题三/图片",
}

PREAMBLE = r"""\documentclass[tikz,border=1.6mm]{standalone}
\usepackage[UTF8,fontset=windows]{ctex}
\setCJKmainfont{SimSun}
\usepackage{amsmath,amssymb}
\usetikzlibrary{arrows.meta,positioning,calc,fit,backgrounds,shapes.geometric,shapes.misc}
\definecolor{navy}{HTML}{17324D}
\definecolor{blue}{HTML}{2878A5}
\definecolor{teal}{HTML}{218C83}
\definecolor{orange}{HTML}{D9873F}
\definecolor{ink}{HTML}{243746}
\definecolor{muted}{HTML}{647789}
\definecolor{line}{HTML}{9BAAB5}
\definecolor{pale}{HTML}{F3F7FA}
\definecolor{pblue}{HTML}{E9F2F8}
\definecolor{pteal}{HTML}{E8F4F1}
\definecolor{porange}{HTML}{FCF1E7}
\tikzset{
  op/.style={draw=navy!75,fill=white,rounded corners=1.6mm,line width=.55pt,
    text=ink,align=center,font=\fontsize{8.3}{10}\selectfont,minimum height=9mm,inner sep=1.4mm},
  opmini/.style={draw=navy!55,fill=white,rounded corners=1.2mm,line width=.45pt,
    text=ink,align=center,font=\fontsize{7.6}{9}\selectfont,minimum height=7mm,inner sep=1mm},
  band/.style={draw=none,fill=pale,rounded corners=2mm},
  bandtitle/.style={text=navy,font=\fontsize{8.5}{10}\selectfont\bfseries,anchor=west},
  link/.style={-{Stealth[length=2mm,width=1.5mm]},draw=blue,line width=.65pt},
  datalink/.style={-{Stealth[length=2mm,width=1.5mm]},draw=teal,line width=.75pt},
  ctrllink/.style={-{Stealth[length=2mm,width=1.5mm]},draw=orange,densely dashed,line width=.7pt},
  note/.style={text=muted,align=center,font=\fontsize{7.0}{8.5}\selectfont},
  tag/.style={text=navy,font=\fontsize{7.3}{9}\selectfont\bfseries,align=left},
  store/.style={draw=teal!75!black,fill=pteal,rounded corners=1.3mm,line width=.6pt,
    text=ink,align=center,font=\fontsize{8}{9.5}\selectfont,minimum height=8mm,inner sep=1.2mm},
  qcard/.style={draw=navy!50,fill=white,rounded corners=1.6mm,line width=.5pt,
    text=ink,align=left,font=\fontsize{7.7}{9.3}\selectfont,minimum height=15mm,inner sep=1.6mm}
}
\begin{document}
"""

FIGURES = {
"roadmap": r"""\begin{tikzpicture}[x=1mm,y=1mm]
% Four compact bands: decisions, parallel task semantics, common evaluator, and feedback.
\def\W{160}
\path[band] (0,0) rectangle (\W,17);
\path[band] (0,21) rectangle (\W,39);
\path[band] (0,43) rectangle (\W,60);
\path[band] (0,64) rectangle (\W,81);
\node[bandtitle] at (4,14.4) {联合决策};
\node[opmini,minimum width=36mm] (p) at (22,8.1) {子图划分 $\mathcal P$};
\node[opmini,minimum width=36mm] (a) at (62,8.1) {核心归属 $a$};
\node[opmini,minimum width=36mm] (pi) at (102,8.1) {核内顺序 $\boldsymbol\pi$};
\node[op,minimum width=29mm,minimum height=8mm,fill=pblue] (x) at (143,8.1) {完整方案 $x$};
\draw[link] (p)--(a); \draw[link] (a)--(pi); \draw[link] (pi)--(x);
\node[bandtitle] at (4,35.5) {三问执行场景（并列特化）};
\node[qcard,minimum width=46mm] (q1) at (26,28.9) {\textbf{问题一·子图级任务}\\跨子图均经 DDR片外存储器（含同核）；同核切换等待 100 周期；跨核依赖任务完成后等待 1000 周期};
\node[qcard,minimum width=46mm] (q2) at (80,28.9) {\textbf{问题二·核心级任务}\\同核片上驻留可延续；跨核输出搬运完成后等待 500 周期再释放输入搬运};
\node[qcard,minimum width=46mm] (q3) at (134,28.9) {\textbf{问题三·核心级任务与先进先出缓存}\\沿用跨核交接；只读二级缓存查询，读带宽池独立};
\node[note] at (80,22.3) {三个场景分别执行，不表示彼此依赖};
\node[bandtitle] at (4,57.5) {统一事件执行与目标评价};
\node[opmini,minimum width=38mm] (event) at (27,50.2) {流水线 / 容量 / DDR片外存储器\\离散事件推进};
\node[opmini,minimum width=34mm] (feas) at (71,50.2) {完整可行性与事件记录};
\node[opmini,minimum width=36mm,fill=pblue] (obj) at (113,50.2) {$C_q=\max_j f_j$\\周期优先};
\node[opmini,minimum width=30mm,fill=pteal] (copy) at (148,50.2) {$D_q$\\同周期次比};
\draw[link] (event)--(feas); \draw[link] (feas)--(obj); \draw[link] (obj)--(copy);
\node[bandtitle] at (4,78.5) {多邻域候选与可行解反馈};
\node[opmini,minimum width=38mm] (moves) at (29,71.2) {结构 / 驻留 / 顺序候选};
\node[opmini,minimum width=37mm] (screen) at (76,71.2) {结构预检、下界筛选};
\node[opmini,minimum width=40mm,fill=porange] (eval) at (123,71.2) {完整执行；严格改善才接受};
\node[opmini,minimum width=22mm] (inc) at (148,71.2) {当前解};
\draw[link] (moves)--(screen); \draw[link] (screen)--(eval); \draw[link] (eval)--(inc);
% Parallel scenario branches are alternatives, not a causal chain.
\draw[link] (x.south) -- ++(0,-2) -| (q1.north);
\draw[link] (x.south) -- ++(0,-2) -| (q2.north);
\draw[link] (x.south) -- ++(0,-2) -| (q3.north);
\draw[link] (q1.south) -- ++(0,-1.4) -| (event.north);
\draw[link] (q2.south) -- ++(0,-1.4) -| (event.north);
\draw[link] (q3.south) -- ++(0,-1.4) -| (event.north);
\draw[link] (copy.south) -- ++(0,-1.4) -| (moves.north);
\draw[ctrllink] (inc.north) .. controls +(0,8) and +(7,0) .. (moves.east);
\node[note,anchor=west] at (4,-1.6) {每问分别调用同一执行评价器；统一按 $(C_q,D_q)$ 字典序评价。};
\end{tikzpicture}
""",
"q1_task": r"""\begin{tikzpicture}[x=1mm,y=1mm]
\path[band] (0,0) rectangle (160,67);
\node[tag] at (3,60) {核心 1};
\node[op,minimum width=27mm] (g1) at (34,51) {子图 $G_1$\\任务 1};
\node[op,minimum width=27mm] (g2) at (100,51) {子图 $G_2$\\任务 2};
\draw[link] (g1)-- node[above,note]{同核顺序} (g2);
\node[note] at (66,56.2) {任务 切换间隔 $\geq 100$ 周期};
\node[tag] at (3,23) {核心 2};
\node[op,minimum width=27mm] (g3) at (100,19) {子图 $G_3$\\任务 3};
\node[store,minimum width=29mm] (dram) at (67,36) {DDR片外存储器\\共享带宽池};
\node[opmini,minimum width=24mm] (producer) at (34,36) {边界\\COPY\_OUT};
\node[opmini,minimum width=24mm] (consumer) at (100,36) {边界\\COPY\_IN};
\draw[datalink] (g1.south) -- (producer.north);
\draw[datalink] (producer.east) -- (dram.west);
\draw[datalink] (dram.east) -- (consumer.west);
\draw[datalink] (consumer.south) -- (g2.north);
\draw[ctrllink] (g2.east) -- ++(8,0) |- node[pos=.25,right,note]{跨核依赖\\完成后 $+1000$ 周期} (g3.north);
\node[note,anchor=west,align=left] at (6,5) {所有跨子图数据都经 DDR片外存储器（同核也如此）；图中 COPY 路径示意边界搬运，\\搬运服务时间由共享带宽事件模拟计算，不等于固定交接等待。};
\end{tikzpicture}
""",
"q2_task": r"""\begin{tikzpicture}[x=1mm,y=1mm]
\path[band] (0,0) rectangle (160,67);
\node[tag] at (3,60) {核心 1 · 单一任务};
\node[op,minimum width=26mm] (g1) at (26,51) {子图 $G_1$\\生成张量 $u$};
\node[op,minimum width=26mm] (g2) at (70,51) {子图 $G_2$\\使用 $u$};
\draw[link] (g1)-- node[above,note]{同核顺序} (g2);
\node[store,minimum width=31mm] (ub) at (121,51) {片上存储 片上存储 L1/UB\\驻留实例 $u$};
\draw[datalink] (g1.south) -- ++(0,-4) -| node[pos=.78,above,note]{若未换出则复用} (ub.west);
\draw[datalink] (ub.west) -- ++(-4,0) |- (g2.south);
\node[tag] at (3,23) {核心 2 · 单一任务};
\node[op,minimum width=27mm] (g3) at (128,19) {子图 $G_3$\\目标操作};
\node[opmini,minimum width=25mm] (out) at (26,34) {COPY\_OUT\\跨核写出};
\node[store,minimum width=29mm] (dram) at (71,34) {DDR片外存储器\\共享服务};
\node[opmini,minimum width=25mm] (in) at (116,34) {COPY\_IN\\目标核读入};
\draw[datalink] (g2.south) -- (out.north);
\draw[datalink] (out.east) -- (dram.west);
\draw[datalink] (dram.east) -- (in.west);
\draw[datalink] (in.south) -- (g3.north);
\draw[ctrllink] (out.south) -- ++(0,-5) -| node[pos=.35,below,note]{COPY\_OUT 完成后等待 $500$ 周期} (in.south);
\node[note,anchor=west,align=left] at (6,5) {同核跨子图不另建 任务 切换；驻留受 片上存储 L1/UB 容量及自动换出规则约束。\\跨核数据经 COPY\_OUT / DDR片外存储器 / COPY\_IN，等待约束以输出完成时刻为起点。};
\end{tikzpicture}
""",
"q3_fifo": r"""\begin{tikzpicture}[x=1mm,y=1mm]
\path[band] (0,0) rectangle (160,75);
\node[opmini,minimum width=27mm,minimum height=9mm] (issue) at (16,65) {COPY\_IN 发射\\逻辑张量 $t$};
\node[diamond,draw=navy!70,fill=pblue,line width=.6pt,aspect=2.1,inner sep=1mm,
  text=ink,align=center,font=\fontsize{7.5}{9}\selectfont,minimum width=22mm,minimum height=11mm] (lookup) at (54,65) {先进先出（FIFO）\ 查询};
\draw[link] (issue)--(lookup);
\node[opmini,minimum width=27mm] (hit) at (91,68) {命中：沿用\当前插入位置};
\node[opmini,minimum width=27mm] (miss) at (91,56) {未命中：读请求\发往 DDR片外存储器};
\draw[datalink] (lookup.east) -- ++(5,0) |- node[pos=.35,above,note]{命中} (hit.west);
\draw[link] (lookup.east) -- ++(5,0) |- node[pos=.35,below,note]{未命中} (miss.west);
\node[store,minimum width=26mm] (l2pool) at (132,68) {二级缓存L2 读服务池\\250 B/周期};
\node[store,minimum width=26mm] (ddrpool) at (132,56) {DDR片外存储器 共享池\\60 B/周期};
\draw[datalink] (hit.east)--(l2pool.west);
\draw[datalink] (miss.east)--(ddrpool.west);
\node[opmini,minimum width=30mm,fill=porange] (complete) at (126,43) {DDR片外存储器 读完成事件\\此时尝试填充};
\draw[link] (ddrpool.south)--(complete.north);
\node[tag] at (4,34) {逻辑张量 先进先出（FIFO）（只读命中不更新顺序）};
\node[opmini,minimum width=29mm,minimum height=9mm] (oldest) at (27,24) {最早插入\\优先驱逐};
\node[opmini,minimum width=26mm,minimum height=9mm] (middle) at (69,24) {已驻留项};
\node[opmini,minimum width=29mm,minimum height=9mm] (newest) at (111,24) {最近插入};
\draw[link] (oldest.east)--(middle.west);
\draw[link] (middle.east)--(newest.west);
\draw[line width=.8pt,draw=navy!60] (12,17)--(126,17);
\draw[link] (oldest.west) -- ++(-4,0);
\draw[datalink] (complete.south) -- ++(0,-5) -| (newest.north);
\node[note,anchor=west] at (6,10) {队列容量不足时按插入先后驱逐；大于 二级缓存L2 容量的张量不驻留。};
\node[note,anchor=west] at (6,4) {读未命中仅在 DDR片外存储器 读完成后入队；首次填充完成前的重复发射仍可能再次未命中。};
\node[opmini,minimum width=30mm,minimum height=8mm,fill=porange] (handoff) at (140,24) {跨核写出完成后\\等待 500 周期再读入};
\node[note,align=center] at (140,11) {读池独立；写出仍走 DDR片外存储器\\缓存查询仅针对输入搬运};
\end{tikzpicture}
""",
}

if __name__ == "__main__":
    for name, body in FIGURES.items():
        out = OUTS[name]
        out.mkdir(parents=True, exist_ok=True)
        body = re.sub(r"(?<!\\)\\(?=[\u4e00-\u9fff])", "", body)
        tex = PREAMBLE + body + "\\end{document}\n"
        (out / f"{name}.tex").write_text(tex, encoding="utf-8")
