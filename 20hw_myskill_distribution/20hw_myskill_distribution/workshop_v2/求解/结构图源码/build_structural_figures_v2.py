from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTS = {"roadmap": ROOT/"求解/总体/图片", "q1_task": ROOT/"求解/问题一/图片", "q2_task": ROOT/"求解/问题二/图片", "q3_fifo": ROOT/"求解/问题三/图片"}
PRE = r'''\documentclass[tikz,border=1.5mm]{standalone}
\usepackage[UTF8,fontset=windows]{ctex}
\setCJKmainfont[AutoFakeBold=1.5]{SimSun}
\usepackage{amsmath,amssymb}
\usetikzlibrary{arrows.meta,positioning,calc,shapes.geometric}
\definecolor{navy}{HTML}{17324D}\definecolor{blue}{HTML}{2878A5}\definecolor{teal}{HTML}{218C83}\definecolor{orange}{HTML}{D9873F}\definecolor{ink}{HTML}{243746}\definecolor{muted}{HTML}{647789}\definecolor{pale}{HTML}{F3F7FA}\definecolor{pblue}{HTML}{E9F2F8}\definecolor{pteal}{HTML}{E8F4F1}\definecolor{porange}{HTML}{FCF1E7}
\tikzset{box/.style={draw=navy!65,fill=white,rounded corners=1.5mm,line width=.6pt,text=ink,align=center,font=\fontsize{7.5}{9}\selectfont,text width=30mm,minimum height=9mm,inner sep=1mm},sm/.style={box,font=\fontsize{7}{8.3}\selectfont},store/.style={box,draw=teal!80!black,fill=pteal},heading/.style={text=navy,font=\fontsize{8}{9}\selectfont\bfseries,anchor=west},lab/.style={text=muted,align=center,font=\fontsize{6.8}{8}\selectfont},arr/.style={-{Stealth[length=1.7mm]},draw=blue,line width=.65pt},data/.style={-{Stealth[length=1.7mm]},draw=teal,line width=.7pt},wait/.style={-{Stealth[length=1.7mm]},draw=orange,densely dashed,line width=.7pt}}
\begin{document}
'''
FIG = {
"roadmap": r'''\begin{tikzpicture}[x=1mm,y=1mm]
\path[fill=pale,rounded corners=2mm] (0,0) rectangle (160,88);
\node[heading] at (5,82) {联合决策：构造一个完整候选方案};
\node[sm,text width=32mm] (p) at (25,73) {子图划分 $\mathcal P$};
\node[sm,text width=32mm] (a) at (62,73) {核心归属 $a$};
\node[sm,text width=32mm] (pi) at (99,73) {核内顺序 $\boldsymbol\pi$};
\node[sm,fill=pblue,text width=32mm] (x) at (136,73) {完整候选 $x$};
\draw[arr](p)--(a);\draw[arr](a)--(pi);\draw[arr](pi)--(x);

\node[box,text width=43mm,minimum height=20mm] (q1) at (27,51) {\textbf{问题一｜子图级任务}\\跨子图数据经 DDR；同核切换等待 100 周期；跨核依赖等待 1000 周期};
\node[box,text width=43mm,minimum height=20mm] (q2) at (80,51) {\textbf{问题二｜核心级任务}\\同核片上驻留；跨核写出完成后等待 500 周期，再释放读入};
\node[box,text width=43mm,minimum height=20mm] (q3) at (133,51) {\textbf{问题三｜加入 L2 FIFO（二级缓存）}\\沿用跨核交接；按逻辑张量查询，命中与未命中分池读服务};
\draw[arr](x.south)--(136,64)--(27,64)--(q1.north);\draw[arr](136,64)--(80,64)--(q2.north);\draw[arr](136,64)--(133,64)--(q3.north);
\node[lab] at (80,38) {同一方案空间，三种执行规则，统一的周期与搬运目标};
\node[box,text width=48mm,minimum height=12mm,fill=pblue] (eval) at (48,28) {按场景重建任务、搬运与存储事件\\离散事件执行并检查可行性};
\node[box,text width=40mm,minimum height=12mm] (metric) at (112,28) {总体任务执行时间 $C_q$\\与额外搬运量 $D_q$};
\draw[arr](eval)--(metric);
\node[heading] at (40,15) {邻域搜索与反馈};
\node[sm,text width=33mm] (move) at (26,7) {生成结构、驻留或顺序邻域};
\node[sm,text width=33mm] (screen) at (70,7) {预检并筛除下界劣解};
\node[sm,text width=36mm,fill=porange] (accept) at (116,7) {完整评价；可行且字典序改善才接受};
\node[sm,text width=24mm] (inc) at (150,7) {更新当前解};
\draw[arr](move)--(screen);\draw[arr](screen)--(accept);\draw[arr](accept)--(inc);
\draw[wait](inc.north)--(150,19)--(26,19)--(move.north);
\end{tikzpicture}''',
"q1_task": r'''\begin{tikzpicture}[x=1mm,y=1mm]
\path[fill=pale,rounded corners=2mm](0,0)rectangle(160,68);
\node[heading]at(5,62){核心 1：两个子图任务按序执行};
\node[box](g1)at(35,51){子图 $G_1$\\任务 1};\node[box](g2)at(125,51){子图 $G_2$\\任务 2};
\draw[arr](g1.east)--node[above,lab,text width=49mm]{同核切换等待 100 周期}(g2.west);
\node[sm](out)at(35,32){边界写出\\COPY\_OUT};\node[store](ddr)at(80,32){DDR 片外存储\\共享带宽池};\node[sm](in)at(125,32){边界读入\\COPY\_IN};
\draw[data](g1.south)--(out.north);\draw[data](out.east)--(ddr.west);\draw[data](ddr.east)--(in.west);\draw[data](in.north)--(g2.south);
\node[heading]at(5,22){核心 2};\node[box](g3)at(125,13){子图 $G_3$\\任务 3};
\draw[wait](g2.east)--(153,51)--(153,13)--(g3.east);`n\node[lab,text width=43mm]at(69,15){跨核前驱完成后等待 1000 周期};
\node[lab,anchor=west,align=left,text width=146mm]at(6,3){示例数据边 $G_1\to G_2$ 跨子图，即使同核也经 DDR；跨核依赖另受固定等待约束。};
\end{tikzpicture}''',
"q2_task": r'''\begin{tikzpicture}[x=1mm,y=1mm]
\path[fill=pale,rounded corners=2mm](0,0)rectangle(160,68);
\node[heading]at(5,62){核心 1：一个任务内的片上驻留};
\node[box](g1)at(31,52){子图 $G_1$\\生成张量 $u$};\node[box](g2)at(129,52){子图 $G_2$\\使用张量 $u$};
\draw[arr](g1.east)--node[above,lab,text width=43mm]{同一核心任务内按序执行}(g2.west);
\node[store,text width=35mm](ub)at(80,41){片上 L1 / UB\\张量 $u$ 可驻留};
\draw[data](g1.south)--(ub.north west);\draw[data](ub.north east)--(g2.south);

\node[sm](in)at(31,28){目标核读入\\COPY\_IN};\node[store](ddr)at(80,28){DDR 片外存储\\共享服务};\node[sm](out)at(129,28){来源核写出\\COPY\_OUT};
\draw[data](out.west)--(ddr.east);\draw[data](ddr.west)--(in.east);\draw[data](g2.south)--(out.north);
\node[box,text width=30mm](g3)at(31,10){子图 $G_3$\\目标操作};\draw[data](in.south)--(g3.north);
\draw[wait](out.south)--(129,18)--(31,18)--(in.south);
\node[lab,fill=pale,inner sep=1pt]at(80,18){写出完成后等待 500 周期};
\node[lab,anchor=west,align=left,text width=146mm]at(6,3){同核子图不另建任务切换；驻留受片上容量与换出规则约束。跨核交接依次经过 COPY\_OUT、DDR 与 COPY\_IN。};
\end{tikzpicture}''',
"q3_fifo": r'''\begin{tikzpicture}[x=1mm,y=1mm]
\path[fill=pale,rounded corners=2mm](0,0)rectangle(160,76);
\node[sm,text width=30mm](issue)at(19,64){COPY\_IN 发射\\逻辑张量 $t$};
\node[diamond,draw=navy!70,fill=pblue,aspect=2,inner sep=1mm,text=ink,align=center,font=\fontsize{7}{8}\selectfont,text width=25mm,minimum height=10mm](lookup)at(59,64){先进先出缓存\\按逻辑标识查询};
\draw[arr](issue.east)--(lookup.west);
\node[sm,text width=29mm](hit)at(97,69){命中：保持原队位};\node[sm,text width=29mm](miss)at(97,55){未命中：发起 DDR 读取};
\draw[data](lookup.east)--(73,64)|-node[pos=.28,above,lab]{命中}(hit.west);\draw[arr](lookup.east)--(73,64)|-node[pos=.28,below,lab]{未命中}(miss.west);
\node[store,text width=29mm](l2)at(139,69){二级缓存 L2\\独立读池：250 B/周期};\node[store,text width=29mm](ddr)at(139,55){DDR 片外存储\\共享读写池：60 B/周期};
\draw[data](hit.east)--(l2.west);\draw[data](miss.east)--(ddr.west);
\node[sm,text width=59mm,fill=porange](done)at(114,40){任一 COPY\_IN 完成后尝试填充\\仍驻留：保持队位；已离开：重新入队};\draw[arr](ddr.south)--(139,48)--(done.north east);\draw[data](l2.east)--(158,69)--(158,40)--(done.east);
\node[heading]at(5,31){FIFO 队列：按成功填入的先后排列};
\node[sm,text width=31mm](old)at(31,21){最早插入\\优先驱逐};\node[sm,text width=27mm](resident)at(79,21){已驻留项};\node[sm,text width=31mm](new)at(127,21){最近插入};
\draw[arr](old.east)--(resident.west);\draw[arr](resident.east)--(new.west);\draw[arr](old.west)--(5,21);\node[lab,anchor=west]at(5,26){驱逐};
\draw[data](done.south)--(119,34)-|(new.north);
\node[lab,anchor=west,align=left,text width=148mm]at(6,9){命中保持队位；每次读入完成时尝试填充，空间不足则从队首淘汰；大于 L2 容量的张量跳过填充。};
\node[lab,anchor=west,align=left,text width=148mm]at(6,4){跨核写出仍经 DDR，完成后等待 500 周期再释放 COPY\_IN；填充完成前重复发射仍可能未命中。};
\end{tikzpicture}'''
}
if __name__ == "__main__":
    for name, body in FIG.items():
        out = OUTS[name]; out.mkdir(parents=True, exist_ok=True)
        (out/f"{name}.tex").write_text(PRE+body+r"\end{document}"+"\n", encoding="utf-8")







