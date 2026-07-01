#!/usr/bin/env python3
"""
智联招聘 IM 消息监控与回复脚本

功能：
1. 轮询会话列表，检测新消息（候选人回复）
2. 将新消息推送到飞书群
3. 通过飞书回复指令，自动发送消息给候选人
4. 与现有打招呼流程联动

API 依赖：
- POST /api/im/session/list - 获取会话列表
- POST /api/im/session/detail - 获取会话详情
- POST /api/im/sendText - 发送文本消息
- POST /api/im/getUnread - 获取未读统计

使用方式：
  python3 im_monitor.py --action poll          # 轮询新消息
  python3 im_monitor.py --action reply         # 回复候选人
  python3 im_monitor.py --action send          # 主动发送消息
  python3 im_monitor.py --action list          # 列出所有会话

回复示例：
  python3 im_monitor.py --action reply --session-id "xxx" --content "您好，感谢您的关注..."
  或
  python3 im_monitor.py --action send --name "夏旭昊" --content "您好..."

配置文件：
  config/im_state.json - 已处理消息状态跟踪
"""

import argparse
import json
import os
import sys
import time
import requests
from datetime import datetime

# ============ 配置 ============
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = '/root/.openclaw/workspace-HR-Agent'
COOKIE_FILE = os.path.join(WORKSPACE_DIR, 'config', 'zhaopin_cookies.txt')
STATE_FILE = os.path.join(WORKSPACE_DIR, 'config', 'im_state.json')
API_BASE = 'https://rd6.zhaopin.com/api'

# 飞书群配置（招聘组）
FEISHU_CHAT_ID = 'oc_7b1b6aafdf683e4aa9120391f9cceba6'

# ============ Cookie 管理 ============
def load_cookies():
    """加载 Cookie"""
    if not os.path.exists(COOKIE_FILE):
        print(f"错误：Cookie 文件不存在: {COOKIE_FILE}")
        return None, None
    
    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookie_str = f.read().strip()
    
    if not cookie_str:
        return None, None
    
    # 解析为 dict
    cookie_dict = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            k, v = item.split('=', 1)
            cookie_dict[k.strip()] = v.strip()
    
    return cookie_str, cookie_dict


def get_headers():
    """获取标准请求头"""
    return {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Origin': 'https://rd6.zhaopin.com',
        'Referer': 'https://rd6.zhaopin.com/app/im',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }


# ============ 状态管理 ============
def load_state():
    """加载已处理消息状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'processed_messages': {},  # sessionId -> [messageId, ...]
        'last_poll_time': 0,
        'known_sessions': {}       # sessionId -> {name, lastMsgTime, lastMsgText}
    }


def save_state(state):
    """保存消息状态"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ============ IM API 调用 ============
def api_post(path, data=None):
    """调用智联 API"""
    cookie_str, cookie_dict = load_cookies()
    if not cookie_dict:
        return None
    
    url = f"{API_BASE}/{path}"
    
    try:
        resp = requests.post(
            url,
            json=data or {},
            cookies=cookie_dict,
            headers=get_headers(),
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  [API] {path} 返回 HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [API] {path} 请求异常: {e}")
        return None


def get_session_list():
    """获取会话列表"""
    result = api_post('im/session/list', {})
    if result and result.get('code') == 200:
        return result.get('data', [])
    return []


def get_session_detail(session_id):
    """获取会话详情"""
    result = api_post('im/session/detail', {
        'sessionId': session_id,
        'markRead': False,
        'includeResumeDetail': False
    })
    if result and result.get('code') == 200:
        return result.get('data')
    return None


def get_unread():
    """获取未读统计"""
    result = api_post('im/getUnread', {})
    if result and result.get('code') == 200:
        return result.get('data', {})
    return {}


def send_text_message(session_id, content):
    """发送文本消息"""
    result = api_post('im/sendText', {
        'sessionId': session_id,
        'content': content
    })
    if result and result.get('code') == 200:
        return True
    return False


def get_attach_resume_info(job_number, resume_number):
    """
    获取附件简历下载信息
    
    Args:
        job_number: 职位编号
        resume_number: 简历编号
    
    Returns:
        dict: {url, fileId, fileName, fileType} 或 None
    """
    result = api_post('resume/getAttachResumeInfo', {
        'jobNumber': job_number,
        'resumeNumber': resume_number,
        'language': 1
    })
    if result and result.get('code') == 200:
        return result.get('data')
    return None


def download_attach_resume(download_url, save_dir='/tmp/zhaopin_attachments'):
    """
    下载附件简历
    
    Args:
        download_url: 附件下载URL
        save_dir: 保存目录
    
    Returns:
        str: 保存的文件路径，或 None
    """
    os.makedirs(save_dir, exist_ok=True)
    
    try:
        resp = requests.get(download_url, timeout=30)
        if resp.status_code == 200:
            # 从 Content-Disposition 或 URL 中提取文件名
            filename = '附件简历.pdf'
            content_disp = resp.headers.get('Content-Disposition', '')
            if 'filename*=' in content_disp:
                import re
                match = re.search(r"filename\*\=UTF\-8''(.+)", content_disp)
                if match:
                    from urllib.parse import unquote
                    filename = unquote(match.group(1))
            
            filepath = os.path.join(save_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            print(f"   [附件] ✅ 已下载: {filepath} ({len(resp.content)} bytes)")
            return filepath
        else:
            print(f"   [附件] ⚠️ 下载失败: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"   [附件] ⚠️ 下载异常: {e}")
        return None


def check_and_download_attach(session):
    """
    检查会话是否有附件简历，如有则下载
    
    Args:
        session: 会话对象（来自 session/list）
    
    Returns:
        dict: 附件信息 {filepath, fileName, fileType} 或 None
    """
    job_number = session.get('jobNumber')
    resume_number = session.get('resumeNumber')
    
    if not job_number or not resume_number:
        return None
    
    # 获取附件简历信息
    attach_info = get_attach_resume_info(job_number, resume_number)
    if not attach_info or not attach_info.get('url'):
        return None
    
    # 下载附件
    filepath = download_attach_resume(attach_info['url'])
    if filepath:
        return {
            'filepath': filepath,
            'fileName': attach_info.get('fileName', '附件简历'),
            'fileType': attach_info.get('fileType', 'PDF'),
            'fileId': attach_info.get('fileId', '')
        }
    
    return None


# ============ 消息解析 ============
def parse_last_sentence(last_sentence):
    """解析 lastSentence JSON 字符串"""
    if not last_sentence:
        return None
    if isinstance(last_sentence, str):
        try:
            return json.loads(last_sentence)
        except:
            return None
    return last_sentence


def is_system_message(text):
    """判断是否为系统消息（非候选人真实回复）"""
    system_patterns = [
        '您的同事',
        '正在与候选人沟通',
        '系统消息',
    ]
    for pattern in system_patterns:
        if pattern in text:
            return True
    return False


def is_new_message(session, state):
    """判断会话是否有新消息（候选人回复）"""
    session_id = session.get('sessionId')
    last_sentence = parse_last_sentence(session.get('lastSentence'))
    
    if not last_sentence:
        return False
    
    sender_type = last_sentence.get('senderType', '')
    send_time = last_sentence.get('sendTime', 0)
    text = last_sentence.get('text', '')
    
    # 只关注候选人发来的消息（非 STAFF 发送）
    if sender_type != 'USER':
        return False
    
    # 过滤系统消息
    if is_system_message(text):
        return False
    
    # 检查是否已处理过
    known = state.get('known_sessions', {}).get(session_id, {})
    known_time = known.get('lastMsgTime', 0)
    known_text = known.get('lastMsgText', '')
    
    if send_time > known_time or (send_time == known_time and text != known_text):
        return True
    
    return False


# ============ 核心功能 ============
def poll_messages():
    """
    轮询新消息
    返回新消息列表
    """
    state = load_state()
    new_messages = []
    
    # 获取会话列表
    sessions = get_session_list()
    if not sessions:
        print("  [轮询] 获取会话列表失败")
        return []
    
    print(f"  [轮询] 共 {len(sessions)} 个会话")
    
    # 检查未读统计
    unread = get_unread()
    if unread:
        items = unread.get('items', [])
        for item in items:
            tag = item.get('tag', '')
            count = item.get('unreadCount', 0)
            if 'UNREAD_COUNT' in tag and count:
                print(f"  [轮询] {tag}: {count} 条未读")
    
    for session in sessions:
        session_id = session.get('sessionId')
        name = session.get('name', '未知')
        last_sentence = parse_last_sentence(session.get('lastSentence'))
        
        if not last_sentence:
            continue
        
        sender_type = last_sentence.get('senderType', '')
        send_time = last_sentence.get('sendTime', 0)
        text = last_sentence.get('text', '')
        
        # 更新已知会话状态
        if session_id not in state['known_sessions']:
            state['known_sessions'][session_id] = {}
        
        known = state['known_sessions'][session_id]
        
        # 检测新消息（候选人回复）
        if sender_type == 'USER' and not is_system_message(text):
            known_time = known.get('lastMsgTime', 0)
            known_text = known.get('lastMsgText', '')
            
            is_new = send_time > known_time or (send_time == known_time and text != known_text)
            
            if is_new:
                # 检测是否有附件简历
                attach_info = None
                if '简历' in text or '附件' in text:
                    attach_info = check_and_download_attach(session)
                
                msg_info = {
                    'session_id': session_id,
                    'name': name,
                    'user_id': session.get('userId'),
                    'text': text,
                    'send_time': send_time,
                    'send_time_str': datetime.fromtimestamp(send_time / 1000).strftime('%m-%d %H:%M'),
                    'job_title': session.get('jobTitle', ''),
                    'resume_number': session.get('resumeNumber', ''),
                    'unread_count': session.get('unreadCount', 0),
                    'candidate_state': session.get('candidateState', ''),
                    'sender_type': sender_type,
                    'attach': attach_info
                }
                new_messages.append(msg_info)
                attach_tag = ' 📎' if attach_info else ''
                print(f"  [轮询] 🔔 新消息: {name} -> {text[:60]}{attach_tag}")
        
        # 更新状态
        known['lastMsgTime'] = send_time
        known['lastMsgText'] = text
        known['name'] = name
    
    state['last_poll_time'] = int(time.time() * 1000)
    save_state(state)
    
    return new_messages


def send_reply(session_id, content):
    """回复候选人消息"""
    print(f"  [回复] 发送消息到会话 {session_id}")
    print(f"  [回复] 内容: {content[:100]}")
    
    success = send_text_message(session_id, content)
    
    if success:
        print(f"  [回复] ✅ 发送成功")
        # 更新状态
        state = load_state()
        if session_id in state['known_sessions']:
            state['known_sessions'][session_id]['lastMsgTime'] = int(time.time() * 1000)
            state['known_sessions'][session_id]['lastMsgText'] = content
        save_state(state)
        return True
    else:
        print(f"  [回复] ❌ 发送失败")
        return False


def list_sessions(show_all=False):
    """列出所有会话"""
    sessions = get_session_list()
    if not sessions:
        print("无会话数据")
        return
    
    print(f"\n{'='*80}")
    print(f"📋 会话列表（共 {len(sessions)} 个）")
    print(f"{'='*80}")
    
    for i, session in enumerate(sessions, 1):
        name = session.get('name', '未知')
        job = session.get('jobTitle', '')
        unread = session.get('unreadCount', 0)
        candidate_state = session.get('candidateState', '')
        session_id = session.get('sessionId', '')
        
        last_sentence = parse_last_sentence(session.get('lastSentence'))
        if last_sentence:
            sender = last_sentence.get('senderType', '')
            text = last_sentence.get('text', '')
            send_time = last_sentence.get('sendTime', 0)
            time_str = datetime.fromtimestamp(send_time / 1000).strftime('%m-%d %H:%M') if send_time else ''
        else:
            sender = ''
            text = ''
            time_str = ''
        
        # 状态标记
        state_tag = ''
        if candidate_state == 'PENDING':
            state_tag = '⏳待处理'
        elif candidate_state == 'APPOINTABLE':
            state_tag = '📅可约面'
        
        unread_tag = f' 🔴{unread}条未读' if unread else ''
        
        print(f"\n  {i}. {name} {state_tag}{unread_tag}")
        print(f"     职位: {job}")
        print(f"     状态: {candidate_state}")
        if text:
            print(f"     最后消息: [{sender}] {text[:100]}")
            print(f"     时间: {time_str}")
        if show_all:
            print(f"     sessionId: {session_id}")
    
    print(f"\n{'='*80}")


# ============ 飞书推送 ============
def format_feishu_card(new_messages):
    """将新消息格式化为飞书卡片"""
    if not new_messages:
        return None
    
    blocks = []
    
    blocks.append({
        "type": "text",
        "text": f"📩 **智联招聘 - 候选人新消息提醒**\n共 {len(new_messages)} 条未读回复"
    })
    blocks.append({"type": "divider"})
    
    for msg in new_messages:
        name = msg['name']
        text = msg['text']
        time_str = msg['send_time_str']
        job = msg['job_title']
        unread = msg.get('unread_count', 0)
        attach = msg.get('attach')
        
        attach_tag = ''
        if attach:
            file_name = attach.get('fileName', '附件简历')
            file_type = attach.get('fileType', '')
            attach_tag = f'\n📎 附件简历: {file_name}.{file_type}'
        
        blocks.append({
            "type": "text",
            "text": f"**{name}** | {job}\n💬 {text[:200]}{attach_tag}\n🕐 {time_str} | 🔴 {unread} 条未读"
        })
        blocks.append({"type": "divider"})
    
    blocks.append({
        "type": "text",
        "text": "💡 如需回复，请发送：\n`回复 [姓名] [内容]`\n例如：`回复 夏旭昊 您好，方便电话沟通吗？`"
    })
    
    return {
        "presentation": {
            "blocks": blocks,
            "title": "📩 智联招聘消息提醒",
            "tone": "info"
        }
    }


# ============ 主入口 ============
def main():
    parser = argparse.ArgumentParser(description='智联招聘 IM 消息监控')
    parser.add_argument('--action', '-a', required=True,
                        choices=['poll', 'reply', 'send', 'list', 'status'],
                        help='操作类型')
    parser.add_argument('--session-id', help='会话 ID')
    parser.add_argument('--name', '-n', help='候选人姓名')
    parser.add_argument('--content', '-c', help='消息内容')
    parser.add_argument('--show-all', action='store_true', help='显示所有详情')
    
    args = parser.parse_args()
    
    if args.action == 'poll':
        print(f"\n🔍 开始轮询新消息...")
        new_msgs = poll_messages()
        if new_msgs:
            print(f"\n✅ 发现 {len(new_msgs)} 条新消息")
            for msg in new_msgs:
                print(f"  - {msg['name']}: {msg['text'][:80]}")
        else:
            print(f"\n✅ 无新消息")
        return 0
    
    elif args.action == 'reply':
        if not args.session_id or not args.content:
            print("错误：回复需要 --session-id 和 --content")
            return 1
        success = send_reply(args.session_id, args.content)
        return 0 if success else 1
    
    elif args.action == 'send':
        if args.name and not args.session_id:
            # 按姓名查找 sessionId
            sessions = get_session_list()
            for s in sessions:
                if s.get('name') == args.name:
                    args.session_id = s.get('sessionId')
                    break
            if not args.session_id:
                print(f"错误：未找到候选人 '{args.name}' 的会话")
                return 1
        
        if not args.session_id or not args.content:
            print("错误：发送需要 --session-id（或 --name）和 --content")
            return 1
        
        success = send_reply(args.session_id, args.content)
        return 0 if success else 1
    
    elif args.action == 'list':
        list_sessions(show_all=args.show_all)
        return 0
    
    elif args.action == 'status':
        state = load_state()
        print(f"\n📊 IM 监控状态")
        print(f"{'='*40}")
        print(f"  已知会话: {len(state.get('known_sessions', {}))}")
        print(f"  上次轮询: {datetime.fromtimestamp(state.get('last_poll_time', 0)/1000).strftime('%H:%M:%S') if state.get('last_poll_time') else '从未'}")
        print(f"  已处理消息: {sum(len(v) for v in state.get('processed_messages', {}).values())}")
        print(f"\n  已知会话列表:")
        for sid, info in state.get('known_sessions', {}).items():
            name = info.get('name', '未知')
            last_time = info.get('lastMsgTime', 0)
            last_text = info.get('lastMsgText', '')[:50]
            time_str = datetime.fromtimestamp(last_time/1000).strftime('%m-%d %H:%M') if last_time else ''
            print(f"    - {name}: {last_text} ({time_str})")
        return 0
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
