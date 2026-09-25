#!/usr/bin/env python3
"""Project-local writing workbench with integrated theory and local raw evidence."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from common import read,write,stamp
from paths import project_paths,session_home
import sources,install,publication,local_data,theory


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('paths');a.add_argument('--project-root',default='.');a.add_argument('--home');a.add_argument('--repo');a.add_argument('--data-root')
    a=sub.add_parser('probe');a.add_argument('--template',required=True)
    a=sub.add_parser('locate-template');a.add_argument('--project-root',default='.');a.add_argument('--template')
    a=sub.add_parser('template-source');a.add_argument('--repo',required=True);a.add_argument('--revision',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('install');a.add_argument('--template',required=True);a.add_argument('--home');a.add_argument('--project-root',default='.');a.add_argument('--repo');a.add_argument('--data-root')
    a=sub.add_parser('discover');a.add_argument('--repo',required=True);a.add_argument('--ref',default='main');a.add_argument('--fetch',action='store_true');a.add_argument('--out',required=True)
    a=sub.add_parser('sync');a.add_argument('--repo',required=True);a.add_argument('--profile',required=True);a.add_argument('--home',required=True);a.add_argument('--fetch',action='store_true');a.add_argument('--metadata-only',action='store_true');a.add_argument('--lfs',action='store_true')
    a=sub.add_parser('adopt-export');a.add_argument('--profile',required=True);a.add_argument('--export',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('assets');a.add_argument('--spec',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('unpack');a.add_argument('--parts',nargs='+',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('scan-local');a.add_argument('--home',required=True);a.add_argument('--root')
    a=sub.add_parser('materialize-local');a.add_argument('--catalogue',required=True);a.add_argument('--entry',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('local-spec');a.add_argument('--export',required=True);a.add_argument('--runs',nargs='+',required=True);a.add_argument('--config-local',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('prepare-theory');a.add_argument('--home',required=True);a.add_argument('--snapshot');a.add_argument('--workspace')
    a=sub.add_parser('package-inputs');a.add_argument('--home',required=True);a.add_argument('--snapshot',required=True)
    a=sub.add_parser('bind');a.add_argument('--home',required=True);a.add_argument('--workspace',required=True)
    a=sub.add_parser('intake');a.add_argument('--spec',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('changes');a.add_argument('--old',required=True);a.add_argument('--new',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('lint');a.add_argument('--body',nargs='+',required=True);a.add_argument('--glossary');a.add_argument('--home');a.add_argument('--out',required=True)
    a=sub.add_parser('check-edit');a.add_argument('--before',required=True);a.add_argument('--after',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('final-ready');a.add_argument('--intake',required=True)
    args=p.parse_args(argv);result=None
    if args.cmd=='paths':result=project_paths(args.project_root,args.home,args.repo,args.data_root)
    elif args.cmd=='probe':result=install.probe(args.template)
    elif args.cmd=='locate-template':result=install.locate_template(args.project_root,args.template)
    elif args.cmd=='template-source':result=install.template_source(args.repo,args.revision,args.out)
    elif args.cmd=='install':
        paths=project_paths(args.project_root,args.home,args.repo,args.data_root)
        result=install.install(args.template,paths['agent_root'],Path(__file__).parent,
                               paths['project_root'],paths['local_data_root'],paths['repo_cache'])
    elif args.cmd=='discover':result=sources.discover(args.repo,args.ref,args.fetch)
    elif args.cmd=='sync':
        manifest,out=sources.sync(args.repo,args.profile,args.home,fetch=args.fetch,metadata_only=args.metadata_only,lfs=args.lfs)
        result=dict(snapshot=str(out),files=len(manifest['files']),errors=manifest['errors'])
    elif args.cmd=='adopt-export':result=publication.adopt(args.profile,args.export,args.out)
    elif args.cmd=='assets':result=publication.assets(args.spec,args.out)
    elif args.cmd=='unpack':result=publication.unpack(args.parts,args.out)
    elif args.cmd=='scan-local':result=local_data.scan(args.home,args.root)
    elif args.cmd=='materialize-local':result=local_data.materialize(args.catalogue,args.entry,args.out)
    elif args.cmd=='local-spec':result=local_data.make_spec(args.export,args.runs,args.config_local,args.out)
    elif args.cmd=='prepare-theory':
        snapshot=args.snapshot or read(Path(args.home)/'.orion_paper/latest_snapshot.json')['snapshot']
        result=theory.prepare(args.home,snapshot,args.workspace)
    elif args.cmd=='package-inputs':result=install.package_inputs(args.home,args.snapshot)
    elif args.cmd=='bind':result=install.bind(args.home,args.workspace)
    elif args.cmd=='intake':
        import intake
        result=intake.build(args.spec,args.out)
    elif args.cmd=='changes':result=sources.changes(args.old,args.new)
    elif args.cmd=='lint':
        import manuscript
        glossary=args.glossary
        if not glossary and args.home:
            s=read(Path(args.home)/'.orion_paper/SESSION.json')
            if s.get('theory_binding'):glossary=read(s['theory_binding'])['glossary']
        if not glossary:raise ValueError('Use --home with prepared theory or an explicit --glossary')
        result=manuscript.lint(args.body,glossary)
    elif args.cmd=='check-edit':
        import manuscript
        result=manuscript.compare(Path(args.before).read_text(encoding='utf-8'),Path(args.after).read_text(encoding='utf-8'))
    elif args.cmd=='final-ready':
        status=read(Path(args.intake)/'INTAKE_STATUS.json');result=dict(formal_data_ready=status['formal_ready'],
            next='Use the selected evidence in the results chapter and complete the original workflow reviews.' if status['formal_ready'] else 'Continue the supported manuscript sections and resolve the listed data gaps.')
    if hasattr(args,'out') and args.cmd not in ('intake','assets','unpack','adopt-export','template-source','materialize-local','local-spec'):write(args.out,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 2 if args.cmd=='final-ready' and not result['formal_data_ready'] else 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError) as exc:
        print(json.dumps(dict(status='action_required',error=str(exc)),ensure_ascii=False),file=sys.stderr);raise SystemExit(2)
