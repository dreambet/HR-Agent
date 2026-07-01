#!/usr/bin/env python3
"""
智联招聘 IM 回复 - 快捷调用脚本
供 OpenClaw 主会话调用，处理飞书群中的"回复 XXX 内容"指令

用法：
  python3 im_reply.py "回复 夏旭昊 您好，方便电话沟通吗？"
  python3 im_reply.py --name "夏旭昊" --content "您好"
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from im_monitor import get_session_list, send_text_message

def parse_reply_command(text):
    """解析"回复 XXX 内容"格式的指令"""
    # 支持格式：回复 姓名 内容
    # 回复：姓名 内容
    # 回复姓名 内容
    patterns = [
        r'^回复[：:]\s*(\S+)\s+(.+)$',      # 回复：夏旭昊 内容
        r'^回复\s+(\S+)\s+(.+)$',            # 回复 夏旭昊 内容
        r'^回复(\S+)\s+(.+)$',               # 回复夏旭昊 内容
    ]
    
    for pattern in patterns:
        m = re.match(pattern, text.strip())
        if m:
            return m.group(1), m.group(2)
    
    return None, None


def find_session_by_name(name, sessions=None):
    """按姓名查找会话"""
    if sessions is None:
        sessions = get_session_list()
    
    if not sessions:
        return None
    
    # 精确匹配
    for s in sessions:
        if s.get('name') == name:
            return s
    
    # 模糊匹配（去掉先生/女士）
    name_clean = name.replace('先生', '').replace('女士', '').strip()
    for s in sessions:
        sname = s.get('name', '')
        if sname.replace('先生', '').replace('女士', '').strip() == name_clean:
            return s
        if name_clean in sname:
            return s
    
    return None


def handle_reply(text):
    """处理回复指令"""
    name, content = parse_reply_command(text)
    
    if not name or not content:
        return {
            'success': False,
            'error': '无法解析指令，格式：回复 姓名 内容',
            'help': True
        }
    
    # 查找会话
    session = find_session_by_name(name)
    if not session:
        # 列出可用候选人
        sessions = get_session_list()
        names = [s.get('name', '') for s in sessions[:10]]
        return {
            'success': False,
            'error': f'未找到候选人"{name}"的会话',
            'available': names,
            'help': True
        }
    
    session_id = session.get('sessionId')
    job_title = session.get('jobTitle', '')
    
    # 发送消息
    success = send_text_message(session_id, content)
    
    if success:
        return {
            'success': True,
            'name': name,
            'content': content,
            'job_title': job_title,
            'message': f'✅ 已回复 {name}'
        }
    else:
        return {
            'success': False,
            'error': f'发送失败，请检查Cookie是否有效',
            'name': name
        }


def main():
    if len(sys.argv) < 2:
        print("用法: python3 im_reply.py \"回复 夏旭昊 您好\"")
        return 1
    
    text = ' '.join(sys.argv[1:])
    result = handle_reply(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
