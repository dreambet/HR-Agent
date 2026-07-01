#!/bin/bash
# RAG Knowledge Base Search Script (Hybrid: BM25 + TF-IDF Rerank)
# Usage: ./rag_search.sh "your query here"

cd /root/.openclaw/workspace-HR-Agent/skills/raglite
source .venv/bin/activate

QUERY="$1"

python3 << PYEOF
import os, sys, pickle
import numpy as np
import jieba
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_DIR = '/root/.openclaw/workspace-HR-Agent/rag-kb'
BM25_INDEX = os.path.join(KB_DIR, 'bm25_index.pkl')

def tokenize_chinese(text):
    return list(jieba.cut(text))

# ===== Load BM25 Index =====
with open(BM25_INDEX, 'rb') as f:
    index_data = pickle.load(f)

bm25 = index_data['bm25']
documents = index_data['documents']
doc_sources = index_data['doc_sources']

query = '''${QUERY}'''

# ===== Phase 1: BM25 Recall (Top 20) =====
query_tokens = tokenize_chinese(query)
scores = bm25.get_scores(query_tokens)
bm25_top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:20]

# ===== Phase 2: TF-IDF Vector Rerank =====
candidates = [documents[i] for i in bm25_top]
all_texts = [query] + candidates

# Build TF-IDF on the fly (lightweight, no model download)
vectorizer = TfidfVectorizer(
    tokenizer=tokenize_chinese,
    lowercase=False,
    max_features=5000
)
tfidf_matrix = vectorizer.fit_transform(all_texts)
query_vec = tfidf_matrix[0:1]
doc_vecs = tfidf_matrix[1:]

sims = cosine_similarity(query_vec, doc_vecs)[0]

# Rerank by TF-IDF similarity
reranked = sorted(zip(bm25_top, sims), key=lambda x: x[1], reverse=True)
final_indices = [x[0] for x in reranked[:5]]

# ===== Output =====
print(f'🔍 Query: {query}')
print(f'{"="*60}')
print(f'📊 Mode: Hybrid (BM25 recall + TF-IDF rerank)')

found = 0
for idx in final_indices:
    if scores[idx] > 0:
        found += 1
        tfidf_sim = [s for i, s in zip(bm25_top, sims) if i == idx]
        sim_str = f" | TF-IDF: {tfidf_sim[0]:.3f}" if tfidf_sim else ""
        print(f'\n[{found}] BM25: {scores[idx]:.2f}{sim_str}')
        print(f'    📄 {doc_sources[idx]}')
        preview = documents[idx][:300].replace('\n', ' ')
        print(f'    {preview}...')

if found == 0:
    print('No results found.')
PYEOF
