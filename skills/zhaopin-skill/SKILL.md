---
name: zhaopin-skill
description: 智联招聘简历自动化抓取与分析技能。通过飞书交互接收招聘需求，自动从智联招聘网站抓取简历，生成初筛报告和详细分析报告。当用户需要：(1) 在智联招聘上搜索简历 (2) 生成简历初筛报告 (3) 生成详细简历分析报告 (4) 将简历数据存入结构化表格时触发此技能。
---

# 智联招聘自动化技能 (zhaopin-skill)

## 概述

本技能实现从智联招聘网站自动抓取简历、生成结构化分析报告的全流程招聘自动化。

**数据来源：** 所有数据均来自智联招聘 rd6.zhaopin.com 企业版接口返回的真实数据，**严禁捏造任何数据**。

---

## 工作流程

### 阶段一：接收招聘需求（飞书交互）

用户发送招聘需求，格式如下：
```
抓取简历(N份)
岗位名称：xxxxx
期望工作地：xxxx
学历要求：本科/大专
经验要求：1-3年
```

**关键字段：**
- 简历数量（N）
- 岗位名称
- 工作地点
- 学历要求
- 经验要求

### 阶段二：初筛简历抓取与报告生成

**执行脚本：** `scripts/search_resumes.py`

**流程：**
1. 使用 Cookie 认证调用智联招聘搜索 API
2. 根据岗位关键词、地区、学历等条件搜索简历
3. 抓取初筛字段并过滤（经验、学历等）
4. 生成临时 Markdown 报告到 `/tmp/`
5. 创建飞书文档并写入完整内容
6. 使用 `create_table` + `write_table_cells` 插入候选人排名表格
7. 使用 `scripts/share_report_to_feishu.py` 分享给招聘组群
8. 发送飞书卡片，附带文档链接
9. 清理 `/tmp/` 临时文件

**❌ 不再保存到本地目录或 cosfs**，飞书文档为最终载体。

**初筛报告格式（严格遵循模版）：**
- 标题 + 元数据 → 📊 候选人匹配度排名表格（8列）→ 📄 简历详情（每人完整信息）→ 💡 招聘建议 → 页脚
- 表格列：序号 | 姓名 | 性别/年龄 | 工作年限 | 学历 | 教育经历 | 期望薪资 | 匹配度/备注
- 每人详情：基本信息、求职意向、活跃状态、工作经历、技能标签、证书、推荐理由、简历类型

### 阶段三：详细简历分析与报告生成

**执行脚本：** `scripts/get_resume_detail.py`

**流程：**
1. 根据姓名+序号查找对应候选人（支持同名区分）
2. 优先使用搜索上下文中的 resumeK/resumeT 直接调用详情API
3. 解析详细简历数据
4. 生成临时 Markdown 报告到 `/tmp/`
5. 创建飞书文档并写入内容
6. 使用 `create_table` + `parent_block_id` 插入匹配分析表格（3列）和基本信息表格（2列）
7. 分享给招聘组群
8. 发送飞书卡片，附带文档链接
9. 清理 `/tmp/` 临时文件

**详细报告格式（严格遵循模版）：**
- 🎯 人物画像（核心标签、职业发展路径、个人优势、风险提示）
- 🔍 岗位匹配度评估（匹配分析表格 3列 + 匹配亮点 + 存在差距）
- 💡 面试建议（面试结论、重点考察方向、参考提问问题、背景调查关注点、薪资谈判建议）
- 📋 基本信息表格（2列）
- 💼 工作经历、🚀 项目经历、🎓 教育背景、🛠️ 技能证书、📝 自我评价

### 阶段四：主动打招呼

**执行脚本：** `scripts/greet_candidate.py`

**流程：**
1. 根据姓名+序号定位候选人
2. 自动匹配企业职位
3. 使用默认AI招呼语发送
4. 发送结果卡片到飞书群组

### 阶段五：结构化数据存储（可选）

**执行脚本：** `scripts/store_resume_data.py`

**流程：**
1. 解析详细简历数据
2. 以表格形式存储到 CSV

---

## 脚本说明

### scripts/search_resumes.py

搜索智联招聘简历并生成初筛报告。

**参数：**
- `--keywords` / `-k` - 岗位关键词（必填）
- `--location` / `-l` - 工作地点（可选）
- `--education` / `-e` - 学历要求（可选）
- `--experience` / `-exp` - 工作经验要求（可选）
- `--count` / `-c` - 简历数量（默认5）
- `--output` / `-o` - 输出报告路径（默认使用 `/tmp/`）
- `--screenshot` / `-s` - 启用截图（默认关闭）
- `--cookies` - Cookie 字符串（可选）

**用法：**
```bash
python3 scripts/search_resumes.py \
  --keywords "平台开发工程师" \
  --location "河南-周口" \
  --education "本科" \
  --experience "1-3年" \
  --count 6 \
  --output /tmp/初筛报告.md
```

### scripts/get_resume_detail.py

获取单个候选人详细简历。

**参数：**
- `--name` / `-n` - 候选人姓名（必填）
- `--index` / `-i` - 初筛报告中的序号（1-based，用于精确定位同名候选人）
- `--keyword` / `-k` - 搜索关键词（岗位名称）
- `--location` / `-l` - 工作地点
- `--education` / `-e` - 学历要求
- `--experience` / `-exp` - 工作经验要求
- `--output` / `-o` - 输出报告路径
- `--screenshot` / `-s` - 启用截图（默认关闭）
- `--cookies` - Cookie 字符串（可选）

**用法：**
```bash
python3 scripts/get_resume_detail.py \
  --name "康先生" \
  --index 1 \
  --keyword "平台开发工程师" \
  --location "河南-周口" \
  --education "本科" \
  --experience "1-3年" \
  --output /tmp/详细报告.md
```

### scripts/greet_candidate.py

对指定候选人发送打招呼消息。

**参数：**
- `--name` / `-n` - 候选人姓名（必填）
- `--index` / `-i` - 候选人序号（1-based）
- `--keyword` / `-k` - 搜索关键词（岗位名称）
- `--location` / `-l` - 工作地点
- `--education` / `-e` - 学历要求
- `--experience` / `-exp` - 工作经验要求
- `--screenshot` / `-s` - 每步操作后截图调试（默认关闭）
- `--cookies` - Cookie 字符串（可选）

**用法：**
```bash
python3 scripts/greet_candidate.py \
  --name "康先生" \
  --index 1 \
  --keyword "平台开发工程师" \
  --location "河南-周口"
```

### scripts/share_report_to_feishu.py

将飞书文档分享给招聘组群。

**参数：**
- `--doc-id` / `-d` - 飞书文档 ID（必填）
- `--group-id` / `-g` - 群组 ID（默认招聘组群）

**用法：**
```bash
python3 scripts/share_report_to_feishu.py --doc-id "LoVrdjeKbo96VlxK7FpctFH9nGc"
```

### scripts/store_resume_data.py

将简历数据解析并存储为 CSV 表格。

**参数：**
- `--input` - 报告文件路径（必填）
- `--output` - CSV 输出路径（必填）
- `--overwrite` - 覆盖已有文件（可选）

---

## 飞书文档生成规范

### 表格创建规则
- 表格最大 8 列，最大行数约 8-9 行
- 使用 `parent_block_id` 参数将表格插入到正确的标题下方
- 先 delete 占位文本，再 create_table 到正确 parent_block_id
- 匹配分析表格和基本信息表格**分别独立呈现**，不合并

### 流程
```
1. feishu_doc create → 创建文档壳
2. feishu_doc write → 写入完整 Markdown 内容（不含表格）
3. feishu_doc delete_block → 删除占位文本
4. feishu_doc create_table + write_table_cells → 插入表格到指定位置
5. share_report_to_feishu.py → 分享给招聘组群
6. message → 发送卡片（附文档链接）
7. rm /tmp/*.md → 清理临时文件
```

---

## ⚠️ 截图功能规则

| 脚本 | 默认状态 | 触发条件 |
|------|---------|---------|
| search_resumes.py | ❌ 关闭 | `--screenshot` / `-s` |
| get_resume_detail.py | ❌ 关闭 | `--screenshot` / `-s` |
| greet_candidate.py | ❌ 关闭 | `--screenshot` / `-s` |

截图功能**不是自动执行的**，只有用户明确要求时才启用。

---

## 配置文件

智联招聘 Cookie 配置：`/root/.openclaw/workspace-HR-Agent/config/zhaopin_cookies.txt`

**Cookie 获取方法：**
1. 在浏览器中登录智联招聘企业版 (https://rd6.zhaopin.com)
2. 按 F12 打开开发者工具
3. 切换到 Network（网络）标签
4. 刷新页面
5. 点击任意一个请求
6. 在 Request Headers 中找到 Cookie 字段
7. 复制完整的 Cookie 字符串到配置文件

**注意：** Cookie 优先从配置文件读取，如需更新请编辑该文件。

---

## 注意事项

1. **隐私保护：** 所有候选人信息仅供内部招聘使用，严禁外泄
2. **Cookie 有效期：** 智联招聘 Cookie 通常有时效，如遇认证失败请更新 Cookie
3. **反爬限制：** 请合理控制请求频率
4. **数据真实性：** 所有输出数据均来自智联招聘接口的真实返回，严禁捏造
5. **报告存储：** 飞书文档为最终载体，不保存本地副本，不保存到 cosfs
6. **序号定向：** 用户说"获取序号X"时，直接按序号对应 resumeNumber 获取，不做二次确认

---

## 已验证功能状态

| 功能 | 状态 | 说明 |
|------|------|------|
| Cookie 登录 rd6.zhaopin.com | ✅ 正常 | 使用企业版 Cookie 可正常访问 |
| 简历搜索 API | ✅ 正常 | 可根据关键词搜索候选人 |
| 初筛报告生成 | ✅ 正常 | 生成飞书文档 + 群卡片链接 |
| 详细简历获取 | ✅ 正常 | 详情API直接调用 |
| 详细报告生成 | ✅ 正常 | 生成飞书文档 + 群卡片链接 |
| 主动打招呼 | ✅ 正常 | 自动匹配职位并发送AI招呼语 |
| 飞书文档分享 | ✅ 正常 | 自动分享给招聘组群 |
| CSV 存储 | ✅ 正常 | 将简历数据存储为表格 |

## 参考文档

详细的智联招聘网站结构和选择器说明，请参阅：
- `references/zhaopin_guide.md` - 网站结构、Cookie获取方法、页面选择器等
