# 打招呼脚本技术修复详情（2026-06-03）

## 故障现象

执行 `greet_candidate.py` 打招呼时，脚本日志显示"✅ 成功向 XX 发送打招呼消息"，但实际在智联招聘网站的消息列表中**未找到任何打招呼记录**，属于"假成功"。

## 根因分析

### 问题1：JavaScript click() 无法触发实际点击

**位置**：Step 7 - 点击"确定"按钮

**原因**：脚本使用 `page.evaluate()` 中的 `btn.click()`（JavaScript 原生点击）来点击"确定"按钮。但智联招聘的前端框架（可能是 Vue/React）对按钮事件有特殊处理，JS 原生 click 无法触发框架绑定的事件监听器。

**表现**：
- JS 返回 `{success: true}`，但按钮实际未被点击
- 截图显示"选择沟通职位"弹窗仍然打开，"取消"和"确定"按钮都还在页面上
- 脚本误判为成功，继续执行后续流程

### 问题2：空字符串误判为"职位已选中"

**位置**：Step 7 - 检查职位是否已选中

**原因**：检查逻辑为 `job_title.strip() in current_value.strip()`，当 `current_value` 为空字符串时，`"资讯工程师" in ""` 返回 False，但 `"" in "资讯工程师"` 返回 True，导致空值被误判为已选中。

**表现**：
- 日志显示 `[UI] 当前职位值: `（空值）
- 日志显示 `✅ 职位已选中: ，跳过下拉选择`
- 实际上职位未被选中，弹窗中没有正确设置

## 修复方案

### 修复1：Playwright locator 替代 JS click

**修改前**（错误）：
```python
js_result = page.evaluate("""() => {
    const modal = document.querySelector('.km-modal__wrapper');
    const buttons = modal.querySelectorAll('button');
    for (const btn of buttons) {
        if (btn.textContent.trim() === '确定') {
            btn.click();  // ❌ JS原生click，无法触发框架事件
            return { success: true };
        }
    }
}""")
```

**修改后**（正确）：
```python
# 用 Playwright locator 查找可见按钮
confirm_btn = None
modals = page.locator('.km-modal__wrapper').all()
for modal in modals:
    if not modal.is_visible():
        continue
    buttons = modal.locator('button:visible').all()
    for btn in buttons:
        txt = btn.text_content().strip()
        if txt in ('确定', '确认'):
            confirm_btn = btn
            break
    if confirm_btn:
        break

if confirm_btn:
    confirm_btn.click(force=True)  # ✅ Playwright强制点击
```

**关键差异**：
- 使用 `button:visible` 选择器，只匹配可见按钮
- 使用 `click(force=True)` 绕过可见性检查
- 使用 Playwright 的真实鼠标事件，而非 JS DOM click

### 修复2：空字符串检查

**修改前**（错误）：
```python
if job_title.strip() in current_value.strip() or current_value.strip() in job_title.strip():
    # 当 current_value="" 时，"" in "资讯工程师" → True → 误判
```

**修改后**（正确）：
```python
if current_value.strip() and (job_title.strip() in current_value.strip() or current_value.strip() in job_title.strip()):
    # 增加 current_value.strip() 非空检查
```

### 修复3：坐标点击回退方案

当 Playwright click 失败时，使用 bounding_box + mouse.click 作为兜底：

```python
try:
    confirm_btn.click(force=True)
except Exception as e:
    # 回退: 使用坐标点击
    box = confirm_btn.bounding_box()
    if box:
        page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
```

## 验证结果

| 验证项 | 修复前 | 修复后 |
|--------|--------|--------|
| 确定按钮点击 | JS click 假成功 | Playwright click 真实触发 |
| 职位选择 | 空值误判跳过 | 正确检测并执行选择 |
| 消息发送 | 假成功（弹窗未关闭） | 真成功（弹窗关闭，消息送达） |
| 智联网站验证 | 消息列表无记录 | 消息列表有记录 ✅ |

## 快速排查清单

若日后打招呼再次出现类似问题：

1. 检查截图 `/tmp/zhaopin_debug/greet_06_after_confirm.png` — 弹窗是否仍然打开？
2. 检查日志 `[UI] JavaScript点击结果` — 是否返回 success: true 但弹窗未关闭？
3. 检查日志 `[UI] 当前职位值` — 是否为空？
4. 检查日志 `button:visible` — 是否找到可见的确定按钮？
5. 如果 Playwright click 失败，检查 bounding_box 回退是否生效
