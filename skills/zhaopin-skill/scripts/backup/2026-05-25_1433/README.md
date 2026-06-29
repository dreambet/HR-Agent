# 招聘功能完整备份
备份时间：2026-05-25 14:33
备份标记：2026-05-25_1433

## 包含文件
- search_resumes.py       初筛报告脚本
- get_resume_detail.py    详细简历报告脚本
- greet_candidate.py       打招呼脚本
- zhaopin_search_context.json  当前搜索上下文
- MEMORY.md               长期记忆
- LEARNINGS.md            学习记录
- zhaopin_cookies.txt     Cookie配置

## 核心优化记录（2026-05-25）
- get_city_id 增强解析：支持"市-区"/"省-市"格式（深圳-宝安→765）
- greet_candidate 新增--index参数：序号定向联系
- get_resume_detail 新增--index参数：序号定向获取详细报告
- greet_candidate 城市映射修复：郑州762→701，宝安734→765
- greet_candidate 新增城市：惠州773、清溪779
- get_resume_detail 新增城市：惠州773、清溪779
- search_resumes 新增城市：宝安765、惠州773、清溪779
- 打招呼搜索过滤参数增强：注入教育/经验/排序/城市等参数
- 同名候选人去重逻辑：多字段辅助匹配（年龄+工作年限+学历）

## 恢复方法
# 恢复所有脚本
cp backup/2026-05-25_1433/*.py skills/zhaopin-skill/scripts/

# 验证语法
python3 -m py_compile skills/zhaopin-skill/scripts/search_resumes.py
python3 -m py_compile skills/zhaopin-skill/scripts/get_resume_detail.py
python3 -m py_compile skills/zhaopin-skill/scripts/greet_candidate.py
