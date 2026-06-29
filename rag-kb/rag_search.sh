#!/bin/bash
# RAG Knowledge Base Search Script
# Usage: ./rag_search.sh "your query here"

cd /root/.openclaw/workspace-HR-Agent/skills/raglite
source .venv/bin/activate

QUERY="$1"

cd /root/.openclaw/workspace-HR-Agent/skills/raglite
source .venv/bin/activate

python3 -c "
import os, sys, pickle, jieba
from rank_bm25 import BM25Okapi

KB_DIR = '/root/.openclaw/workspace-HR-Agent/rag-kb'
INDEX_FILE = os.path.join(KB_DIR, 'bm25_index.pkl')

def tokenize_chinese(text):
    return list(jieba.cut(text))

with open(INDEX_FILE, 'rb') as f:
    index_data = pickle.load(f)

bm25 = index_data['bm25']
documents = index_data['documents']
doc_sources = index_data['doc_sources']

query = '''${QUERY}'''
query_tokens = tokenize_chinese(query)
scores = bm25.get_scores(query_tokens)
top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:5]

print(f'Found results for: {query}')
print('='*50)
found = 0
for idx in top_indices:
    if scores[idx] > 0:
        found += 1
        print(f'\n[{found}] Score: {scores[idx]:.2f} | Source: {doc_sources[idx]}')
        print(f'    {documents[idx][:300]}...')
if found == 0:
    print('No results found.')
"
