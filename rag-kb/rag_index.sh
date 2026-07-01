#!/bin/bash
# RAG Knowledge Base Index Script (Hybrid: BM25 + FAISS Vector)
# Usage: ./rag_index.sh

cd /root/.openclaw/workspace-HR-Agent/skills/raglite
source .venv/bin/activate

python3 << 'PYEOF'
import os, pickle, json, sys
import jieba
from rank_bm25 import BM25Okapi

KB_DIR = "/root/.openclaw/workspace-HR-Agent/rag-kb"
BM25_INDEX = os.path.join(KB_DIR, "bm25_index.pkl")
DOCS_DIR = os.path.join(KB_DIR, "docs")

def tokenize_chinese(text):
    return list(jieba.cut(text))

# ===== Phase 1: BM25 Index =====
print("📚 Phase 1: Building BM25 index...")

documents = []
doc_ids = []
doc_sources = []

for filename in sorted(os.listdir(DOCS_DIR)):
    if filename.endswith('.md'):
        filepath = os.path.join(DOCS_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        chunks = content.split('\n\n')
        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if chunk and len(chunk) > 20:  # skip very short chunks
                documents.append(chunk)
                doc_ids.append(f"{filename}-{i}")
                doc_sources.append(filename)

print(f"   Loaded {len(documents)} chunks from {len(set(doc_sources))} files")

tokenized_docs = [tokenize_chinese(doc) for doc in documents]
bm25 = BM25Okapi(tokenized_docs)

bm25_data = {
    "bm25": bm25,
    "documents": documents,
    "doc_ids": doc_ids,
    "doc_sources": doc_sources
}
with open(BM25_INDEX, 'wb') as f:
    pickle.dump(bm25_data, f)
print(f"   ✅ BM25 index saved ({len(documents)} docs)")

print("\n✅ Index build complete (BM25 only — vector index disabled for stability)!")
PYEOF
