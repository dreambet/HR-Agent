# 详细报告获取失败技术修复详情（2026-06-03）

## 故障现象

初筛报告生成后，立即获取候选人详细报告时失败，日志显示：
- `[增强] 第X页返回 50 条`（搜索了20页共1000条）
- `⚠️ 发现同名但辅助字段不一致，跳过`（找到同名但年龄/经验不匹配）
- `⚠️ 候选人 'XX' 不在搜索结果中`
- 最终回退到浏览器点击流程，也失败

## 根因分析

### 问题1：搜索结果时效性

智联招聘的搜索API结果具有**强时效性**：
- 结果按时间排序（`sort: {type: "TIME"}`）
- 候选人简历更新、被其他HR联系、活跃状态变化都会影响排序
- 同样的搜索参数，30分钟前后结果可能完全不同

**验证**：
```
初筛时（16:49）：范先生(38岁)、宋先生(36岁) 在结果中
30分钟后（17:15）：同样参数搜索，这两位候选人已不在结果中
```

### 问题2：初筛上下文缺少关键字段

**原代码**（search_resumes.py `save_search_context`）：
```python
context = {
    "candidates": [
        {
            "name": r.get('姓名', ''),
            "resume_number": r.get('resumeNumber', ''),
            # ❌ 缺少 resumeK 和 resumeT
        }
        for r in resumes
    ]
}
```

**后果**：
- get_resume_detail.py 必须重新搜索才能获取 resumeK/resumeT
- 但搜索结果已变化，找不到原候选人
- 详情API要求必须有 resumeK 才能调用（`职位编号或加密串至少有一项不能为空`）

## 修复方案

### 修复1：search_resumes.py 保存 resumeK/resumeT

```python
# extract_resume_from_item 函数中新增：
'resumeK': item.get('resumeK', ''),
'resumeT': item.get('resumeT', ''),

# save_search_context 函数中新增：
"resumeK": r.get('resumeK', ''),
"resumeT": r.get('resumeT', ''),
```

### 修复2：get_resume_detail.py 优先使用上下文直接调用API

```python
# 优先使用上下文中的 resumeK/resumeT 直接调用详情API
ctx_resume_k = (context_candidate or {}).get('resumeK', '')
ctx_resume_t = (context_candidate or {}).get('resumeT', '')
ctx_resume_number = (context_candidate or {}).get('resume_number', '')

if ctx_resume_k and ctx_resume_number:
    # 直接调用详情API，跳过重新搜索
    raw_item = {
        'resumeNumber': ctx_resume_number,
        'resumeK': ctx_resume_k,
        'resumeT': ctx_resume_t or str(int(time.time() * 1000)),
        'resumeLanguage': '1',
    }
else:
    # 回退到搜索API查找
    raw_item = find_candidate_raw_item(...)
```

## 验证结果

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 初筛后立即获取详细报告 | ❌ 失败（搜索结果已变） | ✅ 成功（直接调用API） |
| 初筛后长时间再获取 | ❌ 失败 | ⚠️ 可能失败（上下文被覆盖） |
| 不在上下文中的候选人 | ❌ 失败 | ✅ 通过搜索API获取 |

## 涉及文件

- `skills/zhaopin-skill/scripts/search_resumes.py`（保存 resumeK/resumeT）
- `skills/zhaopin-skill/scripts/get_resume_detail.py`（优先使用上下文直接调用API）

## 快速排查清单

若日后详细报告再次获取失败：

1. 检查上下文：`python3 -c "import json; print(json.load(open('/tmp/zhaopin_search_context.json'))['candidates'])"`
2. 检查日志是否显示 `[增强] 上下文已含 resumeK/resumeT，直接调用详情API`
3. 如果显示 `[增强] 使用初筛一致搜索API查找候选人原始项`，说明上下文没有 resumeK/resumeT
4. 检查搜索结果是否包含目标候选人：用相同参数手动搜索
