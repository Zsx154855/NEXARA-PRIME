# PHASE 8 UPGRADE / ROLLBACK (真实验证)

UPGRADE:
- 变更: ThrottleInterval 5→10 (模拟版本配置变更)
- SHA: d92fafbf... → 10dd2149e30a7a... (变更生效)
- launch(kickstart -k): health ok, pid 63959, provider deepseek
- real conversation: deepseek 真实回复 ("你好！我是 NEXARA PRIME...")
- 结论: 升级后 runtime 功能正常

ROLLBACK:
- 恢复: cp golden-20260821-015858 → plist
- SHA: 10dd2149... → d92fafbf... (恢复一致)
- launch(kickstart -k): health ok, pid 63990
- 结论: 回滚后 runtime 正常, SHA 与 golden 一致

判定: UPGRADE=PASS, ROLLBACK=PASS (非仅脚本存在, 真实执行 upgrade→launch→health→conversation→rollback→restore)
注: 首次 bootout+bootstrap 有 launchd 时序问题, 改用 kickstart -k 后稳定。
