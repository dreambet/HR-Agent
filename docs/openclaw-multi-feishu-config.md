# OpenClaw 多 Feishu Agent 配置指南

## 概述

本文档说明如何在 OpenClaw 中配置多个独立的 Agent，每个 Agent 绑定到不同的 Feishu App，实现多个飞书机器人同时工作、互不影响。

## 场景说明

- **HR-Agent**：使用原有的 Feishu App（`cli_a97ec8ac45785cd1`）
- **PPT-Agent**：使用新的 Feishu App（`cli_a9605b27aeaa9bde`）

## 配置架构

```
openclaw.json
├── channels.feishu
│   ├── accounts.default.appId      → HR-Agent 的 App ID
│   ├── accounts.default.appSecret  → HR-Agent 的 App Secret
│   ├── accounts.ppt.appId          → PPT-Agent 的 App ID
│   ├── accounts.ppt.appSecret      → PPT-Agent 的 App Secret
│   └── defaultAccount: "default"  → 默认账号
│
└── bindings
    ├── { agentId: "hr-agent", match: { channel: "feishu", accountId: "default" } }
    └── { agentId: "ppt", match: { channel: "feishu", accountId: "ppt" } }
```

---

## 详细步骤

### 第一步：确认 Agent 已注册

在 `openclaw.json` 的 `agents.list` 中确认目标 Agent 已存在：

```json
"agents": {
  "list": [
    { "id": "main" },
    { "id": "hr-agent", "name": "HR-Agent", "workspace": "/root/.openclaw/workspace-HR-Agent" },
    { "id": "ppt", "name": "PPT", "workspace": "/root/.openclaw/workspace-ppt" }
  ]
}
```

如果 Agent 不存在，需要先添加。详细方法请参考 OpenClaw Agent 管理文档。

---

### 第二步：配置 Feishu 多账号（使用 CLI）

#### 2.1 设置默认账号的凭据（如果尚未配置）

```bash
# 设置默认账号的 App ID
openclaw config set channels.feishu.accounts.default.appId '"你的第一个AppID"' --strict-json

# 设置默认账号的 App Secret
openclaw config set channels.feishu.accounts.default.appSecret '"你的第一个AppSecret"' --strict-json
```

#### 2.2 添加第二个账号（以 "ppt" 为例）

```bash
# 添加 ppt 账号的 App ID
openclaw config set channels.feishu.accounts.ppt.appId '"你的第二个AppID"' --strict-json

# 添加 ppt 账号的 App Secret
openclaw config set channels.feishu.accounts.ppt.appSecret '"你的第二个AppSecret"' --strict-json
```

#### 2.3 设置默认账号

```bash
openclaw config set channels.feishu.defaultAccount '"default"' --strict-json
```

#### 2.4 验证配置已写入

```bash
openclaw config get channels.feishu
```

输出应包含 `accounts` 对象和 `defaultAccount` 字段：

```json
{
  "accounts": {
    "default": { "appId": "...", "appSecret": "..." },
    "ppt": { "appId": "...", "appSecret": "..." }
  },
  "defaultAccount": "default"
}
```

---

### 第三步：配置路由绑定

#### 3.1 添加 Agent 绑定

为每个 Agent 添加到对应 Feishu 账号的路由：

```bash
# HR-Agent 绑定到 default 账号
openclaw agents bind --agent hr-agent --bind feishu:default

# PPT-Agent 绑定到 ppt 账号
openclaw agents bind --agent ppt --bind feishu:ppt
```

#### 3.2 验证绑定

```bash
openclaw agents bindings
```

正确的输出应为：

```
Routing bindings:
- hr-agent <- feishu accountId=default
- ppt <- feishu accountId=ppt
```

---

### 第四步：验证配置

#### 4.1 验证配置文件格式

```bash
openclaw config validate
```

输出 `Config valid: ~/.openclaw/openclaw.json` 表示配置格式正确。

#### 4.2 检查 Gateway 状态

```bash
openclaw gateway status
```

确认 `Runtime: running` 和 `Connectivity probe: ok`。

#### 4.3 测试消息收发

通过飞书向各 Agent 发送私信，确认：
- HR-Agent 能正常回复（使用第一个 App）
- PPT-Agent 能正常回复（使用第二个 App）

---

### 第五步：重启 Gateway（如需要）

如果配置后 Agent 无法响应，可能需要重启 Gateway：

```bash
openclaw gateway restart
```

重启后等待几秒钟，让服务完全启动。

---

## 关键命令速查

| 操作 | 命令 |
|------|------|
| 添加账号 AppID | `openclaw config set channels.feishu.accounts.<账号名>.appId '"AppID"' --strict-json` |
| 添加账号 AppSecret | `openclaw config set channels.feishu.accounts.<账号名>.appSecret '"AppSecret"' --strict-json` |
| 设置默认账号 | `openclaw config set channels.feishu.defaultAccount '"账号名"' --strict-json` |
| 查看 Feishu 配置 | `openclaw config get channels.feishu` |
| 添加 Agent 绑定 | `openclaw agents bind --agent <agentId> --bind feishu:<accountId>` |
| 查看所有绑定 | `openclaw agents bindings` |
| 验证配置 | `openclaw config validate` |
| 重启 Gateway | `openclaw gateway restart` |

---

## 注意事项

### 1. 账号名字母数字符

账号名（如 `ppt`）只能包含小写字母、数字和短横线，不能以数字开头。

### 2. AppID 和 AppSecret 格式

- AppID 格式：`cli_xxxxxxxxxxxxxxxx`
- AppSecret：通常是 32-48 位的字母数字组合

### 3. 不要手动编辑 openclaw.json

建议使用 `openclaw config set` 命令修改配置，因为：
- 手动编辑可能触发 OpenClaw 的配置校验和恢复机制（创建 `.clobbered` 文件）
- CLI 命令会正确处理 JSON 格式和校验

### 4. 配置文件位置

- CLI 读取：`~/.openclaw/openclaw.json`
- Gateway 服务读取：`~/.openclaw/openclaw.json`（同一文件）

---

## 故障排查

### 问题：配置后 Agent 无法响应

**检查项：**
1. 绑定是否正确：`openclaw agents bindings`
2. Gateway 是否加载了新配置：重启 Gateway
3. Feishu App 是否启用了机器人功能
4. Feishu App 的权限是否包含机器人相关权限

### 问题：提示 "unknown channel id"

**原因：** 尝试使用 `channels.feishu-xxx` 格式创建新通道，但 OpenClaw 不支持这种格式。

**解决：** 使用 `channels.feishu.accounts.xxx` 方式在同一 Feishu 通道下创建多个账号。

### 问题：配置被还原/覆盖

**原因：** 手动编辑了 openclaw.json 或编辑格式不正确，触发了 OpenClaw 的自动还原机制。

**解决：** 使用 `openclaw config set` 命令修改配置，不要手动编辑。

---

## 总结

配置多个 Feishu App 的关键是：

1. **使用 `accounts` 结构**：在 `channels.feishu` 下创建多个账号
2. **使用 `accountId` 区分**：每个账号有唯一的 ID（如 `default`、`ppt`）
3. **使用 `bindings` 路由**：将不同 Agent 绑定到不同账号

这样，一个 OpenClaw 实例可以同时运行多个 Agent，每个 Agent 使用独立的飞书机器人，实现完全独立的通讯管理。
