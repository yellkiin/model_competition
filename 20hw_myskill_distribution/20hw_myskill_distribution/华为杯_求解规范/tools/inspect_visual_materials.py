"""Inventory attachments with actual readers; failures and ambiguous formats stay visible."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from build_academic_figure_asset_index import safe, sha, write_json

EXTENSIONS = {
    'image': '.jpg .jpeg .png .bmp .gif .webp .tif .tiff',
    'video': '.avi .mp4 .mov .mkv .wmv .flv',
    'vector': '.shp .shx .dbf .prj .cpg .geojson .kml .kmz .gml .gpx',
    'raster': '.img .dem .grd .asc .hgt',
    'multidimensional': '.nc .h5 .hdf .hdf5 .he5 .grib .grb .grib2 .mat',
    'point_cloud': '.las .laz .ply .pcd .xyz .obj .stl',
    'audio': '.wav .mp3 .flac .ogg .m4a',
    'text': '.txt .doc .docx .pdf .json .xml',
    'raw': '.raw .dat .bin',
}


def image_info(path):
    from PIL import Image
    with Image.open(path) as im:
        frames = []
        for i in range(getattr(im, 'n_frames', 1)):
            im.seek(i)
            im.load()
            frames.append({'index': i, 'size': list(im.size), 'mode': im.mode,
                           'duration_ms': im.info.get('duration')})
        return {'format': im.format, 'frames': frames, 'frame_count': len(frames), 'all_frames_decoded': True}


def raster_info(path, spec=None):
    import rasterio

    def metadata(ds):
        crs = ds.crs
        if crs is None and spec and spec.get('crs') and spec.get('crs_evidence'):
            from rasterio.crs import CRS
            crs = CRS.from_user_input(spec['crs'])
        if crs is None:
            raise ValueError('Raster has no confirmed CRS; recover from trusted metadata')
        return {'driver': ds.driver, 'size': [ds.width, ds.height], 'bands': ds.count,
                'dtypes': list(ds.dtypes), 'crs': crs.to_wkt(), 'transform': list(ds.transform),
                'nodata': str(ds.nodata), 'units': list(ds.units), 'bounds': list(ds.bounds),
                'inspection_scope': 'Header and spatial metadata; numerical validity requires data audit'}

    with rasterio.open(path) as ds:
        result = metadata(ds)
        names = list(ds.subdatasets)
    # GDAL exposes separate TIFF pages and container arrays as subdatasets.
    # A readable first page must not hide missing CRS or unreadable later pages.
    result['subdatasets'] = []
    for name in names:
        with rasterio.open(name) as ds:
            result['subdatasets'].append({'name': name, **metadata(ds)})
    if signature_hint(path) == 'tiff':
        try:
            result['image_pages'] = image_info(path)
        except Exception as exc:
            result['image_page_decode'] = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}',
                'scope': 'GDAL metadata above remains available; decode selected bands before rendering'}
    return result


def av_info(path):
    exe = shutil.which('ffprobe')
    if not exe:
        raise ValueError('ffprobe unavailable')
    result = subprocess.run([exe, '-v', 'error', '-show_format', '-show_streams',
                             '-of', 'json', str(path)], capture_output=True, timeout=90)
    if result.returncode:
        raise ValueError(result.stderr.decode('utf8', errors='replace'))
    data = json.loads(result.stdout)
    if not data.get('streams'):
        raise ValueError('No readable streams')
    data['inspection_scope'] = 'Container/stream metadata only; selected frames must be decoded by extraction'
    return data


def sound_info(path):
    import soundfile
    info = soundfile.info(path)
    return {'sample_rate': info.samplerate, 'channels': info.channels, 'frames': info.frames,
            'duration_seconds': info.duration, 'format': info.format, 'subtype': info.subtype}


def vector_info(path, spec=None):
    import fiona
    layers = []
    for layer in fiona.listlayers(path):
        with fiona.open(path, layer=layer) as ds:
            crs = ds.crs_wkt
            if not crs and spec and spec.get('crs') and spec.get('crs_evidence'):
                from pyproj import CRS
                crs = CRS.from_user_input(spec['crs']).to_wkt()
            if not crs:
                raise ValueError('Unconfirmed CRS; provide crs and crs_evidence in format spec')
            layers.append({'name': layer, 'crs': crs, 'bounds': list(ds.bounds),
                           'features': len(ds), 'schema': dict(ds.schema), 'driver': ds.driver})
    if not layers:
        raise ValueError('No vector layers')
    return {'layers': layers, 'inspection_scope': 'Layers, feature counts and schema; geometry review remains required'}


def xml_info(path):
    root = ET.parse(path).getroot()
    tags = {}
    for element in root.iter():
        tag = element.tag.rsplit('}', 1)[-1]
        tags[tag] = tags.get(tag, 0) + 1
    return {'root': root.tag, 'element_counts': tags, 'semantic_state': 'requires_metadata_review'}


def kmz_info(path):
    documents = []
    with zipfile.ZipFile(path) as archive:
        entries = [{'name': n.filename, 'bytes': n.file_size} for n in archive.infolist()]
        for item in archive.infolist():
            if not item.filename.lower().endswith('.kml'):
                continue
            if item.file_size > 64 * 1024 * 1024:
                raise ValueError('KML member exceeds 64 MiB inspection limit; use a dedicated streaming reader')
            root = ET.fromstring(archive.read(item))
            tags, points, links = {}, [], []
            for element in root.iter():
                tag = element.tag.rsplit('}', 1)[-1]
                tags[tag] = tags.get(tag, 0) + 1
                if tag == 'coordinates' and element.text:
                    for token in element.text.split():
                        values = [float(v) for v in token.split(',')]
                        if len(values) not in (2, 3) or not all(math.isfinite(v) for v in values):
                            raise ValueError(f'Invalid coordinate tuple in {item.filename}')
                        points.append(values)
                if tag == 'href' and element.text:
                    links.append(element.text.strip())
            documents.append({'member': item.filename, 'root': root.tag, 'element_counts': tags,
                'coordinate_tuples': len(points),
                'xy_bounds': [[min(v[i] for v in points) for i in (0, 1)],
                              [max(v[i] for v in points) for i in (0, 1)]] if points else None,
                'linked_resources': links})
    if not documents:
        raise ValueError('KMZ contains no readable KML documents')
    return {'archive_entries': entries, 'documents': documents,
            'semantic_state': 'All KML XML and coordinate tuples inspected; confirm CRS, geometry and linked resources before mapping'}


def hdf_info(path):
    import h5py
    variables = []
    with h5py.File(path, 'r') as ds:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                variables.append({'name': name, 'shape': list(obj.shape), 'dtype': str(obj.dtype),
                                  'attributes': {k: str(v) for k, v in obj.attrs.items()}})
        ds.visititems(visit)
    if not variables:
        raise ValueError('No datasets')
    return {'variables': variables, 'inspection_scope': 'All dataset metadata; slices not yet selected'}


def hdf4_info(path):
    from pyhdf.SD import SD, SDC
    ds = SD(str(path), SDC.READ)
    try:
        variables = []
        for name in ds.datasets():
            item = ds.select(name)
            try:
                _, rank, shape, dtype, _ = item.info()
                variables.append({'name': name, 'rank': rank, 'shape': list(shape), 'dtype': str(dtype),
                                  'dimensions': item.dimensions(),
                                  'attributes': {k: str(v) for k, v in item.attributes().items()}})
            finally:
                item.endaccess()
        if not variables:
            raise ValueError('No HDF4 scientific datasets')
        return {'variables': variables, 'format': 'HDF4'}
    finally:
        ds.end()


def netcdf_info(path):
    from netCDF4 import Dataset
    variables, dimensions = [], []
    def visit(group, prefix):
        for k, v in group.dimensions.items():
            dimensions.append({'name': prefix + k, 'length': len(v), 'unlimited': v.isunlimited()})
        for k, v in group.variables.items():
            variables.append({'name': prefix + k, 'dimensions': list(v.dimensions), 'shape': list(v.shape),
                              'dtype': str(v.dtype), 'attributes': {a: str(v.getncattr(a)) for a in v.ncattrs()}})
        for k, g in group.groups.items():
            visit(g, prefix + k + '/')
    with Dataset(path) as ds:
        visit(ds, '/')
    return {'variables': variables, 'dimensions': dimensions}


def xarray_info(path):
    import xarray as xr
    with xr.open_dataset(path, decode_times=False) as ds:
        return {'dimensions': dict(ds.sizes), 'coordinates': list(ds.coords),
                'variables': [{'name': k, 'dimensions': list(v.dims), 'shape': list(v.shape),
                               'dtype': str(v.dtype), 'attributes': {a: str(b) for a, b in v.attrs.items()}}
                              for k, v in ds.variables.items()]}


def grib_info(path):
    import cfgrib
    datasets = cfgrib.open_datasets(str(path), backend_kwargs={'indexpath': ''})
    try:
        return {'groups': [{'dimensions': dict(ds.sizes), 'coordinates': list(ds.coords),
                            'variables': [{'name': k, 'dimensions': list(v.dims), 'shape': list(v.shape),
                                           'attributes': {a: str(b) for a, b in v.attrs.items()}}
                                          for k, v in ds.variables.items()]} for ds in datasets]}
    finally:
        for ds in datasets:
            ds.close()


def mat_info(path):
    from scipy.io import whosmat
    return {'variables': [{'name': n, 'shape': list(s), 'dtype': t} for n, s, t in whosmat(path)],
            'semantic_state': 'MAT containers require explicit variable/channel/frame interpretation'}


def cloud_info(path):
    if path.suffix.lower() in {'.las', '.laz'}:
        import laspy
        with laspy.open(path) as ds:
            crs = ds.header.parse_crs()
            return {'points': ds.header.point_count, 'scales': list(ds.header.scales),
                    'offsets': list(ds.header.offsets), 'crs': crs.to_wkt() if crs else None,
                    'attributes': list(ds.header.point_format.dimension_names)}
    import trimesh
    mesh = trimesh.load(path, process=False)
    if isinstance(mesh, trimesh.Scene):
        return {'objects': [{'name': n, 'vertices': len(g.vertices), 'bounds': g.bounds.tolist()}
                            for n, g in mesh.geometry.items()]}
    return {'vertices': len(mesh.vertices), 'bounds': mesh.bounds.tolist()}


def open3d_info(path):
    import open3d as o3d
    cloud = o3d.io.read_point_cloud(str(path))
    if not cloud.has_points():
        raise ValueError('No points decoded')
    return {'points': len(cloud.points), 'colors': cloud.has_colors(), 'normals': cloud.has_normals()}


def xyz_info(path, spec):
    import numpy as np
    if not spec or not all(spec.get(k) for k in ('columns', 'units', 'evidence')):
        raise ValueError('XYZ requires documented column names, units and evidence')
    columns = spec['columns']
    if not {'x', 'y', 'z'} <= set(columns) or len(columns) != len(set(columns)):
        raise ValueError('XYZ columns must uniquely identify x, y, z')
    values = np.loadtxt(path, delimiter=spec.get('delimiter'), skiprows=spec.get('skiprows', 0), ndmin=2)
    if values.shape[1] != len(columns) or not values.shape[0] or not np.isfinite(values).all():
        raise ValueError('XYZ shape or finite-coordinate validation failed')
    xyz = values[:, [columns.index(k) for k in ('x', 'y', 'z')]]
    return {'points': len(values), 'columns': columns, 'units': spec['units'],
            'bounds': [xyz.min(axis=0).tolist(), xyz.max(axis=0).tolist()],
            'inspection_scope': 'All rows parsed against the supplied column specification'}


def legacy_word_info(path):
    import win32com.client
    word, document = None, None
    try:
        word = win32com.client.DispatchEx('Word.Application')
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = 3
        document = word.Documents.Open(str(path.resolve()), ReadOnly=True, AddToRecentFiles=False,
                                       ConfirmConversions=False, Visible=False)
        return {'paragraphs': document.Paragraphs.Count, 'tables': document.Tables.Count,
                'inline_shapes': document.InlineShapes.Count, 'characters': document.Characters.Count,
                'inspection_scope': 'Read-only legacy Word document inventory; semantic extraction remains task-specific'}
    finally:
        if document is not None:
            document.Close(False)
        if word is not None:
            word.Quit()


def antiword_info(path):
    exe = shutil.which('antiword')
    if not exe:
        raise ValueError('antiword unavailable; a documented Word/LibreOffice conversion copy is another option')
    result = subprocess.run([exe, str(path)], capture_output=True, timeout=90)
    if result.returncode:
        raise ValueError(result.stderr.decode('utf8', errors='replace'))
    return {'text_bytes': len(result.stdout), 'inspection_scope': 'Legacy DOC text extraction; embedded images require separate inspection'}


def document_info(path, format_hint=None):
    ext = format_hint or path.suffix.lower()
    if ext == '.pdf':
        import pymupdf
        with pymupdf.open(path) as doc:
            return {'pages': [{'number': i + 1, 'size': list(p.rect), 'images': len(p.get_images()),
                               'text_characters': len(p.get_text())} for i, p in enumerate(doc)]}
    if ext == '.docx':
        from docx import Document
        d = Document(path)
        return {'paragraphs': len(d.paragraphs), 'tables': len(d.tables), 'inline_shapes': len(d.inline_shapes)}
    if ext == '.doc':
        raise ValueError('Legacy DOC needs a Word/LibreOffice conversion copy; original must remain unchanged')
    if ext == '.xml':
        return xml_info(path)
    text = path.read_text(encoding='utf-8-sig')
    if ext in {'.json', '.geojson'}:
        obj = json.loads(text)
        return {'container': type(obj).__name__, 'keys': list(obj) if isinstance(obj, dict) else [],
                'items': len(obj) if isinstance(obj, (list, dict)) else 1}
    return {'encoding': 'utf-8-sig', 'characters': len(text), 'lines': len(text.splitlines())}


def raw_info(path, spec):
    import numpy as np
    if not spec or not all(k in spec for k in ('shape', 'dtype', 'byte_order', 'layout', 'channel_order', 'evidence')):
        raise ValueError('Raw input needs documented shape/dtype/byte_order/layout/channel_order/evidence')
    if spec['byte_order'] not in {'little', 'big', 'not_applicable'} or spec['layout'] not in {'C', 'F'}:
        raise ValueError('Invalid raw byte order/layout')
    dtype = np.dtype(spec['dtype'])
    if dtype.hasobject or not spec['shape'] or any(type(n) is not int or n <= 0 for n in spec['shape']):
        raise ValueError('Invalid shape or unsafe object dtype')
    if type(spec.get('offset', 0)) is not int or spec.get('offset', 0) < 0:
        raise ValueError('Raw offset must be a nonnegative integer')
    if dtype.itemsize > 1 and spec['byte_order'] == 'not_applicable':
        raise ValueError('Multibyte raw values require documented endianness')
    expected = math.prod(spec['shape']) * dtype.itemsize + spec.get('offset', 0)
    if path.stat().st_size != expected:
        raise ValueError(f'Raw byte size mismatch: {path.stat().st_size} != {expected}')
    return {'format_spec': spec, 'bytes_verified': expected, 'reconstruction_state': 'ready_for_explicit_reconstruction'}


def signature_hint(path):
    """Recognize strong container signatures without interpreting unknown raw bytes."""
    with path.open('rb') as stream:
        head = stream.read(512)
    if head.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'BM')):
        return 'image'
    if head.startswith((b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+')):
        return 'tiff'
    if head[:4] == b'RIFF':
        return {b'WEBP': 'image', b'WAVE': 'audio', b'AVI ': 'video'}.get(head[8:12])
    if head.startswith(b'%PDF-'):
        return 'pdf'
    if head.startswith(b'\x89HDF\r\n\x1a\n'):
        return 'hdf5'
    if head.startswith((b'CDF\x01', b'CDF\x02', b'CDF\x05')):
        return 'netcdf'
    if head.startswith(b'GRIB'):
        return 'grib'
    if head[4:8] == b'ftyp' or head.startswith((b'\x1aE\xdf\xa3', b'FLV')):
        return 'video'
    return None


def inspect_file(root, path, specs=None):
    path = Path(path)
    raw = path.relative_to(root).as_posix()
    ext = path.suffix.lower()
    category = next((k for k, v in EXTENSIONS.items() if ext in v.split()), 'unknown')
    spec = (specs or {}).get(raw)
    signature = signature_hint(path)
    row = {'path': raw, 'sha256': sha(path), 'bytes': path.stat().st_size,
           'extension_hint': category, 'read_status': 'blocked', 'metadata': {}, 'attempts': [],
           'reviewed': False, 'observation': '', 'suggested_route': None,
           'content_signature': signature}
    readers = []
    if category == 'image':
        readers = [('Pillow', lambda: image_info(path))]
        if ext in {'.tif', '.tiff'}:
            readers.insert(0, ('rasterio', lambda: raster_info(path, spec)))
    elif category == 'video':
        readers = [('ffprobe', lambda: av_info(path))]
    elif category == 'audio':
        readers = [('soundfile', lambda: sound_info(path)), ('ffprobe', lambda: av_info(path))]
    elif category == 'raster':
        readers = [('rasterio', lambda: raster_info(path, spec))]
    elif category == 'vector':
        if ext == '.shp':
            missing = [e for e in ('.shx', '.dbf') if not path.with_suffix(e).is_file()]
            if missing:
                row['attempts'].append({'reader': 'Shapefile components', 'status': 'failed', 'error': 'Missing ' + ', '.join(missing)})
                return row
            row['related_files'] = {path.with_suffix(e).relative_to(root).as_posix(): sha(path.with_suffix(e))
                                    for e in ('.shx', '.dbf', '.prj', '.cpg') if path.with_suffix(e).is_file()}
        if ext in {'.shx', '.dbf', '.prj', '.cpg'}:
            row['read_status'] = 'companion' if path.with_suffix('.shp').is_file() else 'blocked'
            row['metadata'] = {'shapefile': path.with_suffix('.shp').relative_to(root).as_posix(),
                               'present': path.with_suffix('.shp').is_file()}
            return row
        readers = [('fiona', lambda: vector_info(path, spec))]
        if ext in {'.kml', '.gml', '.gpx'}:
            readers.append(('XML structure (CRS still unconfirmed)', lambda: xml_info(path)))
        if ext == '.kmz':
            # Explicitly parse every member, even if a GIS driver opens only doc.kml.
            readers.insert(0, ('KMZ KML documents', lambda: kmz_info(path)))
    elif category == 'multidimensional':
        if ext == '.mat':
            readers = [('scipy.whosmat', lambda: mat_info(path)), ('h5py', lambda: hdf_info(path))]
        elif ext in {'.grib', '.grb', '.grib2'}:
            readers = [('cfgrib', lambda: grib_info(path))]
        else:
            readers = [('netCDF4', lambda: netcdf_info(path)), ('h5py', lambda: hdf_info(path)),
                       ('pyhdf HDF4', lambda: hdf4_info(path)),
                       ('xarray', lambda: xarray_info(path))]
    elif category == 'point_cloud':
        readers = [('laspy/trimesh', lambda: cloud_info(path)), ('open3d', lambda: open3d_info(path))]
        if ext == '.xyz':
            readers = [('documented XYZ columns', lambda: xyz_info(path, spec))]
    elif category == 'text':
        readers = [('document parser', lambda: document_info(path))]
        if ext == '.doc':
            readers = [('Word COM read-only', lambda: legacy_word_info(path)), ('antiword', lambda: antiword_info(path))]
    elif category == 'raw':
        readers = [('documented raw layout', lambda: raw_info(path, spec))]
    signature_readers = {
        'image': [('Pillow signature', lambda: image_info(path))],
        'tiff': [('rasterio signature', lambda: raster_info(path, spec)), ('Pillow signature', lambda: image_info(path))],
        'video': [('ffprobe signature', lambda: av_info(path))],
        'audio': [('soundfile signature', lambda: sound_info(path)), ('ffprobe signature', lambda: av_info(path))],
        'hdf5': [('h5py signature', lambda: hdf_info(path))],
        'netcdf': [('netCDF4 signature', lambda: netcdf_info(path))],
        'grib': [('cfgrib signature', lambda: grib_info(path))],
        'pdf': [('PDF signature', lambda: document_info(path, '.pdf'))],
    }
    if signature and not (category == 'raw' and spec):
        # NetCDF4 and MAT v7.3 are HDF5 containers with additional semantics.
        # Preserve their dedicated reader order before generic HDF inspection.
        if signature == 'hdf5' and ext in {'.nc', '.mat'}:
            readers += signature_readers[signature]
        else:
            readers = signature_readers.get(signature, []) + readers
    if ext in {'.json', '.txt'}:
        try:
            obj = json.loads(path.read_text(encoding='utf-8-sig'))
            if isinstance(obj, dict) and obj.get('type') in {'FeatureCollection', 'Feature'}:
                readers.insert(0, ('GeoJSON content', lambda: vector_info(path, spec)))
        except (ValueError, UnicodeError):
            pass
    if not readers:
        row['attempts'].append({'reader': 'classification', 'status': 'failed', 'error': 'Unknown format; explicit reader and metadata required'})
    for name, reader in readers:
        try:
            metadata = reader()
            row['attempts'].append({'reader': name, 'status': 'read', 'error': ''})
            row.update(read_status='readable', metadata=metadata)
            if 'semantic_state' in metadata or ext in {'.kmz', '.mat'}:
                row['read_status'] = 'needs_interpretation'
            break
        except Exception as exc:
            row['attempts'].append({'reader': name, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
    if spec:
        row['format_spec'] = spec
        if row['read_status'] == 'needs_interpretation' and spec.get('interpretation') and spec.get('evidence'):
            row['read_status'] = 'readable'
            row['metadata']['interpretation'] = spec['interpretation']
            row['metadata']['interpretation_evidence'] = spec['evidence']
    if ext == '.xyz' and row['read_status'] == 'readable' and not (
            spec and spec.get('columns') and spec.get('units') and spec.get('evidence')):
        row['read_status'] = 'needs_interpretation'
        row['metadata']['semantic_state'] = 'XYZ column meanings and units require a documented specification'
    return row


def scan(root, inputs, specs=None):
    root = Path(root).resolve()
    files = set()
    for raw in inputs:
        p = safe(root, str(raw))
        if not p.exists():
            raise ValueError('Missing attachment path: ' + str(p))
        files.update(x for x in p.rglob('*') if x.is_file()) if p.is_dir() else files.add(p)
    rows = [inspect_file(root, p, specs) for p in sorted(files)]
    sequences = {}
    import re
    for row in rows:
        p = Path(row['path'])
        if row['extension_hint'] == 'image' and re.search(r'\d+$', p.stem):
            sequences.setdefault(p.parent.as_posix(), []).append(row['path'])
    return {'schema_version': '1.0', 'created_at': datetime.now(timezone.utc).isoformat(),
            'roots': [str(s) for s in inputs], 'files': rows, 'numbered_sequence_candidates': sequences,
            'status': 'REQUIRES_REVIEW', 'assurance': 'Reader metadata is not scientific or visual approval.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--input', action='append')
    p.add_argument('--format-spec', type=Path)
    p.add_argument('--output', type=Path, default=Path('求解/视觉素材索引.json'))
    a = p.parse_args()
    root = a.project_root.resolve()
    specs = json.loads(safe(root, str(a.format_spec)).read_text(encoding='utf8')) if a.format_spec else None
    out = safe(root, str(a.output))
    if out.exists():
        raise SystemExit('Keep historical inventory; choose a new --output')
    result = scan(root, a.input or ['数据'], specs)
    write_json(out, result)
    print(json.dumps({'status': result['status'], 'files': len(result['files']),
                      'blocked': [r['path'] for r in result['files'] if r['read_status'] == 'blocked']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
