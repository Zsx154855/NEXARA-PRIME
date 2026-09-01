# LAUNCHD DIAGNOSTIC REPORT (P0)

## 结论
launchd (gui domain) 进程无法访问外接 USB 卷 `/Volumes/NEXARA`，返回
`Operation not permitted`。这是 macOS TCC (可移动卷/完全磁盘访问) 的系统级限制。

## 证据链
1. `plutil -lint` → plist OK
2. `launchctl bootstrap` → 成功，但 `last exit code = 78: EX_CONFIG`，runs=20 全部失败
3. 极简 echo 测试（/bin/echo，内盘，WorkingDirectory 默认）→ **成功**（exit 0，日志写入）
4. 诊断脚本（/tmp 内盘脚本 + 外盘 WorkingDirectory）→ 78（chdir 外盘失败，连日志第一行都没写）
5. run_prod.sh（外盘脚本 + 内盘 WorkingDirectory）→ **`/bin/bash: /Volumes/NEXARA/.../run_prod.sh: Operation not permitted`**（exit 126）
6. run_prod.sh 手动运行 + env -i 完整模拟 launchd 环境 → **成功**（provider=deepseek）

## 根因
- 外盘：`Protocol=USB, Device Location=External, Removable Media=Fixed`（USB 外接 APFS 卷）
- macOS TCC 限制 launchd 守护进程访问外接卷，需 Full Disk Access / Removable Volumes 授权

## 结论分类
PERMISSION_BLOCKER（系统级权限，无法自动授权）
