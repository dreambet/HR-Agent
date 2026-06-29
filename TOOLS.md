# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Web Fetch Workflow

**重要规则：** 当常规 `web_fetch` 被网站拒绝时（如 403、Cloudflare 保护等），使用 web-content-fetcher 获取网页内容：

```bash
# 首选 r.jina.ai（最稳定）
curl -s "https://r.jina.ai/{url}"

# Cloudflare 专用
curl -s "https://markdown.new/{url}"

# 备用方案
curl -s "https://defuddle.md/{url}"
```

**使用场景：**
- 网站返回 403 或其他错误时
- Cloudflare 验证页面阻止访问时
- 需要获取被保护网页的内容时

## Summarize Skill

- CLI 路径：`/root/.nvm/versions/node/v22.22.2/bin/summarize`
- 版本：0.14.1
- 用法：`summarize "<url>" --length medium`

## Tavily Search

- API Key：已配置在环境中（tvly-dev-3mqGLc-...）
- 配额：1000次/月（免费）
- 用法：`TAVILY_API_KEY="..." python3 <skill-path>/scripts/tavily_search.py "query"`

## Agent Browser

- CLI 路径：已安装但浏览器未激活
- 状态：Chrome 下载失败，需手动运行 `agent-browser install`

## RAG 知识库 (BM25 + Jieba)

本地 RAG 知识库，支持中文语义搜索。用于持续学习和知识积累。

**目录：**
- 知识库根目录：`/root/.openclaw/workspace-HR-Agent/rag-kb/`
- 文档目录：`rag-kb/docs/`
- 索引文件：`rag-kb/bm25_index.pkl`
- 搜索脚本：`rag-kb/rag_search.sh`
- 索引脚本：`rag-kb/rag_index.sh`

**使用方法：**

```bash
# 搜索知识库
cd /root/.openclaw/workspace-HR-Agent/rag-kb
./rag_search.sh "婉聘的核心能力是什么？"

# 重新索引（添加新文档后）
cd /root/.openclaw/workspace-HR-Agent/rag-kb
./rag_index.sh
```

**添加新文档：**
1. 将 Markdown 文件放入 `rag-kb/docs/` 目录
2. 运行 `./rag_index.sh` 重新构建索引
3. 使用 `./rag_search.sh "查询内容"` 进行搜索

**当前已索引文档：**
- wanpin-info.md（婉聘身份、能力、技能列表等）

**技术栈：**
- BM25 关键词排序算法
- Jieba 中文分词
- rank_bm25 库
