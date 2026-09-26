#!/usr/bin/env python3
"""Reproduce V9 companion scripts and paper prose from published V8 templates."""
from pathlib import Path
root=Path(__file__).resolve().parent.parent
old=root/'ink_v8'; new=root/'ink_v9'
s=(old/'verify.py').read_text()
s=s.replace('Check exact V7 preservation, cloned annotations, references and vector exports.', 'Check exactly five removed strips and preservation of all remaining objects.')
s=s.replace('COPY_DX, COPIES, find, git_hash','STRIPS, strip_nodes, find, git_hash')
a=s.index('def exact_scope('); b=s.index('\n\ndef main():',a)
s=s[:a]+'''def exact_scope(old, new):
    undo = deepcopy(new)
    group = find(undo, 'hardware-cutaway-v6')
    removed = strip_nodes(old)
    assert len(removed) == 5
    for index, node in removed:
        group.insert(index, deepcopy(node))
    for key in ('data-version', 'data-input-version'):
        undo.set(key, old.get(key))
    del undo.attrib['data-v9-changes']
    for ident in ('title', 'desc'):
        find(undo, ident).text = find(old, ident).text
    assert ET.tostring(undo) == ET.tostring(old), 'An out-of-scope object or attribute changed'
    assert sum(1 for _ in old.iter()) - sum(1 for _ in new.iter()) == 5
    for _, node in removed:
        assert not any(n.get('d') == node.get('d') for n in new.iter()), 'Target strip remains'
''' + s[b:]
s=s.replace('ink_v8','ink_v9').replace('_v8','_v9').replace('ink_v7','ink_v8').replace('_v7','_v8').replace('V7','V8')
s=s.replace("'exact_source_preservation': 'PASS', 'exact_four_clones': 'PASS',", "'exact_preservation_except_five_strips': 'PASS', 'removed_strip_paths': 5,\n                     'removed_horizontal_segments': 38,")
s=s.replace("'copy_translation_x': COPY_DX, 'copy_translation_y': 0,", "'all_existing_copy_pairs_unchanged': 'PASS',")
s=s.replace("'ddr-to-l2-fill', *(f'pipe-private-{i}' for i in range(4)))", "'ddr-to-l2-fill', 'l2-hit-read', 'right-copy-annotations-v8',\n                          'copy-out-label', 'copy-in-label', 'copy-out-tensor-v6', 'copy-in-tensor-v6',\n                          *(f'pipe-private-{i}' for i in range(4)))")
(new/'verify.py').write_text(s,encoding='utf-8')
s=(old/'pixel_check.py').read_text().replace('V7/V8','V8/V9').replace('outside annotations','outside the five deleted strip regions')
s=s.replace("allowed = (3075, 700, 3335, 792)", "allowed = [(2643, 651, 2755, 667), (2790, 651, 2902, 667),\n               (3058, 651, 3170, 667), (3205, 651, 3317, 667),\n               (2688, 910, 3310, 932)]")
s=s.replace("'ink-v8-pixels-'","'ink-v9-pixels-'").replace('(7, 8)','(8, 9)')
s=s.replace('Expected the new annotations to be visible', 'Expected the strip removal to be visible')
s=s.replace('outside.paste((0, 0, 0), allowed)', "for box in allowed:\n                assert difference.crop(box).getbbox(), f'Expected visible change in {box}'\n                outside.paste((0, 0, 0), box)")
s=s.replace("'allowed_bbox_page_pixels': list(allowed)","'allowed_regions_page_pixels': [list(box) for box in allowed]")
s=s.replace("'version': 'ink_v8'", "'version': 'ink_v9'")
(new/'pixel_check.py').write_text(s,encoding='utf-8')
s=(old/'review.py').read_text().replace('_v8.pdf','_v9.pdf').replace('COPY detail','memory detail')
s=s.replace('(2560, 1070)', '(2560, 1370)').replace('(2600, 775, 3420, 1095)','(2600, 790, 3420, 1200)').replace('* 535','* 685').replace('detail_copy_pairs.png','detail_memory_clean.png').replace('four_palettes_copy_detail.png','four_palettes_memory_detail.png')
(new/'review.py').write_text(s,encoding='utf-8')
for f in ('.gitignore','.gitattributes'):
 (new/f).write_bytes((old/f).read_bytes())
s=(old/'docs/PR69_figure_and_text.tex').read_text().replace('ink_v8','ink_v9').replace('_v8.pdf','_v9.pdf')
(new/'docs/PR69_figure_and_text.tex').write_text(s,encoding='utf-8')
s=(old/'docs/PAPER_TEXT_PR69.md').read_text().replace('第八版','第九版').replace('ink_v8','ink_v9').replace('_v8.pdf','_v9.pdf').replace('15e8f51623ccbf02cbb89732b030858e1b6ad7c5','de860f7a2babb1e2f851b3e4d6745fbc0af0c862')
s=s.replace('第九版仅为右侧既有COPY箭头补充文字和小立方体，未新增硬件路径或修改执行规则。第七版既有布局及底部候选—评价—反馈闭环完整保留。','第九版仅删除两侧L1、UB及DDR正面底部的五组装饰性横条纹，未新增硬件路径或修改执行规则。第八版全部COPY标注、张量立方体、布局及底部候选—评价—反馈闭环完整保留。该视觉调整无需写进论文正文。')
s=s.replace('本轮新增标注的简短说明（正文空间有限时）','硬件与搬运示意的简短说明（正文空间有限时）')
s=s.replace('新增标注仅补全既有路径的含义，不改变调度方案和执行模型。','这些标注说明既有路径的含义，不改变调度方案和执行模型。')
(new/'docs/PAPER_TEXT_PR69.md').write_text(s,encoding='utf-8')
print('Prepared V9 scripts and prose')
