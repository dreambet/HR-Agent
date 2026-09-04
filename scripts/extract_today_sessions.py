#!/usr/bin/env python3
"""提取指定日期 session 文件中的对话内容，保存为 Markdown 存档。"""
import json, os, sys, glob
from datetime import datetime

SESSIONS_DIR = "/root/.openclaw/agents/hr-agent/sessions"
TARGET_DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-03"
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else f"/root/.openclaw/workspace-HR-Agent/memory/{TARGET_DATE}-conversations.md"

def is_today(path, date_str):
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return mtime.strftime("%Y-%m-%d") == date_str

def extract_text(content):
    """从 message.content 中提取文本"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                if c.get("type") == "text":
                    parts.append(c.get("text", ""))
                elif c.get("type") == "image":
                    parts.append("[图片]")
                elif c.get("type") == "file":
                    parts.append(f"[文件: {c.get('name', 'unknown')}]")
        return "\n".join(parts)
    return ""

def summarize_role(role):
    return {"user": "👤 用户", "assistant": "🤖 婉聘"}.get(role, role)

# 收集今日 session 文件（排除 trajectory）
sessions = sorted(
    [f for f in glob.glob(os.path.join(SESSIONS_DIR, "*.jsonl"))
     if not f.endswith(".trajectory.jsonl") and is_today(f, TARGET_DATE)],
    key=os.path.getmtime
)

lines = []
lines.append(f"# {TARGET_DATE} 对话存档")
lines.append("")
lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
lines.append(f"> 会话数量：{len(sessions)}")
lines.append("")
lines.append("---")
lines.append("")

if not sessions:
    lines.append("今日无活跃会话")
else:
    for i, sf in enumerate(sessions, 1):
        sid = os.path.basename(sf).replace(".jsonl", "")
        mtime = datetime.fromtimestamp(os.path.getmtime(sf)).strftime("%H:%M")
        # 读取文件提取消息
        msgs = []
        try:
            with open(sf, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except Exception:
                        continue
                    if evt.get("type") != "message":
                        continue
                    msg = evt.get("message", {})
                    role = msg.get("role", "")
                    text = extract_text(msg.get("content", ""))
                    if text.strip():
                        ts = evt.get("timestamp", "")
                        t = ts[11:16] if len(ts) >= 16 else ""
                        msgs.append((t, role, text.strip()))
        except Exception as e:
            msgs.append(("", "error", f"读取失败: {e}"))

        if not msgs:
            lines.append(f"## 会话 {i} ({sid[:8]}… {mtime})")
            lines.append("")
            lines.append("_无实质对话内容（可能为静默轮询）_")
            lines.append("")
            continue

        lines.append(f"## 会话 {i} ({sid[:8]}… {mtime})")
        lines.append("")
        for t, role, text in msgs:
            # 截断超长消息
            if len(text) > 1500:
                text = text[:1500] + f"\n…[截断，共{len(text)}字]"
            lines.append(f"**{summarize_role(role)}** ({t})：")
            lines.append("")
            lines.append(text)
            lines.append("")

content = "\n".join(lines)
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(content)

# 输出统计
total_msgs = 0
sessions_with_content = 0
for sf in sessions:
    count = 0
    with open(sf, "r", encoding="utf-8") as f:
        for line in f:
            try:
                evt = json.loads(line)
                if evt.get("type") == "message" and evt.get("message", {}).get("role") in ("user", "assistant"):
                    txt = extract_text(evt.get("message", {}).get("content", ""))
                    if txt.strip():
                        count += 1
            except Exception:
                pass
    if count > 0:
        sessions_with_content += 1
    total_msgs += count

print(f"✅ 已生成: {OUTPUT}")
print(f"📊 今日 session 总数: {len(sessions)}, 有对话内容: {sessions_with_content}, 消息总数: {total_msgs}")
