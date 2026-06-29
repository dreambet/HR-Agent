# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice
**Areas**: frontend | backend | infra | tests | docs | config
**Statuses**: pending | in_progress | resolved | wont_fix | promoted | promoted_to_skill

## Status Definitions

| Status | Meaning |
|--------|---------|
| `pending` | Not yet addressed |
| `in_progress` | Actively being worked on |
| `resolved` | Issue fixed or knowledge integrated |
| `wont_fix` | Decided not to address (reason in Resolution) |
| `promoted` | Elevated to CLAUDE.md, AGENTS.md, or copilot-instructions.md |
| `promoted_to_skill` | Extracted as a reusable skill |

## Skill Extraction Fields

When a learning is promoted to a skill, add these fields:

```markdown
**Status**: promoted_to_skill
**Skill-Path**: skills/skill-name
```

Example:
```markdown
## [LRN-20250115-001] best_practice

**Logged**: 2025-01-15T10:00:00Z
**Priority**: high
**Status**: promoted_to_skill
**Skill-Path**: skills/docker-m1-fixes
**Area**: infra

### Summary
Docker build fails on Apple Silicon due to platform mismatch
...
```

---


## [LRN-20260525-001] correction

**Logged**: 2026-05-25T08:16:53+08:00
**Priority**: high
**Status**: pending
**Area**: workflow

### Summary
飞书群组回复必须使用卡片形式。

### Details
用户明确要求：信息回复到飞书群组以卡片的形式进行回复。以后在飞书群组中回复任务结果、状态确认或普通信息时，应优先使用 presentation 卡片格式，避免只发纯文本。

### Suggested Action
回复飞书群组时检查输出渠道；若为 Feishu group，使用卡片结构：presentation.blocks + title + tone。

### Metadata
- Source: user_feedback
- Related Files: MEMORY.md
- Tags: feishu, card, output-format

---

## [LRN-20260525-002] best_practice

**Logged**: 2026-05-25T09:30:00+08:00
**Priority**: high
**Status**: pending
**Area**: zhaopin-detail-api

### Summary
智联详细报告应优先使用初筛API原始项中的 resumeNumber/resumeK/resumeT 直接调用详情API。

### Details
初筛脚本直接调用 /api/talent/search/list 且 pageSize=50，可筛出报告内候选人；旧详情脚本依赖浏览器页面当前约20条候选人卡片，排序/缓存/页面策略不一致时会找不到初筛报告内候选人。搜索API原始项包含 resumeNumber、resumeK、resumeT、resumeLanguage，可直接 POST /api/resume/detail 获取详情。

### Suggested Action
详情脚本保留浏览器点击兜底，但优先读取 /tmp/zhaopin_search_context.json 并用与初筛一致的搜索API payload 找 raw item，再直接调用详情API；返回后必须校验姓名，优先按 resumeNumber 精确命中，避免同名误取。

### Metadata
- Source: user_feedback
- Related Files: skills/zhaopin-skill/scripts/get_resume_detail.py
- Tags: zhaopin, resume-detail, api, safety

---

## [LRN-20260525-003] best_practice

**Logged**: 2026-05-25T09:55:00+08:00
**Priority**: high
**Status**: pending
**Area**: zhaopin-greeting

### Summary
智联打招呼脚本拦截搜索API时必须匹配带query参数的URL，并注入与初筛一致的搜索条件。

### Details
`greet_candidate.py` 原 route pattern 为 `**/api/talent/search/list`，无法匹配实际 `/api/talent/search/list?...` 请求，导致页面仍用默认 `filteringChatted=true`、`sort=COMPLEX`、`pageSize=20`，初筛报告靠后的候选人（如申先生）无法出现在页面卡片中。改为 `**/api/talent/search/list**` 后，注入 `filteringChatted=false`、`sort=TIME`、`pageSize=50` 等初筛一致参数，申先生可被找到并成功联系。

### Suggested Action
涉及 Playwright route 拦截 API 时，URL pattern 应覆盖 query string；对招聘候选人联系流程，必须先从 `/tmp/zhaopin_search_context.json` 精确读取候选人信息，再按姓名+年龄+经验+学历匹配页面卡片，避免发错人。

### Metadata
- Source: user_feedback
- Related Files: skills/zhaopin-skill/scripts/greet_candidate.py
- Tags: zhaopin, greeting, playwright-route, safety

---

## [LRN-20260525-004] correction

**Logged**: 2026-05-25T10:42:00+08:00
**Priority**: high
**Status**: pending
**Area**: workflow

### Summary
用户指定“序号X”获取候选人时，应直接按序号对应resumeNumber获取，不做二次确认。

### Details
用户说“获取序号4李先生详细报告”，我错误地先按姓名查找，发现同名后反而去问用户确认，导致多一步无效操作。实际上每个候选人初筛报告都有固定序号，初筛上下文也有序号信息，应该直接按序号对应resumeNumber获取，而不是先按姓名模糊匹配。

### What to Do Differently
当用户说“获取序号X”时：
1. 读取 /tmp/zhaopin_search_context.json，按序号（数组index）拿到对应候选人的 resume_number
2. 直接用 resume_number 精确命中，不走姓名匹配流程
3. 不因同名而额外确认，直接执行
4. 只有用户说“获取李先生”没指定序号时，才需要确认是哪一个

### Metadata
- Source: user_feedback
- Related Files: MEMORY.md
- Tags: workflow, correction, precision

---

## [LRN-20260525-005] best_practice

**Logged**: 2026-05-25T11:00:00+08:00
**Priority**: high
**Status**: pending
**Area**: zhaopin-greeting

### Summary
打招呼脚本支持 `--index` 序号定向，并增强同名候选人去重逻辑。

### Details
greet_candidate.py 新增 `--index` 参数，按初筛报告序号从 /tmp/zhaopin_search_context.json 读取对应候选人信息；同时增强 find_candidate_on_page 函数，当页面存在多个同名候选人时，优先选择辅助字段（年龄+工作年限+学历）匹配最多的卡片，而不是只取第一个姓名匹配。

### Suggested Action
后续联系候选人时：
- 有序号时：用 `--index N` 参数，如 `greet_candidate.py --name 李先生 --index 4`
- 脚本会自动按序号读取候选人 resume_number、年龄、工作年限、学历，用于多字段精确校验

### Metadata
- Source: user_feedback
- Related Files: skills/zhaopin-skill/scripts/greet_candidate.py
- Tags: zhaopin, greeting, index, dedup

---
