#!/usr/bin/env python3
"""export_figure.py — 把 .drawio 导成 1:1 PNG 与矢量 PDF，供肉眼自检和交付。

    python3 export_figure.py fig.drawio                 # 出 fig.png + fig.pdf
    python3 export_figure.py fig.drawio --png-only -s 2 # 只出 2 倍图，便于看细节

依赖 draw.io 桌面版命令行（macOS: brew install --cask drawio；命令名 drawio）。
没装时会给出替代方案，不静默失败。
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys


def find_drawio_cli():
    """跨平台定位 draw.io 桌面版命令行。

    顺序：环境变量 DRAWIO_CLI → PATH 中的 drawio → PATH 中的 draw.io
    （Windows 安装后命令名通常是 draw.io）→ Windows 常见安装目录兜底。
    """
    cli = (
        os.environ.get('DRAWIO_CLI')
        or shutil.which('drawio')
        or shutil.which('draw.io')
    )
    if cli:
        return cli
    if os.name == 'nt':
        candidates = [
            r'C:\Program Files\draw.io\draw.io.exe',
            r'C:\Program Files (x86)\draw.io\draw.io.exe',
            str(pathlib.Path(os.environ.get('LOCALAPPDATA', ''))
                / 'Programs' / 'draw.io' / 'draw.io.exe'),
        ]
        for p in candidates:
            if p and pathlib.Path(p).exists():
                return p
    return None


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        print(p.stdout + p.stderr, file=sys.stderr)
    return p.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('drawio')
    ap.add_argument('-s', '--scale', type=float, default=1, help='PNG 缩放，默认 1（1 单位=1 像素）')
    ap.add_argument('--png-only', action='store_true')
    ap.add_argument('--pdf-only', action='store_true')
    a = ap.parse_args()

    src = pathlib.Path(a.drawio)
    if not src.exists():
        sys.exit(f'找不到 {src}')
    cli = find_drawio_cli()
    if not cli:
        sys.exit('未找到 drawio/draw.io 命令行。\n'
                 '  Windows: 安装 draw.io 桌面版并将其目录加入 PATH（命令名为 draw.io），\n'
                 '           或设置环境变量 DRAWIO_CLI 指向 draw.io.exe 全路径；\n'
                 '  macOS: brew install --cask drawio\n'
                 '  或：用 diagrams.net 网页版打开 .drawio 后 File → Export as → PNG/PDF\n'
                 '  注意：没有渲染图就无法自检，不要跳过这一步。')

    # 用画布宽度锁定输出，保证 1 单位 = 1 像素；否则 drawio 会按内容包围盒另算，
    # 输出比画布大几像素，没法和参考图做逐像素比对
    m = re.search(r'pageWidth="([\d.]+)"', src.read_text(encoding='utf-8'))
    width = [f'--width', str(int(float(m.group(1)) * a.scale))] if m else []

    ok = True
    if not a.pdf_only:
        png = src.with_suffix('.png')
        ok &= run([cli, '-x', '-f', 'png', '-s', str(a.scale), '-b', '0',
                   *width, '-o', str(png), str(src)])
        if ok:
            print(f'✓ {png}')
    if not a.png_only:
        pdf = src.with_suffix('.pdf')
        ok &= run([cli, '-x', '-f', 'pdf', '--crop', '-o', str(pdf), str(src)])
        if ok:
            print(f'✓ {pdf}')
    if not ok:
        sys.exit(1)
    print('接下来务必打开 PNG 逐块核对：文字有无溢出/压线、箭头方向、数值有没有抄错。')


if __name__ == '__main__':
    main()
