#!/usr/bin/env python3
"""Paper preparation, source intake, manuscript checks and incremental handoff."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from common import read,write
import sources,intake,manuscript,install,publication


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('probe');a.add_argument('--template',required=True)
    a=sub.add_parser('template-source');a.add_argument('--repo',required=True);a.add_argument('--revision',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('install');a.add_argument('--template',required=True);a.add_argument('--home',required=True)
    a=sub.add_parser('discover');a.add_argument('--repo',required=True);a.add_argument('--ref',default='main');a.add_argument('--fetch',action='store_true');a.add_argument('--out',required=True)
    a=sub.add_parser('sync');a.add_argument('--repo',required=True);a.add_argument('--profile',required=True);a.add_argument('--home',required=True);a.add_argument('--fetch',action='store_true');a.add_argument('--metadata-only',action='store_true');a.add_argument('--lfs',action='store_true')
    a=sub.add_parser('adopt-export');a.add_argument('--profile',required=True);a.add_argument('--export',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('assets');a.add_argument('--spec',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('unpack');a.add_argument('--parts',nargs='+',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('package-inputs');a.add_argument('--home',required=True);a.add_argument('--snapshot',required=True)
    a=sub.add_parser('bind');a.add_argument('--home',required=True);a.add_argument('--workspace',required=True)
    a=sub.add_parser('intake');a.add_argument('--spec',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('changes');a.add_argument('--old',required=True);a.add_argument('--new',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('lint');a.add_argument('--body',nargs='+',required=True);a.add_argument('--glossary',default=str(Path(__file__).parent/'policies/GLOSSARY.json'));a.add_argument('--out',required=True)
    a=sub.add_parser('check-edit');a.add_argument('--before',required=True);a.add_argument('--after',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('final-ready');a.add_argument('--intake',required=True)
    args=p.parse_args();result=None
    if args.cmd=='probe':result=install.probe(args.template)
    elif args.cmd=='template-source':result=install.template_source(args.repo,args.revision,args.out)
    elif args.cmd=='install':result=install.install(args.template,args.home,Path(__file__).parent)
    elif args.cmd=='discover':result=sources.discover(args.repo,args.ref,args.fetch)
    elif args.cmd=='sync':
        manifest,out=sources.sync(args.repo,args.profile,args.home,fetch=args.fetch,metadata_only=args.metadata_only,lfs=args.lfs)
        result={'snapshot':str(out),'files':len(manifest['files']),'errors':manifest['errors']}
    elif args.cmd=='adopt-export':result=publication.adopt(args.profile,args.export,args.out)
    elif args.cmd=='assets':result=publication.assets(args.spec,args.out)
    elif args.cmd=='unpack':result=publication.unpack(args.parts,args.out)
    elif args.cmd=='package-inputs':result=install.package_inputs(args.home,args.snapshot)
    elif args.cmd=='bind':result=install.bind(args.home,args.workspace)
    elif args.cmd=='intake':result=intake.build(args.spec,args.out)
    elif args.cmd=='changes':result=sources.changes(args.old,args.new)
    elif args.cmd=='lint':result=manuscript.lint(args.body,args.glossary)
    elif args.cmd=='check-edit':result=manuscript.compare(Path(args.before).read_text(encoding='utf-8'),Path(args.after).read_text(encoding='utf-8'))
    elif args.cmd=='final-ready':
        status=read(Path(args.intake)/'INTAKE_STATUS.json');result={'formal_data_ready':status['formal_ready'],
          'next':'Write results with the selected evidence, then perform scientific, figure and PDF review through the original workflow.' if status['formal_ready'] else 'Continue theory preparation; use INTAKE_STATUS.json to complete missing final records.'}
    if hasattr(args,'out') and args.cmd not in ('intake','assets','unpack','adopt-export','template-source'):write(args.out,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.cmd=='final-ready' and not result['formal_data_ready']:return 2
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError) as exc:
        print(json.dumps({'status':'action_required','error':str(exc)},ensure_ascii=False),file=sys.stderr);raise SystemExit(2)
