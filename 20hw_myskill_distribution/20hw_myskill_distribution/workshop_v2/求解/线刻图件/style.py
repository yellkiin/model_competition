"""Ink-engraving figure language: white paper, semantic pigments, editable text.

No data manipulation. Uses installed fonts; never copies/distributes font files.
"""
from pathlib import Path
import json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import PercentFormatter

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
REPO=next(p for p in HERE.parents if (p/'paper_a_figures/ink_engraving_agent/palettes.json').exists())
TOKENS=json.loads((REPO/'paper_a_figures/ink_engraving_agent/palettes.json').read_text(encoding='utf8'))
THEME=os.environ.get('PAPER_INK_THEME','qinglu')
if THEME not in TOKENS['palettes']:raise ValueError('Unknown manuscript theme')
P={**TOKENS['common'],**TOKENS['palettes'][THEME]}
INK,S,M,F=P['ink'],P['structure'],P['memory'],P['fifo']
GRAY=P['muted']

def wash(c, a=.14):
    rgb=[int(c[i:i+2],16) for i in (1,3,5)]
    return '#'+''.join(f'{round(255+(v-255)*a):02x}' for v in rgb)

# Explicit families let Latin/numerals and Chinese match the manuscript roles.
# Native fonts are preferred. CJK fallback is explicit, not labelled as SimSun.
font_folder=os.environ.get('PAPER_INK_FONT_DIR')
if font_folder:
    for f in Path(font_folder).glob('*.ttf'):font_manager.fontManager.addfont(str(f))
installed={x.name for x in font_manager.fontManager.ttflist}
FONT=[x for x in ['Times New Roman','SimSun','Noto Serif CJK SC','Noto Serif CJK JP','DejaVu Serif'] if x in installed]
plt.rcParams.update({
    'font.family':FONT,'font.size':10,'axes.labelsize':10,'axes.titlesize':10.5,
    'axes.titleweight':'normal','text.color':INK,'axes.labelcolor':INK,
    'axes.edgecolor':INK,'axes.linewidth':.7,'axes.spines.top':False,'axes.spines.right':False,
    'xtick.color':GRAY,'ytick.color':GRAY,'xtick.labelsize':9,'ytick.labelsize':9,
    'xtick.major.width':.65,'ytick.major.width':.65,'xtick.major.size':3,'ytick.major.size':3,
    'lines.linewidth':1.55,'lines.markersize':4.5,'legend.frameon':False,'legend.fontsize':9,
    'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white',
    'axes.unicode_minus':False,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
    'mathtext.fontset':'cm','hatch.linewidth':.45,
})

def figure(size=(6.35,3.5),grid='y'):
    fig,ax=plt.subplots(figsize=size,layout='constrained')
    if grid:ax.grid(axis=grid,color=wash(INK,.12),lw=.5)
    ax.set_axisbelow(True)
    return fig,ax

def core_style(n):
    # Consistent core-count coding across questions; color is not the only key.
    colors={1:GRAY,2:wash(S,.68),3:S,4:M,5:F}
    styles={1:':',2:(0,(5,2)),3:(0,(4,1.5,1,1.5)),4:(0,(1,1.6)),5:'-'}
    return dict(color=colors[n],linestyle=styles[n],lw=1.55)

def pigment_map(role='structure'):
    color=P[role]
    return LinearSegmentedColormap.from_list('ink_'+role,[wash(color,.1),wash(color,.5),color,INK])

def finish(fig,question,name):
    out=WORK/'求解'/('问题'+['','一','二','三'][question])/'图片'
    out.mkdir(parents=True,exist_ok=True)
    for ext in ('pdf','svg','png'):
        fig.savefig(out/f'{name}.{ext}',dpi=300,bbox_inches='tight',pad_inches=.06,
                    metadata={'Creator':'paper ink figure suite'} if ext=='pdf' else None)
    plt.close(fig)
    return str(out.relative_to(WORK)/name)
