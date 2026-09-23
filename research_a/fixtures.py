"""Controlled graph families for mechanism experiments with the OFFICIAL evaluator.

Generated inputs are synthetic, never part of the 100-case competition score.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from .model import write_json


class Builder:
    def __init__(self):
        self.graph = dict(ops=[], tensors=[], edges=[])
        self.op_id, self.tensor_id = 1, 10001

    def tensor(self, size, pos='UB'):
        t = self.tensor_id
        self.tensor_id += 1
        self.graph['tensors'].append(dict(id=t, size=size, pos=pos))
        return t

    def op(self, inputs=(), size=1024, cycles=5000, pipe='PIPE_V', name='COMPUTE', pos='UB'):
        u = self.op_id
        self.op_id += 1
        t = self.tensor(size, pos)
        self.graph['ops'].append(dict(id=u, op=name, pipe=pipe, cycles=cycles))
        self.graph['edges'].extend(dict(source=x, target=u) for x in inputs)
        self.graph['edges'].append(dict(source=u, target=t))
        return u, t

    def source(self, size=8192):
        ddr = self.tensor(size, 'DDR')
        return self.op([ddr], size, 1, 'PIPE_MTE2', 'COPY_IN')[1]

    def sink(self, t):
        size = next(x['size'] for x in self.graph['tensors'] if x['id'] == t)
        self.op([t], size, 1, 'PIPE_MTE3', 'COPY_OUT', 'DDR')


def make(kind):
    b = Builder()
    if kind == 'chain':
        x = b.source()
        for i in range(6):
            _, x = b.op([x], pipe='PIPE_M' if i % 2 else 'PIPE_V')
        b.sink(x)
    elif kind in ('independent', 'mixed'):
        for i in range(8):
            x = b.source()
            _, y = b.op([x], cycles=(1000 + i * 900 if kind == 'mixed' else 5000),
                        pipe='PIPE_M' if kind == 'mixed' and i % 2 else 'PIPE_V')
            b.sink(y)
    elif kind in ('fanout', 'tiny_oracle'):
        x = b.source()
        _, t = b.op([x], size=16384, cycles=2000, pipe='PIPE_M')
        if kind == 'fanout':
            for _ in range(4):
                _, y = b.op([t], cycles=3000)
                b.sink(y)
        else:
            _, y = b.op([t], cycles=2500)
            _, z = b.op([t], cycles=3500)
            _, w = b.op([y, z], cycles=1500)
            b.sink(w)
    elif kind in ('cache_burst', 'cache_stagger'):
        shared = b.source(60000)
        for i in range(6):
            inputs = [shared]
            if kind == 'cache_stagger':
                _, warm = b.op([b.source(1024)], cycles=(i + 1) * 2500, pipe='PIPE_M')
                inputs.append(warm)
            _, y = b.op(inputs, cycles=2000)
            b.sink(y)
    elif kind == 'spill':
        x = b.source(30000)
        producers, values = [], []
        for _ in range(3):
            u, y = b.op([x], size=56000, cycles=3000)
            producers.append(u)
            values.append(y)
        for t in values:
            u, y = b.op([t], size=1024, cycles=2000)
            b.graph['edges'].extend(dict(source=p, target=u, data_size=0) for p in producers)
            b.sink(y)
    else:
        raise ValueError(kind)
    return b.graph


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    names = ['chain', 'independent', 'mixed', 'fanout', 'cache_burst', 'cache_stagger', 'spill', 'tiny_oracle']
    for i, name in enumerate(names, 1):
        write_json(args.out / f'case_{i:03d}.json', make(name))
    write_json(args.out / 'families.json', {f'case_{i:03d}': name for i, name in enumerate(names, 1)})
    print(args.out)


if __name__ == '__main__':
    main()
