#!/usr/bin/env python3
"""
将飞书文档分享给招聘组群。

用法:
  python3 scripts/share_report_to_feishu.py --doc-id <doc_id> [--group-id <group_id>]
"""

import argparse
import json
import subprocess
import sys

APP_ID = "cli_a97ec8ac45785cd1"
CONFIG_PATH = "/root/.openclaw/openclaw.json"
DEFAULT_GROUP_ID = "oc_7b1b6aafdf683e4aa9120391f9cceba6"


def get_app_secret():
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    return config["channels"]["feishu"]["appSecret"]


def get_tenant_token(app_id, app_secret):
    resp = subprocess.run(
        ["curl", "-s", "-X", "POST",
         "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"app_id": app_id, "app_secret": app_secret})],
        capture_output=True, text=True
    )
    data = json.loads(resp.stdout)
    if data.get("code") != 0:
        raise RuntimeError(f"获取token失败: {data}")
    return data["tenant_access_token"]


def share_to_group(token, doc_id, group_id, perm="full_access"):
    resp = subprocess.run(
        ["curl", "-s", "-X", "POST",
         f"https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_id}/members?type=docx",
         "-H", f"Authorization: Bearer {token}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"member_type": "openchat", "member_id": group_id, "perm": perm})],
        capture_output=True, text=True
    )
    data = json.loads(resp.stdout)
    if data.get("code") != 0:
        raise RuntimeError(f"分享文档失败: {data}")
    return True


def main():
    parser = argparse.ArgumentParser(description="分享飞书文档给招聘组群")
    parser.add_argument("--doc-id", "-d", required=True, help="飞书文档 ID")
    parser.add_argument("--group-id", "-g", default=DEFAULT_GROUP_ID, help="群组 ID")
    args = parser.parse_args()

    app_secret = get_app_secret()
    token = get_tenant_token(APP_ID, app_secret)

    print(f"🔗 分享文档 {args.doc_id} → 群组 {args.group_id}")
    share_to_group(token, args.doc_id, args.group_id)
    print(f"✅ 分享成功")
    print(f"📎 https://feishu.cn/docx/{args.doc_id}")


if __name__ == "__main__":
    main()
