#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from paper_a_figures.ink_engraving_agent.style import (
    mpl_context, series_style, export_figure, restyle_axes, colormaps
)

HERE = Path(__file__).resolve().parent
OUT = HERE / 'outputs'
OUT.mkdir(parents=True, exist_ok=True)


def line_demo(name='qinglu'):
    x = np.array([1,2,3,4,5])
    y1 = np.array([1.0,1.5,1.9,2.2,2.6])
    y2 = np.array([1.0,1.3,1.6,1.7,1.8])
    y3 = np.array([1.0,1.1,1.4,1.9,2.1])
    with mpl_context(name):
        fig, ax = plt.subplots(figsize=(6.2, 3.4))
        ax.plot(x, y1, label='结构优化', **series_style('structure'))
        ax.plot(x, y2, label='驻留优化', **series_style('memory'))
        ax.plot(x, y3, label='FIFO优化', **series_style('fifo'))
        ax.set_xlabel('搜索时间 / min')
        ax.set_ylabel('加速比')
        ax.set_title('示例：时间—质量曲线')
        ax.legend(loc='lower right')
        export_figure(fig, OUT / f'line_demo_{name}')
        plt.close(fig)


def bar_demo(name='qinglu'):
    labels = ['Q1','Q2','Q3']
    base = np.array([2.8, 3.6, 3.9])
    improve = np.array([3.2, 4.1, 4.5])
    with mpl_context(name):
        fig, ax = plt.subplots(figsize=(5.4, 3.2))
        xx = np.arange(len(labels))
        ax.bar(xx - 0.18, base, width=0.34, label='原方法')
        ax.bar(xx + 0.18, improve, width=0.34, label='本文方法')
        restyle_axes(ax, {'原方法':'memory', '本文方法':'structure'}, name=name)
        ax.set_xticks(xx, labels)
        ax.set_ylabel('平均加速比')
        ax.set_title('示例：三问平均效果')
        ax.legend(loc='upper left')
        export_figure(fig, OUT / f'bar_demo_{name}')
        plt.close(fig)


def heatmap_demo(name='qinglu'):
    data = np.array([
        [0.1, 0.2, 0.5, 0.8],
        [0.2, 0.3, 0.6, 0.9],
        [0.15, 0.4, 0.55, 0.7],
    ])
    with mpl_context(name):
        fig, ax = plt.subplots(figsize=(5.6, 2.8))
        im = ax.imshow(data, aspect='auto', cmap=colormaps(name)['sequential'])
        ax.set_title('示例：参数敏感性热图')
        ax.set_xlabel('时间预算档位')
        ax.set_ylabel('图类别')
        ax.set_xticks(range(4), ['30s','60s','120s','300s'])
        ax.set_yticks(range(3), ['稠密','稀疏','长链'])
        cbar = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
        cbar.set_label('相对收益')
        export_figure(fig, OUT / f'heatmap_demo_{name}')
        plt.close(fig)


if __name__ == '__main__':
    for palette_name in ['qinglu', 'qianjiang', 'yanlan', 'mono']:
        line_demo(palette_name)
        bar_demo(palette_name)
        heatmap_demo(palette_name)
