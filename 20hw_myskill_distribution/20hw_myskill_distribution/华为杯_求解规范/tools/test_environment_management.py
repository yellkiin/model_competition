"""Environment management tests use temporary paths and controlled adapters."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import environment_contract as contract
import environment_manager as manager
import environment_platform as platform_tools
import test_workspace_context as fixtures


class Response(io.BytesIO):
    status=200
    headers={'Content-Type':'application/octet-stream'}
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def geturl(self):return 'https://official.example/artifact.exe'


class InterruptedResponse(Response):
    def __init__(self,payload):
        super().__init__(payload);self.reads=0
    def read(self,size=-1):
        self.reads+=1
        if self.reads>1:raise OSError('connection interrupted')
        return super().read(4)


class EnvironmentTests(unittest.TestCase):
    def test_catalog_is_strict_and_git_is_not_base(self):
        catalog=contract.load_catalog();base=contract.validate_needs(contract.read_json(contract.ENV_DIR/'基础需求.json'))
        self.assertNotIn('git',{r['capability'] for r in base['requirements']})
        broken=dict(base,unexpected=True)
        with self.assertRaises(ValueError):contract.validate_needs(broken)
        provider=dict(catalog['providers'][0]);provider['unexpected']=True
        bad=dict(catalog,providers=[provider,*catalog['providers'][1:]])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.json';path.write_text(json.dumps(bad),encoding='utf8')
            with mock.patch.object(contract,'read_json',side_effect=lambda p: bad if Path(p).name=='软件目录.json' else json.loads(Path(p).read_text(encoding='utf-8-sig'))):
                with self.assertRaises(ValueError):contract.load_catalog()

    def test_merge_keeps_reason_and_sources_without_success(self):
        base={'schema_version':'1.0','requirements':[dict(capability='pdf',necessity='conditional',enabled=False,sources=['base'],reason='基础按需',provider=None)]}
        add={'schema_version':'1.0','requirements':[dict(capability='pdf',necessity='required',enabled=True,sources=['data_format'],reason='输入 PDF',provider=None),dict(capability='unknown-reader',necessity='optional',enabled=False,sources=['problem'],reason='待确认格式',provider=None)]}
        result=contract.merge_needs(base,add)
        self.assertEqual(result['requirements'][0]['sources'],['base','data_format'])
        self.assertNotIn('status',result['requirements'][0])

    def test_windowsapps_alias_rejected(self):
        with self.assertRaisesRegex(ValueError,'WindowsApps'):
            platform_tools.python_probe(r'C:\Users\u\AppData\Local\Microsoft\WindowsApps\python.exe')

    def test_path_preserves_and_deduplicates_unicode(self):
        value=platform_tools.append_path(r'C:\工具;C:\Existing;C:\工具',[r'c:\工具',r'D:\New Folder'])
        self.assertEqual(value,r'C:\工具;C:\Existing;D:\New Folder')

    def test_process_environment_injects_tools_without_pythonpath(self):
        env=platform_tools.process_env([r'C:\工作区\.venv\Scripts',r'C:\TeX Bin'],{'DRAWIO_CLI':r'C:\Draw IO\draw.io.exe'},{'PATH':r'C:\Windows','PYTHONPATH':'bad'})
        self.assertTrue(env['PATH'].startswith(r'C:\工作区\.venv\Scripts'))
        self.assertNotIn('PYTHONPATH',env);self.assertEqual(env['DRAWIO_CLI'],r'C:\Draw IO\draw.io.exe')

    def test_download_falls_back_and_reuses_verified_cache(self):
        payload=b'MZ'+b'x'*30;digest=hashlib.sha256(payload).hexdigest()
        artifact=dict(filename='tool.exe',urls=['https://mirror.example/tool.exe','https://official.example/tool.exe'],sha256=digest,format='exe',publisher_reference='https://official.example/release')
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            if 'mirror.example' in req.full_url:raise OSError('mirror down')
            return Response(payload)
        with tempfile.TemporaryDirectory() as d:
            events=[];path=platform_tools.download(artifact,d,events,opener=opener)
            self.assertEqual(path.read_bytes(),payload);self.assertEqual(len(calls),3)
            platform_tools.download(artifact,d,events,opener=lambda *_: self.fail('network used'))
            path.write_bytes(b'MZbad')
            with self.assertRaises(ValueError):
                platform_tools.download(dict(artifact,urls=[]),d,events)

    def test_interrupted_download_is_quarantined_before_fallback(self):
        payload=b'MZ'+b'x'*(1024*1024+16);digest=hashlib.sha256(payload).hexdigest()
        artifact=dict(filename='tool.exe',urls=['https://mirror.example/tool.exe','https://official.example/tool.exe'],sha256=digest,format='exe',publisher_reference='https://official.example/release')
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            if 'mirror.example' in req.full_url:return InterruptedResponse(payload)
            return Response(payload)
        with tempfile.TemporaryDirectory() as d:
            events=[];path=platform_tools.download(artifact,d,events,opener=opener)
            self.assertEqual(path.read_bytes(),payload)
            self.assertEqual(calls[:2],['https://mirror.example/tool.exe']*2)
            self.assertEqual(calls[-1],'https://official.example/tool.exe')
            self.assertTrue(list(Path(d).glob('*.rejected')))

    def test_real_venv_create_and_reuse(self):
        case=fixtures.WorkspaceTests('runTest');case.setUp()
        try:
            context=case.create();events=[]
            first=manager.ensure_venv(context,Path(os.path.realpath(os.sys.executable)),events)
            second=manager.ensure_venv(context,Path(os.path.realpath(os.sys.executable)),events)
            self.assertEqual(first,second);self.assertTrue(first.is_file())
            self.assertEqual(platform_tools.python_probe(first,first.parent.parent)['prefix'],str(first.parent.parent))
        finally:case.tearDown()

    def test_existing_tex_provider_prevents_install(self):
        case=fixtures.WorkspaceTests('runTest');case.setUp()
        try:
            context=case.create();manager.initialize(context)
            additions={'schema_version':'1.0','requirements':[dict(capability='latex',necessity='required',enabled=True,sources=['rendering'],reason='论文编译',provider=None)]}
            manager.register(context,_json_file(context.workspace_root/'求解/add.json',additions))
            python=manager.ensure_venv(context,Path(os.path.realpath(os.sys.executable)),[])
            fake=Path(r'C:\Existing TeX\xelatex.exe')
            passed=[{'name':'xelatex','returncode':0,'output':'ok'}]
            with mock.patch.object(manager,'ensure_venv',return_value=python),mock.patch.object(manager,'tex_candidates',return_value=[fake]),mock.patch.object(manager,'tex_probe',return_value=passed),mock.patch.object(manager,'run',return_value={'name':'xelatex','returncode':0,'output':'XeTeX, TeX Live 2026'}),mock.patch.object(manager,'install_external',side_effect=AssertionError('must not install')):
                report,_=manager.detect(context,contract.load_catalog(),contract.validate_needs(contract.read_json(context.read_path(manager.NEEDS))),context.workspace_root/'求解/test-probe',prepare=True,persist_user=False)
            latex=next(r for r in report['results'] if r['capability']=='latex')
            self.assertEqual(latex['status'],'satisfied');self.assertEqual(latex['provider'],'texlive')
        finally:case.tearDown()


def _json_file(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf8');return path

if __name__=='__main__':unittest.main()
