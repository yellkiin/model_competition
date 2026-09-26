"""Shared ink/engraving tokens. No network, data transforms, or global plot state."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
import json

TOKENS = json.loads(Path(__file__).with_name('palettes.json').read_text(encoding='utf8'))
ACTIVE_PALETTE = ContextVar('ink_engraving_palette', default=TOKENS['default'])


def palette(name: str | None = None) -> dict:
    name = name or ACTIVE_PALETTE.get()
    if name not in TOKENS['palettes']:
        raise ValueError(f"Unknown palette {name!r}; use {', '.join(TOKENS['palettes'])}")
    return {**TOKENS['common'], **TOKENS['palettes'][name], 'key': name}


def wash(color: str, amount: float = .12) -> str:
    """Mix a pigment with white paper, retaining opaque editable vector fills."""
    if not 0 <= amount <= 1:
        raise ValueError('amount must be in [0, 1]')
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(255 + (v - 255) * amount):02X}' for v in rgb)


def svg_css(name: str = 'qinglu') -> str:
    p = palette(name)
    w = p['stroke_svg']
    sans = ','.join("'" + f + "'" if ' ' in f else f for f in p['font_sans'])
    serif = ','.join("'" + f + "'" if ' ' in f else f for f in p['font_serif'])
    return f"""
/* Shared pigment roles; preserve black technical structure and white paper. */
text {{fill:{p['ink']};font-family:{sans};}}
.serif,.math {{font-family:{serif};}}
.muted {{fill:{p['muted']};}}
.white {{fill:white;}}
.fine,.outline,.paper,.route {{stroke:{p['ink']};}}
.hair {{stroke:{p['hair']};}}
.faint {{stroke:{p['faint']};}}
.main-link {{fill:none;stroke:{p['ink']};stroke-width:{w['main']};stroke-linejoin:round;stroke-linecap:round;}}
.feedback-link {{fill:none;stroke:{p['structure']};stroke-width:{w['feedback']};stroke-dasharray:9 7;stroke-linejoin:round;stroke-linecap:round;}}
.branch-link {{fill:none;stroke:{p['muted']};stroke-width:{w['feedback']};stroke-linejoin:round;stroke-linecap:round;}}
.local-link {{stroke-width:{w['local']};}}
.role-structure {{fill:{p['structure']};stroke:{p['structure']};}}
.role-memory {{fill:{p['memory']};stroke:{p['memory']};}}
.role-fifo {{fill:{p['fifo']};stroke:{p['fifo']};}}
.text-structure {{fill:{p['structure']};stroke:none;}}
.text-memory {{fill:{p['memory']};stroke:none;}}
.text-fifo {{fill:{p['fifo']};stroke:none;}}
.wash-structure {{fill:{wash(p['structure'],.13)};}}
.wash-memory {{fill:{wash(p['memory'],.13)};}}
.wash-fifo {{fill:{wash(p['fifo'],.13)};}}
"""


@lru_cache(maxsize=1)
def installed_sans() -> tuple[str, ...]:
    """Prefer SC faces; use an installed CJK collection face when Matplotlib
    exposes only the TTC's first family. No font files are bundled or copied.
    """
    from matplotlib import font_manager
    available = {f.name for f in font_manager.fontManager.ttflist}
    preferred = [*TOKENS['common']['font_sans'][:-1],
                 'Noto Sans CJK JP', 'Noto Sans CJK TC', 'Source Han Sans SC',
                 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    return tuple(dict.fromkeys(n for n in preferred if n in available)) or ('DejaVu Sans',)


@contextmanager
def mpl_context(name: str = 'qinglu'):
    """Use around original plotting code; does not change data/axes/aggregation."""
    import matplotlib as mpl
    from cycler import cycler
    p = palette(name)
    colors = [p['structure'], p['memory'], p['fifo'], p['ink']]
    rc = {
        'font.family': 'sans-serif', 'font.sans-serif': list(installed_sans()),
        'font.size': 9.5, 'axes.titlesize': 11, 'axes.labelsize': 9.5,
        'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5,
        'figure.facecolor': p['paper'], 'axes.facecolor': p['paper'],
        'text.color': p['ink'], 'axes.edgecolor': p['ink'], 'axes.labelcolor': p['ink'],
        'xtick.color': p['muted'], 'ytick.color': p['muted'],
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.linewidth': .65, 'lines.linewidth': 1.5, 'lines.markersize': 4.5,
        'axes.grid': False, 'grid.color': p['faint'], 'grid.linewidth': .45,
        'legend.frameon': False, 'legend.fontsize': 8.5,
        'axes.prop_cycle': cycler(color=colors),
        'svg.fonttype': 'none', 'pdf.fonttype': 42, 'ps.fonttype': 42,
        'savefig.facecolor': p['paper'], 'savefig.dpi': 300,
    }
    token = ACTIVE_PALETTE.set(p['key'])
    try:
        with mpl.rc_context(rc):
            yield p
    finally:
        ACTIVE_PALETTE.reset(token)


def series_style(role: str, name: str | None = None) -> dict:
    """Explicit semantic mapping survives reordered legends and missing series."""
    p = palette(name)
    roles = [*TOKENS['common']['role_order'], 'reference']
    if role not in roles:
        raise ValueError(f'role must be one of {roles}')
    i = roles.index(role)
    return {'color': p['ink'] if role == 'reference' else p[role], 'linestyle': ['-', '--', '-.', ':'][i],
            'marker': TOKENS['common']['markers'][i], 'markerfacecolor': p['paper'],
            'markeredgewidth': .9}


def colormaps(name: str | None = None) -> dict:
    """Sequential for magnitudes, diverging only for data with a real centre."""
    from matplotlib.colors import LinearSegmentedColormap
    p = palette(name)
    return {
        'sequential': LinearSegmentedColormap.from_list('ink_seq',
            [p['paper'], wash(p['structure'], .35), p['structure'], p['ink']]),
        'diverging': LinearSegmentedColormap.from_list('ink_div',
            [p['structure'], p['paper'], p['fifo']]),
    }


def restyle_axes(ax, roles: dict[str, str] | None = None, name: str = 'qinglu'):
    """Restyle already-built Matplotlib artists by their EXISTING labels.

    Data, labels, x/y scales, limits, normalization and aggregation stay unchanged.
    With no role map, only typography and neutral axes are updated. Never infer
    the scientific meaning of a series from its order or color.
    """
    from matplotlib.collections import PathCollection
    from matplotlib.container import BarContainer
    from matplotlib.font_manager import FontProperties
    p = palette(name)
    ax.set_facecolor(p['paper']); ax.figure.set_facecolor(p['paper'])
    for side, spine in ax.spines.items():
        spine.set_visible(side in ('left', 'bottom'))
        spine.set_color(p['ink']); spine.set_linewidth(.65)
    ax.tick_params(colors=p['muted'], width=.65, length=3)
    fp = FontProperties(family=list(installed_sans()), size=9.5)
    for text in [ax.title, ax.xaxis.label, ax.yaxis.label, *ax.get_xticklabels(), *ax.get_yticklabels()]:
        size = text.get_fontsize()
        text.set_fontproperties(fp); text.set_fontsize(size); text.set_color(p['ink'])
    roles = roles or {}
    for line in ax.get_lines():
        if line.get_label() in roles:
            style = series_style(roles[line.get_label()], name)
            for key, value in style.items():getattr(line, 'set_' + key)(value)
            line.set_linewidth(1.5)
    for collection in ax.collections:
        if isinstance(collection, PathCollection) and collection.get_label() in roles:
            role = roles[collection.get_label()]
            color = p['ink'] if role == 'reference' else p[role]
            collection.set_facecolor(wash(color, .55)); collection.set_edgecolor(color)
            collection.set_linewidth(.65)
    for container in ax.containers:
        if isinstance(container, BarContainer) and container.get_label() in roles:
            role = roles[container.get_label()]
            color = p['ink'] if role == 'reference' else p[role]
            for bar in container.patches:
                bar.set_facecolor(wash(color, .3)); bar.set_edgecolor(color); bar.set_linewidth(.75)
    return ax


def export_figure(fig, path: str | Path):
    """Vector text in SVG/PDF; no font files copied to the deliverable."""
    import matplotlib as mpl
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with mpl.rc_context({'svg.fonttype':'none', 'pdf.fonttype':42, 'savefig.facecolor':'white'}):
        for extension in ('.svg', '.pdf', '.png'):
            fig.savefig(path.with_suffix(extension), bbox_inches='tight', dpi=300)
