# 近期论文原文：2023 年 12 篇

本目录是 `model_competition` 中现有优秀论文索引的原文补充，不是另起一个论文库。

- **实际下载**：12 篇 2023 年论文，A/C 各 4 篇，B/D/E/F 各 1 篇，共 811 个物理页。
- **索引覆盖**：`index_match.csv` 保留 2023—2025 全部 103 条记录；只有其中 12 条为 downloaded。
- **没有取得**：2024 年 24 篇、2025 年 21 篇的原始 PDF。未用摘要、方法卡或题面冒充论文。
- **核验范围**：原始文件字节、ZIP 清单、CRC、Git blob、SHA256、pdfinfo 页数、与父目录现有索引的精确身份。并非逐篇精读，不代表数学正确；具体奖项未逐篇核验。

## 文件与编号

|题号|论文编号|
|---|---|
|A|A23100070049、A23102470073、A23102480015、A23102860239|
|B|B23100070010|
|C|C23102540029、C23102890004、C23102980125、C23103360083|
|D|D23100060041|
|E|E23100650012|
|F|F23102520378|

PDF 只保存一份于 `2023_selected_12_papers.zip`，包内路径为 `2023/题号/编号.pdf`。按编号选取不是质量排名；跨年同字母不代表同题型。

`manifest.json` 保留逐篇固定源提交、网址、哈希、大小、页数与阅读/奖项状态。包大小 **47,571,071 字节**，SHA256 为 `9062cd5372ab1fad06a1f85e81f9384187b5e6e5058adc4d886db04d439083dd`，与迁移前提供给用户的包逐字节一致。

## 查询与核验

在仓库根目录：

```bash
python tools/huaweicup.py papers --year 2023 --problem A
python "各种建模agent/hwb-math-modeling-skills/数模资料/优秀论文索引/近期论文原文/library.py" --verify-only
python -m unittest discover -s "各种建模agent/hwb-math-modeling-skills/数模资料/优秀论文索引/近期论文原文" -p 'test_*.py' -v
```

页数核验需要 `pdfinfo`（Poppler）。脚本无参数时也只核验；只有显式 `--download` 才从 manifest 中锁定的公共源下载，且拒绝覆盖已有 ZIP。`--write-report` 才更新机器核验结果。下载流程不执行论文中的脚本，不安装第三方 Agent 后端。

来源为 `zhanwen/MathModel` 的 2023 年优秀论文目录（提交 `cd5be91735ebf11d5ee52eb170e86a6d07131977`）；原索引是 `xieyouxixi/hwb-math-modeling-skills` 的 `afcf23a4085ed15696cb59fefab1e132a4cb6189` 版本，和本仓库父目录 CSV 的 Git blob `f19981bf1dad91aa214ddfcc9d4ee379d06c0b88` 一致。按年份、题号和编号对齐，不覆盖父目录原始 CSV。

版权归原作者及相关权利人，不把代码许可证套到论文；本次用于用户指定私有仓库内学习研究，未核实公开二次分发或商业使用授权。检索、下载、阅读、数学核验和奖项核验需要分别记录。
