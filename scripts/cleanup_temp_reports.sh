#!/bin/bash
# 全流程结束后自动清理临时报告文件
# 保留 zhaopin_search_context.json（详细报告依赖）
# 调用方式：bash scripts/cleanup_temp_reports.sh

echo "🧹 清理临时报告文件..."

# 临时报告 .md 文件（已写入飞书文档，可安全删除）
count_md=$(ls /tmp/简历分析报告-*.md 2>/dev/null | wc -l)
rm -f /tmp/简历分析报告-*.md
echo "  ✅ 删除 $count_md 个临时报告文件"

# 旧附件缓存（已改用内存 base64）
if [ -d /tmp/zhaopin_attachments ]; then
    rm -rf /tmp/zhaopin_attachments
    echo "  ✅ 删除旧附件缓存"
fi

# 调试截图
if [ -d /tmp/zhaopin_debug ]; then
    rm -rf /tmp/zhaopin_debug
    echo "  ✅ 删除调试截图"
fi

# 保留检查
if [ -f /tmp/zhaopin_search_context.json ]; then
    echo "  ✅ 搜索上下文已保留"
fi

echo "✅ 清理完成"
