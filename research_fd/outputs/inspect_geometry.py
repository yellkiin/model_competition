import json
import os
from pathlib import Path
import sys
import rasterio
import numpy as np
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from research_fd.d_data import workbook

path = next((ROOT/'题目/D题').rglob('*.tif'))
rows = workbook(ROOT/'题目/D题/数据/无人机应急物资运输基础数据/调度中心与服务区.xlsx')['数据']['rows']
node_rows = [(3, rows[2]), *[(i+1, rows[i]) for i in range(6, 21)]]
with rasterio.open(path) as ds:
    raster = ds.read(1, masked=True)
    trans = Transformer.from_crs('EPSG:4326', ds.crs, always_xy=True)
    nodes = []
    for rownum, row in node_rows:
        x, y = trans.transform(row[2], row[3])
        rr, cc = ds.index(x, y)
        terrain_z = float(raster[rr, cc])
        nodes.append({'id': row[0], 'sheet_row': rownum, 'lon': row[2], 'lat': row[3], 'official_z_m': row[4], 'dem_z_m': terrain_z, 'difference_m': row[4]-terrain_z})
    info = {'path': path.relative_to(ROOT).as_posix(), 'crs': str(ds.crs), 'shape': list(raster.shape), 'resolution_native': list(ds.res), 'bounds_native': list(ds.bounds), 'nodata': ds.nodata, 'nodata_count': int(np.ma.getmaskarray(raster).sum()), 'valid_height_min_m': float(raster.min()), 'valid_height_max_m': float(raster.max()), 'nodes': nodes, 'decision': 'Retain official XLSX node elevations; use the official raster for between-node terrain. Record and investigate elevation differences rather than overwriting source values.'}
(OUT/'geometry_audit.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(info, ensure_ascii=False, indent=2))
