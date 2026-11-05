#!/usr/bin/env python3
"""Muse（Satu Digital）的 BotConnect 客户端。

用 WebSocket 连上 botconnectserver（本仓库的服务端），收服务端 / 操作员
发来的消息，带 UTC 时间戳记到同目录的 muse-inbox.log；也可单发一帧回去。

协议（与 botconnectserver/server.py、example_client.py 完全一致，
WebSocket 端口和 TCP 端口用同一套 JSON 帧）：
  连上后第一帧必须是 {"type": "auth", "key": <MUSE_KEY>}，
  服务器回 {"type": "auth_ok", "client_id": ..., "name": ...}。
  之后收到的帧：
    message        广播（服务端发给所有人）/ 客户端上报   from / payload
    dm             私聊                                  from / to / payload
    group_message  群消息                                group_id / from / payload
    presence       上下线                                client_id / name / online
    clients / groups / group_created / group_updated / invited / error  原样记
  发出去的帧（--send 或 send_frame）：
    message        客户端身份只能上报给所有在线服务端，不会广播给其他客户端
    dm             {"type": "dm", "to": <对方 key>, "payload": ...}
    group_message  {"type": "group_message", "group_id": ..., "payload": ...}
    list_clients / list_groups  查询在线客户端 / 群组

配置（环境变量；密钥绝不写进代码）：
  WS_URL    例如 ws://127.0.0.1:9101 或 wss://你的服务器:9101
            默认 ws://127.0.0.1:9101（本仓库 .env 的默认端口）
  MUSE_KEY  服务端 CLIENT_KEYS 里给 Muse 配的 key（必填；兼容旧名 WS_TOKEN）

运行：
  pip install websockets
  WS_URL=ws://127.0.0.1:9101 MUSE_KEY=xxx python3 muse.py
  单发一帧：MUSE_KEY=xxx python3 muse.py --send '{"type": "dm", "to": "admin-secret", "payload": "hi"}'

注意：
  - 本脚本只负责监听和落盘，不会直接往 Muse 聊天里推消息；
    Satu Digital 凭 muse-inbox.log 在聊天里通知你。
  - 服务端要在 CLIENT_KEYS 里加上 Muse 的 key；想让 Muse 能收到
    服务端广播 / 私聊，对方要用服务端 key（SERVER_KEYS 里的）连接。
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

# ---- 只改环境变量，不改代码 ----
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:9101")
MUSE_KEY = os.getenv("MUSE_KEY") or os.getenv("WS_TOKEN", "")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muse-inbox.log")
# --------------------------------

RECONNECT_DELAYS = (1, 2, 5, 10, 30)  # 秒，循环使用


def extract(raw_text):
    """从一条原始消息里抽出 (事件, 内容摘要)。"""
    try:
        frame = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return "raw", raw_text
    if not isinstance(frame, dict):
        return "raw", raw_text
    typ = frame.get("type", "message")
    sender = frame.get("from", "")
    payload = frame.get("payload")
    if typ == "message":
        return "message", f"{sender + ': ' if sender else ''}{payload}"
    if typ == "dm":
        return "dm", f"{sender} -> {frame.get('to', '')}: {payload}"
    if typ == "group_message":
        return "group_message", f"[{frame.get('group_id', '')}] {sender}: {payload}"
    if typ == "presence":
        state = "上线" if frame.get("online") else "下线"
        return "presence", f"{frame.get('name', frame.get('client_id', ''))} {state}"
    if typ == "auth_ok":
        return "auth_ok", f"已登录：{frame.get('name', frame.get('client_id', ''))} ({frame.get('client_id', '')})"
    if typ == "clients":
        items = [f"{c.get('name', c.get('id'))}({'在线' if c.get('online') else '离线'})"
                 for c in frame.get("clients", [])]
        return "clients", "、".join(items) or "(空)"
    if typ == "groups":
        items = [f"{g.get('name', g.get('id'))}({len(g.get('members', []))}人)"
                 for g in frame.get("groups", [])]
        return "groups", "、".join(items) or "(空)"
    if typ in ("group_created", "group_updated", "invited"):
        return typ, f"{frame.get('name', frame.get('group_id', ''))} 成员：{', '.join(frame.get('members', []))}"
    if typ == "error":
        return "error", str(frame.get("error", "未知错误"))
    return typ, json.dumps(frame, ensure_ascii=False)


def record(event, content):
    line = (
        f"{datetime.now(timezone.utc).isoformat()} "
        f"[{event}] {content}\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="", flush=True)


async def listen_forever():
    import websockets  # 需 pip install websockets

    attempt = 0
    while True:
        try:
            async with websockets.connect(WS_URL, ping_interval=20) as ws:
                print(f"已连接 {WS_URL}", flush=True)
                await ws.send(json.dumps({"type": "auth", "key": MUSE_KEY}))
                try:
                    first = await asyncio.wait_for(ws.recv(), timeout=10)
                except asyncio.TimeoutError:
                    print("认证超时：服务器 10 秒内没有回 auth_ok", flush=True)
                    raise ConnectionError("auth timeout")
                event, content = extract(first)
                record(event, content)
                if event == "error":
                    print("认证失败：请检查 MUSE_KEY 是否在服务端 CLIENT_KEYS 里", flush=True)
                    raise ConnectionError("auth failed")
                attempt = 0
                async for raw in ws:
                    event, content = extract(raw)
                    record(event, content)
        except Exception as exc:  # 断线、连不上、认证失败都走重连，不直接退出
            delay = RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS) - 1)]
            attempt += 1
            print(f"连接中断（{exc}），{delay} 秒后重连…", flush=True)
            await asyncio.sleep(delay)


async def send_once(frame):
    """连上、认证、发一帧、退出（供 --send 用）。"""
    import websockets  # 需 pip install websockets

    async with websockets.connect(WS_URL, ping_interval=20) as ws:
        await ws.send(json.dumps({"type": "auth", "key": MUSE_KEY}))
        first = await asyncio.wait_for(ws.recv(), timeout=10)
        event, content = extract(first)
        if event == "error":
            print(f"认证失败：{content}", flush=True)
            raise SystemExit(2)
        print(f"认证成功：{content}", flush=True)
        await ws.send(json.dumps(frame, ensure_ascii=False))
        print(f"已发送：{json.dumps(frame, ensure_ascii=False)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Muse 的 BotConnect 客户端")
    parser.add_argument("--send", metavar="JSON",
                        help="单发一帧 JSON 后退出，例如 --send '{\"type\":\"dm\",\"to\":\"admin-secret\",\"payload\":\"hi\"}'")
    args = parser.parse_args()
    if not MUSE_KEY:
        print("请先设置 MUSE_KEY 环境变量（服务端 CLIENT_KEYS 里给 Muse 配的 key）。", file=sys.stderr)
        raise SystemExit(2)
    try:
        if args.send:
            asyncio.run(send_once(json.loads(args.send)))
        else:
            asyncio.run(listen_forever())
    except KeyboardInterrupt:
        print("已停止监听。", flush=True)


if __name__ == "__main__":
    main()
