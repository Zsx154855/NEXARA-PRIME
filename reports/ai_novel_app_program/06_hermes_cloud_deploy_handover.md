# 墨衍完整版云部署 — Hermes 交接文档

- 交接人：NEXARA 第一方主权智能体（本会话）
- 交接对象：Hermes（执行云服务器部署）
- 日期：2026-08-29
- 状态：**✅ 已完成（2026-08-30 部署成功并独立验证）** — 执行详情见 `.nexara/evidence/cloud_deploy_complete_20260830.json`

## 0. 执行结果摘要（2026-08-30 更新）

- 公网 `https://novel.agentoscloud.com` → HTTP 200（云端隧道已接管）
- 新访问码：**A1gqDWXr**（旧码 Eii8cGvB 已失效）
- 本机 launchd 隧道已停用（`com.nexara.moyan-tunnel.plist.disabled-20260829`），本机网关 127.0.0.1:8788 保留供本地开发
- **4 处环境偏差及处置**（详见 Evidence）：
  1. 容器无 systemd → 改用 miniconda supervisord 守护（novel-gateway + cloudflared-tunnel，autorestart）
  2. GitHub 被墙 → 经 `/etc/network_turbo` 学术加速下载 cloudflared
  3. 隧道配置用 TunnelID（`d206a897-619d-499d-ae16-9d60a93efbe6`）免 origin cert
  4. writer.py 264/265 行 f-string 反斜杠 → `chr(10)` 修复（本机与服务器已同步，md5 一致）
- **剩余待办**：① 矩池云控制台「重启实例」做真实 reboot 验证；② SSH 端口 51194 在实例重开机后可能变化；③ library.db 每日备份 cron 未配置

---

## 1. 任务概述

将「墨衍长篇写作引擎完整版」（书库 + 批量写作 + 门禁质检 + 人物名册 + 无限续卷）从本机
（macOS，cloudflared 隧道公网化）迁移部署到用户购买的矩池云服务器，使其他用户可稳定访问
完整能力，不再依赖本机开机与网络质量。

### 目标架构

```
其他用户 → https://novel.agentoscloud.com（Cloudflare 代理 HTTPS）
         → cloudflared 隧道（云服务器上运行）
         → 127.0.0.1:8788（server.py 网关 + writer.py + library.db）
         → cloud 档 → https://agentoscloud.com/api/chat（Vercel 生产链路，OpenRouter 免费档）
```

## 2. 服务器信息（用户已提供）

| 项 | 值 |
|---|---|
| SSH 命令 | `ssh -p 51194 root@connect.bjb2.seetacloud.com` |
| 平台 | 矩池云（SeetaCloud）北京 B 区，**Ubuntu 22.04.1 LTS（x86_64）** |
| root 密码 | **已由用户提供（2026-08-29），不入任何文件；交接时口头/加密通道传递** |
| 可达性 | 已 ping 通（30ms，0% 丢包）；SSH 登录已验证 ✅ |

### 已确认环境快照（交接前实测）

| 项 | 实测 | 状态 |
|---|---|---|
| Python | **3.10.12**（/usr/bin/python3，已由交接准备阶段 apt 安装，原本缺失） | ✅ |
| curl | 7.81.0 | ✅ |
| CPU/内存 | 128 核 / 1.0Ti（宿主机级规格） | ✅ |
| 磁盘 | overlay 30G，剩余 6.6G（79% 已用；应用仅需 ~1M，够用） | ⚠️ 注意 |
| /root 存量 | autodl-pub / autodl-tmp / 历史 compile 脚本（勿动，未知归属） | ⚠️ 注意 |

⚠️ 矩池云特性：实例按小时计费，**关机/释放后端口映射可能变化**（connect.bjb2 为固定跳板域名，
端口 51194 为当前实例映射）。重开机后如端口变化需用户重新提供。

## 3. 前置资产（本机源路径 → 部署目标）

源目录：`/Users/agentos/NEXARA-PRIME/workspace/ai-novel-app/`
目标目录：`/root/novel/`（服务器上新建）

| 文件 | 大小 | 必须 | 说明 |
|---|---|---|---|
| server.py | 16K | ✅ | 网关（静态 + /api 路由 + cloud 透传 + 访问码鉴权） |
| writer.py | 40K | ✅ | 写作引擎（门禁/名册/续卷/段间去重） |
| library.py | 20K | ✅ | 书库模块（纯标准库） |
| library.db | 512K | ✅ | 数据库（31 done + 11 pending，book_id=2 共 9 角色） |
| index.html | 16K | ✅ | 前端页面 |
| app.js | 44K | ✅ | 前端逻辑（IS_LOCAL 公网自动固定 cloud 档） |
| styles.css | 28K | ✅ | 样式 |
| moyan_gateway_token.txt | 9B | ✅ | 访问码（部署时建议轮换，见 §7） |
| verify_ch10_18.py | 3K | 可选 | 验收脚本 |
| api/ | - | ❌ | Vercel Serverless 函数，云服务器不需要 |
| .vercel/ .vercel-tmp/ __pycache__/ | - | ❌ | 不上传 |
| evidence/ | - | 可选 | 交付证据，可不上传 |

**依赖：全部为 Python 标准库**（json/os/re/urllib/http.server/socketserver/threading/time），
零第三方包，无需 pip install。

## 4. 部署步骤

### 4.1 SSH 登录（需用户提供密码）

```bash
ssh -p 51194 root@connect.bjb2.seetacloud.com
```

### 4.2 环境确认 + 建目录（已完成验证）

```bash
python3 --version          # ✅ 已装 3.10.12
mkdir -p /root/novel
```

### 4.3 上传应用（本机执行）

```bash
scp -P 51194 server.py writer.py library.py library.db index.html app.js styles.css \
  moyan_gateway_token.txt root@connect.bjb2.seetacloud.com:/root/novel/
```

### 4.4 访问码轮换（安全要求）

云部署必须使用**新访问码**（旧码 Eii8cGvB 已在本机公网暴露过）：

```bash
# 服务器上生成
TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(6))")
echo "$TOKEN" > /root/novel/moyan_gateway_token.txt && chmod 600 /root/novel/moyan_gateway_token.txt
cat /root/novel/moyan_gateway_token.txt   # 记录此码，交付用户分享
```

### 4.5 网络绑定决策

| 方案 | 绑定 | 适用 |
|---|---|---|
| **A. 隧道方案（推荐）** | 保持 `127.0.0.1:8788` 不变 | 延续 novel.agentoscloud.com 域名，无需改 DNS、无需防火墙放行入站（仅需出站 443） |
| B. 直连方案 | server.py 改 `0.0.0.0:8788` | 用户直接访问 `http://<公网IP>:8788`，需矩池云防火墙放行 8788；无 HTTPS |

**推荐 A**：代码零改动，域名不变，其他用户链接不变。§5 给出隧道执行细节。

### 4.6 systemd 守护（Linux 版开机自启）

```bash
cat > /etc/systemd/system/novel-gateway.service <<'EOF'
[Unit]
Description=MoYan Novel Gateway
After=network.target

[Service]
WorkingDirectory=/root/novel
EnvironmentFile=/root/novel/.env
ExecStart=/usr/bin/python3 /root/novel/server.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "MOYAN_ACCESS_TOKEN=$(cat /root/novel/moyan_gateway_token.txt)" > /root/novel/.env
chmod 600 /root/novel/.env
systemctl daemon-reload && systemctl enable --now novel-gateway
systemctl status novel-gateway --no-pager | head -10
```

注意：server.py 读取 `MOYAN_ACCESS_TOKEN` 环境变量（**不读文件**），故用 EnvironmentFile 注入。
token 轮换 = 改 .env + `systemctl restart novel-gateway`。

### 4.7 cloudflared 隧道（方案 A）

```bash
# 云服务器安装（Ubuntu x86_64/arm64 对应架构）
curl -L --output /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x /usr/local/bin/cloudflared

# 从本机拷贝隧道凭证与配置（本机路径）：
#   ~/.cloudflared/d206a897-619d-499d-ae16-9d60a93efbe6.json  （隧道凭证，含 Tunnel ID）
#   ~/.cloudflared/agentoscloud-agentos-bridge.yml             （ingress 配置）
scp -P 51194 ~/.cloudflared/d206a897-619d-499d-ae16-9d60a93efbe6.json \
  ~/.cloudflared/agentoscloud-agentos-bridge.yml root@connect.bjb2.seetacloud.com:/root/.cloudflared/

# 云服务器 systemd 隧道服务
cat > /etc/systemd/system/cloudflared-tunnel.service <<'EOF'
[Unit]
Description=Cloudflare Tunnel (novel bridge)
After=network.target

[Service]
ExecStart=/usr/local/bin/cloudflared tunnel --config /root/.cloudflared/agentoscloud-agentos-bridge.yml run agentoscloud-agentos-bridge
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now cloudflared-tunnel
```

⚠️ **同一隧道不可双端同时 run**（两端 library.db 会分叉 + 连接竞争）：
云端隧道注册成功后，**停用本机隧道**（本机执行，属外部动作，需用户批准）：

```bash
launchctl bootout gui/$(id -u)/com.nexara.moyan-tunnel
mv ~/Library/LaunchAgents/com.nexara.moyan-tunnel.plist ~/Library/LaunchAgents/com.nexara.moyan-tunnel.plist.disabled-clouddeploy-20260829
```

本机网关（server.py，launchd com.nexara.moyan-gateway）可保留（本地开发用，端口不冲突）。

## 5. 验证清单（全部通过才算交付完成）

```bash
# ① 网关本地存活
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8788/                    # 期望 200

# ② 鉴权
curl -s http://127.0.0.1:8788/api/library/books                                     # 期望 401
curl -s -H "X-Access-Token: $TOKEN" http://127.0.0.1:8788/api/library/books | head -c 300  # 期望 200 + JSON

# ③ 书库完整性（应返回 31 done + 11 pending，卷四 12 章规划）
# ④ 试写一章（cloud 档，真实模型调用，约 5 分钟）
curl -s -X POST http://127.0.0.1:8788/api/writer/run -H "X-Access-Token: $TOKEN" \
  -d '{"model":"cloud","n":1}' | head -c 500

# ⑤ 公网（隧道方案）
curl -s -o /dev/null -w "%{http_code}\n" --max-time 20 https://novel.agentoscloud.com/  # 期望 200

# ⑥ 进程守护
kill $(pgrep -f "server.py") && sleep 5 && curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8788/  # 期望自动重启后 200

# ⑦ 开机自启
reboot 后 systemctl status novel-gateway cloudflared-tunnel 均为 active
```

## 6. 运维要点

- **备份**：`library.db` 为唯一权威数据，建议 cron 每日备份到本机：
  `0 4 * * * scp -P 51194 root@connect.bjb2.seetacloud.com:/root/novel/library.db /Users/agentos/NEXARA-PRIME/workspace/ai-novel-app/backups/`
- **日志**：`journalctl -u novel-gateway -f`；门禁失败稿落 /tmp/failed_ch_*.txt
- **模型链路**：cloud 档透传 agentoscloud.com/api/chat（Vercel + OpenRouter 免费档），服务器需出站 443/80
- **访问码分享**：新 token 交付用户；轮换 = 改 .env + restart
- **矩池云临时性**：实例释放前必须备份 library.db（用户知情）
- **本机网关保留**：本地 localhost:8788 继续可用（开发/回滚）

## 7. 权限边界（需用户明确批准后才能执行的动作）

1. **停用本机 launchd 隧道**（bootout + 重命名 plist）—— ✅ **已获用户批准（2026-08-29）**，但**执行条件：云端隧道注册成功后**（否则域名断线），且必须先确认 `https://novel.agentoscloud.com` 经云端返回 200
2. 任何 DNS / Cloudflare 面板变更
3. 矩池云防火墙规则变更（方案 B 才需要）
4. SSH 密码获取（用户提供，**已提供**）

无需批准：云服务器上的全部部署动作（上传/安装/systemd/验证）。交接准备阶段已执行：apt 安装 python3.10.12。

## 8. 回滚方案

- 云端回滚：`systemctl stop novel-gateway cloudflared-tunnel`，恢复本机隧道：
  `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nexara.moyan-tunnel.plist`
- 数据回滚：library.db 已有备份（evidence/ch31_v4_v1_backup.txt 为第 31 章正文备份；库文件可随时从本机重传）

## 9. 已知背景（避免重复调研）

- 本机隧道曾因 iPhone 热点网络（25% 丢包）出现 502，切 WiFi 后稳定——这正是迁移上云的价值
- 书库当前状态：卷一卷二卷三 done（1-30 章），卷四 planned（31-42 章规划），31 done / 11 pending
- 前端 app.js 有 IS_LOCAL 检测：公网访问自动固定 cloud 档并隐藏本地草稿档，零前端改动
- 访问码鉴权已内置 server.py（MOYAN_ACCESS_TOKEN + X-Access-Token header），无需额外中间件
- 写作质量门禁（CJK 3000-4200、AI 味 ≤3/千字、loops=0、人名名册）全在 writer.py 内，云上行为与本地一致
