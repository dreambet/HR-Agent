# HR-Agent 🎯

基于 OpenClaw 的智能招聘助手，集成智联招聘，支持飞书协同。

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 简历初筛 | 按岗位/地区/学历/经验自动搜索候选人，生成结构化初筛报告 |
| 📋 详细分析 | 获取候选人完整简历，生成匹配度评估 + 面试建议 |
| 💬 主动打招呼 | 浏览器自动化向候选人发送AI招呼语 |
| 📎 飞书文档 | 报告以飞书文档形式呈现，群卡片附链接，在线预览/下载 |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+
- OpenClaw Gateway
- Playwright（用于打招呼功能）

### 安装

```bash
git clone git@github.com:dreambet/HR-Agent.git
cd HR-Agent
```

### 配置

1. **飞书应用**：在飞书开放平台创建应用，启用以下权限：
   - `docx:document`（文档读写）
   - `docx:document:create`
   - `drive:drive`（云空间）
   - `docs:permission.member:create`（文档分享）
   - `im:message`（消息发送）

2. **智联招聘 Cookie**：
   - 登录 rd6.zhaopin.com
   - 获取 Cookie 存入 `config/zhaopin_cookies.txt`

### 使用

通过飞书群聊向 Bot 发送指令：

```
抓取简历（6份）
岗位名称：平台开发工程师
期望工作地：河南-周口
学历要求：本科
经验要求：1-3年
```

Bot 自动执行搜索 → 生成飞书文档 → 发送群卡片（附文档链接）。

## 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/search_resumes.py` | 简历搜索 + 初筛报告 |
| `scripts/get_resume_detail.py` | 获取候选人详细简历 |
| `scripts/greet_candidate.py` | 主动打招呼 |
| `scripts/share_report_to_feishu.py` | 飞书文档分享 |

## 报告格式

### 初筛报告
- 📊 候选人排名表格（8列）
- 📄 每位候选人完整详情
- 💡 招聘建议

### 详细报告
- 🎯 人物画像
- 🔍 岗位匹配度评估
- 💡 面试建议
- 📋 基本信息
- 💼 工作经历 / 🚀 项目经历

## 技能文档

详见 `skills/zhaopin-skill/SKILL.md`

## 许可证

仅供内部招聘使用。
