# 2026-05-14 报告修复与卡片格式知识

## 📋 任务完成汇总

本次完成三项任务：
1. ✅ 面试提问暂不修复（已确认）
2. ✅ MEMORY.md 修复经验记录（已保存）
3. ✅ 卡片发送问题修复（已解决验证）

---

## 🔧 修复一：初筛报告工作经验显示错误

### 问题
初筛报告头部显示"工作经验:不限"，但用户要求是"3-5年"

### 根因
`search_resumes.py` 第949行调用 `generate_screening_report` 时漏传 `experience_req` 参数

### 修复代码
```python
# 修复前（漏掉 experience_req）
generate_screening_report(resumes, args.keywords, args.location, output_path, education_req=args.education)

# 修复后（已添加）
generate_screening_report(resumes, args.keywords, args.location, output_path, education_req=args.education, experience_req=args.experience)
```

---

## 🔧 修复二：详细报告"应聘岗位"和"期望薪资"显示错误

### 问题
1. 应聘岗位显示"未知岗位"
2. 期望薪资显示"未知"

### 根因
1. `extract_resume_from_detail_api` 函数只处理详情API数据
2. 期望薪资和期望职位在搜索API数据中，函数未提取
3. 函数签名缺少 `search_data` 参数

### 修复方案
1. 修改函数签名：`def extract_resume_from_detail_api(detail_data, candidate_name, search_data=None)`
2. 从 `search_data` 中提取 `desiredSalary` 和 `desiredJobType`
3. 将提取的数据存入 `resume_data` 的 `期望薪资` 和 `期望职位` 字段
4. 更新两处调用，传递 `target_resume_data`

### 关键代码
```python
# 函数签名修改
def extract_resume_from_detail_api(detail_data, candidate_name, search_data=None):
    # ...原有代码...
    
    # 在返回前添加
    if search_data:
        if not result.get('期望薪资'):
            result['期望薪资'] = search_data.get('desiredSalary', '')
        if not result.get('期望职位'):
            result['期望职位'] = search_data.get('desiredJobType', '')
```

### 调用处修改
```python
# 修复前
return extract_resume_from_detail_api(detail_api_response, candidate_name)

# 修复后
return extract_resume_from_detail_api(detail_api_response, candidate_name, target_resume_data)
```

### 默认值修复
```python
# 修复前
parser.add_argument('--job-title', '-j', default='未知岗位', help='应聘岗位（用于搜索）')

# 修复后
parser.add_argument('--job-title', '-j', default='面议', help='应聘岗位（用于搜索）')
```

### 报告模板修复
```python
# 修复前
**应聘岗位**：{job_title}

# 修复后
**应聘岗位**：{resume_data.get('期望职位') or job_title}
```

---

## 🔧 修复三：卡片发送400错误

### 问题
使用 `message(action=send, card={...})` 发送卡片时返回400错误

### 根因
错误地添加了 `msg_type: "interactive"`，导致请求格式不正确

### 正确格式（无需 msg_type）
```json
{
  "header": {
    "title": {"tag": "plain_text", "content": "标题"},
    "template": "blue"
  },
  "elements": [
    {"tag": "div", "text": {"tag": "lark_md", "content": "内容"}},
    {"tag": "hr"},
    {"tag": "note", "elements": [{"tag": "plain_text", "content": "备注"}]}
  ]
}
```

### 模板说明
- `header.template` 可选值：blue, red, green, purple, yellow, orange, default
- `text.content` 使用 `lark_md` 支持 Markdown 格式
- 分隔线使用 `{"tag": "hr"}`
- 备注使用 `{"tag": "note", "elements": [{"tag": "plain_text", "content": "..."}]}`

---

## 📁 报告存储路径

### 正确路径（脚本默认值，不要覆盖）
- 初筛报告：`/lhcos-datas/reports/初筛报告/智联招聘{岗位}简历初筛报告-{日期}.md`
- 详细报告：`/lhcos-datas/reports/详细报告/简历分析报告-{姓名}-{日期}.md`

### 正确做法
- ✅ **不传 `--output` 参数**，让脚本使用默认路径
- ❌ **不要手动指定 `--output`**，除非确认路径正确

---

## 📌 经验教训

1. **函数调用时检查参数完整性**：调用函数时必须传递所有必要的参数
2. **跨API数据合并**：详情API和搜索API数据不同，需要合并时要在函数间传递数据
3. **默认值要合理**："未知"表示不知道但应该有数据，"面议"表示该字段本身不适用于此场景
4. **卡片格式**：不要手动包含 msg_type，工具自动处理

---

## ⚠️ 强制规则

**任务结果汇报必须使用卡片形式！**

每次任务完成后，必须使用 `message(action=send, card={...})` 发送卡片汇报结果，不要使用普通文本回复。

卡片格式模板：
```json
{
  "header": {
    "title": {"tag": "plain_text", "content": "标题"},
    "template": "blue"
  },
  "elements": [...]
}
```
