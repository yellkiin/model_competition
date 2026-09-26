# 线刻设色总流程图 · 第二版

保留原 `engraved_workflow` 的六算子案例、子图包络、核心剖面、细排线与各方法模块；本轮重点改局部设色、跨模块连接和右下角公式留白。原母版、论文正文和其他论文图不覆盖。

## 先看成图

默认配色：青绿·赭石。仓库 `assets/workflow_qinglu.svgz` 为可编辑母版；另有浅绛、烟岚及灰阶。会话交付包同时提供普通 `.svg`。所有文字仍是text/tspan，各模块、公式与流程连接都有独立ID。SVG中没有嵌入位图或字体文件。

`.svgz` 是同一SVG的无损压缩版本，Inkscape可直接打开编辑；本地运行会生成普通 `.svg`。所有PDF/高清PNG在本次会话完整包内，并可用下面命令在本地重新导出。

主要连接现在只用单线：共同状态到来源选择、筛选通过到执行、执行到右侧评价、判断到更新、停止到输出。筛去重选和下一轮反馈各走独立通道。删除了原来包围公式的小弯箭头，Cq公式恢复为右侧评价区域的居中对象，箭头从区域右边进入，不穿过公式。

按 `workshop_v2` 明确一次小文字：每次读完成均尝试缓存填充，已驻留对象保持FIFO位置。其余方法名、符号、接受条件、三问执行参数和同方案配对含义不变。详见 `docs/SOURCE_ALIGNMENT.md`。

## 本地生成

仅生成可编辑SVG：

```bash
python paper_a_figures/engraved_workflow/ink_v2/build.py --all-palettes --svg-only
```

同时导出PDF、6000像素PNG和预览，需要本机Inkscape：

```bash
python paper_a_figures/engraved_workflow/ink_v2/build.py --all-palettes
```

可单独指定 `--palette qinglu`、`qianjiang`、`yanlan`、`mono`。颜色来自 `paper_a_figures/ink_engraving_agent/palettes.json`，构图与文字由本目录build.py读取旧母版后重组，始终以旧母版为输入，不读取自己上轮导出的文件。

画布420×310.8mm，额外高度只用于外侧回路与图例留白；三个上部模块的原坐标不改变。适合整页横向总图或数字放大阅读。后续小图应取相应局部模块，不能把所有细节压进半栏。

两条编辑路径：Inkscape手改SVG后另存；长期维护则改Python和角色色板再生成。重新生成会覆盖对应自动产物，不会覆盖另存的手工稿。

## 可持续图件Agent

`paper_a_figures/ink_engraving_agent/AGENT.md` 是完整操作提示词；`style.py` 能将同套风格赋予SVG及既有Matplotlib绘图代码，提供显式角色绑定、连续/发散色阶和保留文字的矢量导出。当前只交付总流程图与工具，不提前替换论文所有数据图。

`docs/REFERENCES.md` 记录新增国画设色来源。本次所有排版、绘制、渲染和视觉检查在本地容器完成，没有文生图、云端渲染或复制画作像素。
