# 实际验证记录与结论边界

## 原题读取

已从仓库原始DOCX提取正文和OfficeMath文字，记录在[原题提取工作流](https://github.com/yellkiin/model_competition/actions/runs/35869201557)。这不是用半成品论文转述题面，也不是完整插图校对。

## 代码与原评估器

代码版本 `f99618af3ee6cabc116f42021728eebbaadfa874`，Python **3.12.5 x64**，验证命令：

```text
python -m unittest -v research_a_next.test_math research_a_next.test_extensions
```

[实际GitHub Actions运行](https://github.com/yellkiin/model_competition/actions/runs/35875278084)：Windows与Ubuntu两个作业均成功。Windows作业107229453107的日志明确记录 **18项通过，4.534秒，零跳过**；这个秒数只指小型测试函数，不包含创建CI环境或正式数据运行。

测试真正调用仓库中未修改的三个原评估器，不是mock。内容包含：六类二部图的三问/五种核数构造；26/526张量链下界；限制窗口整数枚举对照；三问原API与原CLI周期一致；三问批量导出与n1口径；一个实际发生4096字节Cache命中的例子；Q3五个参数轴点、固定与适配方案共10行小型结果。

### 原始日志中的合成上下界结果摘录

下表每行三问均分别运行，三个问题在这些小例子上恰好具有相同数值，不意味着三问一般等价。

|合成图，8个计算操作，3核|全局下界|原评估周期|解析后验上界|
|---|---:|---:|---:|
|链|52|54|70|
|扇出汇合|21|54|70|
|共享输入、独立计算|17.3333333333|24|136|
|多Pipe独立计算|9.3333333333|19|178|

另一个专门的FIFO例子通过自然输入请求顺序触发 `OFFICIAL_FIFO_HIT_BYTES=4096`；不是假定缓存命中。小型批量报告得到 `OFFICIAL_SYNTHETIC_BATCH_COMPLETE=true`，并保持 `formal_full100_complete=false`。

## Windows脚本

同一个Windows作业实际通过 `powershell -NoProfile -ExecutionPolicy Bypass -File .../configure_windows.ps1 -Python <CI解释器>` 执行环境脚本，得到3.12.5/64位、`status=ready`、`cuda_required=false`、第三方包列表为空；两个PS脚本语法解析通过。CI是Windows Server环境，不宣称已在用户那台Windows桌面电脑上执行。环境脚本不会安装Python、CUDA、Conda或修改用户已有解释器。

## 本地容器

当前容器没有原评估源码实体，`results/local_tests.txt`记录12项数学检查通过，原评估测试类明确跳过；上述CI补齐实际原评估验证。两处的验证范围不混为一谈。

## 尚未获得的证据

没有在本轮执行6张正式诊断图或完整100张正式图；没有测得超过稿件3.5093/3.5456/3.6104的结果。上述秒数不能估计大图评估耗时，合成图不能代表正式图的Spill/等待环复杂性。30分钟是本地计算阶段的截止设置，不保证所有机器届时都能完成全部36配置；未完成必须保留missing。

本记录只确认公式、接口与受控执行路径。跨机器合并、异常进程树清理和大规模内存使用还需要在实际运行中观察，不能把这18项检查写成所有输入/平台均已被验证。也不把任何单元检查要求为用户启动实验的前置流程。
