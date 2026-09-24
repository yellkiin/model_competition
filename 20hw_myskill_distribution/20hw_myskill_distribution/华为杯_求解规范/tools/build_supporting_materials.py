#!/usr/bin/env python3
"""Build a reader-facing submission and retain internal evidence separately."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from supporting_contract import (SUPPORT_DIR_NAME, README_NAME, BUILD_MANIFEST_NAME,
    HASH_NAME, FORBIDDEN_PARTS, load_json, sha256, project_path, internal_root,
    question_name, validate_manifest, attachment_summary, structure_errors)


def build(manifest_path, root, output, runtime=None):
    manifest = load_json(manifest_path)
    validate_manifest(manifest)
    root, output = root.resolve(), output.resolve()
    from model_selection import supporting_gate, publish
    complete_manifest = dict(manifest, questions=[q for q in manifest['questions'] if q['status'] == 'complete'])
    errors = supporting_gate(root, complete_manifest, package=True)
    if errors:
        raise ValueError('Model selection gate: ' + '; '.join(errors))
    registry = root / '求解/候选图清单.json'
    if registry.is_file():
        from candidate_figures import package_selection_errors
        if runtime not in ('codex', 'claude'):
            raise ValueError('Candidate-enabled projects require --runtime codex|claude')
        errors = package_selection_errors(root, registry, manifest, runtime)
        if errors:
            raise ValueError('Candidate package selection failed: ' + '; '.join(errors))
    output.relative_to(root)
    if output == root or output.name != '提交附件':
        raise ValueError('输出必须为项目内名为提交附件的独立目录')
    internal = internal_root(root)
    internal.mkdir(parents=True, exist_ok=True)
    token = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid4().hex[:8]
    stage = internal / ('待发布_' + token)
    stage.mkdir()
    support = stage / SUPPORT_DIR_NAME
    support.mkdir()
    for category in ['其他数据', '其他支撑材料']:
        (support / category).mkdir()
    entries, records, used_paths = [], [], set()

    def copy(item, relative, category, question_id=None):
        source = project_path(root, item['path'])
        try:
            source.relative_to(output)
        except ValueError:
            pass
        else:
            raise ValueError(f'打包源不能是提交包副本：{source}')
        destination = project_path(stage, relative)
        rel = destination.relative_to(stage).as_posix()
        if FORBIDDEN_PARTS.intersection(source.relative_to(root).parts + destination.relative_to(stage).parts):
            raise ValueError(f'禁止目录出现在提交源或目的地：{rel}')
        if rel in used_paths: raise ValueError(f'打包目的路径冲突：{rel}')
        if not source.is_file() or not source.stat().st_size: raise ValueError(f'源文件不存在或为空：{source}')
        used_paths.add(rel)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        entry = dict(source_path=source.relative_to(root).as_posix(), package_path=rel,
                     description=item['description'], category=category,
                     size_bytes=source.stat().st_size, sha256=sha256(source))
        if question_id: entry['question_id'] = question_id
        entries.append(entry)
        return entry

    def record(raw, category, qid=None):
        source = project_path(root, raw)
        destination = internal / '运行记录' / (qid or '公共') / source.name
        if not source.is_file() or not source.stat().st_size: raise ValueError(f'核验记录缺失：{raw}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source != destination: shutil.copy2(source, destination)
        records.append(dict(source_path=source.relative_to(root).as_posix(),
                            record_path=destination.relative_to(root).as_posix(),
                            category=category, sha256=sha256(source)))

    completed = []
    for index, q in enumerate(manifest['questions'], 1):
        qdir = Path(SUPPORT_DIR_NAME) / question_name(index)
        for sub in ['源码', '中间图表']: (stage / qdir / sub).mkdir(parents=True)
        copy({'path': q['environment_doc'], 'description': '软件环境、输入输出及运行方法'},
             qdir / '代码环境说明.md', 'environment_doc', q['question_id'])
        if q['status'] != 'complete': continue
        qid = q['question_id']; completed.append(qid)
        if q['entrypoint'] not in [s['path'] for s in q['source_files']]:
            raise ValueError(f'{qid}主入口未登记')
        for item in q['source_files']:
            copy(item, qdir / '源码' / item['package_path'], 'source_code', qid)
        record(q['run_verification']['record_path'], 'run_verification', qid)
        if q.get('model_selection'):
            record(q['model_selection'], 'model_selection', qid)
        from reproduce_supporting_materials import receipt_path
        reproduction_record = receipt_path(root, qid)
        if reproduction_record.is_file():
            record(reproduction_record.relative_to(root).as_posix(), 'independent_reproduction', qid)
        for item in q['supplementary_materials']:
            copy(item, qdir / '中间图表' / item.get('package_path', Path(item['path']).name),
                 'supplementary_' + item['material_type'], qid)

    for data in manifest['external_data']:
        if not set(data['used_by']).intersection(completed): continue
        base = Path(SUPPORT_DIR_NAME) / '其他数据' / data['name']
        for item in data['files']:
            copy(item, base / item.get('package_path', Path(item['path']).name), 'external_data')
        for item in data['collection_scripts']:
            copy(item, base / '采集程序' / item.get('package_path', Path(item['path']).name), 'external_data_script')
        copy({'path': data['provenance_file'], 'description': data['description']},
             base / '来源说明.md', 'external_data_provenance')
    for item in manifest['additional_files']:
        if Path(item['package_path']).parts[0] not in {'其他数据', '其他支撑材料'}:
            raise ValueError('公共文件只能归入其他数据或其他支撑材料')
        copy(item, Path(SUPPORT_DIR_NAME) / item['package_path'], 'additional')
    officials = []
    for item in manifest['official_outputs']:
        if Path(item['package_path']).parts[0] not in {'其他数据', '其他支撑材料'}:
            raise ValueError('官方输出必须归入其他数据或其他支撑材料')
        entry = copy(item, Path(SUPPORT_DIR_NAME) / item['package_path'], 'official_output')
        officials.append(dict(entry, status=item['status'], verification_path=item['verification_path']))
        record(item['verification_path'], 'official_output_verification')
    copy({'path': manifest['readme_source'], 'description': '材料目录、整体复现顺序与结果位置'}, README_NAME, 'readme')
    errors = structure_errors(stage, manifest)
    if errors and manifest['package_status'] == 'complete': raise ValueError('\n'.join(errors))
    summaries = attachment_summary(manifest, stage)
    summary_text = (stage / README_NAME).read_text(encoding='utf-8-sig')
    if any(row['path'] not in summary_text or row['description'] not in summary_text for row in summaries):
        raise ValueError('总说明须包含与附录一致的目录概括表')
    snapshot = dict(schema_version='2.0', project_title=manifest['project_title'],
                    package_status=manifest['package_status'], built_at=datetime.now(timezone.utc).isoformat(),
                    source_manifest=manifest_path.relative_to(root).as_posix(), source_manifest_sha256=sha256(manifest_path),
                    completed_questions=completed, entries=sorted(entries, key=lambda x:x['package_path']),
                    official_outputs=officials, internal_records=records, attachment_summary=summaries,
                    output_root=output.relative_to(root).as_posix(), unregistered_files=[])
    if output.exists():
        archived = internal / '历史包' / token
        archived.parent.mkdir(parents=True, exist_ok=True)
        output.rename(archived)
        snapshot['previous_package'] = archived.relative_to(root).as_posix()
    stage.rename(output)
    (internal / BUILD_MANIFEST_NAME).write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (internal / HASH_NAME).write_text(''.join(f"{e['sha256']}  {e['package_path']}\n" for e in snapshot['entries']),encoding='utf-8')
    return snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--project-root',type=Path,default=Path('.'))
    parser.add_argument('--output',type=Path,default=Path('提交附件'))
    parser.add_argument('--runtime', choices=('codex', 'claude'))
    parser.add_argument('--package-only', action='store_true',
        help='Prepare an unaudited snapshot for reproduction; never marks delivery/appendix complete')
    args=parser.parse_args(); root=args.project_root.resolve()
    result=build(project_path(root,args.manifest),root,project_path(root,args.output),args.runtime)
    manifest=load_json(project_path(root,args.manifest))
    if not args.package_only and manifest['package_status']=='complete' and all(q['status']=='complete' for q in manifest['questions']) and (root/'论文/论文输入.json').is_file():
        from workspace_context import resource_path
        appendix_tool = resource_path(root,'华为杯_论文规范模板/tools/build_appendix.py',args.runtime)
        subprocess.run([sys.executable,'-B','-X','utf8',str(appendix_tool),
                        '--project-root',str(root),'--supporting-manifest',str(project_path(root,args.manifest)),
                        '--submission-dir',str(project_path(root,args.output)),
                        *(['--runtime',args.runtime] if args.runtime else [])],check=True,
                       env=dict(os.environ,PYTHONIOENCODING='utf-8'))
    print(json.dumps(dict(status='BUILT_UNAUDITED' if args.package_only else 'BUILT',files=len(result['entries']),internal_records=str(internal_root(root))),ensure_ascii=False))

if __name__=='__main__': main()
