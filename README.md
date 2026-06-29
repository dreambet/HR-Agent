# 🎯 HR-Agent — 智能招聘助手

基于 OpenClaw 的智联招聘自动化技能，通过飞书协同完成简历搜索、分析、联系全流程。

> 说句话就能找人 — "帮我搜6份平台开发工程师简历，周口，本科，1-3年"

---

## ✨ 特性

- **飞书原生交互** — 群聊中发指令，Bot 自动执行并返回结果
- **API 直连智联** — 调用智联招聘企业版 API，数据 100% 真实
- **飞书文档报告** — 报告以飞书文档呈现，群卡片附链接，在线预览/下载
- **结构化分析** — 候选人排名表格、匹配度评估、面试建议一键生成
- **一键打招呼** — 浏览器自动化，自动匹配职位并发送 AI 招呼语
- **同名区分** — 支持序号精确定位同名候选人
- **经验自适应** — 某地区候选人经验普遍超出时，自动放宽并注明原因

---

## 📦 安装

### 环境要求

- Python 3.12+
- Node.js 22+
- OpenClaw Gateway
- Playwright（用于打招呼浏览器自动化）

### 克隆仓库

```bash
git clone git@github.com:dreambet/HR-Agent.git ~/.openclaw/workspace-HR-Agent
```

### 安装依赖

```bash
pip install requests playwright
playwright install chromium
```

---

## 🚀 使用

### 1. 简历初筛

在飞书群聊中发送：

```
抓取简历（6份）
岗位名称：平台开发工程师
期望工作地：河南-周口
学历要求：本科
经验要求：1-3年
```

Bot 自动执行：搜索 → 过滤 → 生成飞书文档 → 发送群卡片（附文档链接）

### 2. 获取详细报告

```
获取康先生的详细报告
```

或按序号：

```
获取序号4的详细报告
```

### 3. 主动联系候选人

```
帮我联系一下康先生
```

Bot 自动打开智联招聘 → 定位候选人 → 匹配职位 → 发送招呼语

### 命令行使用

```bash
# 搜索简历
python3 scripts/search_resumes.py \
  --keywords "平台开发工程师" \
  --location "河南-周口" \
  --education "本科" \
  --experience "1-3年" \
  --count 6

# 获取详细简历
python3 scripts/get_resume_detail.py \
  --name "康先生" \
  --index 1 \
  --keyword "平台开发工程师"

# 打招呼
python3 scripts/greet_candidate.py \
  --name "康先生" \
  --index 1 \
  --keyword "平台开发工程师"
```

---

## 📂 目录结构

```
HR-Agent/
├── README.md                          # 本文件
├── AGENTS.md                          # Agent 行为规范
├── SOUL.md                            # Agent 人格定义
├── IDENTITY.md                        # 身份信息
├── USER.md                            # 用户偏好
├── TOOLS.md                           # 工具配置
├── HEARTBEAT.md                       # 心跳巡检清单
├── config/
│   └── zhaopin_cookies.txt            # 智联招聘 Cookie（不入库）
├── scripts/
│   ├── search_resumes.py              # 🔍 简历搜索 + 初筛报告
│   ├── get_resume_detail.py           # 📋 详细简历获取
│   ├── greet_candidate.py             # 💬 主动打招呼
│   ├── share_report_to_feishu.py      # 📎 飞书文档分享
│   └── check_zhaopin_status.py        # 🩺 健康检查
├── skills/
│   └── zhaopin-skill/
│       ├── SKILL.md                   # 技能完整文档
│       ├── references/
│       │   └── zhaopin_guide.md       # 网站结构/选择器参考
│       └── scripts/
│           ├── search_resumes.py      # 脚本本体（符号链接）
│           ├── get_resume_detail.py
│           ├── greet_candidate.py
│           ├── zhaopin_heartbeat.py   # 心跳检测
│           └── backup/                # 历史稳定版本备份
├── rag-kb/                            # RAG 知识库
│   ├── docs/                          # 知识文档
│   ├── bm25_index.pkl                 # BM25 索引
│   └── rag_search.sh                  # 搜索脚本
└── docs/                              # 配置参考文档
```

---

## 📊 报告格式

### 初筛报告

| 章节 | 内容 |
|------|------|
| 📊 候选人排名 | 8 列表格：序号/姓名/性别年龄/年限/学历/教育经历/薪资/匹配度 |
| 📄 简历详情 | 每人：基本信息、求职意向、活跃状态、工作经历、技能、证书 |
| 💡 招聘建议 | 现状分析、推荐策略、面试建议 |

### 详细报告

| 章节 | 内容 |
|------|------|
| 🎯 人物画像 | 核心标签、职业路径、个人优势、风险提示 |
| 🔍 匹配度评估 | 3 列匹配表格 + 亮点 + 差距 |
| 💡 面试建议 | 结论、考察方向、提问问题、背调关注点、薪资谈判 |
| 📋 基本信息 | 2 列表格 |
| 💼🚀🎓🛠️📝 | 工作经历、项目经历、教育背景、技能证书、自我评价 |

---

## 🛠️ 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| Agent 平台 | OpenClaw | AI Agent 运行时 |
| 飞书集成 | 飞书开放平台 | 消息收发 + 文档创建 + 权限管理 |
| 简历数据源 | 智联招聘 API | rd6.zhaopin.com 企业版 |
| 浏览器自动化 | Playwright | 打招呼流程 |
| 搜索 | Tavily API | 网页搜索（可选） |
| RAG | BM25 + Jieba | 本地知识库检索 |
| 云存储 | 腾讯云 COS | cosfs 挂载（可选） |

---

## ⚙️ 配置

### 飞书应用权限

在飞书开放平台启用：

| 权限 | 用途 |
|------|------|
| `docx:document` | 文档读写 |
| `docx:document:create` | 创建文档 |
| `drive:drive` | 云空间 |
| `docs:permission.member:create` | 文档分享给群组 |
| `im:message` | 消息收发 |
| `im:message.group_msg` | 群消息 |

### 智联招聘 Cookie

```bash
# 登录 rd6.zhaopin.com 后获取 Cookie
cat > config/zhaopin_cookies.txt << 'EOF'
rd-staff-id=xxx; at=xxx; rt=xxx; ...
EOF
```

---

## 🤝 贡献

欢迎 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 创建 Pull Request

---

## 📄 License

仅供内部招聘使用。

---

## 🙏 致谢

- [OpenClaw](https://openclaw.ai) — AI Agent 平台
- [智联招聘](https://rd6.zhaopin.com) — 企业招聘平台
- [飞书](https://feishu.cn) — 协同办公平台
- [Playwright](https://playwright.dev) — 浏览器自动化
