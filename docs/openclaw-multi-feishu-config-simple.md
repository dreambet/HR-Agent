# OpenClaw 配置第三个 Feishu Agent

## 只需 2 步

---

### 第一步：添加第三个 Feishu 账号凭据

```bash
openclaw config set channels.feishu.accounts.<账号名>.appId '"AppID"' --strict-json
openclaw config set channels.feishu.accounts.<账号名>.appSecret '"AppSecret"' --strict-json
```

**示例**（假设第三个 Agent 叫 `xxx`，账号名也叫 `xxx`）：
```bash
openclaw config set channels.feishu.accounts.xxx.appId '"cli_xxxxxxxxxxxxxxxx"' --strict-json
openclaw config set channels.feishu.accounts.xxx.appSecret '"你的AppSecret"' --strict-json
```

---

### 第二步：绑定 Agent 到该账号

```bash
openclaw agents bind --agent <AgentID> --bind feishu:<账号名>
```

**示例**：
```bash
openclaw agents bind --agent xxx --bind feishu:xxx
```

---

### 验证

```bash
openclaw agents bindings
```

确认输出包含你的新 Agent 绑定。

---

## 完整示例（直接复制修改）

假设：
- 第三个 Agent ID：`third`
- 账号名：`third`
- App ID：`cli_abc123`
- App Secret：`xxx`

```bash
# 1. 添加凭据
openclaw config set channels.feishu.accounts.third.appId '"cli_abc123"' --strict-json
openclaw config set channels.feishu.accounts.third.appSecret '"xxx"' --strict-json

# 2. 绑定
openclaw agents bind --agent third --bind feishu:third

# 3. 验证
openclaw agents bindings
```
