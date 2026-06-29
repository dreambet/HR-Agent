# 智联招聘打招呼脚本修复记录（2026-06-05）

## 问题现象

打招呼脚本（greet_candidate.py）报告"✅ 成功向候选人发送打招呼消息"，但智联招聘消息列表中实际没有发出消息。此问题称为"假成功"。

## 根因分析

### 第一层：JS click 假成功

**问题**："使用并发送"按钮使用 JavaScript `btn.click()` 触发，但智联招聘前端框架（KMUI/Vue）不响应原生 JS click 事件。

**表现**：脚本打印"✅ 点击'使用并发送'成功"，但实际没有触发发送。

**修复**：改用 Playwright `click(force=True)` + 坐标点击回退兜底。

```python
# ❌ 错误：JS click 假成功
send_result = page.evaluate("""() => {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
        if (btn.textContent.includes('使用并发送')) {
            btn.click();  // 不触发实际点击
            return { success: true };
        }
    }
}""")

# ✅ 正确：Playwright 真实点击
send_btn = page.locator('button:visible', has_text='使用并发送').first
send_btn.click(force=True)
```

### 第二层：模态框遮挡导致填写失败

**问题**：切换到"自己设置招呼语"后，模态框遮挡层阻止了 textarea 的点击和填写。

**表现**：Playwright fill() 超时，报错 `<div class="km-modal__wrapper ai-greeting-modal"> intercepts pointer events`。

**修复**：跳过"自己设置招呼语"切换，直接使用系统默认 AI 招呼语。AI 招呼语由系统自动填充，不存在遮挡填写失败的问题。

```python
# ❌ 错误：切换到自定义招呼语（会被遮挡）
switch_to_custom_greeting(page)  # 模态框遮挡
textarea.fill(greeting_msg)      # 填写失败

# ✅ 正确：直接使用默认 AI 招呼语
print("使用默认AI招呼语，直接发送...")
page.wait_for_timeout(500)
```

### 第三层：验证机制缺失

**问题**：脚本仅检查对话框是否关闭，未验证发送是否真正成功。

**修复**：新增多重验证机制：
- Toast 监控（检测"已获取过人才联系方式"等提示）
- 网络请求监控（捕获发送 API 调用）
- 职位选择值验证
- 对话框关闭确认

## 关键经验教训

### 1. 智联招聘 KMUI 框架不响应 JS click

智联招聘使用 KMUI（基于 Vue）组件框架，所有模态框内的按钮都不能用 JavaScript `btn.click()` 触发，必须使用 Playwright 的真实点击事件。

**规则**：智联招聘页面上**所有按钮点击**都应使用 Playwright click，不使用 JS click。包括：
- 打招呼按钮
- 确定按钮
- 使用并发送按钮
- 职位选择下拉

### 2. 模态框遮挡层会阻止底层元素操作

智联招聘的模态框有遮挡层（overlay），会阻止对底层元素的点击和填写。

**解决方案**：
- 优先使用系统默认功能，避免自定义操作被遮挡
- Playwright `click(force=True)` 可以绕过遮挡层点击
- 但 `fill()` 不能绕过遮挡层

### 3. "成功"不可靠，需要多重验证

脚本报告的"成功"可能只是 UI 状态变化（如对话框关闭），不代表实际发送成功。

**验证方法**：
- 检查 Toast 提示
- 监控网络请求
- 验证输入框值
- 检查对话框是否真正关闭

### 4. "已获取过人才联系方式，本次免费"是正常提示

当候选人已被联系过时，智联招聘会弹出此 Toast 提示。这不是错误，而是确认提示。

## 涉及文件

- `skills/zhaopin-skill/scripts/greet_candidate.py` - 打招呼脚本
- `skills/zhaopin-skill/scripts/search_resumes.py` - 搜索脚本（上下文保存）
- `skills/zhaopin-skill/scripts/get_resume_detail.py` - 详情脚本

## 修复时间线

| 时间 | 修复内容 | 状态 |
|------|---------|------|
| 2026-06-03 | "确定"按钮改用 Playwright click | ✅ |
| 2026-06-05 16:04 | "使用并发送"按钮改用 Playwright click | ✅ |
| 2026-06-05 16:25 | 跳过自定义招呼语，使用默认 AI 招呼语 | ✅ |
| 2026-06-05 16:45 | 新增 Toast/网络/职位值多重验证 | ✅ |
| 2026-06-05 17:25 | 测试验证：蒋先生打招呼成功 | ✅ |
