"""Generated standalone environment documents, with no local user/path disclosure."""
from __future__ import annotations
from pathlib import Path
import re
from environment_contract import active


def escape(value):
    mapping={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    return ''.join(mapping.get(c,c) for c in str(value))


def public_text(value):
    # Human reports deliberately omit paths and raw subprocess output.
    return re.sub(r'(?:[A-Za-z]:[\\/]|\\\\)[^\s]*','[本机路径]',str(value))


def render_tex(catalog, needs, report=None):
    caps={c['id']:c for c in catalog['capabilities']};providers={p['id']:p for p in catalog['providers']}
    results={r['capability']:r for r in (report or {}).get('results',[])}
    lines=[r'\documentclass[UTF8,a4paper,10pt]{ctexart}',r'\usepackage[margin=22mm]{geometry}',r'\usepackage{longtable,array,booktabs,xurl,hyperref}',r'\hypersetup{hidelinks}',r'\setlength{\emergencystretch}{3em}',r'\begin{document}',r'\section*{环境与依赖说明}',r'本文件由机器可读能力清单生成，独立于正式论文；不授予科学、视觉或论文验收通过。',r'\par 正式支持：Windows 10/11 x64，PowerShell 5.1 以上。',r'\small',r'\begin{longtable}{>{\raggedright\arraybackslash}p{.19\linewidth}>{\raggedright\arraybackslash}p{.27\linewidth}>{\raggedright\arraybackslash}p{.43\linewidth}}',r'\toprule 能力 / 状态 & 提供者 / 版本 & 需求依据 \\ \midrule\endhead']
    for row in needs['requirements']:
        cap=caps.get(row['capability'],{'name':row['capability'],'providers':[]});result=results.get(row['capability'],{})
        provider=result.get('provider') or row['provider']
        names=providers.get(provider,{}).get('name') if provider else ' / '.join(providers[p]['name'] for p in cap['providers'])
        state=result.get('status','待检测' if active(row) else '按需启用')
        lines.append(escape(cap['name']+' / '+state)+' & '+escape((names or '未解析')+' '+result.get('version','').split('\n')[0][:80])+' & '+escape(public_text(row['reason']))+r' \\')
    lines.extend([r'\bottomrule\end{longtable}',r'\normalsize\section*{安装与复现}',r'优先复用实测兼容的软件。Python 包安装到工作区虚拟环境；直接依赖见 requirements.txt，精确版本见 requirements.lock.txt。虚拟环境与下载缓存不提交。',r'\par 国内 PyPI 镜像优先，失败时显式回退官方源；TeX 宏包仓库须与发行版年度兼容。字体须来自合法来源，不替换官方标题样式。',r'\section*{来源}'])
    for url in dict.fromkeys([*catalog['pip_indexes'],*catalog['tex_repositories'],'https://www.python.org/downloads/','https://yihui.org/tinytex/','https://github.com/jgraph/drawio-desktop/releases']):
        lines.append(r'\noindent\url{'+url+r'}\par')
    lines.append(r'\end{document}')
    return '\n'.join(lines)+'\n'


def write_reports(context, catalog, needs, report):
    from workspace_context import atomic_json
    target=context.write_path('论文/requirements.tex');target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(render_tex(catalog,needs,report),encoding='utf8')
    lines=['# 环境与依赖（自动生成）','',f"当前检测：{report['status']}。功能检测不代表科学、视觉或论文完成。",'', '| 能力 | 提供者 | 状态 | 版本 |','|---|---|---|---|']
    for r in report['results']:
        lines.append('| '+' | '.join(public_text(r.get(k) or '').replace('|','/').replace('\n',' ')[:120] for k in ['capability','provider','status','version'])+' |')
    lines.extend(['','直接依赖：`requirements.txt`；实际精确版本：`requirements.lock.txt`。','复现安装：`python -m venv .venv`，然后使用 `.venv/Scripts/python.exe -m pip install -r requirements.lock.txt`。','逐问运行命令、工作目录、输入输出、随机种子需另按支撑材料清单填写。本文件不替代逐问说明。','本机路径和安装日志仅存内部环境检测；不将虚拟环境、缓存或内部日志打包。'])
    context.write_path('求解/环境与依赖.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
