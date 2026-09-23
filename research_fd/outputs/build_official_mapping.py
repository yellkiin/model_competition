"""Build explicit official sheet/row/column mappings after parameter review."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
params = json.loads((OUT/'official_parameters.json').read_text(encoding='utf-8'))
folder = '题目/D题/数据/无人机应急物资运输基础数据/'

def nodes(header, first, last, identifier, height):
    return {'file': folder+'调度中心与服务区.xlsx', 'sheet': '数据', 'header_row': header,
            'row_start': first, 'row_end': last, 'skip_if_empty': identifier,
            'fields': {'id': {'column': identifier, 'type': 'str'}, 'lon': '经度（°）',
                       'lat': '纬度（°）', 'z': '海拔（m）', 'work_height': {'const': height}}}

template = {'schema_version': 1,
    'metadata': {'source': 'Official D DOCX/XLSX and DEM with explicit source mappings',
                 'source_commit': '4012819',
                 'parameter_sources': 'official_parameter_sources.md',
                 'physical_runtime': 'runtime/research_fd',
                 'node_elevation_rule': 'Retain official node-table elevation; DEM gives intervening terrain',
                 'numerical_controls': {'arc_step_m': 15, 'ray_step_m': 15, 'relay_heights_m': [100, 200, 300]},
                 'transport_aircraft_ids': params['transport_aircraft_ids'],
                 'relay_aircraft_ids': params['relay_aircraft_ids'],
                 'modeling_conventions': params['modeling_conventions'],
                 'energy_convention': 'Horizontal energy=usable_kwh*distance/range(load); climb=m*g*h/eta. Explicit model interpretation of DOCX energy terms, not additional official measurements.'},
    'depot': 'O01', 'clearance_m': params['clearance_m'], 'arc_step_m': 15,
    'terrain': {'kind': 'raster', 'path': next((ROOT/'题目/D题').rglob('*.tif')).relative_to(ROOT).as_posix()},
    'fleet': params['fleet'], 'radio': params['radio'], 'relay': params['relay']}
template['radio']['ray_step_m'] = 15
# Heights are an explicitly finite numerical candidate set, not official fixed positions.
template['relay']['heights_m'] = [100, 200, 300]
mapping = {'coordinates': {'input': 'lonlat', 'source_crs': 'EPSG:4326'}, 'template': template,
    'tables': {
        'nodes': {'blocks': [nodes(2, 3, 3, '调度中心编号', 0), nodes(6, 7, 21, '服务区编号', 30)]},
        'boxes': {'file': folder+'物资需求与配送时限.xlsx', 'sheet': '逐箱货箱清单', 'header_row': 1,
                  'row_start': 2, 'row_end': 81, 'skip_if_empty': '货箱编号',
                  'fields': {'id': {'column': '货箱编号', 'type': 'str'}, 'node': '服务区编号',
                             'mass': '单箱质量（kg）', 'volume': '单箱体积（m³）',
                             'due': {'column': '期望送达时间（s）', 'scale': 1},
                             'hard_due': {'min': [
                                 {'when': {'column': '物资类型', 'in': ['医疗物资']}, 'then': {'column': '期望送达时间（s）'}},
                                 {'when': {'column': '是否首批保障', 'in': ['是']}, 'then': {'column': '首批截止时间（s）'}}]},
                             'weight': '应急优先系数', 'release': {'const': 0}}}},
    'mapping_notes': [
        'Node sheet contains two headers; read only specified inclusive row blocks.',
        'All deadline fields are already seconds. No minute conversion.',
        'Medical due and first-batch deadline are both hard; choose the earlier nonempty deadline.',
        'Work heights 0/30m and clearance 50m follow DOCX P0046.',
        'Release at time zero is the static initial-stock scenario convention; no release column exists.',
        'Model-specific fleet/radio/relay values are documented in official_parameter_sources.md.'
    ]}
(OUT/'official_mapping.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote explicit official mapping')
