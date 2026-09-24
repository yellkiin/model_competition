"""Bind manually reviewed bibliographic fields and scientific claims to retained originals."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
PAPER=ROOT/'论文'
sys.path.insert(0,str((ROOT/'../华为杯_论文规范模板/tools').resolve()))
from ai_disclosure import disclosure_record
from reference_evidence import SourceHTML, norm, source_metadata

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def raw_text(folder):
    p=next((PAPER/'参考来源'/folder).glob('source.*'))
    raw=p.read_text(encoding='utf-8-sig')
    if p.suffix=='.html':
        parser=SourceHTML();parser.feed(raw);return ' '.join(parser.text)
    return raw

def fields(folder, specs):
    """Specs are (field, value, unique inspected locator) tuples."""
    raw=raw_text(folder)
    result={}
    for field,value,needle in specs:
        m=re.search(re.escape(needle),raw,re.I)
        if not m: raise ValueError(f'{folder}: locator absent: {needle}')
        q=raw[max(0,m.start()-32):m.end()+70]
        if norm(value) not in norm(q): raise ValueError(f'{folder}: field absent in quote: {field}: {value}')
        result.setdefault(field,[]).append({'value':value,'quote':q})
    return result

def source(folder,authority,reason,observation,*,format=None,pages=None,quotes=None):
    draft=json.loads((PAPER/'参考来源'/folder/'draft.json').read_text(encoding='utf-8-sig'))['source_draft']
    if format: draft['format']=format
    if pages: draft['pdf_pages']=pages
    if quotes is not None: draft['field_quotes']=fields(folder,quotes) if quotes else {}
    draft['authority']=authority
    draft['authority_reason']=reason
    draft['review']={'reviewed':True,'tool_ref':f'论文/参考来源/{folder}/source.* 实际原文或页面',
      'observation':observation}
    p=PAPER/draft['capture_path']
    meta,_=source_metadata(p,draft)
    print(folder,'metadata',','.join(meta))
    return draft

CSL_REVIEW='逐项核对 Crossref 所存作者、题名、刊名、年份、卷期和页码；书目字段仅据本条原始记录登记。'
def csl(folder):
    return source(folder,'publisher','Crossref DOI 注册元数据对应正式期刊或会议记录，作为印刷书目字段的核对来源。',CSL_REVIEW)

usage_text={
 'sze2017':('pre1','sze2017_author','various hardware platforms and architectures','作者摘要论述硬件平台、体系结构和计算成本路径；正文只概括其综述范围。'),
 'eyeriss2017':('pre1','eyeriss2017_mit','maximally reusing data locally to reduce expensive data movement','MIT 作者机构摘要直接说明局部复用减少昂贵的数据搬移。'),
 'jouppi2017':('pre1','jouppi2017_google','99th-percentile response-time requirement','作者机构摘要并列给出峰值吞吐与尾部响应时间；正文将其作为应用级评价动机。'),
 'hongkung1981':('pre1','hongkung1981_author','red-blue pebble game is proposed to model the','原刊首页明确提出红蓝卵石游戏刻画输入输出复杂度，正文不移植其下界数值。'),
 'perotin2021':('q1','perotin2021','multi-resource scheduling to minimize the makespan','预印本摘要明确同时列出多种资源、先后约束及完工时间目标。'),
 'topcuoglu2002':('q1','topcuoglu2002_university','The HEFT algorithm selects the task with the highest upward rank','作者所在高校的论文摘要明确说明 HEFT 的优先级与最早完工选择。'),
 'kernighan1970':('q1','kernighan1970_author','minimize the total cost of the edges cut','原出版机构展示论文开篇定义：给定规模限制下最小化被切边的总成本。'),
 'karypis1998':('q1','karypis1998_original','all three phases: coarsening, partition','原刊第一页摘要列出粗化、粗图划分与细化三阶段。'),
 'chen2018tvm':('q2','chen2018tvm','high-level operator fusion, mapping to arbitrary hardware primitives','USENIX 原论文摘要明确提到算子融合与硬件映射；正文只借鉴系统动机。'),
 'mattson1970':('q3','mattson1970_original','an efficient technique called “stack processing”','原刊首页描述基于访问轨迹与栈处理评价存储层级；正文未把其模型套作本题 FIFO。'),
}

SZE={
 'kind':'article','title':'Efficient Processing of Deep Neural Networks: A Tutorial and Survey',
 'authors':['Vivienne Sze','Yu-Hsin Chen','Tien-Ju Yang','Joel S. Emer'],'year':'2017',
 'container':'Proceedings of the IEEE','volume':'105','issue':'12','pages':'2295-2329'}
EYERISS={
 'kind':'article','title':'Eyeriss: An Energy-Efficient Reconfigurable Accelerator for Deep Convolutional Neural Networks',
 'authors':['Yu-Hsin Chen','Tushar Krishna','Joel S. Emer','Vivienne Sze'],'year':'2017',
 'container':'IEEE Journal of Solid-State Circuits','volume':'52','issue':'1','pages':'127-138'}
META = {
 'sze2017': SZE,
 'eyeriss2017': EYERISS,
 'jouppi2017': {'kind':'inproceedings','title':'In-Datacenter Performance Analysis of a Tensor Processing Unit',
   'authors':['Norman P. Jouppi','Cliff Young','Nishant Patil'],'year':'2017',
   'container':'Proceedings of the 44th Annual International Symposium on Computer Architecture','pages':'1-12'},
 'hongkung1981': {'kind':'inproceedings','title':'I/O Complexity: The Red-Blue Pebble Game',
   'authors':['Hong, J-W','Kung, H T'],'year':'1981','container':'STOC 1981','pages':'326-333'},
 'perotin2021': {'kind':'preprint','title':'Multi-Resource List Scheduling of Moldable Parallel Jobs under Precedence Constraints',
   'authors':['Lucas Perotin','Hongyang Sun','Padma Raghavan'],'year':'2021','container':'arXiv:2106.07059'},
 'topcuoglu2002': {'kind':'article','title':'Performance-Effective and Low-Complexity Task Scheduling for Heterogeneous Computing',
   'authors':['H. Topcuoglu','S. Hariri','Min-You Wu'],'year':'2002',
   'container':'IEEE Transactions on Parallel and Distributed Systems','volume':'13','issue':'3','pages':'260-274'},
 'kernighan1970': {'kind':'article','title':'An Efficient Heuristic Procedure for Partitioning Graphs',
   'authors':['B. W. Kernighan','S. Lin'],'year':'1970',
   'container':'Bell System Technical Journal','volume':'49','issue':'2','pages':'291-307'},
 'karypis1998': {'kind':'article','title':'A Fast and High Quality Multilevel Scheme for Partitioning Irregular Graphs',
   'authors':['George Karypis','Vipin Kumar'],'year':'1998',
   'container':'SIAM Journal on Scientific Computing','volume':'20','issue':'1','pages':'359-392'},
 'chen2018tvm': {'kind':'inproceedings','title':'TVM: An Automated End-to-End Optimizing Compiler for Deep Learning',
   'authors':['Tianqi Chen','Thierry Moreau','Ziheng Jiang'],'year':'2018',
   'container':'13th USENIX Symposium on Operating Systems Design and Implementation (OSDI 18)','pages':'578-594'},
 'mattson1970': {'kind':'article','title':'Evaluation Techniques for Storage Hierarchies',
   'authors':['R.L. Mattson','J. Gecsei','D. R. Slutz','I. L. Traiger'],'year':'1970',
   'container':'IBM Systems Journal','volume':'9','issue':'2','pages':'78-117'},
}

def reviewed_sources(key):
    if key=='sze2017': return [csl('sze2017'),source('sze2017_author','author','作者在 arXiv 发布的预印本摘要，可直接核对硬件平台与体系结构的综述范围。','实读 arXiv 摘要对平台、架构和降低计算成本的讨论，正文没有引用未出现的具体量化结果。',format='field_quotes',quotes=[])]
    if key=='eyeriss2017': return [csl('eyeriss2017'),source('eyeriss2017_mit','author','论文作者所属 MIT 研究机构提供的 Eyeriss 原文摘要及数据流说明。','实读 MIT 摘要关于 row-stationary 数据流、局部复用与片外搬运的句子。',format='field_quotes',quotes=[])]
    if key=='jouppi2017': return [
      source('jouppi2017_google','author','Google Research 作者机构的 TPU 论文页面，提供原始摘要及前三位作者。','逐句阅读峰值吞吐、应用利用率和尾部响应时间段落。',format='field_quotes',quotes=[
        ('title',META[key]['title'],'In-Datacenter Performance Analysis of a Tensor Processing Unit'),
        ('authors','Norman P. Jouppi','Norman P. Jouppi'),('authors','Cliff Young','Cliff Young'),('authors','Nishant Patil','Nishant Patil'),
        ('year','2017','ISCA (2017)')]),
      source('jouppi2017','publisher','Crossref DOI 登记的正式会议题名和页码，可核对印刷书目中会议及页码。','只提取会议名与页码，不用它替代论文方法或性能摘要。',format='field_quotes',quotes=[
        ('container',META[key]['container'],META[key]['container']),('pages','1-12','1-12')])]
    if key=='hongkung1981': return [
      source('hongkung1981_biblio','author','Kung 教授公开的个人正式发表论文目录，含本论文完整标题、作者、年份和页码。','实读该目录中 STOC 1981 的完整题名与页码，避免 DOI 注册题名的截断。',format='field_quotes',quotes=[
        ('title',META[key]['title'],META[key]['title']),('authors','Hong, J-W','Hong J-W'),
        ('authors','Kung, H T','Kung HT'),('year','1981','STOC 1981'),('container','STOC 1981','STOC 1981'),('pages','326-333','326-333')]),
      source('hongkung1981_author','author','Kung 教授个人站点公开的原刊论文扫描件，首页可读摘要与模型定义。','核对第一页确实提出红蓝卵石游戏刻画 I/O 复杂度。',format='field_quotes',pages=[1],quotes=[])]
    if key=='perotin2021': return [source('perotin2021','author','三位作者在 arXiv 公开的完整预印本摘要及书目页。','实读摘要中多资源类型、先后约束和最小化 makespan 的完整语句。',format='field_quotes',quotes=[
      ('title',META[key]['title'],META[key]['title']),('authors','Lucas Perotin','Lucas Perotin'),
      ('authors','Hongyang Sun','Hongyang Sun'),('authors','Padma Raghavan','Padma Raghavan'),
      ('year','2021','Submitted on 13 Jun 2021'),('container','arXiv:2106.07059','arXiv:2106.07059')])]
    if key=='topcuoglu2002': return [csl('topcuoglu2002'),source('topcuoglu2002_university','author','合著者所在亚利桑那大学的论文页面，提供完整原摘要和算法描述。','实读 HEFT 的 upward rank 及最早完工处理器选择句。',format='field_quotes',quotes=[])]
    if key=='kernighan1970': return [csl('kernighan1970'),source('kernighan1970_author','publisher','Nokia Bell Labs 为原作者工作机构与原期刊版权关联机构，提供论文开篇正文。','实读图划分的割边目标及子集大小上限，没有把局部交换细节错引到所摘段落。',format='field_quotes',quotes=[])]
    if key=='karypis1998': return [csl('karypis1998'),source('karypis1998_original','repository','伯克利大学服务器保存原刊排版 PDF，第一页摘要可核实多层次三阶段。','实读原刊 PDF 第一页摘要，核对粗化、粗图划分与细化三个过程。',format='field_quotes',pages=[1],quotes=[])]
    if key=='chen2018tvm': return [source('chen2018tvm','publisher','USENIX 会议官网原论文页面，包含作者、正式会议书目与原始摘要。','实读摘要关于算子融合和硬件映射，且核对页面 BibTeX 中的年份和页码。',format='field_quotes',quotes=[
      ('title',META[key]['title'],META[key]['title']),('authors','Tianqi Chen','Tianqi Chen'),
      ('authors','Thierry Moreau','Thierry Moreau'),('authors','Ziheng Jiang','Ziheng Jiang'),
      ('year','2018','year = {2018}'),('container',META[key]['container'],META[key]['container']),
      ('pages','578-594','578--594')])]
    if key=='mattson1970': return [csl('mattson1970'),source('mattson1970_original','repository','保存 IBM Systems Journal 原刊扫描件的公共文献档案，首页有可提取摘要。','实读第一页关于访问轨迹、存储层级与 stack processing 的原始描述。',format='field_quotes',pages=[1],quotes=[])]
    raise KeyError(key)

def main():
    chapters={'pre1':PAPER/'章节内容/01_问题重述.tex','q1':PAPER/'章节内容/04_问题一.tex',
              'q2':PAPER/'章节内容/05_问题二.tex','q3':PAPER/'章节内容/06_问题三.tex'}
    records=[]
    for key,meta in META.items():
        chapter,folder,excerpt,relevance=usage_text[key]
        text=chapters[chapter].read_text(encoding='utf-8-sig')
        marker=r'\cite{'+key+'}'
        i=text.find(marker)
        if i<0: raise ValueError('citation absent: '+key)
        start=max(text.rfind('。',0,i),text.rfind('\n',0,i))+1
        end=text.find('。',i)
        body=text[start:end+1 if end>=0 else len(text)].strip()
        sources=reviewed_sources(key)
        found=False
        for entry in sources:
            _,actual=source_metadata(PAPER/entry['capture_path'],entry)
            if norm(excerpt) in norm(actual): found=True
        if not found: raise ValueError('source excerpt absent: '+key)
        records.append({'key':key,'reference_type':'ordinary','sources':sources,
          'manual_metadata':meta,'usages':[{'chapter_id':chapter,'body_excerpt':body,'source_excerpt':excerpt,
          'relevance':relevance+' 原文与该句在主题和限定语上对应，未把文献结论作为本题实测成绩。',
          'reviewed':True,'tool_ref':f'论文/参考来源/{folder}/source.* 源句复核'}]})
    records.append(disclosure_record())
    bib=PAPER/'章节内容/08_参考文献.tex'
    evidence={'schema_version':'1.1','bibliography_files':[{'path':'章节内容/08_参考文献.tex','sha256':sha(bib)}],
              'references':records}
    out=PAPER/'参考文献证据.json'
    out.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(out, len(records))

if __name__=='__main__': main()
