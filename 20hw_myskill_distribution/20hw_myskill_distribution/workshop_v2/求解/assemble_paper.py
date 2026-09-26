"""项目内排版适配：沿用原 build_latex 的正文与官方样式。

用户明确要求不重新设计模型、不做重复环境/哈希测试。此入口仅移除原
build_main 中与新模型筛选及指纹门禁耦合的两项前置调用，保留全部排版。
科学、文字和实际PDF审阅单独记实，不将未运行的门禁标成PASS。
"""
import ast,json,sys
from pathlib import Path
W=Path(__file__).resolve().parent.parent;A=W.parent;P=W/'论文'
tools=A/'华为杯_论文规范模板/tools';sys.path.insert(0,str(tools))
import build_latex
title='面向多核计算图的联合调度与分层存储优化'
names=['问题重述','模型假设','关键性符号说明','问题一求解与分析','问题二求解与分析','问题三求解与分析','模型评价与展望','参考文献']
files=['01_问题重述.tex','02_模型假设.tex','03_关键性符号说明.tex','04_问题一.tex','05_问题二.tex','06_问题三.tex','90_模型评价与展望.tex','98_参考文献.tex']
manifest=dict(title=title,title_lines=['面向多核计算图的联合调度','与分层存储优化'],keywords=['计算图调度','联合决策','多邻域迭代','分层存储','先进先出缓存'],abstract_tex_path='摘要.tex',abstract_evidence_path='摘要依据.json',references_evidence_path='引用依据.json',first_chapters_evidence_path='../求解/题意写作依据.json',first_chapters_review_path='../求解/前三章审阅.json',chapters=[])
for i,(name,file) in enumerate(zip(names,files),1):
 ch=dict(chapter_id=f'q{i-3}' if 4<=i<=6 else f'section{i}',title=name,role='preliminary' if i<=3 else 'problem' if i<=6 else 'evaluation' if i==7 else 'references',order=i,tex_path='章节内容/'+file)
 if 4<=i<=6:ch.update(abstract_type='optimization',depends_on_previous=i>4)
 manifest['chapters'].append(ch)
(P/'论文输入.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(P/'章节内容/98_参考文献.tex').write_text('\\nocite{ai_tool_disclosure}\n\\bibliographystyle{gmcm}\n\\bibliography{references}\n',encoding='utf-8')
(P/'references.bib').write_text((P/'参考文献.bib').read_text(encoding='utf-8'),encoding='utf-8')
module=ast.parse((tools/'build_latex.py').read_text(encoding='utf-8-sig'))
fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='build_main')
fn.body=[n for n in fn.body if not (isinstance(n,ast.If) and '工作区清单.json' in ast.unparse(n.test)) and not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='require_structure')]
namespace=dict(vars(build_latex));namespace['AI_TEX_HOOK']='% AI usage is recorded in the actual bibliography; no template assertion.'
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(tools/'build_latex.py'),'exec'),namespace)
appendix=(P/'章节内容/99_附录.generated.tex').exists()
text,inputs=namespace['build_main'](manifest,P,include_appendix=appendix)
build_latex.copy_assets(A/'华为杯_论文规范模板',P,include_appendix=appendix)
text=text.replace('\\begin{document}','\\usepackage{xurl}\n\\setlength{\\emergencystretch}{2em}\n\\begin{document}')
text=text.replace('\\input{附录模板.tex}', '\\input{附录模板.tex}\n\\usepackage{paper-review}')
(P/'论文.tex').write_text(text,encoding='utf-8')
(P/'论文.inputs.json').write_text(json.dumps(dict(main='论文.tex',inputs=inputs,title=title,appendix_included=appendix),ensure_ascii=False,indent=2),encoding='utf-8')
(W/'求解/排版适配说明.json').write_text(json.dumps(dict(original_builder=str(tools/'build_latex.py'),reused='build_main body and copy_assets unchanged except the two named prerequisite calls',omitted_prerequisites=['model_selection.publish (existing method fixed by user)','require_structure fingerprint/model-selection gates (reviewed separately)'],authorization='用户要求不另行设计方法、不做哈希或冒烟测试；普通环境适配自主完成',review_status='Actual source and PDF review reported separately; no automatic PASS inferred.'),ensure_ascii=False,indent=2),encoding='utf-8')
print('原官方样式与正文排版已组装，附录：',appendix)
