"""Register real overview artifacts and their current scientific dependencies."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT.parent
SIDE=ROOT/'求解/视觉计划.diagrams.json'
PLAN=ROOT/'求解/视觉计划.json'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def sr(path,locator):
    return {'path':path,'sha256':sha(ROOT/path),'locator':locator}
def ref(path,obs,decision):
    return {'path':path,'sha256':sha(TEMPLATE/path),'reviewed':True,
            'observation':obs,'decision':decision}

GALLERY={
 '02':'.agents/skills/comprehensive-graphic-text-flowchart/assets/约束优化综合图_疲劳模型与遗传搜索验证.png',
 '06':'.agents/skills/comprehensive-graphic-text-flowchart/assets/多源检测综合图_样本采集与传感分析及模型构建.jpg',
 '10':'.agents/skills/comprehensive-graphic-text-flowchart/assets/双模态融合综合图_RGB与高光谱重建及预测.jpg',
 'algo':'.agents/skills/algorithm-mechanism-diagram/assets/光谱双分支网络_专家知识与全局特征动态融合.png',
}
RESULTS={1:('q1-F02','q1-F03'),2:('q2-F02','q2-F03'),3:('q3-F02','q3-F03')}
QUESTIONS={
 1:'切图、依赖序列和官方场景A响应如何构成可核验的调度？',
 2:'同核合并、跨核边界与存储压力怎样共同决定场景B时长？',
 3:'共享只读L2的双读池与FIFO机制怎样影响同方案收益？',
}

def build(q):
    qid=f'q{q}';f1,f2=RESULTS[q]
    vector=f'求解/综合图/{qid}-overview.pdf';preview=f'求解/综合图/{qid}-overview.png'
    source=f'求解/综合图/{qid}-overview.tex'
    result_path='求解/正式实验/统计分析.json'
    validate_path='求解/正式实验/逐问核验摘要.json'
    source_records=[sr('求解/题面约束清单.md','本问硬约束及官方口径'),
                    sr('求解/求解计划.md','三问候选构造与评价路径'),
                    sr(result_path,f'{qid}各核数与五核成对统计'),
                    sr(validate_path,'独立核验或正式结果交叉校验')]
    for fid in (f1,f2):
        source_records.append(sr(f'求解/正式图件/{fid}.pdf',f'{fid}已计算图件的完整原图'))
    if q==3:
        source_records.append(sr('求解/正式实验/L2参数敏感性_非官方/统计验证.json',
                                 '六例54格非官方配置与默认官方配置交叉核验'))
    refs=[ref(GALLERY['02'],'原图上侧公式与算法、下侧验证结果的非等宽矩形分区清晰；历史疲劳数据不可复用。','继承对象—方法—证据纵向组织，不复制统计数值。'),
          ref(GALLERY['06'],'三栏浅马卡龙底板与窄白隙组织复杂证据；缩图保留且由正文详细图承担读数。','继承浅色紧凑分区与直接复用结果原图。'),
          ref(GALLERY['algo'],'原图有真实输入到双支路再汇合的矢量连接语法，但卷积网络题材与调度无关。','只继承分支与连接画法，本题顶端节点、Cache或核心关系依据题面重绘。')]
    if q==3:
        refs[0]=ref(GALLERY['10'],'原图上层两条数据路径汇合，下层方法和结果形成全幅矩形；历史重建任务与数值不适用。','继承左右两读池路径的连接组织，不使用历史图像或模型。')
    panels=[
      {'panel_id':'mechanism','kind':'algorithm','content':['非COPY操作—张量交替DAG及依赖箭头','同核保留与跨核COPY对比','COPY_IN命中L2读池、未命中DDR读池'][q-1],
       'mechanism_skill':'algorithm-mechanism-diagram','source_path':'求解/题面约束清单.md',
       'source_locator':f'问题{["一","二","三"][q-1]}题定规则',
       'semantic_review':'顶部矢量图元只绘题定节点与真实数据流，不引入神经网络模板的历史层数。'},
      {'panel_id':'method','kind':'process','content':['连通块、深度段和分批候选→官方场景A择优','场景A候选→场景B重评→容量与COPY分解','命中/未命中双读池→同方案反事实→官方评价'][q-1],
       'source_path':'求解/求解计划.md','source_locator':f'逐问工作{q}',
       'semantic_review':'箭头对应真实候选产生、规则重评和验证顺序，不画不存在的反馈迭代。'},
      {'panel_id':'resulta','kind':'result','content':f'{f1}真实定量结果缩图',
       'source_path':f'求解/正式图件/{f1}.pdf','source_locator':f'{f1}论文尺寸矢量图',
       'visual_plan':'求解/视觉计划.json','visual_figure_id':f1,'detail_figure_id':f1,
       'reuse_mode':'direct','semantic_review':'直接嵌入当前结果图，缩图仅作导航，完整值由正文详细图承担读取。'},
      {'panel_id':'resultb','kind':'result','content':f'{f2}真实定量结果缩图',
       'source_path':f'求解/正式图件/{f2}.pdf','source_locator':f'{f2}论文尺寸矢量图',
       'visual_plan':'求解/视觉计划.json','visual_figure_id':f2,'detail_figure_id':f2,
       'reuse_mode':'direct','semantic_review':'直接嵌入当前结果图，非官方配置在问题三缩图中明确标注。'},
      {'panel_id':'validation','kind':'validation','content':['500条所选配置的官方响应与独立时间线一致','500条所选配置的容量峰值与时间线独立核验','100例默认配置与六例非官方网格的交叉核验'][q-1],
       'source_path':validate_path,'source_locator':'结果校验字段与统计验证',
       'semantic_review':'只概括实际执行的独立或交叉核验，未绘虚构精度。'},
    ]
    relations=[('mechanism','method','derivation','题定结构约束决定候选和规则'),
               ('method','resulta','sequence','官方评估候选产生实际图一'),
               ('method','resultb','sequence','官方评估候选产生实际图二'),
               ('resulta','validation','validation','独立记录核验所展示结果'),
               ('resultb','validation','validation','独立记录核验所展示结果')]
    con=[{'from':a,'to':b,'type':c,'meaning':m,'source_locator':f'求解/求解计划.md:逐问工作{q}'} for a,b,c,m in relations]
    deps=['求解/build_overviews.py','求解/视觉计划.json',source,vector,preview]
    return {'diagram_id':f'{qid}-OVERVIEW','problem_id':qid,'kind':'comprehensive','placement':'body',
      'scientific_question':QUESTIONS[q],'backend':'tikz',
      'backend_reason':'题定DAG、核心或Cache路径需要自由矢量图元，已有两张正式图可直接嵌入；TikZ保证中文与公式可编辑。',
      'source':source,'dependencies':deps,'outputs':{'vector':vector,'preview':preview},
      'target_width_mm':160,'physical_size':{'target_body_height_mm':154,
        'minimum_body_height_mm':148.5,'minimum_text_width_fraction':0.9,
        'measurement':'actual_pdf_ink_excluding_caption',
        'density_review':'三带分别包含本问实质机理、求解约束与两张真实结果，非空板拉伸。'},
      'sources':source_records,'references':refs,'panels':panels,'connections':con,
      'flow_semantics':True,'narrative':{'task':QUESTIONS[q],
        'basis':'题定图和官方事件模拟规则作为前提，100例实算为结果。',
        'solve':'候选构造、场景评价与独立核验按图中编号推进。',
        'outcome':'100例五核均值及机制成对指标取自当前结构化统计。'},
      'overview_detail':f'结果缩图 {f1} 与 {f2} 分别对应正文详细图，缩图数字不负责单独读数。',
      'paper':{'caption':f'问题{["一","二","三"][q-1]}求解与核验总览',
               'label':f'fig:{qid}-overview',
               'reference_context':'本问首节问题描述与分析先引用图，再通过生成的浮动保护片段入文。'},
      'qa_path':f'求解/综合图/{qid}-overview.qa.json','status':'incomplete'}

def main():
    data=json.loads(SIDE.read_text(encoding='utf8'))
    data['questions']=[{'problem_id':f'q{q}','chapter_id':f'q{q}','supporting_question_id':f'q{q}',
                        'overview_id':f'q{q}-OVERVIEW'} for q in (1,2,3)]
    data['diagrams']=[d for d in data['diagrams'] if not str(d['diagram_id']).endswith('-OVERVIEW')]
    data['diagrams'] += [build(q) for q in (1,2,3)]
    data['figure_accounting']=[r for r in data['figure_accounting'] if not str(r['figure_id']).endswith('-OVERVIEW')]
    data['figure_accounting'] += [{'figure_id':f'q{q}-OVERVIEW','purpose':'question_overview',
      'problem_id':f'q{q}','per_question':False,'paper_total':True,'flow_total':True,
      'scientific_contribution':QUESTIONS[q]} for q in (1,2,3)]
    SIDE.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('registered three overview diagrams')

if __name__=='__main__':main()
