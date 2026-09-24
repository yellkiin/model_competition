# V3 本地执行入口

本轮直接读 LOCAL_AGENT_PROMPT.md 并运行 best5。quality.py 已完整提交，不再从旧临时包恢复。
禁止冒烟、哈希/指纹、pytest/unittest、全仓审计、环境基准。保留全部官方合法性检查。
只修改本目录；不改官方图/配置/评估器，不覆盖其他agent和旧结果，不自动第二轮/全量/合并PR。
