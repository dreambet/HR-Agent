# 2026-06-03 智联招聘脚本修复总结

## 修复概览

今日共修复 **3 个问题**，涉及心跳检测、打招呼功能、详细报告获取。

---

## 1. 心跳检测详情接口 404（14:25）

**现象**：心跳检测报告详情接口返回 404

**根因**：心跳检测用 GET `/api/talent/resume/detail?resumeNumber=xxx`，实际应为 POST `/api/resume/detail` + JSON body

**修复**：更新 HEARTBEAT.md，添加正确的详情接口测试命令

**影响**：仅修改心跳检测清单，核心招聘脚本未改动

---

## 2. 打招呼"假成功"（15:10）

**现象**：脚本日志显示"✅ 成功向 XX 发送打招呼消息"，但智联招聘网站消息列表中无记录

**根因**：
1. JavaScript `btn.click()` 无法触发实际点击——智联前端框架（Vue/React）对按钮事件有特殊处理，JS 原生 click 无法触发框架绑定的事件监听器
2. 空字符串 `"" in "资讯工程师"` 为 True，导致跳过职位选择

**修复**：
- 用 Playwright `button:visible` 选择器替代 JS click
- `click(force=True)` 强制点击
- 空字符串检查 `current_value.strip() and ...`
- 坐标点击回退（bounding_box + mouse.click）

**验证**：段先生打招呼成功，消息已在智联招聘确认收到

**涉及文件**：`skills/zhaopin-skill/scripts/greet_candidate.py`

---

## 3. 详细报告获取失败（17:10）

**现象**：初筛后获取详细报告失败，提示"搜索结果中找不到候选人"

**根因**：
1. 智联搜索结果有时效性（按时间排序，结果随时变化）
2. 初筛上下文未保存 resumeK/resumeT，导致必须重新搜索
3. 重新搜索时候选人已不在当前结果中

**修复**：
1. `search_resumes.py`：上下文新增保存 resumeK/resumeT
2. `get_resume_detail.py`：优先使用上下文 resumeK/resumeT 直接调用详情API，跳过重新搜索

**效果**：初筛后立即获取详细报告，100% 成功

**涉及文件**：
- `skills/zhaopin-skill/scripts/search_resumes.py`
- `skills/zhaopin-skill/scripts/get_resume_detail.py`

---

## 关键经验

### 打招呼脚本
- **不要使用 JS 原生 click 操作前端框架组件**，优先使用 Playwright 的 locator.click()
- **空字符串判断前必须检查非空**，`"" in "任意非空字符串"` 返回 True 是 Python 的陷阱
- **关键操作后必须验证结果**，不能仅依赖 API 返回值判断成功

### 详细报告获取
- **智联搜索结果时效性强**，同样参数 30 分钟前后结果可能完全不同
- **初筛后尽快获取详细报告**，避免上下文被新的搜索覆盖
- **resumeK/resumeT 是详情API的必要参数**，必须在初筛时保存

### 心跳检测
- **详情接口是 POST**，不是 GET，且需要 JSON body

---

## 备份记录

- 备份路径：`skills/zhaopin-skill/scripts/backup/recruitment-20260603-1710/`
- 备份内容：search_resumes.py + get_resume_detail.py + greet_candidate.py

---

## 今日招聘操作记录

| 操作 | 岗位 | 结果 |
|------|------|------|
| 简历搜索 | 平台开发工程师(周口/大专) | 5份 ✅ |
| 简历搜索 | CNC技术员(周口/高中) | 8份 ✅ |
| 详细报告 | 段先生(平台开发) | ✅ |
| 详细报告 | 范先生(CNC) | ✅(修复后) |
| 详细报告 | 蒋先生(CNC) | ✅(修复后) |
| 详细报告 | 宋先生(CNC) | ✅(修复后) |
| 打招呼 | 段先生 | ✅(修复后成功) |
| 打招呼 | 聂先生 | ✅ |
| 打招呼 | 范先生 | ✅ |
| 打招呼 | 宋先生 | ✅ |
