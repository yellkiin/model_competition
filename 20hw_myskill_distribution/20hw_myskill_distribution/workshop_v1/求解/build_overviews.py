"""Build three evidence-led, editable TikZ question overviews from audited results."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "综合图"
OUT.mkdir(exist_ok=True)

CONFIG = {
    1: dict(title="问题一  独立Task的切图与多核调度", mechanism="二部计算图 $G=(\\mathcal O\\cup\\mathcal T,E)$", left="非COPY操作\\\\弱连通块", center="连通块分核\\\\深度分段／宽图分批", right="每子图一个Task\\\\边界张量经DDR", formula="$S_k=T_1/T_k$；最小化官方全局完成周期 $T_k$", result="100例五核平均加速比 $3.5093$；中位数 $4.1473$", validation="500个所选配置通过官方评估与独立时间线核验", imgs=("q1-F02", "q1-F03"), refs=("fig:q1-f02", "fig:q1-f03")),
    2: dict(title="问题二  同核Task合并与存储驻留", mechanism="场景A方案在场景B重新评价", left="同核子图合并\\\\中间量留在L1/UB", center="跨核边界COPY\\\\固定同步等待", right="容量约束与Spill\\\\DDR共享带宽", formula="$L(t)\\le C_{\\rm L1},\\;U(t)\\le C_{\\rm UB}$；按场景B $T_k$ 择优", result="100例五核平均加速比 $3.5456$；同方案A/B比均值 $1.0202$", validation="500个所选配置：合法性与时间线复核；容量峰值取官方输出", imgs=("q2-F02", "q2-F03"), refs=("fig:q2-f02", "fig:q2-f03")),
    3: dict(title="问题三  共享只读L2与成对反事实", mechanism="COPY\\_IN按逻辑张量编号查询共享L2", left="命中：Cache读池\\\\FIFO次序不刷新", center="未命中：DDR读池\\\\完成后按容量写入", right="同方案场景B对照\\\\隔离Cache机制收益", formula="$R_k=T_k^{(0)}/T_k^{(L2)}$；命中字节率按官方口径", result="100例五核同方案收益均值 $1.0260$；58例获益", validation="正式默认配置复核；六例54格非官方敏感性单独标识", imgs=("q3-F02", "q3-F03"), refs=("fig:q3-f02", "fig:q3-f03")),
}

MECHANISMS = {
    1: r'''
\foreach \x/\y/\label/\col in {82/128/$o_1$/pink,103/134/$t_1$/cream,103/122/$t_2$/cream,126/128/$o_2$/pink,145/128/$t_3$/cream}{\node[circle,draw=blue!65,fill=\col,minimum size=8mm,font=\fontsize{8}{9}\selectfont] at (\x,\y) {\label};}
\draw[blue,thick,-{Latex[length=2mm]}] (86,130)--(99,133);
\draw[blue,thick,-{Latex[length=2mm]}] (86,126)--(99,123);
\draw[blue,thick,-{Latex[length=2mm]}] (107,133)--(122,130);
\draw[blue,thick,-{Latex[length=2mm]}] (107,123)--(122,126);
\draw[blue,thick,-{Latex[length=2mm]}] (130,128)--(140,128);
\node[text=ink,font=\fontsize{7.5}{9}\selectfont] at (114,116) {操作—张量交替；箭头为依赖};
''',
    2: r'''
\draw[rounded corners=1mm,draw=blue!65,fill=white] (72,121) rectangle (111,140);
\draw[rounded corners=1mm,draw=blue!65,fill=white] (117,121) rectangle (156,140);
\node[text=ink,font=\fontsize{8}{9}\selectfont] at (91.5,136) {核心1：单Task};
\node[text=ink,font=\fontsize{8}{9}\selectfont] at (136.5,136) {核心2：单Task};
\node[draw=blue!50,fill=cyan,minimum width=12mm] (b1) at (82,127) {$g_1$};
\node[draw=blue!50,fill=cyan,minimum width=12mm] (b2) at (101,127) {$g_2$};
\node[draw=blue!50,fill=cream,minimum width=12mm] (b3) at (136,127) {$g_3$};
\draw[blue,thick,-{Latex[length=2mm]}] (b1)--(b2);
\draw[orange!85!black,thick,dashed,-{Latex[length=2mm]}] (b2)--node[above,font=\fontsize{7}{8}\selectfont]{COPY}(b3);
\node[text=ink,font=\fontsize{7.3}{8.5}\selectfont] at (113,116) {同核保留；跨核同步与搬运};
''',
    3: r'''
\node[draw=blue!60,fill=white,rounded corners=1mm,minimum width=25mm,minimum height=12mm,font=\fontsize{8}{9}\selectfont] (query) at (83,130) {COPY\_IN查询};
\node[draw=blue!60,fill=cream,rounded corners=1mm,minimum width=22mm,minimum height=12mm,font=\fontsize{8}{9}\selectfont] (cache) at (122,137) {L2读池};
\node[draw=blue!60,fill=white,rounded corners=1mm,minimum width=22mm,minimum height=12mm,font=\fontsize{8}{9}\selectfont] (ddr) at (122,121) {DDR读池};
\draw[blue,thick,-{Latex[length=2mm]}] (query.north east)--node[above,font=\fontsize{7}{8}\selectfont]{命中}(cache.west);
\draw[orange!85!black,thick,-{Latex[length=2mm]}] (query.south east)--node[below,font=\fontsize{7}{8}\selectfont]{未命中}(ddr.west);
''',
}


def build(q, d):
    # Absolute scientific graphic paths keep TeX compilation independent of cwd.
    img1 = (ROOT / '正式图件' / (d['imgs'][0] + '.pdf')).as_posix()
    img2 = (ROOT / '正式图件' / (d['imgs'][1] + '.pdf')).as_posix()
    tex = r'''\documentclass{article}
\usepackage[paperwidth=160mm,paperheight=154mm,margin=0pt]{geometry}
\usepackage[UTF8,fontset=windows]{ctex}
\usepackage{tikz}
\usepackage{graphicx}
\usetikzlibrary{arrows.meta,positioning,calc}
\begin{document}
\pagestyle{empty}\noindent
\begin{tikzpicture}[x=1mm,y=1mm, every node/.style={font=\sffamily}]
\definecolor{ink}{HTML}{26374F}
\definecolor{cyan}{HTML}{E3F3F5}
\definecolor{pink}{HTML}{F9E8EB}
\definecolor{green}{HTML}{E7F4EB}
\definecolor{cream}{HTML}{FFF3DD}
\definecolor{blue}{HTML}{4A9DAD}
\fill[white] (0,0) rectangle (160,154);
\fill[cyan] (0,113) rectangle (160,154);
\fill[pink] (0,71) rectangle (160,110);
\fill[green] (0,0) rectangle (160,68);
\node[anchor=west,text=ink,font=\sffamily\bfseries\fontsize{12}{14}\selectfont] at (5,148) {TITLE};
\node[anchor=west,text=ink,font=\sffamily\bfseries\fontsize{10}{12}\selectfont] at (5,137) {01 对象与机理};
\node[anchor=west,text=ink,font=\sffamily\fontsize{9}{11}\selectfont] at (6,125) {MECHANISM};
MECHGRAPH
\node[anchor=west,text=ink,font=\sffamily\bfseries\fontsize{10}{12}\selectfont] at (5,103) {02 方法与约束};
\node[rounded corners=1mm,draw=blue!50,fill=white,minimum width=43mm,minimum height=19mm,align=center,text=ink,font=\sffamily\fontsize{8.6}{10.5}\selectfont] (a) at (26,89) {LEFT};
\node[rounded corners=1mm,draw=blue!50,fill=white,minimum width=43mm,minimum height=19mm,align=center,text=ink,font=\sffamily\fontsize{8.6}{10.5}\selectfont] (b) at (80,89) {CENTER};
\node[rounded corners=1mm,draw=blue!50,fill=white,minimum width=43mm,minimum height=19mm,align=center,text=ink,font=\sffamily\fontsize{8.6}{10.5}\selectfont] (c) at (134,89) {RIGHT};
\draw[blue,thick,-{Latex[length=2mm]}] (a.east) -- (b.west);
\draw[blue,thick,-{Latex[length=2mm]}] (b.east) -- (c.west);
\node[anchor=west,text=ink,font=\sffamily\fontsize{8.2}{10}\selectfont] at (5,74) {FORMULA};
\node[anchor=west,text=ink,font=\sffamily\bfseries\fontsize{10}{12}\selectfont] at (5,62) {03 实测结果与核验};
\node[anchor=west,text=ink,font=\sffamily\bfseries\fontsize{8.8}{10.5}\selectfont] at (5,52) {RESULT};
\node[anchor=west,text=ink,font=\sffamily\fontsize{8.3}{10}\selectfont] at (5,44) {VALIDATION};
\node[anchor=west] at (5,21) {\includegraphics[width=72mm,height=30mm,keepaspectratio]{IMG1}};
\node[anchor=east] at (155,21) {\includegraphics[width=72mm,height=30mm,keepaspectratio]{IMG2}};
\node[anchor=west,text=ink,font=\sffamily\fontsize{7.5}{9}\selectfont] at (5,4) {细节参见正文图~\ref{REF1}、图~\ref{REF2}；缩图仅作证据导航。};
\end{tikzpicture}
\end{document}
'''
    for k,v in {'TITLE':d['title'],'MECHANISM':d['mechanism'],'MECHGRAPH':MECHANISMS[q],'LEFT':d['left'],'CENTER':d['center'],'RIGHT':d['right'],'FORMULA':d['formula'],'RESULT':d['result'],'VALIDATION':d['validation'],'IMG1':img1,'IMG2':img2,'REF1':d['refs'][0],'REF2':d['refs'][1]}.items():
        tex=tex.replace(k,v)
    # Standalone figures should not carry unresolved cross-document labels.
    tex=tex.replace('图~\\ref{'+d['refs'][0]+'}、图~\\ref{'+d['refs'][1]+'}', '图 '+d['imgs'][0]+'、'+d['imgs'][1])
    target=OUT/f'q{q}-overview.tex'
    target.write_text(tex,encoding='utf-8')
    return target


if __name__=='__main__':
    for q,d in CONFIG.items():
        print(build(q,d))

