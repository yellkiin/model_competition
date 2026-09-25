# 三台主机提示词索引

固定 GitHub PR：#38  
固定分支：`integration/orion-trident-publish-20260925`

三台在开跑前都执行：

```powershell
git fetch origin integration/orion-trident-publish-20260925
git switch integration/orion-trident-publish-20260925
git pull --ff-only origin integration/orion-trident-publish-20260925
git rev-parse HEAD
```

三台必须记录相同 HEAD；正式长实验开始后不要自动更新代码。

## 主机 0

完整提示词：`HOST_0.md`  
分片：ShardIndex=0，34 图。

```powershell
& .\research_a_orion_trident\run_windows.ps1 -ShardIndex 0 -FetchInputs -Seconds 600 -Hours 12
```

## 主机 1

完整提示词：`HOST_1.md`  
分片：ShardIndex=1，33 图。

```powershell
& .\research_a_orion_trident\run_windows.ps1 -ShardIndex 1 -FetchInputs -Seconds 600 -Hours 12
```

## 主机 2

完整提示词：`HOST_2.md`  
分片：ShardIndex=2，33 图。

```powershell
& .\research_a_orion_trident\run_windows.ps1 -ShardIndex 2 -FetchInputs -Seconds 600 -Hours 12
```

三份 HOST 文件中的研究逻辑、预算、退化消融、30 秒采点和结果发布要求完全一致；只有分片编号、图清单和输出目录不同。

首次准备输入后，后续复用本片 assets 时去掉 `-FetchInputs`。每台完成或截止后运行本机 HOST 文件末尾的 `publish_results.ps1` 命令，分别建立结果 PR；三片齐后只由一台执行最终 collect。

