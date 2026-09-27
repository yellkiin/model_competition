"""Compact native stage 01 component gaps before uniform artwork enlargement."""
import copy
import re
import xml.etree.ElementTree as ET

SVG='http://www.w3.org/2000/svg'


def space_joint(root, find, shift):
    graph=find(root,'bipartite-example')
    nodes=list(graph)
    if graph.get('data-v13-spaced')=='true': return
    # Widen the vertical separation between the two intact subgraph clusters.
    # Middle nodes remain centred between them. Every primitive keeps its shape.
    shifts={
        2:100, 3:50, 4:50, 6:50, 7:50, 9:0, 12:100, 13:100,
        15:100, 18:50, 19:50, 20:50, 22:100, 24:100, 25:50,
        26:50, 27:50, 28:50, 29:50, 34:100, 35:100, 36:100,
        37:100, 42:100, 43:100, 44:100, 45:100, 46:50, 47:50,
        48:50, 49:50, 50:50, 52:100, 53:50,
    }
    for index,dy in shifts.items():
        if dy: shift(nodes[index],0,dy)
    # The V11 pen-stroke object contains both clusters; separate its original
    # subpaths so the lower strokes can move intact with the lower cluster.
    hatch=nodes[5]
    upper=[]; lower=[]
    for subpath in re.findall(r'M[^M]*',hatch.get('d')):
        match=re.match(r'M\s*[-.\d]+\s*,\s*([-.\d]+)',subpath)
        if not match: raise ValueError('Unexpected V11 cluster hatch subpath')
        (lower if float(match.group(1))>250 else upper).append(subpath)
    hatch.set('d',' '.join(upper)); hatch.set('id','joint-upper-hatching-v13')
    lower_hatch=copy.deepcopy(hatch); lower_hatch.set('id','joint-lower-hatching-v13')
    lower_hatch.set('d',' '.join(lower)); shift(lower_hatch,0,100)
    graph.insert(list(graph).index(hatch)+1,lower_hatch)
    for index,d in {
        8:'M215,274C253,269 252,150 263,128',
        9:'M215,307C253,312 252,429 263,450',
        16:'M654,117C685,124 700,230 717,255',
        17:'M654,462C685,455 700,350 717,325',
    }.items(): nodes[index].set('d',d)
    # Enlarge B and C as complete engraved subgraphs into the surrounding
    # whitespace. Their circles, hatching, tensor, internal arrows and text
    # share one uniform transform; external edges are reconnected below.
    upper_indices=(1,5,10,11,21,30,31,32,33,38,39,40,41,51)
    lower_indices=(2,12,13,22,34,35,36,37,42,43,44,45,52)
    for index in upper_indices:
        nodes[index].set('transform','translate(410,99) scale(1.18) translate(-410,-107) '+nodes[index].get('transform',''))
    for node in [nodes[i] for i in lower_indices]+[lower_hatch]:
        node.set('transform','translate(410,497) scale(1.18) translate(-410,-472) '+node.get('transform',''))
    shift(nodes[23],50,-8)
    shift(nodes[24],50,25)
    for index,d in {
        8:'M215,274C239,250 226,160 236.54,123.78',
        9:'M215,307C239,330 226,435 236.54,471.04',
        14:'M601.16,99H662',
        15:'M601.16,397H662',
        16:'M704,109C730,150 715,230 717,255',
        17:'M704,487C730,446 715,350 717,325',
    }.items(): nodes[index].set('d',d)
    graph.set('data-v13-spaced','true')
    graph.set('data-v13-cluster-gap-increase','100')
    graph.set('data-v13-cluster-uniform-scale','1.18')
    # Spread the major stages and the two intact core assignment rows as well.
    shift(graph,50,0)
    shift(find(root,'partition-expression'),50,-48)
    shift(find(root,'partition-map-explanation'),0,160)
    shift(find(root,'best-layout-title'),0,210)
    cores=find(root,'core-assignment-v6'); core_nodes=list(cores)
    for index in (14,15,16,17,18,19,21): shift(core_nodes[index],0,54)
    shift(cores,0,210)
    cores.set('transform','translate(531,1488) scale(1.06) translate(-516,-1488) '+cores.get('transform',''))
    for n in find(root,'joint-body-v13'):
        if n.get('data-label')=='核心映射 a  ·  核内顺序 π': shift(n,-20,264)
    find(root,'graph-to-partition').set('d','M516,1035V1084')
    find(root,'partition-to-cores').set('d','M516,1206V1290')
