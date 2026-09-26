# 第三版设计与来源记录

## 图形来源与本次边界

图形结构继续继承 ink_v2：六算子计算图、任务条、基础构造图、迁核示例、驻留弧线、FIFO 窗口、核心与存储剖面均保持矢量形式。历史设计参考提交为 `70d4888886cd9f77037f7b010ce0241349ef056d`。本次工作不修改 ink_v2、论文正文、求解算法或实验结果，不读取或引用其他图形 PR 的设计。

## 实际字体证据

直接核对 `20hw_myskill_distribution/20hw_myskill_distribution/workshop_v2/论文/论文.pdf` 的字体资源，并查看第9页的计算图定义、划分表达式与 Makespan 公式。该 PDF 使用 SimSun、TimesNewRomanPSMT / TimesNewRomanPS-BoldMT，以及 CMMI12 / CMSY10 / CMR12 等 Computer Modern 数学字体。宋体标题使用合成粗体。

先前“STIX Math + 宋体兼容字体”的说明不等同于论文实际字体。本次改为真实 SimSun / Times New Roman 文本轮廓和 LaTeX Computer Modern 公式轮廓，尤其将 Unicode 装饰花体 P 改为 `\mathcal{P}`。

中文和西文的轮廓由 Windows 本机已安装字体生成；公式由 LaTeX 排版。没有复制、上传或随交付包附带字体文件，也没有将图片栅格化。普通 SVG 的文字已转成路径，另保留 `_editable.svg` 文字源稿。公式对象保留 `data-tex`，文字对象保留 `data-label`，便于定位与重新生成。

## 位置与视觉语义

G=(T∪O,E) 固定在左列输入行右侧，不压在子图上。核心 k_1、k_2 在各自核心剖面上方居中，数学下标由 LaTeX 正式排版。COPY_OUT 与 COPY_IN 分别居中位于对应搬运立方体上方，白色描边用于避开背景细线。Makespan 公式位于右下结果框内，基线和下标一起重排。

B 的深色仅用于旧稿的迁移示意，并非另一类任务；本次将其与 A、C、D 统一为纸面框，以“迁移 B”和箭头表达操作。删除最下方 Q3 配对说明整行，保留最终输出短句。关于第三问同方案有无 L2 的比较，仍可在独立图解和论文正文解释。

主流程保留两条从左到右的模块间实线箭头、单一视觉反馈回路和停止输出分支。所有局部计算依赖、任务迁移及内存访问箭头保持为内部示意，不新增算法机制或实验结论。

## 构建与检查

build.py 已集成 finalize_v3.py，避免重建后恢复旧问题。math_layout.py 负责公式排版，outline_native.py 负责实际字体转曲，validate_v3.py 检查结构、字体独立性、同色 B、公式标记、输出尺寸、冲突标记与文件完整性。结构检查不替代实际 SVG / PDF 预览审阅。

正式文件位于 ink_v3；另保留明确触发的 GitHub 图件导出工作流。临时字体检查工作流在完成审查后移除。图件导出只提交 ink_v3，不自动合并 main。
