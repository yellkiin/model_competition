# F组件已接入

默认smf使用research_a_orion_fusion.fifo，FUSION_API=1。Q1/2中F参与来源选择，Q3还提供消费者窗口、真实填充读前移、真实驱逐者后移、联合/长窗口。

接口propose(g,n,cfg,q,context,feedback,deadline)，context含plan、official_result、epoch。返回plan/name/family/proxy/bounds/evidence。proxy只作指导，bounds为可信下界。

select_source(sources,state,context,remaining_seconds)返回当前可用来源，不自行评估/写文件/停止宿主/改官方对象。宿主统一接受规则及600秒截止。

--fifo-module可接其他已审阅实现，必须新根，不能运行中切换。peer-v4与reconcile-v6位于research_a_orion_track_anytime；原#26无成功新实验，不作为独立已胜出方法。

本版保留上游首轮合法顺序，取消每个重排的完整内存/FIFO代理重算。083的18候选逐对象相同，一次生成1.091→0.227秒；不代表整个求解等价或整体同倍加速。
