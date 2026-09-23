# 本次可执行验证记录

日期：2026-09-23。环境：Python 3.13.5、NumPy 2.3.5、Matplotlib 3.10.8；有 XeLaTeX/ctex/Fandol，无 BibTeX。声明最低 Python 3.11，但本次未做多 Python 版本矩阵测试。

```bash
python -m unittest discover -s huaweicup_agent/tests -v
python -m huaweicup_agent demo /tmp/huaweicup-demo --compile
python -m huaweicup_agent audit /tmp/huaweicup-demo
python -m huaweicup_agent audit /tmp/huaweicup-demo --final
python -m huaweicup_agent freeze /tmp/huaweicup-demo --filename DEMO.pdf --rehearsal
```

回归测试：30 项，29 项通过，1 项跳过。跳过的是需要实际 BibTeX 可执行文件的正向编译测试；不将跳过计为通过。完整 demo 实际完成五个固定种子、两种候选、验证/测试两种划分，共 20 行结果。独立重跑实验脚本所得 JSON 内容哈希相同。图件和中文 LaTeX 编译已实际运行，演练 PDF 已逐页渲染查看。

已覆盖：非空目录拒绝覆盖、路径穿越/符号链接拒绝、输入增删改、递归依赖过期与循环、局部产物更新、非有限数值拒绝、来源状态与定位、Crossref HTTP 替身、TeX 转义、SSE/N/RMSE 一致性、重复结果、真实 CSV 图件、折线横轴顺序、编译授权、演练最终提交阻断、冻结文件字节 MD5 一致性和不可覆盖。

普通 audit 演练通过；final audit 演练必须失败，因为它不是实际赛题、缺少真实竞赛规则/队员签署，且包含 synthetic 结果。冻结演练明确使用 rehearsal，清单始终 `uploaded: false`。没有测试或声称向赛事平台提交成功。

没有验证：实际 LLM 端到端求解、付费模型连接、真实 Crossref 网络请求、任意赛题求解器、BibTeX 正向运行、Biber、多平台字体表现、2026 官方版式/AI 规则适配、各往年论文全文复现、模型获奖能力。当前只有合成演练的完整数学实验链，不能从中外推真实竞赛准确率。

安全/科学边界：哈希证明内容一致不证明真实；本地签署不认证人类身份；关闭 shell escape 不等于安全沙箱；种子/分母配对不证明样本 ID 一致。代码主要检查 RMSE，其他指标需题目专用适配。正式结论仍须队员审查。测试应在安装 requirements 后重新运行；未来上游/环境变化可能影响结果。
