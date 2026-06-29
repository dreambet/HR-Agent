# 脚本稳定版备份
**备份时间**: 2026-05-22 10:58
**备份原因**: 经过多轮调试验证，所有脚本功能正常稳定

## 已验证功能
- ✅ search_resumes.py: 搜索API正常，初筛报告生成正常
- ✅ get_resume_detail.py: 详情API正常，详细报告生成正常  
- ✅ greet_candidate.py: 精确选择器，发错人问题已修复
  - 软硬件开发岗 → 资讯工程师 映射规则
  - 统一招呼语格式
- ✅ Cookie有效期: 正常

## 回退方法
```bash
cp backup/2026-05-22_stable/search_resumes.py ../search_resumes.py
cp backup/2026-05-22_stable/get_resume_detail.py ../get_resume_detail.py
cp backup/2026-05-22_stable/greet_candidate.py ../greet_candidate.py
```
