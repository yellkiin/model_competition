#!/usr/bin/env python3
"""Audit the illustrative topology and SVG. This is not a solver validation suite."""
import json, sys, unittest, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CASE=json.loads((ROOT/'assets/example_case.json').read_text())
NS={'s':'http://www.w3.org/2000/svg'}

def acyclic(vertices,edges):
    successors={v:set() for v in vertices};indegree={v:0 for v in vertices}
    for a,b in set(edges):
        if b not in successors[a]:successors[a].add(b);indegree[b]+=1
    q=[v for v in vertices if indegree[v]==0];seen=0
    while q:
        v=q.pop();seen+=1
        for w in successors[v]:
            indegree[w]-=1
            if indegree[w]==0:q.append(w)
    return seen==len(vertices)

def group_edges():
    owner={o:g for g,ops in CASE['partition'].items() for o in ops}
    return {(owner[t['producer']],owner[c]) for t in CASE['tensors'].values() if t['producer'] for c in t['consumers'] if owner[t['producer']]!=owner[c]}

class FigureTests(unittest.TestCase):
    def test_partition_complete_disjoint_nonempty(self):
        groups=CASE['partition'];flat=sum(groups.values(),[])
        self.assertTrue(all(groups.values()));self.assertEqual(sorted(flat),sorted(CASE['operations']));self.assertEqual(len(flat),len(set(flat)))
    def test_example_schedules_have_unique_assignment_and_no_cycle(self):
        for key in ('parent_core_schedules','migration_candidate_core_schedules'):
            lanes=CASE[key];self.assertEqual(sorted(sum(lanes,[])),sorted(CASE['partition']))
            edges=group_edges()|{(a,b) for lane in lanes for a,b in zip(lane,lane[1:])}
            self.assertTrue(acyclic(CASE['partition'],edges),key)
    def test_migration_preserves_partition(self):
        before=CASE['parent_core_schedules'];after=CASE['migration_candidate_core_schedules']
        self.assertEqual([[g for g in lane if g!='B'] for lane in before],[[g for g in lane if g!='B'] for lane in after])
        self.assertIn('B',after[1]);self.assertNotIn('B',after[0])
    def test_residency_orders_preserve_dependencies(self):
        for key in ('residency_local_before','residency_local_after'):
            seq=CASE[key];self.assertEqual(set(seq),{'o2','o3','o4','o5'})
            self.assertLess(seq.index('o2'),seq.index('o4'));self.assertLess(seq.index('o3'),seq.index('o5'))
    def test_split_does_not_delete_or_duplicate_operations(self):
        self.assertEqual(sorted(sum(CASE['split_example'].values(),[])),sorted(CASE['partition']['B']))
    def test_fifo_proposal_is_inside_hypothesized_window(self):
        order=CASE['fifo_window_proposal_event_order']
        self.assertLess(order.index('fill'),order.index('proposed_read'));self.assertLess(order.index('proposed_read'),order.index('evict'));self.assertLess(order.index('evict'),order.index('old_read'))
    def test_svg_is_editable_and_self_contained(self):
        root=ET.parse(ROOT/'assets/workflow.svg').getroot()
        self.assertEqual(root.attrib['viewBox'],'0 0 3000 2120')
        self.assertGreater(len(root.findall('.//s:text',NS)),90)
        self.assertGreater(len(root.findall('.//s:path',NS)),350)
        for forbidden in ('image','script','foreignObject'):
            self.assertEqual(root.findall('.//s:'+forbidden,NS),[])
        ids=[x.attrib['id'] for x in root.iter() if 'id' in x.attrib];self.assertEqual(len(ids),len(set(ids)))
        for node in root.iter():
            for k,v in node.attrib.items():
                if k.endswith('href'):self.assertTrue(v.startswith('#'))
        self.assertGreater(len(root.findall('.//s:tspan',NS)),8)
    def test_critical_labels_and_strict_filter(self):
        root=ET.parse(ROOT/'assets/workflow.svg').getroot();text=' '.join(root.itertext())
        for term in ('总体任务执行时间（Makespan）','L(y) > U','等号保留','合图无环','命中不刷新 FIFO','固定同一个','配对不参与搜索接受'):
            self.assertIn(term,text)
        self.assertNotIn('L(y) ≥ U',text)

if __name__=='__main__':unittest.main(verbosity=2)
