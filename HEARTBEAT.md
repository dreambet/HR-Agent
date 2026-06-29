# 每日巡检清单

## 早上第一个心跳（08:00-10:00 时段）执行开工检查

- [ ] 搜索接口：`curl -b "$(cat config/zhaopin_cookies.txt | tr '\n' ';')" -X POST "https://rd6.zhaopin.com/api/talent/search/list" -H "Content-Type: application/json" -d '{"coId":"200890090","keyword":"测试","pageNo":1,"pageSize":1}' -o /dev/null -w "%{http_code}"` → 应为 200
- [ ] 详情接口：`curl -b "$(cat config/zhaopin_cookies.txt | tr '\n' ';')" -X POST "https://rd6.zhaopin.com/api/resume/detail" -H "Content-Type: application/json" -d '{"resumeNumber":"test","k":"test","t":"test","resumeLanguage":"1"}' -o /dev/null -w "%{http_code}"` → 应为 200（业务code可能为400，但HTTP状态码应为200，非404）
- [ ] 三个核心脚本存在：`scripts/search_resumes.py`, `scripts/get_resume_detail.py`, `scripts/greet_candidate.py`
- [ ] 磁盘 < 80%：`df -h / | tail -1 | awk '{print $5}'`
- [ ] 内存 > 1G 可用：`free -h | grep Mem | awk '{print $7}'`
- [ ] 定时任务正常：`openclaw cron list`
- [ ] 备份存在：`ls -1t skills/zhaopin-skill/scripts/backup/ | head -1`

## 异常时

1. 先查 RAG：`bash rag-kb/rag_search.sh "故障现象"`
2. 再查会话存档：检查当日及近期 memory 文件
3. 仍解决不了再想新方案

## 非早上时段

- 保持静默，除非有异常告警