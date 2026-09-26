# 可复用的线刻设色工具

入口：`AGENT.md`。色彩与线条唯一来源：`palettes.json`。不是新增调度算法，也不修改原始实验数据。

- `qinglu`：青绿·赭石，默认；`qianjiang`：浅绛·苔色；`yanlan`：烟岚·石青；`mono`：灰阶。
- SVG：`svg_css()`、`palette()`、`wash()`。
- Matplotlib：`mpl_context()` 用于原绘图程序；`restyle_axes()` 用于已创建的图；`series_style()` 显式绑定角色；`colormaps()` 提供连续/发散色图。
- 一篇论文固定一个主题。不同图保持角色与标记，不能逐图随意交换颜色。

## 将风格交给现有画图代码

在仓库根目录运行。仅SVG生成使用标准库，数据图适配需要原程序使用的Matplotlib。

```python
import matplotlib.pyplot as plt
from paper_a_figures.ink_engraving_agent.style import (
    mpl_context, series_style, restyle_axes, export_figure,
)

# x, values_s, values_m, values_f 仍由原始、已绑定数据读入。
with mpl_context('qinglu'):
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(x, values_s, label='结构候选', **series_style('structure'))
    ax.plot(x, values_m, label='驻留候选', **series_style('memory'))
    ax.plot(x, values_f, label='FIFO候选', **series_style('fifo'))
    # 原程序原有标题、坐标、尺度、统计、区间仍留在这里。
    ax.legend()
    export_figure(fig, 'outputs/example')
```

已有 `fig, ax` 时：

```python
restyle_axes(ax, {'结构候选':'structure', '驻留候选':'memory',
                 'FIFO候选':'fifo'}, name='qinglu')
# 原程序控制图例位置；重新生成图例以反映新样式。
ax.legend()
export_figure(fig, 'outputs/restyled')
```

`restyle_axes(ax)` 不提供角色表时，只调整中性轴和文字，不猜系列归属。不更改数组、标签、坐标尺度、范围或热图归一化。导出保持SVG文字可编辑，PDF为矢量；不随项目分发字体文件。

可在不同Matplotlib版本上继续使用原画图代码；本次以容器中实际版本验证线、散点、柱图的数值和坐标范围不变。不是批量重画当前论文的所有图。

字体优先使用本机简体中文字体；Matplotlib仅识别CJK字体集合的首个名称时会选本机可用CJK族。需要与SVG完全相同的简体字形时，安装独立SC字体。程序不复制、下载或分发字体文件。
