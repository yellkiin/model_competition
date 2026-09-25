# 获取已发布代码与运行

代码已经提交到 `yellkiin/model_competition` 的 PR #38：
https://github.com/yellkiin/model_competition/pull/38

分支：`integration/orion-trident-publish-20260925`。三台使用同一个冻结提交；运行前记录 `git rev-parse HEAD`。不需要再运行旧代码发布脚本，也不要各建重复代码PR。

## 已授权仓库：独立稀疏worktree

在现有已授权仓库执行，以主机0为例；目录名选一个不存在的路径：

```powershell
git fetch --filter=blob:none --no-tags origin integration/orion-trident-publish-20260925
git worktree add --no-checkout --detach D:\orion_trident_host0 FETCH_HEAD
git -C D:\orion_trident_host0 sparse-checkout set research_a_orion_trident
git -C D:\orion_trident_host0 checkout --detach
Set-Location D:\orion_trident_host0
& .\research_a_orion_trident\run_windows.ps1 -ShardIndex 0 -FetchInputs -Seconds 600 -Hours 12
```

主机1/2只改独立worktree目录和ShardIndex。不要切换、更新或中断正在执行别的实验的原worktree。首次`-FetchInputs`会用固定Git引用按本片取原图、config、官方脚本、day01方案/表、三线研究、原DOCX和PDF；它不要求事先下载整个仓库。后续复用输入时去掉该开关。

## 数据与原始证据

原样实测文本、实际计划及相关索引在本目录`evidence/`，具体远端覆盖见`DELIVERY_STATUS.json`。完整本地原始证据附件为 `TRIDENT_REAL_EVIDENCE_20260925.zip`；原本地提交bundle也继续可用。这些大档案可另行归档，不是正式运行的前置条件，不将未上传附件写成已有Release。

在本机阅读原始包时，可以安装普通ZIP分卷：

```powershell
& 'D:\python\python.exe' -m research_a_orion_trident.install_evidence 'D:\Downloads\TRIDENT_REAL_EVIDENCE_20260925.zip'
```

已有raw分卷则跳过。此操作只搬运既有字节，不跑求解器。

## 分片结果上传

每台完成或截止后使用自己的结果路径：

```powershell
& .\research_a_orion_trident\publish_results.ps1 -RunRoot .\research_a_orion_trident\runs\round01\shard_0 -ShardIndex 0 -Round trident_round01
```

脚本使用本机已有git/gh授权，建立独立结果worktree，仅提交本片文本与计划；大原始响应拆40MiB上传本仓库Release。读回实际asset状态/大小/链接后创建分片结果PR。三个结果PR与代码PR均不自动合并。没有gh授权时先完成实验和本地导出，再由本地Agent处理该发布动作，勿因此暂停已具备输入的求解。
