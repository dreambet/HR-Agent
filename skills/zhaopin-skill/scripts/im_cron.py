#!/usr/bin/env python3
"""
智联招聘 IM 消息监控 - Cron 包装脚本
每 5 分钟轮询一次，发现未读消息推送到飞书群（含完整消息内容）
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from im_monitor import poll_messages, format_feishu_card, get_session_list, load_state, save_state, parse_last_sentence, is_system_message, check_and_download_attach


def get_unread_user_messages():
    """
    获取所有有候选人未读消息的会话
    返回包含候选人姓名、消息内容、职位等信息的列表
    """
    sessions = get_session_list()
    if not sessions:
        return []
    
    state = load_state()
    unread_list = []
    
    for session in sessions:
        name = session.get('name', '未知')
        last_sentence = parse_last_sentence(session.get('lastSentence'))
        
        if not last_sentence:
            continue
        
        sender_type = last_sentence.get('senderType', '')
        text = last_sentence.get('text', '')
        send_time = last_sentence.get('sendTime', 0)
        unread_count = session.get('unreadCount', 0)
        
        # 只关注候选人发来的真实消息
        if sender_type != 'USER' or is_system_message(text):
            continue
        
        # 检查是否是新消息（比状态文件中记录的时间更新）
        known = state.get('known_sessions', {}).get(session.get('sessionId'), {})
        known_time = known.get('lastMsgTime', 0)
        is_new = send_time > known_time
        
        # 检测是否有附件简历（仅对新消息检测，避免重复下载）
        attach_info = None
        if is_new and ('简历' in text or '附件' in text):
            attach_info = check_and_download_attach(session)
        
        msg_info = {
            'session_id': session.get('sessionId'),
            'name': name,
            'user_id': session.get('userId'),
            'text': text,
            'send_time': send_time,
            'send_time_str': __import__('datetime').datetime.fromtimestamp(send_time / 1000).strftime('%m-%d %H:%M'),
            'job_title': session.get('jobTitle', ''),
            'resume_number': session.get('resumeNumber', ''),
            'unread_count': unread_count,
            'candidate_state': session.get('candidateState', ''),
            'is_new': is_new,
            'attach': attach_info
        }
        unread_list.append(msg_info)
    
    return unread_list


def main():
    # 第一步：先检测新消息（基于当前状态文件，尚未更新）
    all_unread = get_unread_user_messages()
    
    # 第二步：再执行标准轮询（更新状态文件）
    # 注意：顺序很重要！必须先检测再更新，否则新消息会被标记为旧消息
    truly_new = [m for m in all_unread if m.get('is_new')]
    
    # 第三步：更新状态文件
    poll_messages()
    
    # 第四步：有真正的新消息才推送
    if truly_new:
        card = format_feishu_card(truly_new)
        if card:
            output = {
                "new_messages": len(truly_new),
                "total_unread": len(all_unread),
                "messages": [{
                    "name": m["name"],
                    "text": m["text"][:500],
                    "time": m["send_time_str"],
                    "job": m["job_title"],
                    "unread": m["unread_count"],
                    "is_new": m["is_new"],
                    "attach": m.get("attach")
                } for m in truly_new],
                "feishu_card": card
            }
            print(json.dumps(output, ensure_ascii=False))
            return 0
    
    # 无新消息，静默退出
    return 0


if __name__ == '__main__':
    sys.exit(main())
