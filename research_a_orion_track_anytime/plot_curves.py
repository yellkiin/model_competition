"""Plot actual parent-observed trajectories only; never manufacture missing data."""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('result_root')
    p.add_argument('--clock', choices=['added', 'end_to_end'], default='added')
    a = p.parse_args()
    root = Path(a.result_root)
    with (root/'trajectory.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not any(r.get('best_makespan') for r in rows):
        raise ValueError('No measured feasible trajectory: no curve is generated')
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError('Plotting alone needs matplotlib; the solver and recorder use the standard library') from exc
    grouped = defaultdict(lambda: defaultdict(list))
    key = 'elapsed_seconds' if a.clock == 'added' else 'total_elapsed_seconds'
    for r in rows:
        if r.get('best_makespan'):
            grouped[(r['case'], r['q'], r['n'], r['mode'])][r['method']].append(
                (float(r[key]), float(r['best_makespan'])))
    (root/'figures').mkdir(exist_ok=True)
    for tag, methods in grouped.items():
        fig, ax = plt.subplots()
        for method, points in sorted(methods.items()):
            points.sort()
            ax.step([v[0] for v in points], [v[1] for v in points], where='post', label=method)
        ax.set_xlabel('Additional solve time (seconds)' if a.clock == 'added' else 'Seed + additional solve time (seconds)')
        ax.set_ylabel('Best validated makespan (cycles; lower is better)')
        ax.set_title(' / '.join(tag))
        ax.legend()
        fig.tight_layout()
        fig.savefig(root/'figures'/('_'.join(tag)+'_'+a.clock+'.svg'))
        plt.close(fig)


if __name__ == '__main__':
    main()
