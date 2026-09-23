"""Build a reproducible local input inventory; never deserialize pickle files."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '题目'

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    files = sorted(p for p in DATA.rglob('*') if p.is_file())
    names = [p.relative_to(ROOT).as_posix() for p in files]
    # NUL-delimited binary I/O avoids Windows CRLF translation and Git quoting.
    ignored = subprocess.run(['git', 'check-ignore', '-z', '--stdin'],
                             input=('\0'.join(names)+'\0').encode('utf-8'), cwd=ROOT, capture_output=True)
    if ignored.returncode not in (0, 1):
        raise RuntimeError(ignored.stderr)
    excluded = set(ignored.stdout.decode('utf-8').split('\0'))
    rows = []
    for p, name in zip(files, names):
        rows.append({'path':name, 'bytes':p.stat().st_size, 'sha256':sha256(p),
                     'git_policy':'local_only' if name in excluded else 'commit'})
    report = {'generated_date':'2026-09-23', 'hash_algorithm':'SHA-256',
              'scope':'题目目录全部现存文件；未改变原始数据内容', 'files':rows}
    (ROOT/'调研'/'数据文件清单.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = ['# 本地数据清单', '', '盘点日期：2026-09-23。原始数据保留本地；按用户选择，不推送原始数据到 GitHub。题面、A 题评估代码及说明、调研报告、校验清单纳入版本管理。', '',
             '| 题目 | 文件数 | 合计字节 | 本地数据文件数 | 主要格式 |', '|---|---:|---:|---:|---|']
    for letter in 'ABCDEF':
        selected = [r for r in rows if r['path'].startswith(f'题目/{letter}题/')]
        formats = Counter(Path(r['path']).suffix for r in selected)
        lines.append(f"| {letter}题 | {len(selected)} | {sum(r['bytes'] for r in selected):,} | {sum(r['git_policy']=='local_only' for r in selected)} | "+'、'.join(f'{k or "无扩展名"} × {v}' for k,v in sorted(formats.items()))+' |')
    lines += ['', '完整逐文件路径、字节数及 SHA-256 见 [数据文件清单.json](数据文件清单.json)。原压缩包校验值和每个解压文件的核验结果见 [数据整理记录.json](数据整理记录.json)。', '',
              '## 文件获取与读取', '',
              '另一台机器克隆此仓库后不会自动拥有原始附件。请从原题提供方或队内授权渠道取得附件，按清单放回对应目录并核对 SHA-256。清单不提供缺失数据的下载保证。', '',
              '- A 题：测试图及 `config.txt` 位于附件的 `data/`；测试图仅保留本地，固定配置 `config.txt`、评估程序 `code/` 和说明 `docs/` 随仓库提交。',
              '- B 题：附件1/2 Excel 在同名附件目录。已有版本与 ZIP 内文件逐字节校验一致。',
              '- C 题：四组 `VisualCog*.mat` 位于原数据目录；以各文件字段核对采样率、通道和事件。',
              '- D 题：地理空间和应急运输数据位于 `数据/`；坐标系、单位和链路定义必须联合核对。',
              '- E 题：四类附件位于 `E题数据/`；`.pkl` 是 Python 序列化格式，仅在可信隔离环境读取，清单生成过程不会执行其中内容。',
              '- F 题：四个 `.jsonl.xz` 已展开为同路径 `.jsonl`，其余附件不变；原《数据说明》中 `.xz` 路径请改用去除末尾 `.xz` 的路径。逐行读取 JSONL，避免一次载入全部语料。', '',
              '## 校验方式', '',
              '运行 `python tools/build_data_inventory.py` 可重新生成现有文件的清单。比较时应先保存旧清单，按路径比对 `sha256` 和 `bytes`；重新生成清单本身不等于与原始清单比对通过。', '',
              '`python tools/prepare_problem_data.py --delete-archives` 用于新增 ZIP/XZ 的解压核验；工具先校验输出，再删除对应压缩包。已有同名文件若内容不同则中止并保留副本，不覆盖现有数据。', '',
              '清单包含系统元数据文件（如 `.DS_Store`），这些文件被忽略且不参与建模。']
    (ROOT/'调研'/'数据清单说明.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'files':len(rows), 'bytes':sum(r['bytes'] for r in rows),
                      'local_only':sum(r['git_policy']=='local_only' for r in rows)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
