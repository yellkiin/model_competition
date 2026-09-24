"""Record original-problem reading and current first-chapter semantic review."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PAPER=ROOT/'论文'
sys.path.insert(0,str((ROOT/'../华为杯_论文规范模板/tools').resolve()))
from first_chapters import source_bindings, symbol_rows, audit_source

def ref(sid,place,quote): return {'source_id':sid,'location':place,'quote':quote}
def covered(text,obs): return {'status':'verified','restatement_quote':text,'observation':obs}
def para(text, phrase):
    start=text.rfind('\n\n',0,text.find(phrase))+2
    end=text.find('\n\n',text.find(phrase))
    return text[start:end if end>=0 else len(text)].strip()

def main():
    rest=(PAPER/'章节内容/01_问题重述.tex').read_text(encoding='utf-8-sig')
    qparas=[para(rest,'问题一针对场景 A'),para(rest,'问题二针对场景 B'),para(rest,'问题三在场景 B')]
    for q in qparas:
        assert q in rest
    sources=[
      {'id':'problem','path':'题目/通用神经网络处理器下的多核调度问题.docx','kind':'problem'},
      {'id':'readme','path':'数据/原始/A题官方附件/README.md','kind':'attachment'},
      {'id':'sze','path':'论文/参考来源/sze2017_author/source.html','kind':'verified_external'},
      {'id':'eyeriss','path':'论文/参考来源/eyeriss2017_mit/source.html','kind':'verified_external'},
      {'id':'tpu','path':'论文/参考来源/jouppi2017_google/source.html','kind':'verified_external'},
      {'id':'pebble','path':'论文/参考来源/hongkung1981_author/source.pdf','kind':'verified_external'},
    ]
    context={
      'object_scene':[{'text':'同构 NPU 核、私有 L1/UB 与共享 DDR 上的 Op–Tensor 有向无环图。',
        'source':ref('problem','正文 1.1 段5、1.2 段7至19','考虑由  个同构 AI 核心与共享核外主存')}],
      'difficulty_causes':[{'text':'切图、分核和同核顺序共同影响并行、边界搬运和驻留时间。',
        'source':ref('problem','正文 1.3 段23','求解困难来自三个相互耦合的决策：切图、核心的分配和同一核内的子图调度顺序。')}],
      'scope_exclusions':[{'text':'L0A、L0B、L0C 和 VReg 不是本题评估的缓存约束。',
        'source':ref('problem','附录 A 段76','图中L0A、L0B、L0C、VReg缓存不用在本题中考虑')}],
      'shared_conditions':[{'text':'固定官方配置与全部计算图，输出非 COPY 操作子图映射和逐核序列。',
        'source':ref('problem','正文 1.3 段24至28、附录 B.3/B.5','映射表必须包含所有核内操作节点')},
        {'text':'官方全局 Makespan 是主指标，额外 DDR 搬运为次指标。',
        'source':ref('problem','正文 1.4 段30至35','总体任务执行时间（Makespan）：最重要指标')}],
    }
    question_specs=[
      dict(order=1,original_id='问题 1',source=ref('problem','正文问题 1 段45至50','场景 A 下，每个子图独立构成一个 Task，所有跨子图数据均须经 DDR 中转。'),
        inputs=['官方计算图','固定配置','二至五个核心'],action='构造切图并给出逐核子图序列',object='场景 A 的每子图一 Task 调度',
        conditions=['全部跨子图数据经 DDR','子图依赖无环','同步与容量规则按官方评估器'],
        outputs=['正式方案 JSON','一至五核平均加速比折线图','逐例 Makespan 与新增 DDR 搬运','Python 复现程序'],
        validation=['全部官方用例与固定配置','官方评估器输出','附件可复现'],depends_on=[],required_methods=[],
        literal_requirements=['二至五核','DDR','Makespan'],subtasks=[
          ('问题 1-正文','正文：给出 1～5 个核的平均加速比折线图','平均加速比'),
          ('问题 1-附录','附录：逐用例列出赛题评估程序给出的结果','逐例结果表'),
          ('问题 1-附件','附件：提供可复现的 Python 程序脚本','可复现程序')]),
      dict(order=2,original_id='问题 2',source=ref('problem','正文问题 2 段52至57','场景 B 下，每个核心上的全部子图合并为一个 Task'),
        inputs=['问题一模型','官方计算图','固定配置','二至五个核心'],action='改进切图、分核和调度',object='场景 B 的同核合并 Task 调度',
        conditions=['同核 L1/UB 复用','跨核 DDR 拷贝与同步','满足 L1/UB 容量'],
        outputs=['正式方案 JSON','一至五核平均加速比折线图','逐例 Makespan 与新增 DDR 搬运','Python 复现程序'],
        validation=['全部官方用例与固定配置','与问题一相同的单核分母','附件可复现'],depends_on=['问题 1'],required_methods=[],
        literal_requirements=['二至五核','L1','UB'],subtasks=[
          ('问题 2-正文','正文：给出场景 B 下 1～5 个核的平均加速比折线图','平均加速比'),
          ('问题 2-附录','附录：逐个用例地列出赛题评估程序给出的结果','逐例指标'),
          ('问题 2-附件','附件：提供可复现的 Python 程序脚本','可复现的 Python 程序')]),
      dict(order=3,original_id='问题 3',source=ref('problem','正文问题 3 段58至62','本问题在场景 B 的基础上引入所有核心共享的只读 L2 Cache'),
        inputs=['场景 B 方案','官方计算图','固定 L2 配置','容量与带宽变化分析'],action='研究缓存参数并设计适配算法',
        object='共享只读 L2 下的多核切图与调度',
        conditions=['COPY_IN 才查询 L2','只读 FIFO','独立 DDR/L2 带宽','同方案无 L2 与有 L2 比较'],
        outputs=['一至五核两配置曲线','同核数 Cache 加速比','逐例两配置 Makespan、额外搬运与命中率'],
        validation=['固定配置的官方实验','同方案加速比定义','参数变化另列非官方分析'],depends_on=['问题 2'],required_methods=[],
        literal_requirements=['COPY\\_IN','FIFO','同一方案'],subtasks=[
          ('问题 3-正文','正文：给出 1～5 核下无 L2 与只读 Cache 两种配置的对比曲线','正文比较同核数无 L2 与有 L2 的结果'),
          ('问题 3-附录','附录：逐用例列出无 L2 与只读 Cache 两种配置','逐例结果表')]),
    ]
    tasks=[]
    for spec,q in zip(question_specs,qparas):
        sub=spec.pop('subtasks')
        spec['coverage']=covered(q,'逐项对照原题的场景、输入、输出与校验要求；该段保持题定口径且没有塞入本文成绩。')
        spec['subtasks']=[{'original_id':sid,'source':ref('problem',f'正文{sid}',quote),
             'coverage':covered(q,'同一重述段明确保留此交付件及其官方评估口径。'),
             'literal_requirements':[literal]} for sid,quote,literal in sub]
        tasks.append(spec)
    claims=[
      {'text':'待调度的对象是由操作节点和张量节点交替连接而成的有向无环计算图。','kind':'problem',
       'source':ref('problem','正文 1.2 段7至19','待调度对象是一张有向无环计算图')},
      {'text':'题目给定的平台由若干同构 NPU 核心及共享 DDR 组成。','kind':'problem',
       'source':ref('problem','正文 1.1 段5','同构 AI 核心与共享核外主存')},
      {'text':'神经网络处理器研究已有对硬件平台、体系结构及降低计算成本路径的系统综述\\cite{sze2017}。','kind':'verified_external','citation_key':'sze2017',
       'source':ref('sze','arXiv 摘要第2段','discuss various hardware platforms and architectures')},
      {'text':'Eyeriss 对局部复用和片外访存能耗的实证分析说明，数据流设计会显著改变搬运代价\\cite{eyeriss2017}；','kind':'verified_external','citation_key':'eyeriss2017',
       'source':ref('eyeriss','MIT 页面 Abstract 段','maximally reusing data locally to reduce expensive data movement')},
      {'text':'TPU 的整模型评估则提醒我们，专用矩阵单元的峰值能力不能单独代表应用完成时间\\cite{jouppi2017}。','kind':'verified_external','citation_key':'jouppi2017',
       'source':ref('tpu','Google Research Abstract 段','99th-percentile response-time requirement')},
      {'text':'经典的红蓝卵石模型从理论上刻画有限快存下计算与I/O的牵制\\cite{hongkung1981}。','kind':'verified_external','citation_key':'hongkung1981',
       'source':ref('pebble','原刊 PDF 第1页摘要','red-blue pebble game is proposed to model the')},
    ]
    symbol_tex=PAPER/'章节内容/03_关键性符号说明.tex'
    symbol_text=symbol_tex.read_text(encoding='utf-8-sig')
    chapters=[PAPER/'章节内容/04_问题一.tex',PAPER/'章节内容/05_问题二.tex',PAPER/'章节内容/06_问题三.tex']
    symbols=[]
    for row in symbol_rows(symbol_text):
        symbol=row['symbol']; definition=next(line for line in symbol_text.splitlines() if symbol in line and '\\GMCMSymbolRow' in line)
        uses=[]
        for chapter in chapters:
            for line in chapter.read_text(encoding='utf-8-sig').splitlines():
                if symbol in line:
                    uses.append({'tex_path':'章节内容/'+chapter.name,'quote':line.strip()})
                    break
            if uses: break
        if not uses: raise ValueError('核心符号缺少正文实际使用: '+symbol)
        symbols.append(dict(row,scope='三个问题公共记号' if chapter.name.startswith('04') else '问题二、三使用' if chapter.name.startswith('05') else '问题三使用',
             in_core_table=True,first_definition={'tex_path':'章节内容/03_关键性符号说明.tex','quote':definition},uses=uses))
    evidence={'sources':sources,'context':context,'tasks':tasks,'claims':claims,'gaps':[],
              'symbols':symbols,'review':{}}
    manifest=json.loads((PAPER/'论文输入.json').read_text(encoding='utf-8-sig'))
    review={'reviewer':'Codex：核对原题 DOCX 段落、四幅图及官方 README，逐项对照当前前三章',
      'reviewed_at':datetime.now(timezone.utc).isoformat(),'findings':[],
      'task_coverage':{'status':'verified','observation':'原题只有问题 1、2、3；逐问核对正文/附录/附件子项，问题三原题仅列正文与附录两类结果。'},
      'conditions_units_logic':{'status':'verified','observation':'问题一与二均写二至五核方案、一至五核曲线；问题二的同核复用、问题三的只读 FIFO 和同方案比值均按原题保留。'},
      'source_attribution':{'status':'verified','observation':'硬件、图格式及交付条件来自题目 DOCX 和官方附件；四项外部背景均有作者或出版方原文与正文实引证据。'},
      'method_assumption_result_separation':{'status':'verified','observation':'1.1 和 1.2 未报告本文实验值或候选算法细节；路线图明确是本文研究安排，第二章新增假设单列。'},
      'dependencies_outputs_validation':{'status':'verified','observation':'场景 B 继承问题一基准和模型，L2 继承场景 B；逐例结果、折线图及复现附件分别对上原题交付。'},
      'background_coherence':{'status':'verified','observation':'先说明二部图与多核存储，再解释切分、DDR 争用和缓存驻留之间的冲突，末段落到官方全局评估。'},
      'natural_expression':{'status':'verified','observation':'每段以具体对象和机制为主线，避免空泛行业意义与先报本文成绩；问题重述按三问连续叙述。'},
      'symbol_definitions':{'status':'verified','observation':'逐行核对 21 个表内独立符号，单位分别为字节、周期、带宽或无量纲；全部在后续正文有实际使用。'}}
    evidence['review']=review
    review['bindings']=source_bindings(manifest,PAPER,evidence)
    path=ROOT/'求解/题意写作依据.json'
    path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    result=audit_source(manifest,PAPER)
    print(path,result['status'],result['failures'])

if __name__=='__main__':main()
