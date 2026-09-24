"""Render the adapted roadmap at the paper's actual 160 mm text width."""

from pathlib import Path

import fitz


folder = Path(__file__).resolve().parent
source = fitz.open(folder / "总体路线图_紧凑.pdf")
page = fitz.open()
a4 = page.new_page(width=fitz.paper_rect("a4").width, height=fitz.paper_rect("a4").height)
mm = 72 / 25.4
width = 160 * mm
height = width * source[0].rect.height / source[0].rect.width
a4.show_pdf_page(fitz.Rect(25 * mm, 25 * mm, 25 * mm + width, 25 * mm + height), source, 0)
page.save(folder / "总体路线图_论文尺寸.pdf")
a4.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72)).save(folder / "总体路线图_论文尺寸.png")
print({"figure_width_mm": 160, "figure_height_mm": height / mm})
