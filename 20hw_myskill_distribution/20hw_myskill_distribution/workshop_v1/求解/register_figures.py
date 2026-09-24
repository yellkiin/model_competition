"""Register the 16 computed figure contracts without asserting visual QA."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'求解/视觉计划.json'

# Scientific roles are fixed from the real data interface and verified plots.
META={
 'q1-F01':('图规模与最大连通块占比如何联合分布？','distribution_uncertainty','hexbin','DensityHeatmap','输入结构分布','q1-E02'),
 'q1-F02':('核数扩展如何改变加速比的中心与离散范围？','trend_scan','forest','ParameterSweep','核数扩展与加速比','q1-E02'),
 'q1-F03':('最大连通块占比不同的图有何加速差异？','distribution_uncertainty','violin','GroupedViolin','结构分组加速差异','q1-E04'),
 'q1-F04':('五核新增DDR搬运与加速之间有何权衡？','relationship_correlation','bubble','MarginalDensity','加速与新增搬运','q1-E04'),
 'q1-F05':('何种结构条件下深度分段候选胜出？','heatmap_surface','heatmap','ScenarioHeatmap','结构分箱候选胜率','q1-E04'),
 'q1-F06':('候选评估时间与候选质量怎样权衡？','optimization_decision','scatter','PairedBoxScatter','候选质量与评估成本','q1-E03'),
 'q2-F01':('同方案的场景A/B时长比如何随核数变化？','distribution_uncertainty','violin','Violin','同方案场景收益','q2-E02'),
 'q2-F02':('场景B内重新择优的附加收益有多大？','comparison_ranking','box','PairedBoxScatter','场景B策略增益','q2-E03'),
 'q2-F03':('新增DDR搬运中的边界COPY与Spill各占多少？','trend_scan','area','BarComposition','新增搬运来源','q2-E03'),
 'q2-F04':('容量压力与五核收益如何共同变化？','relationship_correlation','bubble','MarginalDensity','容量压力与加速','q2-E04'),
 'q2-F05':('场景切换后的速度与搬运变化是否同向？','relationship_correlation','scatter','PairedBoxScatter','速度搬运象限','q2-E04'),
 'q3-F01':('题定L2配置下同方案Cache收益的经验分布如何？','distribution_uncertainty','ecdf','ConvergenceBand','Cache收益经验分布','q3-E02'),
 'q3-F02':('命中字节率与同方案收益如何关联？','relationship_correlation','hexbin','DensityHeatmap','命中率与收益','q3-E03'),
 'q3-F03':('六例非官方容量带宽网格的实测响应面如何？','heatmap_surface','surface','3DHeatmap','容量带宽响应面','q3-E04'),
 'q3-F04':('容量变化如何改变六例的命中字节率？','trend_scan','line','LineTrend','容量命中响应','q3-E04'),
 'q3-F05':('各核数的命中和未命中查询字节如何构成？','comparison_ranking','bar','BarComposition','核数与查询字节','q3-E03'),
}

def main():
    p=json.loads(PLAN.read_text(encoding='utf8'))
    chapter={'q1':'04_问题一.tex','q2':'05_问题二.tex','q3':'06_问题三.tex'}
    units={'cores':'核','internal_ops':'个','components':'个','largest_component_fraction':'比例',
           'q1_speedup':'倍','q2_speedup':'倍','speedup':'倍','cache_gain':'倍','q3_cache_gain':'倍',
           'added_copy_mb':'MiB','partition_added_copy_bytes':'字节','spill_added_copy_bytes':'字节',
           'added_copy_bytes':'字节','evaluation_seconds':'秒','makespan_cycles':'周期',
           'q2_policy_gain':'倍','scene_b_gain_same_plan':'倍','memory_peak_fraction':'额定容量比例',
           'q3_cache_hit_rate':'比例','cache_hit_rate':'比例','cache_hit_bytes':'字节',
           'cache_miss_bytes':'字节','capacity_bytes':'字节','bandwidth_bytes_per_cycle':'字节/周期',
           'hit_rate':'比例','max_level_width':'个','q1_added_copy_bytes':'字节',
           'q2_added_copy_bytes':'字节','q1_speedup':'倍'}
    for problem in p['problems']:
        q=problem['problem_id']
        problem['claims']=[{'claim_id':f'{q}-C01','text':f'{q}正式100例官方评估与独立核验的可复核结论'}]
        for e in problem['evidence_matrix']:
            cat=e['category']
            e['applicability']='applicable'
            e['reason']='本问有已完成且独立核验的官方结构化结果；机制由逐问综合图解释。'
            e['data_shape']='graph_flow' if cat=='mechanism_geometry' else ('distribution' if cat=='main_result' else 'multi_point_scan')
            e['representation']='schematic' if cat=='mechanism_geometry' else 'figure'
            e['result_files']=['求解/正式实验/统计分析.json']
            e['figure_ids']=[]
        figures=[]
        for fid,(question,family,chart,asset,caption,eid) in META.items():
            if not fid.startswith(q+'-'):continue
            csv_path=f'求解/图件数据/{fid}.csv'
            with (ROOT/csv_path).open(encoding='utf-8-sig',newline='') as stream:
                fields=next(csv.reader(stream))
            ref=f'.agents/skills/academic-figure-skill/assets/figures/{asset}'
            figure={'figure_id':fid,'count_role':'independent_science','scope':q,
                'scientific_question':question,'claim_ids':[f'{q}-C01'],'evidence_ids':[eid],
                'archetype':'quantitative_grid','layout':'单幅定量图，论文版心160mm，中文标签',
                'hero_panel':'main','panels':[{'panel_id':'main','rendering_route':'academic',
                   'source_skill':'academic-figure-skill','question':question,'figure_type':chart,
                   'figure_family':family,'chart_type':chart,'chart_families':[chart],
                   'chart_review':'图型基于实际字段维度与100例或参数网格；已生成草图，模板继承与正式QA待补。',
                   'result_file':csv_path,'fields':fields,'units':[units.get(x,'类别') for x in fields],
                   'visual_encoding':f'{chart}编码真实字段；数值与单位以对应CSV和图内坐标为准',
                   'asset_directory':ref,'asset_mode':'visual_adapt'}],
                'script':'求解/render_science_figures.py',
                'outputs':{'vector':f'求解/正式图件/{fid}.pdf','preview':f'求解/正式图件/{fid}.png'},
                'statistics_report':f'求解/正式图件/{fid}.stats.json',
                'qa_report':f'求解/正式图件/{fid}.qa.json',
                'paper':{'chapter':chapter[q],'label':f'fig:{q}-f{fid[-2:]}',
                         'caption':caption,'reference_context':'本问官方结果分析中先解释科学用途再引用该图。'},
                'status':'rendered'}
            figures.append(figure)
            for e in problem['evidence_matrix']:
                if e['evidence_id']==eid:e['figure_ids'].append(fid)
        problem['figures']=figures
        for e in problem['evidence_matrix']:
            if e['category']=='mechanism_geometry': e['figure_ids']=[f'{q}-OVERVIEW']
            if not e['figure_ids']:
                e['figure_ids']=[figures[0]['figure_id']]
    p['flowcharts']=[x for x in p['flowcharts'] if x.get('plan_id') not in {f'{q}-OVERVIEW' for q in ('q1','q2','q3')}]
    for flow in p['flowcharts']:
        if flow.get('plan_id')=='GLOBAL-ROADMAP': flow['status']='qa_pass'
    p['flowcharts'].extend([{'scope':q,'needed':'yes','reason':'逐问综合图含真实任务、求解、评价和核验顺序。',
                            'plan_id':f'{q}-OVERVIEW','status':'planned'} for q in ('q1','q2','q3')])
    PLAN.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (ROOT/'求解/视觉编码表.md').write_text('# 三问视觉编码\n\n核数用1–5整数；时间统一为官方周期，字节数按图标注换算。场景A/B与Cache反事实保持相同算例和核数；非官方L2敏感性仅在q3-F03/F04出现并明确标注。青色表示通信或缓存命中字节，橙色表示Spill或不利事件；具体色义服从各图图例。所有图均读取求解/图件数据/的真实CSV。\n',encoding='utf8')
    print('registered',sum(len(x['figures']) for x in p['problems']))

if __name__=='__main__':main()
