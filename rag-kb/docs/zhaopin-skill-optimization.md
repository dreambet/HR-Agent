# 智联招聘简历助手（zhaopin-skill）优化记录

## 2026-05-05 优化总结

### 问题一：初筛报告返回候选人数量过少

**现象描述：**
- 使用 COMPLEX 排序时，API 返回 `foundTotal: 2125` 但 `total: 2`
- 只抓取到 2 份简历，而非请求的 5 份
- 用户在浏览器看到 7 个候选人

**根本原因：**
- COMPLEX 排序算法采用多维度加权评分，只返回得分最高的 Top N 结果
- `pageSize` 设置过小，导致返回候选人不足

**解决方案：**
1. 将排序方式从 `COMPLEX` 改为 `TIME`（最新优先）
2. 将 `pageSize` 从 `count` 改为 `max(count * 2, 10)`
3. 确保能获取到用户请求数量的候选人

**修复代码：**
```python
payload = {
    "sort": {
        "type": "TIME",  # 改用最新优先排序
        "version": 0
    },
    "pageSize": max(count * 2, 10),  # 确保足够数量
    ...
}
```

---

### 问题二：educations 参数导致 API 返回异常

**现象描述：**
- 当 `educations=["1"]`（仅"不限"）时，API 返回 0 结果
- 但 `educations=["4", "3", "10", "1"]` 时正常返回

**根本原因：**
- 单独使用 `["1"]` 时 API 解析异常
- 需要使用完整的教育程度数组

**解决方案：**
```python
# 修复前
edu_levels = ["1"]

# 修复后
edu_levels = ["4", "3", "10", "1"]  # 大专、本科、硕士、不限
```

---

### 问题三：初筛报告不应生成 JSON 文件

**用户要求：**
- 只保存按模板输出的初筛报告（.md）
- 无需生成对应的 .json 文件

**解决方案：**
- 移除 JSON 文件生成逻辑
- 只保留 Markdown 报告输出

---

## API 关键技术参数

### 搜索 API
- URL: `https://rd6.zhaopin.com/api/talent/search/list`
- Method: POST
- 认证: Cookie（存储于 `config/zhaopin_cookies.txt`）

### 城市 ID 映射
| 城市 | ID |
|------|-----|
| 周口 | 734 |
| 郑州 | 701 |
| 北京 | 530 |
| 上海 | 538 |
| 深圳 | 765 |

### 教育程度 ID
| 学历 | ID |
|------|-----|
| 大专 | 3 |
| 本科 | 4 |
| 硕士 | 10 |
| 博士 | 5 |
| 不限 | 1 |

### 排序方式
| 排序 | 说明 |
|------|------|
| TIME | 最新优先 |
| COMPLEX | 复杂排序（默认，会过滤结果） |
| DEFAULT | 默认排序 |

---

## 技能文件路径

- 技能根目录: `/root/.openclaw/workspace-HR-Agent/skills/zhaopin-skill/`
- 搜索脚本: `scripts/search_resumes.py`
- 详情脚本: `scripts/get_resume_detail.py`
- Cookie 配置: `/root/.openclaw/workspace-HR-Agent/config/zhaopin_cookies.txt`
- 报告输出: `/lhcos-datas/reports/初筛报告/`、`/lhcos-datas/reports/详细报告/`

---

## ⚠️ 重要：两个不同的API接口

### API 1：搜索 API（用于初筛）
- **URL**: `POST https://rd6.zhaopin.com/api/talent/search/list`
- **用途**: 获取候选人列表，生成初筛报告
- **调用场景**: 用户提供招聘条件后，第一次搜索获取候选人列表

### API 2：详情 API（用于详细简历）
- **URL**: `POST https://rd6.zhaopin.com/api/resume/detail`
- **用途**: 获取特定候选人的详细简历
- **调用场景**: 用户指定某个候选人后，获取其详细简历
- **触发方式**: 点击候选人卡片时拦截，或直接调用该接口
- **所需参数**:
  - `resumeNumber`: 简历编号（从搜索结果获取）
  - `resumeLanguage`: "1"
  - `k`: 加密 key（从搜索结果获取）
  - `t`: 时间戳

### 关键区别
| 操作 | API接口 | 脚本 |
|------|---------|------|
| 初筛报告 | `/api/talent/search/list` | `search_resumes.py` |
| 详细报告 | `/api/resume/detail` | `get_resume_detail.py` |`

---

## 2026-05-07 修复：详细简历获取接口调用

### 问题描述
用户反馈获取详细简历时数据不完整，仅有基础信息。

### 根本原因
之前调用的是**搜索 API** (`/api/talent/search/list`)，而非**详情 API** (`/api/resume/detail`)。

另一个关键问题是**工作流程错误**：
- 错误：直接在搜索框输入候选人姓名（如"葛先生"）进行搜索
- 正确：先输入**岗位名称**（如"平台开发工程师"）搜索，再在结果中点击候选人卡片

### 详情 API 接口信息
- URL: `POST https://rd6.zhaopin.com/api/resume/detail`
- 触发方式：通过 Playwright 点击候选人卡片时拦截
- 所需参数：
  - `resumeNumber`: 简历编号
  - `resumeLanguage`: "1"
  - `k`: 加密 key（从搜索结果获取）
  - `t`: 时间戳

### API 响应数据结构
```json
{
  "code": 200,
  "data": {
    "user": {           // 用户基本信息
      "name": "葛先生",
      "ageLabel": "33岁",
      "genderLabel": "男",
      "workYearsLabel": "9年",
      "maxEducationLabel": "本科",
      "careerStateLabel": "在职-正在找工作",
      "cityLabel": "现居北京 昌平区"
    },
    "resume": {          // 详细简历信息
      "workExperiences": [...],  // 工作经历
      "educationExperiences": [...],  // 教育经历
      "projectExperiences": [...],  // 项目经历
      "skillTags": [...],     // 技能标签
      "selfEvaluation": "..."  // 自我评价
    }
  }
}
```

### 正确的实现流程
1. 访问搜索页面 `https://rd6.zhaopin.com/app/search`
2. 输入**岗位关键词**（不是候选人姓名！）
3. 点击搜索按钮
4. 在搜索结果中查找目标候选人
5. 点击候选人卡片，**拦截详情 API 调用**
6. 从 API 响应中提取完整数据
7. 生成详细报告

### 关键修复代码
```python
# 拦截详情 API
def handle_response(response):
    if 'resume/detail' in response.url:
        data = response.json()
        if data.get('code') == 200:
            resume_detail_data = data

# 解析工作经历
for exp in resume.get('workExperiences', []):
    company = exp.get('orgName', '') or exp.get('simpleOrgName', '')
    position = exp.get('jobTitle', '')
    desc = exp.get('description', '')
```

### 验证结果
- ✅ 姓名: 葛先生
- ✅ 工作经历: 6条（拓保软件、长城汽车、集度科技等）
- ✅ 教育经历: 1条（南阳理工学院 软件工程 本科）
- ✅ 技能标签: web前端, 功能测试, 联调
- ✅ 自我评价: 完整的技能描述

---

## 2026-05-07 工作流程修正：正确两步流程

### 问题描述
用户反馈工作流程混乱，表现为：
- 生成初筛报告后，直接自动生成多份详细报告
- 没有等待用户指定需要哪些候选人的详细报告

### 正确的两步流程

**第一步：生成初筛报告**
- 根据用户提供的招聘条件（岗位名称、工作地点、学历要求、工作经验等）
- 从智联招聘搜索匹配的候选人
- 生成**初筛报告**（初筛报告），展示所有候选人的概览和排名
- 输出候选人列表，供用户筛选

**第二步：生成详细报告（等待用户指定）**
- 用户查看初筛报告后，指定需要哪几位候选人的详细报告
- 只有用户明确指定后，才生成对应的**详细报告**
- 不是自动获取全部候选人简历，而是按需获取

### 错误流程（修正前）
1. 搜索候选人
2. 生成初筛报告
3. ❌ 直接自动获取5份详细简历（没有等待用户指定）

### 正确流程（修正后）
1. 搜索候选人
2. 生成初筛报告
3. ✅ 展示候选人列表，等待用户指定
4. 用户指定后，获取指定候选人的详细简历
5. 生成详细报告

### 关键原则
- **初筛报告是给用户看的选人依据**
- **详细报告需要用户明确指定候选人**
- 不要自动生成多份详细报告，要等用户需求

## 2026-05-07 下午 问题修复：详情API拦截

### 问题现象
get_resume_detail.py 脚本始终无法捕获详情API响应，最终回退到使用搜索API数据。

### 根本原因
原脚本使用两个独立的响应处理器：
1. `handle_search_response` - 监听搜索API
2. `handle_detail_response` - 监听详情API

代码逻辑是：搜索 → 找到候选人 → 移除搜索处理器 → 添加详情处理器 → 点击卡片 → 等待详情响应

问题出在处理器切换时，Playwright的监听器管理出现时序问题，导致详情API响应无法被捕获。

### 解决方案
改用**单一响应处理器**，根据URL判断API类型：

```python
def handle_response(response):
    nonlocal search_api_response, detail_api_response, target_resume_data
    url = response.url
    
    # 处理搜索API响应
    if '/api/talent/search/list' in url and response.status == 200:
        # ... 处理搜索数据 ...
    
    # 处理详情API响应
    if '/api/resume/detail' in url and response.status == 200:
        # ... 处理详情数据 ...
```

### 关键修改
1. 定义单个 `handle_response` 函数，根据URL判断API类型
2. 整个会话只注册一次处理器：`page.on('response', handle_response)`
3. 删除 `page.remove_listener` 和第二次 `page.on` 调用

### 第二个问题：skill_tags解析
详情API返回的 `skillTags` 是字符串列表 `['python', 'Java']`，而不是字典列表。原代码假设是字典列表，导致 `.get('name', '')` 调用失败。

**修复**：
```python
skills_list = [tag if isinstance(tag, str) else tag.get('name', '') for tag in skill_tags]
```

### 验证结果
```
✅ 拦截到搜索API响应
✅ 在搜索结果中找到目标候选人: 周先生
✅ 拦截到详情API响应 (3次)
✅ 成功获取详情API响应
解析完成: 姓名=周先生, 工作经历=6条, 教育经历=1条, 项目经历=3条
```

**注意**：详情API会调用3次（可能是因为前端 prefetch 或多个组件各自请求），脚本只取最后一次响应。

---

## 2026-05-07 16:40 修复：点击卡片后返回错误候选人数据

### 问题现象
用户反馈：搜索结果中找到周先生（索引0），但点击卡片后详情API返回了祝先生的数据。

### 排查过程
1. 搜索API正确找到周先生在索引0
2. DOM卡片顺序也正确（索引0=周先生）
3. 点击索引0后，详情API却返回了祝先生

### 根本原因分析
1. **页面预取机制**：页面加载搜索结果时，会预加载所有候选人的详情数据（prefetch）
2. **点击不触发新请求**：当用户点击卡片时，浏览器使用已预取的缓存数据，不会发起新的API请求
3. **时序问题**：预取响应在搜索API返回之前就已到达，导致跳过预取时丢失数据

### 解决方案：缓冲+精确名称匹配
不再依赖"点击后捕获新响应"，而是：
1. **缓冲所有详情API响应**（包括预取响应）
2. 搜索API返回后获得目标候选人姓名
3. 在缓冲中查找**精确名称匹配**的响应（而非模糊匹配）
4. 匹配成功直接使用，无需等待点击后的新响应

### 关键代码
```python
# 搜索API响应后，扫描缓冲找精确name匹配
for buffered in detail_api_buffer:
    buffered_user_name = buffered.get('data', {}).get('user', {}).get('name', '')
    if buffered_user_name == candidate_name:  # 精确匹配，不是 fuzzy
        detail_api_response = buffered
        break
```

### 字段说明
- 搜索API返回的候选人信息中有 `resumeNumber`（格式如 `ZtSVePjMyOda149X)fv1p2Awgy8iPEr4`）
- 详情API响应中 resume 对象的字段是 `id`（纯数字），与 resumeNumber 格式不同
- 因此无法通过 resumeNumber 做精确匹配，只能用姓名匹配

### 验证结果
```
📋 详情API响应: 王女士, 彭先生, 程先生, 周先生 (4条缓冲)
✅ name匹配: 周先生 == 周先生
解析完成: 工作经历=6条, 教育经历=1条, 项目经历=3条
简历来源: 详情API ✅
```

---

## 2026-05-07 17:48 修复：工作经历模块无信息显示

### 问题现象
生成的详细报告中，"工作经历"模块显示为空白或"工作经历详情见基本信息"，没有实际内容。

### 根本原因
`get_resume_detail.py` 中有两套数据提取函数，字段名称不一致：

| 函数 | 公司字段 |
|------|---------|
| 搜索API数据提取 | `companyName` |
| 详情API数据提取 | `orgName`（或 `simpleOrgName`）|
| `summarize_work_experience()` 总结函数 | `companyName` |

当使用详情API数据时，`summarize_work_experience()` 查找 `companyName` 字段，但详情API返回的是 `orgName`，导致匹配失败，回退到"工作经历详情见基本信息"。

### 解决方案
修改 `summarize_work_experience()` 函数，检查多个可能的字段名：

```python
# 修复前
company = exp.get('companyName', '')

# 修复后
company = exp.get('orgName', '') or exp.get('simpleOrgName', '') or exp.get('companyName', '')
```

### 验证结果
修复后工作经历正常显示：
```
## 💼 工作经历
联合利华（中国）有限公司 | 数据开发工程师 | 时间不详
科大讯飞股份有限公司 | 算法工程师 | 时间不详
深圳市军海互联网有限责任公司 | 实施工程师 | 时间不详
...
（共6条工作经历）
```

---

## 常见字段名差异（搜索API vs 详情API）

### 工作经历字段对比

| 数据项 | 搜索API字段 | 详情API字段 |
|--------|------------|-------------|
| 公司名称 | `companyName` (简称) | `orgName` (全称) 或 `simpleOrgName` (简称) |
| 职位名称 | `jobTitle` | `jobTitle` |
| 时间段 | `beginDate` + `endDate` (如 "2026.01" + "至今") | `timeLabel` (如 "2025.08 - 至今 (9个月)") |
| 时间戳 | - | `beginTime` + `endTime` (毫秒时间戳，0表示至今) |
| 工作时长 | `duration` (如 "4个月") | - |
| 工作描述 | 无 | `description` (完整工作内容) |
| 工作数量 | 3条 | 6条 (更完整) |

### 关键发现
- **搜索API**：只返回简要信息，`companyName`是简称，无`description`
- **详情API**：返回完整信息，`orgName`是全称，有完整`description`
- **时间格式**：搜索API用字符串，详情API用`timeLabel`格式化字符串

### 建议
在数据处理函数中同时检查多个可能的字段名：
```python
company = exp.get('orgName', '') or exp.get('simpleOrgName', '') or exp.get('companyName', '')
time_label = exp.get('timeLabel', '')  # 详情API优先用这个
```

---

## 2026-05-07 18:54 最终修复：工作经历完整内容显示

### 问题
1. 工作经历时间显示为"时间不详"（使用了错误的字段）
2. 工作内容描述没有完整显示（被截断或缺失）

### 根因分析

**问题1：时间不正确**
- 原代码使用 `duration` 字段（搜索API使用）
- 详情API的`duration`为空，应该使用 `timeLabel` 字段

**问题2：工作内容缺失**
- 原代码对 `description` 截断到500字符
- 搜索API根本不返回 `description`

### 解决方案

**extract_resume_from_detail_api 函数修复：**
```python
# 修复前
duration = exp.get('duration', '')
exp_str = f"{duration} {company} {position}"
if description:
    exp_str += f"\n    {description[:500]}"

# 修复后
time_label = exp.get('timeLabel', '')  # 详情API使用timeLabel
description = exp.get('description', '')
exp_str = f"{company} | {position} | {time_label}"
if description:
    exp_str += f"\n\n{description}"  # 完整内容，不截断
```

**summarize_work_experience 函数修复：**
```python
# 优先使用已格式化的完整工作经历（包含描述）
formatted_work_exps = resume_data.get('工作经历', [])
if formatted_work_exps:
    return '\n\n'.join(formatted_work_exps)

# 回退到处理原始数据
time_label = exp.get('timeLabel', '')
if not time_label:
    # 处理搜索API数据...
```

### 验证结果
修复后工作经历完整显示：
```
## 💼 工作经历

联合利华（中国）有限公司 | 数据开发工程师 | 2026.01 - 至今 (4个月)

1.数据表设计与构建：根据业务需求，在Azure Databricks中使用Spark SQL设计并创建了ODS和DWD表...
2.数据存储、清洗与去重：从表中读取原始数据...
3.管道配置与调度：使用Azure Data Factory配置ETL管道...

科大讯飞股份有限公司 | 算法工程师 | 2025.09 - 2026.01 (4个月)

1.解析接口返回的JSON数据...
...
```

### 文件更新
- `/root/.openclaw/workspace-HR-Agent/skills/zhaopin-skill/scripts/get_resume_detail.py`
