# 招聘功能工作流及异常处理手册

## 核心脚本路径
- `skills/zhaopin-skill/scripts/search_resumes.py` — 简历搜索+初筛报告
- `skills/zhaopin-skill/scripts/get_resume_detail.py` — 详细简历获取
- `skills/zhaopin-skill/scripts/greet_candidate.py` — 打招呼联系
- 备用路径：`scripts/` 下为软链接，指向上述实际路径

## 报告存储路径
- 初筛报告：`/lhcos-datas/reports/初筛报告/`
- 详细报告：`/lhcos-datas/reports/详细报告/`
- 注意：不要手动传 --output 参数覆盖默认路径

## Cookie 管理
- 存储位置：`config/zhaopin_cookies.txt`
- 常见过期症状：API 返回非 200、搜索返回空或错误
- 验证命令：curl -b "$(cat config/zhaopin_cookies.txt | tr '\n' ';')" -X POST "https://rd6.zhaopin.com/api/talent/search/list" -d '{"coId":"200890090","keyword":"测试","pageNo":1,"pageSize":5}' -o /dev/null -w "%{http_code}"
- 更新方式：用户提供新 Cookie 后直接写入文件

## 常见异常及修复
### 1. 脚本找不到（scripts/目录为空）
- 原因：清理旧文件时删除了脚本
- 修复方法：有备份，从 skills/zhaopin-skill/scripts/backup/ 最新目录复制回来
- 命令：cp skills/zhaopin-skill/scripts/backup/recruitment-YYYYMMDD-HHMM/*.py skills/zhaopin-skill/scripts/

### 2. Cookie 过期
- 症状：搜索返回 401 或空结果
- 修复：从用户获取新 Cookie 更新 config/zhaopin_cookies.txt

### 3. 详情 API 返回错误候选人
- 原因：浏览器预取
- 修复：使用姓名精确匹配 + 缓冲区方案（脚本已支持）

### 4. 打招呼弹窗超时
- 原因：页面加载慢或弹窗被拦截
- 修复：脚本已内置重试机制，自动重新点击打招呼按钮

### 5. 报告生成路径错误
- 原因：手动传递 --output 参数覆盖默认路径
- 修复：不传 --output 参数，让脚本使用内置默认路径

## 每日开工前检查清单
1. ✅ Cookie 有效性（API 返回 200）
2. ✅ 三个核心脚本存在且语法正确
3. ✅ 磁盘空间充足（<80%）
4. ✅ 可用内存 > 1G
5. ✅ 定时任务正常运行

## 定时任务列表
- 智联心跳检测：每12小时，检查Cookie/API/系统资源
- RAG知识库同步：每日17:30
- 每日工作总结：每日17:30
