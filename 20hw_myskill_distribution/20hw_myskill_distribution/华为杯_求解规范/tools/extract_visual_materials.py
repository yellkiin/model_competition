"""Extract native frames or reconstruct documented arrays without guessing or enhancement."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from build_academic_figure_asset_index import safe, sha, write_json
from inspect_visual_materials import raw_info


def extract(root, source, output, spec):
    import numpy as np
    from PIL import Image
    root = Path(root).resolve()
    src, out = safe(root, str(source)), safe(root, str(output))
    if out.exists() or out == src or out.is_relative_to(root / '数据/原始'):
        raise ValueError('Use a new derived output directory outside original attachments')
    if not isinstance(spec.get('selection_reason'), str) or len(spec['selection_reason']) < 8:
        raise ValueError('Document a scientific frame/page selection rule')
    before = sha(src)
    frames = spec.get('frames', [])
    if not frames or any(not isinstance(i, int) or i < 0 for i in frames) or len(set(frames)) != len(frames):
        raise ValueError('Provide unique nonnegative frame indices')
    out.mkdir(parents=True)
    rows, attempts = [], []
    def save(array, index, timestamp=None):
        if array.dtype not in (np.uint8, np.uint16):
            raise ValueError('Scientific float/signed arrays require explicit display mapping; no automatic rescale')
        if array.ndim not in (2, 3) or (array.ndim == 3 and array.shape[2] not in (3, 4)):
            raise ValueError('Expected HxW or HxWx3/4 image; declare axis transformation first')
        file = out / f'frame_{index:06d}.png'
        Image.fromarray(array).save(file)
        rows.append({'path': file.relative_to(root).as_posix(), 'sha256': sha(file),
                     'frame_number': index, 'timestamp_seconds': timestamp,
                     'native_size': [array.shape[1], array.shape[0]], 'dtype': str(array.dtype)})
    try:
        mode = spec.get('mode')
        if mode == 'video':
            ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
            if not ffmpeg or not ffprobe:
                raise ValueError('ffmpeg and ffprobe are required')
            probe = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_frames',
                '-show_entries', 'frame=best_effort_timestamp_time,width,height', '-of', 'json', str(src)],
                capture_output=True, timeout=spec.get('timeout_seconds', 300))
            if probe.returncode:
                raise ValueError(probe.stderr.decode('utf8', errors='replace'))
            metadata = json.loads(probe.stdout)['frames']
            if max(frames) >= len(metadata):
                raise ValueError('Requested frame is outside decoded sequence')
            for index in frames:
                file = out / f'frame_{index:06d}.png'
                command = [ffmpeg, '-v', 'error', '-i', str(src), '-map', '0:v:0', '-vf',
                           f'select=eq(n\\,{index})', '-frames:v', '1', '-fps_mode', 'passthrough', str(file)]
                proc = subprocess.run(command, capture_output=True, timeout=spec.get('timeout_seconds', 300))
                attempts.append({'command': command, 'returncode': proc.returncode,
                                 'stderr': proc.stderr.decode('utf8', errors='replace')})
                if proc.returncode or not file.is_file():
                    raise ValueError('Frame decode failed')
                with Image.open(file) as im:
                    im.load()
                    expected = [metadata[index]['width'], metadata[index]['height']]
                    if list(im.size) != expected:
                        raise ValueError('Native dimensions changed during extraction')
                rows.append({'path': file.relative_to(root).as_posix(), 'sha256': sha(file), 'frame_number': index,
                             'timestamp_seconds': float(metadata[index]['best_effort_timestamp_time']),
                             'native_size': expected})
        elif mode == 'image':
            with Image.open(src) as im:
                for index in frames:
                    im.seek(index)
                    im.load()
                    save(np.asarray(im.convert('RGB') if im.mode == 'P' else im), index)
        elif mode in {'raw', 'mat'}:
            if mode == 'raw':
                raw_info(src, spec)
                dtype = np.dtype(spec['dtype'])
                if spec['byte_order'] != 'not_applicable':
                    dtype = dtype.newbyteorder('<' if spec['byte_order'] == 'little' else '>')
                array = np.fromfile(src, dtype=dtype, offset=spec.get('offset', 0)).reshape(spec['shape'], order=spec['layout'])
                array = array.astype(array.dtype.newbyteorder('='), copy=False)
            else:
                if not spec.get('variable') or not spec.get('axis_order_evidence'):
                    raise ValueError('MAT requires explicit variable and documented axis interpretation')
                try:
                    from scipy.io import loadmat
                    array = loadmat(src, variable_names=[spec['variable']])[spec['variable']]
                    attempts.append({'reader': 'scipy.loadmat', 'status': 'read'})
                except (ValueError, NotImplementedError) as exc:
                    attempts.append({'reader': 'scipy.loadmat', 'status': 'failed', 'error': str(exc)})
                    import h5py
                    with h5py.File(src, 'r') as ds:
                        array = ds[spec['variable']][:]
                    attempts.append({'reader': 'h5py', 'status': 'read'})
            axes = spec.get('axis_order', list(range(array.ndim)))
            if sorted(axes) != list(range(array.ndim)):
                raise ValueError('Invalid axis permutation')
            array = array.transpose(axes)
            frame_axis = spec.get('frame_axis')
            for i in frames:
                if frame_axis is None and i != 0:
                    raise ValueError('Single image has only frame zero')
                image = array if frame_axis is None else np.take(array, i, axis=frame_axis)
                save(image, i, (spec.get('timestamps_seconds') or {}).get(str(i)))
        else:
            raise ValueError('Explicit mode must be image, video, raw or mat')
        if sha(src) != before:
            raise ValueError('Original source changed')
        result = {'status': 'EXTRACTED_REVIEW_REQUIRED', 'source': src.relative_to(root).as_posix(),
                  'source_sha256': before, 'spec': spec, 'frames': rows, 'attempts': attempts}
    except Exception as exc:
        result = {'status': 'FAIL', 'source': str(source), 'source_sha256': before,
                  'spec': spec, 'frames': rows, 'attempts': attempts, 'error': f'{type(exc).__name__}: {exc}'}
    write_json(out / 'extraction.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=Path('.'))
    p.add_argument('--source', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--spec', required=True)
    a = p.parse_args()
    spec = json.loads(safe(a.project_root.resolve(), a.spec).read_text(encoding='utf8'))
    result = extract(a.project_root, a.source, a.output, spec)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1 if result['status'] == 'FAIL' else 0)


if __name__ == '__main__':
    main()
