# inkpi-admin Service

`inkpi-admin` 是 InkPi 的本地 Web 管理门户，面向物理上靠近设备的使用者，
提供状态查看、Dashboard 控制、网络配置和系统管理入口。

## Service Role

| 职责 | 说明 |
|------|------|
| Web Portal | 提供 no-build HTML 管理界面（6 个页面） |
| Status API | 聚合 core / display / system / network 状态 |
| Dashboard Control | 页面启用/禁用，live preview 图片 |
| Network Operations | 允许列表内的网络操作，通过 privileged helper 执行 |
| Privileged Helper IPC | 通过 Unix socket 与特权 helper 进程通信 |
| Session Management | Cookie session + CSRF token 管理 |
| Event Log | 有界、脱敏的管理事件流 |

!!! warning "Not a Display Owner"
    `inkpi-admin` 不渲染 dashboard 帧，不拥有 SPI/GPIO。
    通过 `InkPiClient` 与 `inkpi-core` 通信。

## Access Methods

| 方式 | 说明 |
|------|------|
| LAN | 以太网或 Wi-Fi 局域网直接访问 |
| Hotspot | 设备加入 Pi 热点后访问 |
| Hidden Hotspot | Pi 有互联网时，隐藏热点用于维护并共享上游网络 |

默认监听 `127.0.0.1:8081`，可通过启动参数修改。

## Authentication

支持两种认证方式：

**Token Auth**: 所有 POST 请求需要 token 验证，提供方式：`X-InkPi-Admin-Token`
或 `Authorization: Bearer` header。Token 通过 `INKPI_ADMIN_TOKEN` 环境变量配置。

**Session Auth**: 浏览器端使用 cookie-based session（`AdminSession`），
每个 session 携带独立 CSRF token。`SessionStore` 管理 session 生命周期与过期清理。
表单提交需同时携带有效 session cookie 和 CSRF token。

CORS 保护验证 `Origin` 与 `Host` 匹配，不匹配返回 403。

| 场景 | Status |
|------|--------|
| Token 未配置 | 503 |
| Token 无效 | 401 |
| CSRF 不匹配 | 403 |
| 跨域请求 | 403 |

## API Endpoints

### Read-Only (GET)

| Endpoint | 说明 |
|----------|------|
| `/api/status` | 聚合状态 + auth 配置 |
| `/api/network` | 网络 facts + policy 决策 |
| `/api/dashboard` | Dashboard 状态 + 页面列表 |
| `/api/dashboard/preview/{page_id}.png` | 页面 preview 图片 |
| `/api/display` | Display 服务状态 |
| `/api/system` | 系统 facts |
| `/api/events` | 管理事件流 |
| `/api/settings` | 当前非 secret 配置 |

HTML 路由：`/`、`/network`、`/dashboard`、`/system`、`/logs`、`/settings`。

### Mutation (POST, requires token or session)

| Endpoint | Operation |
|----------|-----------|
| `/api/network/wifi/scan` | `wifi_scan` |
| `/api/network/wifi/connect` | `wifi_connect` (staged) |
| `/api/network/wifi/confirm` | 确认 staged Wi-Fi 连接成功 |
| `/api/network/wifi/fail` | 报告 staged Wi-Fi 连接失败 |
| `/api/network/wifi/forget` | `wifi_forget` |
| `/api/network/hotspot/enable` | `hotspot_enable` |
| `/api/network/hotspot/disable` | `hotspot_disable` |
| `/api/network/hotspot/rotate-password` | `hotspot_rotate_password` |
| `/api/network/policy/reconcile` | `policy_reconcile` |
| `/api/dashboard/pages/{id}/enable` | 启用页面 |
| `/api/dashboard/pages/{id}/disable` | 禁用页面 |
| `/api/system/restart/{service}` | 重启服务 (core/display/admin) |
| `/api/settings` | 保存非 secret 配置 |

禁用最后一个 enabled 页面的请求会被 core 拒绝。

## Privileged Helper

网络特权操作通过 `HelperClient` 与独立 `privileged.py` 进程通信。
两者通过 Unix socket IPC 连接，helper 进程仅接受允许列表内的操作
（Wi-Fi 扫描/连接、热点开关、NAT 规则、服务重启）。

Wi-Fi 密码通过 stdin transient secret channel 传递，不进入 argv、JSON 响应、
事件日志或测试文件。`network_helper.py` 负责将操作翻译为 nmcli 命令向量，
`helper_client.py` 负责序列化请求并管理 socket 生命周期。

## Staged Wi-Fi Flow

Wi-Fi 连接采用分阶段提交（staged connection）流程：

1. 用户提交 SSID + 密码，helper 开始尝试连接。
2. 当前热点保持活跃，用户不会断网。
3. 连接成功后 portal 调用 `/api/network/wifi/confirm` 确认。
4. 连接失败后 portal 调用 `/api/network/wifi/fail` 报告，触发 recovery 追踪。
5. 超过重试预算（默认 3 次）后自动恢复 recovery hotspot。

## Hidden Hotspot & NAT

当 Pi 通过以太网或隧道获得互联网时，可启动隐藏热点（hidden hotspot）
用于维护访问并共享上游网络。`privileged.py` 配置 iptables NAT 规则
和 `ip_forward`，使热点客户端能通过上游接口访问互联网。

清理步骤确保热点关闭时 NAT 规则和 sysctl 设置被正确还原。

## Live Preview

Dashboard preview 通过 core render contract 获取实时渲染结果。
core 返回 base64 编码的 PNG 图片，admin 直接透传给浏览器。
当 core 不可用时，自动降级为 mock preview 图片。
preview 请求不触发 live 数据采集，不绕过 display 刷新策略。

## Run Locally

```bash
uv run inkpi-admin --host 127.0.0.1 --port 8081 \
  --core-socket /tmp/inkpi-core.sock --admin-token dev-local-token \
  --helper-socket /tmp/inkpi-helper.sock
```

```bash
curl -X POST -H 'X-InkPi-Admin-Token: dev-local-token' \
  http://127.0.0.1:8081/api/dashboard/pages/codex_usage/disable
```

## See Also

- [Admin Portal Design](admin-portal-design.md)
- [Architecture](../architecture.md)
