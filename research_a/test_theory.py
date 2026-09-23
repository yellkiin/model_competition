"""Mathematical regression tests, not security or smoke tests.

Official formula checks run when the repository's original evaluator is present.
Local toy-oracle results are never reported as official performance scores.
"""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path
import random
import tempfile
import unittest
from .model import Graph, Plan, settings, copy_accounting, fifo_requests, residency, estimate, topo
from .solver import PROFILES, fresh, mutate, search
from .evaluator import metrics, Official
from .fixtures import make
from .report import summaries, paired, diagnosis

CFG = dict(capacity={'L1': 524288, 'UB': 131072}, bandwidth=60,
           task_cross_core_wait_cycles=1000, task_same_core_wait_cycles=100,
           cross_core_copy_delay_cycles=500, cache_capacity_bytes=1048576,
           cache_bandwidth_bytes_per_cycle=250)


def fanout():
    return Graph(dict(ops=[dict(id=i, op='COMPUTE', pipe='PIPE_V', cycles=10) for i in range(4)],
                      tensors=[dict(id=100, pos='UB', size=1024)],
                      edges=[dict(source=0, target=100)] + [dict(source=100, target=i) for i in (1, 2, 3)]))


def legal_order(graph, plan):
    position = {u: i for i, u in enumerate(u for block in plan.blocks for u in block)}
    if set(position) != set(graph.ids):
        return False
    return all(position[u] < position[v] for u in graph.ids for v in graph.succ[u])


class TheoryTests(unittest.TestCase):
    def test_official_whitespace_configuration(self):
        text = '[capacity]\nL1 524288\nUB 131072\n[bandwidth]\nbandwidth 60\n[multicore_scene_a]\ntask_cross_core_wait_cycles 1000\ntask_same_core_wait_cycles 100\n[multicore_scene_b]\ncross_core_copy_delay_cycles 500\n[problem_3]\ncache_capacity_bytes 1048576\ncache_bandwidth_bytes_per_cycle 250\n'
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'config.txt'; p.write_text(text)
            self.assertEqual(settings(p), CFG)

    def test_q1_single_export_q2_per_pair_export(self):
        g = fanout(); p = Plan([[0], [1], [2], [3]], [0, 1, 2, 3], 4)
        self.assertEqual(copy_accounting(g, p, 1)['pre_spill_bytes'], 4 * 1024)
        self.assertEqual(copy_accounting(g, p, 2)['pre_spill_bytes'], 6 * 1024)

    def test_q2_q3_task_copy_identity(self):
        g = fanout(); p = Plan([[0], [1], [2], [3]], [0, 1, 2, 3], 4)
        self.assertEqual(copy_accounting(g, p, 2), copy_accounting(g, p, 3))

    def test_same_core_is_not_free_in_q1(self):
        g = fanout(); p = Plan([[0], [1, 2, 3]], [0, 0], 1)
        self.assertEqual(copy_accounting(g, p, 1)['pre_spill_bytes'], 2048)
        self.assertEqual(copy_accounting(g, p, 2)['pre_spill_bytes'], 0)

    def test_consumers_on_one_remote_core_deduplicate(self):
        g = fanout(); p = Plan([[0], [1], [2], [3]], [0, 1, 1, 1], 2)
        self.assertEqual(copy_accounting(g, p, 2)['pre_spill_bytes'], 2048)

    def test_original_io_counted(self):
        g = Graph(make('chain')); p = Plan([g.order], [0], 1)
        self.assertEqual(copy_accounting(g, p, 1)['pre_spill_bytes'], g.original_copy)

    def test_direct_edges_differ_by_question(self):
        raw = dict(ops=[dict(id=i, op='COMPUTE', pipe='PIPE_V', cycles=1) for i in [0, 1]],
                   tensors=[], edges=[dict(source=0, target=1, data_size=512)])
        g = Graph(raw); p = Plan([[0], [1]], [0, 1], 2)
        self.assertEqual(copy_accounting(g, p, 1)['pre_spill_bytes'], 0)
        self.assertEqual(copy_accounting(g, p, 2)['pre_spill_bytes'], 1024)

    def test_copy_contracted_dependency(self):
        raw = dict(ops=[dict(id=i, op=('COPY_IN' if i == 1 else 'COMPUTE'), pipe='PIPE_V', cycles=1) for i in range(3)],
                   tensors=[], edges=[dict(source=0, target=1), dict(source=1, target=2)])
        self.assertEqual(Graph(raw).pred[2], {0})

    def test_contiguous_plans_and_mutations_are_topological(self):
        g = Graph(make('cache_stagger'))
        for q in (1, 2, 3):
            for profile in PROFILES:
                rng = random.Random(31)
                p = fresh(g, 4, q, rng, profile, bandwidth=60)
                for _ in range(30):
                    self.assertTrue(legal_order(g, p))
                    p = mutate(g, p, rng, profile)

    def test_plan_round_trip(self):
        g = Graph(make('fanout')); rng = random.Random(4)
        p = fresh(g, 3, 2, rng, bandwidth=60)
        self.assertEqual(Plan.load(p.json(), g).json(), p.json())
        raw = p.json()
        raw['node_to_subgraph'] = {u: group + 100 for u, group in reversed(list(raw['node_to_subgraph'].items()))}
        raw['core_schedules'] = [[group + 100 for group in seq] for seq in raw['core_schedules']]
        self.assertEqual(json.dumps(Plan.load(raw, g).json()), json.dumps(raw))

    def test_split_is_not_memory_reset_in_q2(self):
        g = Graph(make('chain'))
        p = Plan([g.order], [0], 1)
        split = Plan([[u] for u in g.order], [0] * len(g.order), 1)
        self.assertEqual(residency(g, p, 2, CFG['capacity']), residency(g, split, 2, CFG['capacity']))
        self.assertEqual(copy_accounting(g, p, 2), copy_accounting(g, split, 2))

    def test_fifo_completion_not_issue_insertion(self):
        r = fifo_requests([(0, 'A', 64), (0, 'A', 64), (2, 'A', 64)], 128, 64, 128)
        self.assertEqual((r['hits'], r['misses'], r['concurrent_misses']), (1, 2, 1))

    def test_fifo_hit_does_not_refresh_order(self):
        r = fifo_requests([(2 * i, key, 1) for i, key in enumerate('ABACA')], 2, 1, 1)
        self.assertEqual(r['hits'], 1)

    def test_fifo_not_monotone_in_capacity(self):
        seq = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
        requests = [(2 * i, key, 1) for i, key in enumerate(seq)]
        self.assertEqual(fifo_requests(requests, 3, 1, 1)['misses'], 9)
        self.assertEqual(fifo_requests(requests, 4, 1, 1)['misses'], 10)

    def test_hit_can_be_reinserted_at_completion(self):
        r = fifo_requests([(0, 'A', 1), (2, 'B', 1), (4, 'A', 1),
                           (5, 'C', 1), (7, 'D', 1), (15, 'A', 1)], 2, 1, .1)
        self.assertEqual(r['hits'], 2)

    def test_compute_bound_on_chain(self):
        g = Graph(make('chain'))
        self.assertEqual(g.lower_bound(5), sum(g.cost.values()))

    def test_compute_bound_independent_same_pipe(self):
        g = Graph(make('independent'))
        self.assertEqual(g.lower_bound(4), sum(g.cost.values()) / 4)

    def test_metrics_ddr_is_not_scheduled_in_q3(self):
        r = metrics(dict(makespan=100, data_movement_bytes={'scheduled_copy_bytes': 1000},
                         cache_stats=dict(hit_bytes=400, miss_bytes=600, hits=2, accesses=5)))
        self.assertEqual(r['ddr_accounted_bytes'], 600)
        self.assertEqual(r['cache_byte_hit_rate'], .4)
        self.assertEqual(r['cache_count_hit_rate'], .4)

    def test_byte_rate_and_count_rate_differ(self):
        r = metrics(dict(makespan=100, cache_stats=dict(hit_bytes=900, miss_bytes=100, hits=1, accesses=10)))
        self.assertEqual(r['cache_byte_hit_rate'], .9)
        self.assertEqual(r['cache_count_hit_rate'], .1)

    def test_occupancy_is_interval_union(self):
        r = metrics(dict(makespan=10, per_core_timeline=[dict(core_id=0, ops=[
            dict(op='COMPUTE', op_id=1, pipe='PIPE_V', start=0, end=6, duration=6),
            dict(op='COMPUTE', op_id=2, pipe='PIPE_V', start=4, end=8, duration=4)])]))
        self.assertEqual(r['pipe_occupancy']['0:PIPE_V'], .8)

    def test_estimates_exist_for_all_questions_and_profiles(self):
        g = Graph(make('spill')); rng = random.Random(1)
        for q in (1, 2, 3):
            for profile, weights in PROFILES.items():
                p = fresh(g, 4, q, rng, profile, bandwidth=60)
                self.assertGreater(estimate(g, p, q, CFG, **weights)['score'], 0)

    def test_budget_prefix_and_incumbent_monotonicity(self):
        # Exact mathematical oracle: independent jobs, one serial compute Pipe/core,
        # no I/O costs. This is NOT a mock competition performance measurement.
        g = Graph(make('independent'))
        def oracle(plan):
            loads = [0.] * plan.cores
            for block, k in zip(plan.blocks, plan.owners):
                loads[k] += sum(g.cost[u] for u in block)
            record = dict(status='ok', makespan=max(loads), ddr_accounted_bytes=0, seconds=0.)
            return record, record
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td) / 'a', Path(td) / 'b'
            search(g, CFG, oracle, a, 2, 3, budget=8, seed=7)
            search(g, CFG, oracle, b, 2, 3, budget=16, seed=7)
            small, big = json.loads((a / 'trajectory.json').read_text()), json.loads((b / 'trajectory.json').read_text())
            for x, y in zip(small, big):
                self.assertEqual((x['proxy_score'], x['incumbent_makespan']), (y['proxy_score'], y['incumbent_makespan']))
            values = [r['incumbent_makespan'] for r in big]
            self.assertTrue(all(a >= b for a, b in zip(values, values[1:])))

    def test_missing_jobs_do_not_produce_full_average(self):
        rows = [dict(case='a', question=1, cores=2, variant='full', status='ok', speedup=2., seed=0),
                dict(case='b', question=1, cores=2, variant='full', status='missing', speedup=None, seed=0)]
        self.assertIsNone(summaries(rows)[0]['mean_speedup'])

    def test_seed_average_before_graph_average(self):
        rows = [dict(case=c, question=1, cores=2, variant='full', status='ok', speedup=v, seed=s)
                for c, s, v in [('a', 0, 1.), ('a', 1, 3.), ('b', 0, 4.), ('b', 1, 4.)]]
        self.assertEqual(summaries(rows)[0]['mean_speedup'], 3.)

    def test_diagnosis_has_executable_profile(self):
        row = dict(status='ok', question=2, cores=4, scheduled_copy_bytes=100, spill_added_copy_bytes=30)
        self.assertEqual(diagnosis(row)[0], 'spill')

    def test_cache_decomposition_is_per_graph_identity(self):
        a, b, d = 150., 120., 100.
        self.assertAlmostEqual(a / d, (a / b) * (b / d))


ROOT = Path(__file__).resolve().parents[1]
ATTACHMENTS = list((ROOT / '题目' / 'A题').glob('*附件'))


@unittest.skipUnless(ATTACHMENTS, 'Original evaluator unavailable in this container; run in the repository after checkout')
class OfficialFormulaTests(unittest.TestCase):
    def test_all_three_questions_against_original_builder(self):
        from .model import write_json
        with tempfile.TemporaryDirectory() as td:
            graph_path = Path(td) / 'tiny.json'
            raw = make('tiny_oracle'); write_json(graph_path, raw)
            graph = Graph(raw)
            plan = Plan([[u] for u in graph.order], [0, 1, 1, 0], 2)
            for q in (1, 2, 3):
                ev = Official(ATTACHMENTS[0] / 'code', ATTACHMENTS[0] / 'data' / 'config.txt', graph_path, Path(td) / str(q))
                record, result = ev.evaluate(plan, q)
                self.assertEqual(record['status'], 'ok', record)
                pre = result['data_movement_bytes']['scheduled_copy_bytes'] - result['data_movement_bytes']['spill_added_copy_bytes']
                self.assertEqual(pre, copy_accounting(graph, plan, q)['pre_spill_bytes'])
                self.assertGreaterEqual(result['makespan'], graph.lower_bound(2))


if __name__ == '__main__':
    unittest.main()
