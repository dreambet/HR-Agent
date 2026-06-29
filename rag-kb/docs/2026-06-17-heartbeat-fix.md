# 2026-06-17 心跳检测数据真实性修复

## 问题
智联招聘心跳检测中，Agent 自行构造了不存在的 `updateRange` 参数来获取"24h活跃简历"数据，导致数据不真实。

## 根因
Cron job 的 message 仅为极简提示词"执行智联招聘定时心跳检测：检查Cookie有效性、接口可用性、新简历监控"，Agent 全靠自己发挥，自行构造了不存在的 API 参数。

## 修复方案
1. 创建专用心跳脚本 `skills/zhaopin-skill/scripts/zhaopin_heartbeat.py`
2. 脚本使用正确的 API payload，从 `activeTime` 字段获取真实活跃数据
3. 更新 cron job 的 message，直接调用专用脚本
4. 所有数字来自脚本 JSON 输出，不允许自行编造

## 关键经验
- Cron job 的 message 应该足够具体，包含明确的执行步骤
- Agent 不应自行构造 API 参数，所有数据必须来自实际 API 响应
- 对于数据敏感的任务，应使用专用脚本而非让 Agent 自由发挥

## 涉及文件
- `skills/zhaopin-skill/scripts/zhaopin_heartbeat.py`（新增）
- `/root/.openclaw/cron/jobs.json`（cron job message 更新）
