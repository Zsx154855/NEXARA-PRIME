# NEXARA V1.2.1 — LONG RUN STABILITY REVALIDATION

时间: 2026-08-25 00:40 CST
样本源: stability_monitor.log (97 样本, cron 自动采集)

## 窗口覆盖
- 24H 窗口: 8/21 21:47 → 8/22 21:47 (样本 1-46) ✓ 完成
- 72H 窗口: 8/21 21:47 → 8/24 21:47 (样本 1-96) ✓ 完成
- 总观察: ~72.5 小时 (97 样本)

## 稳定性指标 (97 样本全量分析)
- health: 97/97 = ok (零失败, 零 crash)
- runtime pid: 63990 连续 72 小时未变 (零 restart, 零 crash)
- dbsize: 6283264 bytes 全程零增长 (无异常写入/泄漏)
- missions: 77 稳定 (无异常变化)
- events: 2817 稳定 (无异常事件增长)
- rss: 36976-66272 KB 波动 (GC 周期性波动, 无持续增长, 无内存泄漏)
- drift: src_mod=6, src_new=12, HEAD=3e07318 未变 (CORE_RUNTIME_DRIFT=0)
- database: quick_check ok

## 判定
24H_STABILITY = PASS (46 样本全 ok)
72H_STABILITY = PASS (96 样本全 ok)
LONG_RUN_STABILITY = PASS
NO_CRASH = PASS (同一 pid 72h)
NO_MEMORY_LEAK = PASS (rss 无持续增长, dbsize 零增长)
NO_DRIFT = PASS (HEAD 未变)

## 已知缺陷 (非本窗口引入)
P2: brain/__init__.py DecisionOutput 缺 estimated_tokens (kernel.py:369 访问)
    → KNOWN_DEFECT, 需 CHANGE_CONTRACT, 观察期间零触发
