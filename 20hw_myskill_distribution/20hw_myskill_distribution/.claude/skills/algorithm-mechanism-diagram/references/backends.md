# 后端与实测边界

本地PlotNeuralNet的`pycore/tikzeng.py`负责生成Box/RightBandedBox/Ball，`layers/*.sty`实现投影与锚点。其`to_generate`使用平台默认编码，中文适配应在自己的生成器中用UTF-8写TeX，不修改上游。复制必要layers/pycore与LICENSE进入输出工程。

已在本机XeLaTeX验证Python调用`to_Conv`、`to_ConvConvRelu`，自定义分支/拼接/投影/残差连接和中文外置标签；参见项目 `output/diagram-skills-DEMO/render_demo.py` 的network_tikz。默认caption宽度按薄片厚度计算，窄薄片会把中文挤成竖列，xlabel/zlabel在窄层可能碰撞；取消内置caption和尺寸槽，改用独立固定宽度节点，实际看图确认。

draw.io已验证Python投影坐标生成自定义stencil多边形、三个表面及同对象连续叠片、分支和跨层连接。整体XML可以编辑；表面是独立矢量cell，组内用diagramObject关联而非假位图。CLI输出PDF再以矢量页面放缩到160mm，并生成300dpi PNG用于复核。

实测不覆盖所有上游示例、任意TikZ宏包或draw.io版本；每张新结构仍需重渲染与论文尺寸复核。选用条件：需要手动调块与连接优先draw.io；大量公式/数学排版及图层表达适合TikZ；不能仅凭已安装软件决定后端。
