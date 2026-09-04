# 🎯 HR-Agent — 智能招聘助手

> 基于 OpenClaw + 智联招聘企业版 API 的 **7×24 自动招聘副驾**：简历搜索、结构化分析、主动联系、IM 双向沟通，全程飞书协同。

说句话就能找人 — `抓取简历(5份) 岗位名称：平台开发工程师 期望工作地：周口-东莞 学历要求：专科及以上 经验要求：不限`

---

## ✨ 核心能力

| 能力 | 说明 | 状态 |
|------|------|------|
| 🔍 简历初筛 | API 直连智联企业版，多城市/多条件筛选，生成飞书文档报告 | ✅ 生产可用 |
| 📋 详细简历分析 | 按序号精确定位，生成人物画像/匹配度/面试建议全维度报告 | ✅ 生产可用 |
| 💬 主动打招呼 | 浏览器自动化，自动匹配职位 + AI 个性化招呼语，**三重验证防假成功** | ✅ 生产可用 |
| 📩 IM 双向沟通 | 5 分钟轮询候选人消息 → 飞书群推送，群内「回复 姓名 内容」直达 | ✅ 生产可用 |
| 📎 附件简历下载 | 候选人发来的附件简历自动识别下载 | ✅ 生产可用 |
| 🩺 链路心跳检测 | 每日 04:00 自动体检 Cookie/接口/简历库水位 | ✅ 生产可用 |
| 🧠 RAG 自我进化 | 每日 17:30 自动沉淀知识点，故障可秒级检索历史解法 | ✅ 生产可用 |
| 🌆 多城市支持 | 一次搜索覆盖多个城市（周口-深圳-东莞 → 三城同时检索） | ✅ 生产可用 |

---

## 🚀 快速开始

### 安装

```bash
# 1. 克隆仓库
git clone git@github.com:dreambet/HR-Agent.git ~/.openclaw/workspace-HR-Agent

# 2. 安装依赖
pip install requests playwright
playwright install chromium

# 3. 配置智联 Cookie（登录 rd6.zhaopin.com → F12 → 复制 Cookie）
cat > config/zhaopin_cookies.txt << 'EOF'
rd-staff-id=xxx; at=xxx; rt=xxx; ...
EOF
```

### 三种用法

| 方式 | 示例 | 适用场景 |
|------|------|----------|
| 💬 **飞书群指令** | `抓取简历(5份) 岗位名称：XX ...` | 日常招聘操作（推荐） |
| 💻 **命令行** | `python3 scripts/search_resumes.py -k "XX"` | 脚本调试 / 集成 |
| 🤖 **IM 回复指令** | `回复 张三 您好，方便电话沟通吗？` | 群内直接回复候选人 |

---

## 📖 使用指南

### 1️⃣ 简历初筛

飞书群发送：

```
抓取简历（5份）
岗位名称：平台开发工程师
期望工作地：周口-东莞        ← 支持多城市，用 - 分隔
学历要求：专科及以上
经验要求：不限
```

自动完成：搜索 → 过滤 → 生成飞书文档 → 群卡片推送（附链接）

### 2️⃣ 详细简历分析

```
获取序号4的详细报告          ← 按序号精确定位（同名候选人不混淆）
```
或
```
获取康先生的详细报告
```

### 3️⃣ 主动打招呼

```
帮我联系一下康先生
```
或
```
联系序号5
```

自动执行：定位候选人 → 匹配企业职位 → 生成 AI 个性化招呼语 → 发送 → **三重验证**（API 响应 + 弹窗关闭 + 无告警）

### 4️⃣ IM 双向沟通

```
回复 黄定平 您好，EPM职位在招
```

候选人回复后 **5 分钟内**自动推送到飞书群（含姓名/岗位/原文/时间），可直接在群内继续对话。

### 命令行速查

```bash
# 搜索简历（初筛）
python3 scripts/search_resumes.py \
  --keywords "平台开发工程师" --location "周口-东莞" \
  --education "专科及以上" --count 5

# 获取详细简历
python3 scripts/get_resume_detail.py --name "康先生" --index 1 --keyword "平台开发工程师"

# 打招呼（自动读取初筛上下文的多城市地点）
python3 scripts/greet_candidate.py --name "康先生" --index 1

# 手动轮询 IM 新消息
python3 scripts/im_cron.py
```

---

## 📂 目录结构

```
HR-Agent/
├── scripts/                              # 核心脚本（搜索/分析/打招呼）
│   ├── search_resumes.py                 # 🔍 简历搜索 + 初筛报告
│   ├── get_resume_detail.py              # 📋 详细简历分析
│   ├── greet_candidate.py                # 💬 打招呼（健壮版）
│   ├── share_report_to_feishu.py         # 📎 飞书文档分享
│   ├── check_zhaopin_status.py           # 🩺 健康检查
│   ├── cleanup_temp_reports.sh           # 🧹 临时报告清理
│   └── extract_today_sessions.py         # 📇 会话存档提取
├── skills/zhaopin-skill/
│   ├── SKILL.md                          # 技能完整文档
│   ├── references/zhaopin_guide.md       # 网站结构/选择器参考
│   └── scripts/
│       ├── im_monitor.py                 # 📩 IM 消息监控/回复
│       ├── im_cron.py                    # ⏱ IM 5分钟轮询包装
│       ├── im_reply.py                   # ✉️ 群内「回复 XX」快捷指令
│       ├── zhaopin_heartbeat.py          # 🩺 链路心跳检测
│       ├── search_resumes.py             # 🔍 搜索（与根目录联动）
│       ├── get_resume_detail.py          # 📋 详情
│       ├── greet_candidate.py            # 💬 打招呼
│       └── backup/                       # 历史稳定版本备份
├── config/
│   └── zhaopin_cookies.txt               # 智联 Cookie（不入库）
├── rag-kb/                               # RAG 知识库（BM25 + Jieba）
├── docs/                                 # 使用与架构文档
└── memory/                               # 每日工作日志（不入库）
```

---

## 📊 报告格式

### 初筛报告（10 列排名表）

| 章节 | 内容 |
|------|------|
| 📊 候选人排名 | 序号/姓名/性别/年龄/工作年限/学历/教育经历/期望薪资/匹配度/备注 |
| 📄 简历详情 | 每人：基本信息、求职意向、活跃状态、工作经历、技能、证书 |
| 💡 招聘建议 | 现状分析、推荐策略、面试建议 |

### 详细报告

| 章节 | 内容 |
|------|------|
| 🎯 人物画像 | 核心标签、职业路径、个人优势、风险提示 |
| 🔍 匹配度评估 | 匹配分析表 + 亮点 + 差距 |
| 💡 面试建议 | 结论、考察方向、参考提问、背调关注点、薪资谈判 |
| 📋 基本信息 | 2 列表格 |
| 💼🚀🎓🛠️📝 | 工作经历、项目经历、教育背景、技能证书、自我评价 |

---

## ⚙️ 自动化任务（cron）

| 任务 | 频率 | 说明 |
|------|------|------|
| 智联 IM 消息轮询 | 工作日 8-12、13-17 点每 5 分钟 | 候选人消息零遗漏，自动推送飞书群 |
| 链路心跳检测 | 每日 04:00 | Cookie 有效性 + 接口可用性 + 简历库水位 |
| 每日工作总结 | 周一至周六 17:30 | 当日候选人动态汇总 |
| RAG 知识同步 | 周一至周六 17:30 | 经验自动沉淀入知识库 |

---

## 🛠️ 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| Agent 平台 | OpenClaw | AI Agent 运行时 |
| 飞书集成 | 飞书开放平台 | 消息收发 + 文档创建 + 权限管理 |
| 简历数据源 | 智联招聘企业版 API | rd6.zhaopin.com |
| 浏览器自动化 | Playwright | 打招呼流程 |
| 知识库 | BM25 + Jieba | 本地 RAG 检索，零外传 |
| 会话存档 | JSONL | IM 状态跟踪与去重 |

---

## ⚠️ 注意事项

1. **数据真实性**：所有数据均来自智联 API 实时返回，**严禁捏造**
2. **隐私保护**：候选人信息仅供内部招聘使用，严禁外泄
3. **Cookie 有效期**：智联 Cookie 通常 7-14 天失效，失效后需招聘官手动更新（系统会告警）
4. **打招呼验证**：成功判定基于「发送 API 响应 + 弹窗关闭 + 无告警」三重证据，杜绝假成功
5. **职位匹配**：打招呼挂载的沟通职位为自动匹配结果，如企业无对应岗位会兜底选相似职位

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
