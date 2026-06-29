#!/usr/bin/env python3
"""
智联招聘心跳检测脚本
检查 Cookie 有效性、搜索接口可用性、简历库总量、最新活跃候选人

【重要】本脚本所有数据均来自智联招聘 API 真实返回，严禁捏造。
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

COOKIE_FILE = "/root/.openclaw/workspace-HR-Agent/config/zhaopin_cookies.txt"
API_BASE = "https://rd6.zhaopin.com"
SEARCH_API = f"{API_BASE}/api/talent/search/list"
STATE_FILE = "/root/.openclaw/workspace-HR-Agent/memory/zhaopin-heartbeat-state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://rd6.zhaopin.com/app/search",
}


def load_cookies():
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    cookies = {}
    for item in raw.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def get_cookie_age_days():
    """从 Cookie 文件修改时间估算 Cookie 年龄（天）"""
    try:
        stat = os.stat(COOKIE_FILE)
        age_seconds = time.time() - stat.st_mtime
        return int(age_seconds / 86400)
    except Exception:
        return None


def check_cookie_validity(cookies):
    """检查 Cookie 有效性：访问 rd6 首页，应返回 302 重定向到 /app/recommend"""
    try:
        r = requests.get(
            f"{API_BASE}/",
            cookies=cookies,
            headers=HEADERS,
            timeout=15,
            allow_redirects=False,
        )
        location = r.headers.get("Location", "")
        if r.status_code == 200:
            return {"ok": True, "status": 200, "note": "返回200，可能是已登录页面"}
        elif r.status_code in (301, 302) and "login" in location.lower():
            return {"ok": False, "status": r.status_code, "redirect": location, "note": "重定向到登录页，Cookie已失效"}
        elif r.status_code in (301, 302) and "/app/recommend" in location:
            return {"ok": True, "status": r.status_code, "redirect": location, "note": "重定向到企业版首页，Cookie有效"}
        else:
            return {"ok": True, "status": r.status_code, "redirect": location, "note": "状态异常但非登录重定向"}
    except Exception as e:
        return {"ok": False, "error": str(e), "note": "请求异常"}


def check_search_api(cookies):
    """
    使用脚本正确 payload 检查搜索接口可用性，
    获取简历库总量（foundTotal）和最近活跃候选人。
    """
    # 正确的 payload 格式（与 search_resumes.py 一致）
    payload = {
        "expectedCityIds": [],
        "keywordIntentions": [],
        "educations": [],
        "workingYears": [],
        "filteringChatted": False,
        "filteringRead": False,
        "filteringDownloaded": False,
        "sort": {"type": "TIME", "version": 0},
        "pageNo": 1,
        "pageSize": 5,
        "filteringOtherChattedType": "DONT_FILTER",
        "matchLatestWorkExperience": False,
        "searchExperimentalGroup": "EXPERIMENT",
        "frontExperiment": True,
        "firstPageCacheable": False,
        "freeMaskLimit": False,
        "experiment": "",
    }

    try:
        r = requests.post(
            SEARCH_API,
            cookies=cookies,
            headers=HEADERS,
            json=payload,
            timeout=20,
        )
        result = {"status": r.status_code}

        if r.status_code != 200:
            result["note"] = f"HTTP {r.status_code}"
            return result

        data = r.json()
        result["code"] = data.get("code")
        result["msg"] = data.get("msg")

        if data.get("code") != 200:
            result["note"] = f"业务code={data.get('code')}"
            return result

        body = data.get("data", {})
        result["foundTotal"] = body.get("foundTotal", 0)  # 真实总数（跨页）
        result["totalOnPage"] = body.get("total", 0)      # 当前页总数（上限1000）
        result["returnedCount"] = len(body.get("list", []))

        # 获取最近活跃的候选人（已按 TIME 排序取前5）
        candidates = []
        for item in body.get("list", [])[:5]:
            candidates.append({
                "name": item.get("userName", "N/A"),
                "activeTime": item.get("activeTime", "N/A"),
                "online": item.get("online", False),
                "workYears": item.get("workYearsLabel", "N/A"),
                "city": item.get("cityLabel", "N/A"),
                "title": item.get("lastJobTitle") or item.get("expectJobTitle") or "N/A",
            })
        result["recentCandidates"] = candidates
        result["note"] = "API正常"
        return result

    except Exception as e:
        return {"status": None, "error": str(e), "note": f"请求异常: {e}"}


def save_state(state):
    """保存心跳状态到文件"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    now = datetime.now(timezone(timedelta(hours=8)))  # Asia/Shanghai
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"🔍 智联招聘心跳检测 — {now_str}\n")

    cookies = load_cookies()
    cookie_age = get_cookie_age_days()
    print(f"📋 Cookie 年龄: ~{cookie_age} 天（估计）")

    # 1. Cookie 有效性
    print(f"\n1️⃣ 检查 Cookie 有效性...")
    cookie_check = check_cookie_validity(cookies)
    cookie_ok = cookie_check.get("ok", False)
    print(f"   结果: {'✅ 有效' if cookie_ok else '❌ 无效'} — {cookie_check.get('note', '')}")
    if not cookie_ok:
        print(f"   错误详情: {cookie_check}")

    # 2. 搜索 API 可用性
    print(f"\n2️⃣ 检查搜索接口可用性...")
    api_check = check_search_api(cookies)
    api_ok = api_check.get("code") == 200
    print(f"   结果: {'✅ 正常' if api_ok else '❌ 异常'} — code={api_check.get('code')}, msg={api_check.get('msg')}")
    if api_ok:
        print(f"   简历库总量: ~{api_check.get('foundTotal', 0):,} 份")
        print(f"   当前页返回: {api_check.get('returnedCount', 0)} 条（按更新时间排序）")
        recent = api_check.get("recentCandidates", [])
        if recent:
            print(f"\n   📌 最近活跃候选人（API按TIME排序取前5）:")
            for i, c in enumerate(recent, 1):
                online_mark = "🟢" if c.get("online") else "⚪"
                print(f"   {i}. {c['name']} | {online_mark} | 活跃:{c['activeTime']} | {c['city']} | {c['title']}")
    else:
        print(f"   错误详情: {api_check}")

    # 3. 保存状态
    state = {
        "lastHeartbeat": now_str,
        "cookieAgeDays": cookie_age,
        "cookieValid": cookie_ok,
        "apiAvailable": api_ok,
        "foundTotal": api_check.get("foundTotal") if api_ok else None,
        "recentCandidates": api_check.get("recentCandidates", []) if api_ok else [],
    }
    save_state(state)

    # 4. 生成摘要（供 cron job 上报）
    summary = {
        "time": now_str,
        "cookieValid": cookie_ok,
        "apiAvailable": api_ok,
        "foundTotal": api_check.get("foundTotal") if api_ok else None,
        "cookieAgeDays": cookie_age,
        "recentCandidates": [
            {
                "name": c["name"],
                "activeTime": c["activeTime"],
                "online": c["online"],
                "city": c["city"],
            }
            for c in (api_check.get("recentCandidates", []) if api_ok else [])
        ],
    }

    print(f"\n{'='*50}")
    print(f"📊 摘要 JSON（供飞书卡片使用）:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0 if (cookie_ok and api_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
