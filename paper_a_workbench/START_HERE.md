# 从当前Codex项目开始

本包修补#42：安装盘符改为当前项目；#44理论直接进入Agent；实验大包改读用户桌面目录。

1. 在做任何cd之前，把当前Codex项目的绝对路径记为PROJECT_ROOT。此值在本次部署中保持固定。仓库为yellkiin/model_competition，工具目录为paper_a_workbench。取得本修补PR的实际head并记录；所有新增工具放到PROJECT_ROOT下，不切换正在跑实验的checkout。
2. 已有授权仓库可用git show/archive从指定提交只导出paper_a_workbench；也可在PROJECT_ROOT/.orion_paper_cache/repository做独立的`--filter=blob:none --no-checkout`克隆，在该缓存检出本工具目录。缓存只是资料来源，不成为新的项目根。
3. 运行本目录BOOTSTRAP_LOCAL.ps1，显式传入原PROJECT_ROOT。Python优先用本机现有3.11+。模板从项目自身、单层/双层20hw_myskill_distribution定位；缺失时脚本从授权冻结版本恢复共享资源。不导入旧论文、实验输出或完成状态。

```powershell
$project=(Get-Location).Path
# $tool 为本修补PR中实际取得的 paper_a_workbench 路径
& "$tool\BOOTSTRAP_LOCAL.ps1" -ProjectRoot $project -DataRoot 'C:\Users\LEGION\Desktop\数据'
```

4. 默认生成PROJECT_ROOT/ORION_Paper_Agent。阅读该目录AGENTS和ORION_论文总控提示词.md，显式读取其skills；继续操作以它为工作根，PROJECT_ROOT仍使用SESSION值。若新开会话，从这个Agent根启动。默认目录已存在且有本次SESSION时续接，不复制第二套，也不猜workshop编号。
5. BOOTSTRAP会同步必需理论源并调用prepare-theory，还会建立桌面数据目录清单。若数据尚未拷齐，先按THEORY/ALGORITHM/PAPER_ROUTE推进理论准备；正式实验选择后再local-spec/intake。
6. package-inputs生成真实DOCX与ZIP。完整读取原工作流、实际版权/使用约定后，通过START_COMMAND中的真实文件参数创建工作区，再bind；该步骤由原workshop分配路径。

不用叠加PR44的APPEND_PROMPT，也不另行运行它的安装/绑定工具。其科学正文、TERMS、SOURCE_MAP和论文路线已经作为必需输入随资料ZIP传入六个角色。

本次代码发布与本地论文生产是两个阶段。写作任务默认只读GitHub；实验大包读桌面原件，不自动上传或下载原始Release分卷。
