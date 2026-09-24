"""Validate actual model integration and public reproduction without paper bypasses."""
import argparse
import copy
from pathlib import Path
import sys
from model_selection import read, write, audit_report, supporting_gate, paper_gate, sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,default=Path('.'));a=p.parse_args()
    from workspace_context import shared_context
    from reproduce_supporting_materials import audit_reproduction
    from supporting_contract import structure_errors
    root=a.project_root.resolve();ctx=shared_context(root)
    if not ctx or ctx.manifest['purpose']!='demo':raise ValueError('Only registered DEMO')
    manifest=root/'求解/支撑材料清单.json';m=read(manifest)
    tests=[]
    def result(name,ok,details=None):
        tests.append(dict(name=name,passed=bool(ok),details=details))
    from build_supporting_materials import build
    # Missing declaration must fail in real builder before publishing output.
    old=manifest.read_bytes();bad=copy.deepcopy(m);bad['questions'][0].pop('model_selection')
    write(manifest,bad)
    try:
        try:
            build(manifest,root,root/'提交附件',ctx.runtime)
            result('真实构建器拒绝缺模型选择声明',False)
        except ValueError as exc:
            result('真实构建器拒绝缺模型选择声明','model_selection declaration' in str(exc),str(exc))
    finally:
        manifest.write_bytes(old)
    from audit_supporting_materials import audit
    full=audit(manifest,root,root/'提交附件','question','q1',ctx.runtime)
    model_check=next(c for c in full['checks'] if c['code']=='model_selection_gate')
    result('既有支撑材料审计实际调用模型选择门禁',model_check['ok'],model_check)
    # The partial DEMO deliberately lacks scientific figures. Never disable the
    # original full-paper gates to make this narrow integration look complete.
    result('专项DEMO仍被完整论文图件门禁拒绝',full['status']=='FAIL',
           [c['code'] for c in full['failures']])
    reproduction=audit_reproduction(root,manifest,root/'提交附件',m['questions'][0],1)
    result('公开包独立重新训练复现',reproduction['status']=='PASS',reproduction['errors'])
    result('公开包目录及内部记录边界',not structure_errors(root/'提交附件',m))
    result('当前模型数值及生成表一致',audit_report(root,m['questions'][0]['model_selection'],'paper')['status']=='PASS')
    # Directly exercise build_main and its common contract using a minimal,
    # explicitly named chapter fixture. Do not claim abstract/citation/PDF QA.
    sys.path.insert(0,str(ctx.template_root/'华为杯_论文规范模板/tools'))
    from paper_contract import chapter_blueprint, audit_structure
    from build_latex import build_main
    paper=root/'论文'
    chapters=chapter_blueprint(1)
    for i,c in enumerate(chapters):
        c.update(chapter_id='q1' if c['role']=='problem' else 'fixture'+str(i),tex_path='章节内容/fixture'+str(i)+'.tex')
        if c['role']=='problem':
            c['tex_path']='章节内容/q1.tex';continue
        if c['role']=='references':
            content='\\begin{thebibliography}{1}\n\\end{thebibliography}\n'
        else:
            content='\\section{'+c['title']+'}\n'
            subs=['问题背景','问题重述'] if i==0 else (['模型优点','模型缺点','模型的推广与改进'] if c['role']=='evaluation' else [])
            content+=''.join('\\subsection{'+s+'}\n仅用于模型接入测试。\n' for s in subs)
        (paper/c['tex_path']).write_text(content,encoding='utf-8')
    (paper/'章节内容/fixture_abstract.tex').write_text('DEMO模型接口测试，不是正式摘要。',encoding='utf-8')
    fixture=dict(title='DEMO模型接入',keywords=['模型','比较','演练'],abstract_tex_path='章节内容/fixture_abstract.tex',chapters=chapters)
    generated,inputs=build_main(fixture,paper,include_appendix=False)
    result('build_latex实际刷新并接入比较片段','\\input{章节内容/q1.tex}' in generated)
    qtex=paper/'章节内容/q1.tex';old_q=qtex.read_bytes();qtex.write_text('\\section{问题一求解与分析}\n\\subsection{问题的描述与分析}\n',encoding='utf-8')
    try:
        negative=audit_structure(fixture,paper)
        result('TeX共用门禁拒绝正文漏比较表',any('comparison must be included' in e for e in negative['failures']),negative['failures'])
    finally:qtex.write_bytes(old_q)
    result('模型审计负例集合通过',read(root/'求解/验收输出/模型竞赛DEMO.json')['status']=='PASS')
    render=read(root/'求解/验收输出/模型比较渲染.json')
    result('实际PDF编译及渲染',all((root/p).is_file() for p in render['pages']))
    report=dict(status='PASS' if all(t['passed'] for t in tests) else 'FAIL',tests=tests,
        evidence={'demo_tests':sha(root/'求解/验收输出/模型竞赛DEMO.json'),'pdf':sha(paper/'模型比较DEMO.pdf')},
        scope='模型选择、论文表接入、失败审计、公开支撑包复现；不包括整篇赛题论文验收')
    write(root/'求解/验收输出/模型机制交付检查.json',report)
    print(report)
    return report['status']!='PASS'


if __name__=='__main__':
    sys.dont_write_bytecode=True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
    raise SystemExit(main())
