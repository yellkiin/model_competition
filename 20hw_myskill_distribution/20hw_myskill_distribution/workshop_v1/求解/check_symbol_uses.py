from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str((root/'../华为杯_论文规范模板/tools').resolve()))
from first_chapters import symbol_rows
rows=symbol_rows((root/'论文/章节内容/03_关键性符号说明.tex').read_text(encoding='utf-8'))
chapters=list((root/'论文/章节内容').glob('0[4-7]*.tex'))
for row in rows:
    symbol=row['symbol']
    paths=[p.name for p in chapters if symbol in p.read_text(encoding='utf-8')]
    print(symbol,paths)
