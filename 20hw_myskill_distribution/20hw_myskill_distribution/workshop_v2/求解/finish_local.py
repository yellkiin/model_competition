"""以实际审阅与交付清单完成本次 SESSION，保留原 workshop 审计状态。

用户明确取消哈希和冒烟检查。原 workspace_completion.finish 强制哈希全部
材料并调用与新建模型流程绑定的门禁，因此本适配只登记真实完成范围，
不伪造原门禁 PASS，不修改只读共享工具或原始运行数据。
"""
import datetime
import json
from pathlib import Path

W = Path(__file__).resolve().parent.parent
A = W.parent
R = W / '求解/验收输出'


def finish():
    review_path = R / '最终审阅.json'
    review = json.loads(review_path.read_text(encoding='utf-8'))
    if review['conclusion'] != 'reviewed_for_delivery':
        raise ValueError('尚无实际最终审阅记录。')
    paths = [W/'论文/论文.pdf', W/'论文/论文.tex', W/'交付清单.md',
             W/'求解/视觉计划.json', W/'论文/引用依据.json',
             W/'求解/规范化数据/combined/main.csv',
             W/'求解/规范化数据/combined/pairs.csv',
             W/'提交附件/支撑材料说明.md']
    # Read the actual README name used by the existing supporting-material builder.
    if not paths[-1].exists():
        readmes = list((W/'提交附件').glob('readme说明*'))
        if readmes:
            paths[-1] = readmes[0]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError('交付文件缺失：' + '；'.join(missing))
    session_path = A / '.orion_paper/SESSION.json'
    session = json.loads(session_path.read_text(encoding='utf-8'))
    if Path(session['workspace_root']).resolve() != W.resolve():
        raise ValueError('SESSION与当前明确工作区不一致。')
    completed_at = datetime.datetime.now().astimezone().isoformat()
    report = dict(status='COMPLETE_LOCAL_REVIEW', completed_at=completed_at,
                  workspace_root=str(W), review=str(review_path),
                  deliverables=[str(p) for p in paths],
                  original_workshop_finish='not_run_user_requested_no_hash_checks',
                  original_workshop_manifest='preserved; no legacy PASS asserted',
                  omitted=['artifact hashing', 'smoke tests', 'new solver selection',
                           'template hardcoded DeepSeek disclosure'],
                  actual_work=['fixed-method theory and literature review',
                               'raw-response normalization',
                               'three authorized official evaluations',
                               'selected-response numerical reproduction',
                               'Chinese vector figures and editable sources',
                               'XeLaTeX and bibliography compilation',
                               'actual rendered-page and figure review',
                               'supporting materials and dynamic appendix'])
    report_path = R / '完成登记.local.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    session.update(mode='complete', paper_complete=True,
                   completion_mode='actual_local_review_with_user_overrides',
                   completed_at=completed_at, completion_report=str(report_path),
                   paper_pdf=str(W/'论文/论文.pdf'), paper_tex=str(W/'论文/论文.tex'),
                   next_update_prompt=str(A/'ORION_论文更新提示词.md'))
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding='utf-8')
    (W/'求解/PENDING_EVIDENCE.md').write_text(
        '# 本次交付状态\n\n100图主配置和500组同方案缓存配对已有实际官方响应；'
        '三项授权补算、理论与引用记录、20张中文正式图件、66页PDF及附件已完成。'
        '实际阅读与版面观察见验收输出/最终审阅.json。\n\n'
        '原workshop强制哈希门禁按用户指示未运行，原门禁状态未改写为通过；'
        '本次SESSION的完成登记见验收输出/完成登记.local.json。'
        '队员信息、签署与赛事提交由用户处理，本文未代填或上传。\n', encoding='utf-8')
    print(str(report_path))


if __name__ == '__main__':
    finish()
