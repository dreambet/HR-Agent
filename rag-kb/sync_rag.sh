#!/bin/bash
# RAG 知识库每日同步脚本
# 功能：将每日知识点文档同步到 RAG 知识库

RAG_DIR="/root/.openclaw/workspace-HR-Agent/rag-kb"
MEMORY_DIR="/root/.openclaw/workspace-HR-Agent/memory"

echo "开始 RAG 知识库同步..."

# 获取今天的日期
TODAY=$(date +%Y-%m-%d)
MEMORY_FILE="${MEMORY_DIR}/${TODAY}.md"

# 检查是否有今日的记忆文件
if [ -f "$MEMORY_FILE" ]; then
    echo "找到今日记忆文件: $MEMORY_FILE"
    
    # 检查是否已有今日的 RAG 文档
    TODAY_DOC="${RAG_DIR}/docs/${TODAY}-updates.md"
    if [ ! -f "$TODAY_DOC" ]; then
        echo "创建今日 RAG 文档: $TODAY_DOC"
        
        # 从记忆文件中提取知识点，生成 RAG 文档
        # 这里可以添加更复杂的解析逻辑
        cat > "$TODAY_DOC" << DOC
# ${TODAY} 知识库更新

## 来自记忆文件的自动同步内容

（此文件由系统自动生成）

## 相关记忆文件
DOC
        echo "" >> "$TODAY_DOC"
        echo "- ${MEMORY_FILE}" >> "$TODAY_DOC"
        echo "" >> "$TODAY_DOC"
        echo '```' >> "$TODAY_DOC"
        head -100 "$MEMORY_FILE" >> "$TODAY_DOC"
        echo '```' >> "$TODAY_DOC"
    else
        echo "今日 RAG 文档已存在: $TODAY_DOC"
    fi
else
    echo "未找到今日记忆文件: $MEMORY_FILE"
    echo "创建占位文档..."
    cat > "${RAG_DIR}/docs/${TODAY}-updates.md" << DOC
# ${TODAY} 知识库更新

今日无重大更新。
DOC
fi

# 重建索引
echo "重建 RAG 索引..."
cd "$RAG_DIR"
./rag_index.sh

echo "RAG 知识库同步完成！"
