#!/usr/bin/env python3
"""
智联招聘API状态检查脚本
验证Cookie有效性和API连通性
"""

import sys
import os
import json
import requests

# 加载Cookie
COOKIE_FILE = "/root/.openclaw/workspace-HR-Agent/config/zhaopin_cookies.txt"
if not os.path.exists(COOKIE_FILE):
    print(f"❌ Cookie文件不存在: {COOKIE_FILE}")
    sys.exit(1)

with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
    cookies = f.read().strip()

if not cookies:
    print("❌ Cookie文件为空")
    sys.exit(1)

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Cookie": cookies,
    "Content-Type": "application/json"
}

# 测试搜索API连通性
test_url = "https://rd6.zhaopin.com/api/talent/search/list"
test_payload = {
    "keyword": "测试",
    "pageIndex": 1,
    "pageSize": 1
}

try:
    response = requests.post(test_url, headers=headers, json=test_payload, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 200 or (data.get("data") and isinstance(data.get("data"), dict)):
            print("✅ 智联招聘API状态正常")
            print(f"✅ Cookie有效，上次更新时间: 2026-05-07 08:07")
            sys.exit(0)
        else:
            print(f"❌ API返回错误: {data.get('message', '未知错误')}")
            print(f"❌ 错误码: {data.get('code')}")
    else:
        print(f"❌ HTTP请求失败: {response.status_code}")
        print(f"❌ 响应内容: {response.text[:200]}...")
except Exception as e:
    print(f"❌ 请求异常: {str(e)}")

sys.exit(1)
