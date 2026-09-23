"""Inventory checked-out inputs and raw LFS parts; never deserialize pickle files."""
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '题目'
MANIFEST = ROOT / 'data-parts' / 'manifest.json'


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        first = True
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            if first and chunk.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
                raise ValueError(f'LFS pointer found instead of data: {path}. Run git lfs pull.')
            first = False
            h.update(chunk)
    return h.hexdigest()


def git_policies(names):
    # NUL-delimited binary I/O avoids Windows CRLF translation and Git quoting.
    encoded = ('\0'.join(names) + '\0').encode('utf-8')
    ignored = subprocess.run(['git', 'check-ignore', '--no-index', '-z', '--stdin'],
                             input=encoded, cwd=ROOT, capture_output=True)
    if ignored.returncode not in (0, 1):
        raise RuntimeError(ignored.stderr.decode('utf-8', errors='replace'))
    excluded = set(ignored.stdout.decode('utf-8').split('\0'))
    attrs = subprocess.run(['git', 'check-attr', '-z', '--stdin', 'filter'],
                           input=encoded, cwd=ROOT, capture_output=True, check=True)
    values = attrs.stdout.decode('utf-8').split('\0')[:-1]
    if len(values) % 3:
        raise RuntimeError('Unexpected git check-attr output')
    lfs = {values[i] for i in range(0, len(values), 3) if values[i + 2] == 'lfs'}
    return {name: ('local_only' if name in excluded else 'lfs' if name in lfs else 'commit')
            for name in names}


def checked_row(name, policy, expected=None):
    path = ROOT / name
    row = {'path': name, 'bytes': path.stat().st_size, 'sha256': sha256(path),
           'git_policy': policy}
    if expected and (row['bytes'] != expected['bytes'] or row['sha256'] != expected['sha256']):
        raise ValueError(f'File differs from reconstruction manifest: {name}')
    return row


def main():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if manifest['version'] != 1:
        raise ValueError('Unsupported reconstruction manifest version')
    originals = {entry['path']: entry for entry in manifest['files']}
    parts = [part for entry in manifest['files'] for part in entry['parts']]
    files = sorted(p for p in DATA.rglob('*') if p.is_file())
    names = [p.relative_to(ROOT).as_posix() for p in files]
    missing = set(originals) - set(names)
    if missing:
        raise FileNotFoundError('Run python tools/restore_data_parts.py first: ' + ', '.join(sorted(missing)))
    policies = git_policies(names + [part['path'] for part in parts])
    rows = [checked_row(name, 'reconstructed_from_parts' if name in originals else policies[name],
                        originals.get(name)) for name in names]
    part_rows = [checked_row(part['path'], policies[part['path']], part) for part in parts]
    if any(row['git_policy'] != 'lfs' for row in part_rows):
        raise ValueError('Every reconstruction part must be tracked through Git LFS')
    generated_date = date.today().isoformat()
    totals = Counter(row['git_policy'] for row in rows)
    report = {
        'generated_date': generated_date,
        'hash_algorithm': 'SHA-256',
        'scope': '题目目录全部现存文件；未改变原始数据内容；分片单列，不重复计入题目总量',
        'git_policy_definitions': {
            'commit': '普通 Git 文件',
            'lfs': 'Git LFS 文件；哈希和字节数针对下载后的实际内容',
            'reconstructed_from_parts': '由 data-parts/manifest.json 中的未压缩字节分片重建，原件不直接提交',
            'local_only': '由 .gitignore 忽略的系统元数据、锁文件或其他本地文件',
        },
        'files': rows,
        'data_parts': {
            'manifest': MANIFEST.relative_to(ROOT).as_posix(),
            'files': part_rows,
            'bytes': sum(row['bytes'] for row in part_rows),
        },
    }
    (ROOT / '调研' / '数据文件清单.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 数据清单与获取说明', '',
        f'盘点日期：{generated_date}。题面、已解压附件、评估代码、说明及调研资料纳入版本管理。A 题测试图及较大的二进制与语料文件通过 Git LFS 管理，超过 2 GiB 的 E 题特征原件由三个未压缩字节分片重建。系统元数据和 Office 锁文件继续忽略。', '',
        '| 题目 | 文件数 | 合计字节 | 普通 Git | Git LFS | 分片重建 | 元数据/本地忽略 | 主要格式 |',
        '|---|---:|---:|---:|---:|---:|---:|---|',
    ]
    for letter in 'ABCDEF':
        selected = [r for r in rows if r['path'].startswith(f'题目/{letter}题/')]
        formats = Counter(Path(r['path']).suffix for r in selected)
        counts = Counter(r['git_policy'] for r in selected)
        lines.append(
            f"| {letter}题 | {len(selected)} | {sum(r['bytes'] for r in selected):,} | "
            f"{counts['commit']} | {counts['lfs']} | {counts['reconstructed_from_parts']} | {counts['local_only']} | "
            + '、'.join(f'{k or "无扩展名"} × {v}' for k, v in sorted(formats.items())) + ' |')
    total_bytes = sum(row['bytes'] for row in rows)
    lines += [
        '', f'题目目录共 {len(rows):,} 个文件、{total_bytes:,} 字节（约 {total_bytes / 10**9:.3f} GB）。此合计包含本地元数据，不重复计入分片。清单中的 `git_policy` 表示存储策略，不代表某次远端推送已经完成。', '',
        '完整逐文件路径、字节数及 SHA-256 见 [数据文件清单.json](数据文件清单.json)。哈希针对实际原始内容，不是 Git LFS 指针文本。原压缩包校验值和每个解压文件的核验结果见 [数据整理记录.json](数据整理记录.json)。', '',
        '## 超大文件分片', '',
        '分片清单见 [data-parts/manifest.json](../data-parts/manifest.json)。这些分片按原始字节顺序切分，未进行压缩；恢复后的文件与原件逐字节一致。', '',
        '| 原文件 | 分片数 | 原文件字节 |', '|---|---:|---:|',
    ]
    for entry in manifest['files']:
        lines.append(f"| `{entry['path']}` | {len(entry['parts'])} | {entry['bytes']:,} |")
    lines += ['', '| Git LFS 分片 | 字节数 |', '|---|---:|']
    for row in part_rows:
        lines.append(f"| `{row['path']}` | {row['bytes']:,} |")
    lines += [
        '', f"分片另外占用 {sum(row['bytes'] for row in part_rows):,} 字节，Git LFS 本地缓存还会占用磁盘空间。", '',
        '## 文件获取与读取', '',
        '先安装 Git、Git LFS 和 Python，然后执行：', '',
        '```sh', 'git lfs install', 'git -c core.longpaths=true clone https://github.com/yellkiin/model_competition.git',
        'cd model_competition', 'git config --local core.longpaths true',
        'git lfs pull', 'python tools/restore_data_parts.py', '```', '',
        '`core.longpaths` 用于 Windows 下 F 题附件的长路径。已有克隆先设置该选项、执行 `git pull`，再执行 `git lfs pull` 和恢复命令。GitHub 的 ZIP 源码下载不能替代上述完整数据获取流程。若文件内容只有 `version https://git-lfs.github.com/spec/v1` 等几行文字，它是 LFS 指针，需完成 `git lfs pull` 才能读取数据。', '',
        '恢复脚本校验每个分片、拼接内容和已有原件的 SHA-256。原件缺失时恢复到原路径；已有且一致时跳过重建，内容不一致时中止，不覆盖文件。', '',
        '- A 题：测试图及 `config.txt` 位于附件的 `data/`；测试图、固定配置、评估程序 `code/` 和说明 `docs/` 均随仓库提交。',
        '- B 题：附件1/2 Excel 在同名附件目录。已有版本与 ZIP 内文件逐字节校验一致。',
        '- C 题：四组 `VisualCog*.mat` 位于原数据目录；以各文件字段核对采样率、通道和事件。',
        '- D 题：地理空间和应急运输数据位于 `数据/`；坐标系、单位和链路定义必须联合核对。',
        '- E 题：四类附件位于 `E题数据/`；`.pkl` 是 Python 序列化格式，仅在可信隔离环境读取，清单生成和分片恢复过程不会执行其中内容。',
        '- F 题：四个 `.jsonl.xz` 已展开为同路径 `.jsonl`，其余附件不变；原《数据说明》中 `.xz` 路径请改用去除末尾 `.xz` 的路径。逐行读取 JSONL，避免一次载入全部语料。', '',
        '## 校验方式', '',
        '`python tools/restore_data_parts.py --verify-only` 仅校验所有分片、拼接哈希和已有原件，不创建原件；原件尚不存在时，校验通过只表示这些分片可以重建它。', '',
        '运行 `python tools/build_data_inventory.py` 可重新生成现有文件的清单，同时校验分片清单记录的原件与分片。必须先下载 LFS 内容并恢复原件；生成器遇到 LFS 指针会中止。它通过 `git check-attr` 区分 LFS 文件，通过 `git check-ignore` 识别本地忽略文件。', '',
        '核对全部题目文件时，应先保存旧清单，再按路径比对 `sha256` 和 `bytes`，同时检查缺失或新增的路径；重新生成清单本身不等于与原始清单比对通过。`files` 为题目目录原文件，`data_parts.files` 为独立的分片清单，统计时不要将两者相加当作原始数据规模。', '',
        '`python tools/prepare_problem_data.py --delete-archives` 用于新增 ZIP/XZ 的解压核验；工具先校验输出，再删除对应压缩包。已有同名文件若内容不同则中止并保留副本，不覆盖现有数据。', '',
        '清单包含系统元数据文件（如 `.DS_Store`），这些文件被忽略且不参与建模。',
    ]
    (ROOT / '调研' / '数据清单说明.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'files': len(rows), 'bytes': total_bytes, 'git_policies': dict(totals),
                      'data_parts': len(part_rows), 'data_parts_bytes': report['data_parts']['bytes']},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
