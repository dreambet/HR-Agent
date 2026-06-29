# 2026-05-29 招聘流程调试总结

## 关键发现

### 1. 页面DOM结构变更
- 智联招聘候选人列表页面选择器已从 `.search-resume-item-wrap` 变更为 `.recommend-item`
- 老选择器返回0个元素
- 影响：greet_candidate.py 的候选人定位和点击打招呼按钮功能

### 2. 页面 vs API 候选人不一致
- 页面使用推荐算法展示候选人
- API使用搜索过滤条件返回候选人
- 两者候选人列表可能完全不同
- 按名字在页面上可能找不到API搜索到的候选人
- 解决方案：增加fallback逻辑，如果按名字找不到则打招呼页面上第一个候选人

### 3. Headless模式限制
- headless浏览器无法通过WebSocket发送消息
- AI招呼语对话框点击"使用并发送"后对话框关闭但消息未实际发送
- 在真实浏览器中应可正常工作

### 4. Cookie更新注意事项
- 2026-05-29更新了两次Cookie（Bing和Chrome）
- Bing浏览器Cookie在部分功能上不如Chrome稳定
- Cookie可能被其他设备登录踢出（错误码4）

### 5. 脚本回退教训
- 回退前必须先诊断根本原因
- 选择器问题只需要修改选择器，不需要回退整个脚本
- 回退会丢失所有已做的优化
- 正确诊断流程：检查DOM结构 → 检查Cookie → 检查代码逻辑

## 当前三个核心脚本状态
- search_resumes.py：搜索API正常，初筛报告生成正常
- get_resume_detail.py：详情API正常，详细报告生成正常
- greet_candidate.py：选择器已更新，但headless模式有发送限制