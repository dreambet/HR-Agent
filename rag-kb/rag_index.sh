#!/bin/bash
# RAG Knowledge Base Index Script
# Usage: ./rag_index.sh

cd /root/.openclaw/workspace-HR-Agent/skills/raglite
source .venv/bin/activate

python3 << 'PYEOF'
import os
import pickle
import jieba
from rank_bm25 import BM25Okapi

KB_DIR = "/root/.openclaw/workspace-HR-Agent/rag-kb"
INDEX_FILE = os.path.join(KB_DIR, "bm25_index.pkl")
DOCS_DIR = os.path.join(KB_DIR, "docs")

def tokenize_chinese(text):
    return list(jieba.cut(text))

print("Building BM25 index...")

documents = []
doc_ids = []
doc_sources = []

for filename in os.listdir(DOCS_DIR):
    if filename.endswith('.md'):
        filepath = os.path.join(DOCS_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        chunks = content.split('\n\n')
        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if chunk:
                documents.append(chunk)
                doc_ids.append(f"{filename}-{i}")
                doc_sources.append(filename)

print(f"Loaded {len(documents)} documents from {len(set(doc_sources))} files")

tokenized_docs = [tokenize_chinese(doc) for doc in documents]
bm25 = BM25Okapi(tokenized_docs)

index_data = {
    "bm25": bm25,
    "documents": documents,
    "doc_ids": doc_ids,
    "doc_sources": doc_sources
}

with open(INDEX_FILE, 'wb') as f:
    pickle.dump(index_data, f)

print(f"Index saved to {INDEX_FILE}")
print("Done!")
PYEOF
