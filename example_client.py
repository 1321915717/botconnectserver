"""Interactive TCP chat: CLIENT_KEY=... python example_client.py."""
import asyncio
import json
import os
import sys
import threading


HELP = """命令：
  /focus g 群ID       切换到群聊
  /focus dm 客户端ID  切换到私聊
  /focus clear 或 /broadcast  切换到广播
  /groups  /clients   查看群组或客户端
  /create 群名        创建群组
  /invite 群ID 客户端ID  邀请成员
  /join 群ID          加入群组
  /g 群ID 内容        发送群消息
  /dm 客户端ID 内容   发送私聊
  /help               显示帮助；Ctrl-D 退出"""


def format_frame(frame, names, own_id=None, groups=None):
    """Format a server frame and update the supplied name caches."""
    groups = groups if groups is not None else {}
    typ = frame.get("type")
    if typ in ("auth_ok", "presence"):
        if frame.get("client_id") and frame.get("name"):
            names[frame["client_id"]] = frame["name"]
    if typ == "clients":
        for client in frame.get("clients", []):
            if client.get("id") and client.get("name"):
                names[client["id"]] = client["name"]
    def display(client_id):
        return "我" if client_id == own_id and own_id is not None else names.get(client_id, client_id or "未知")
    def group_summary(group):
        gid = group.get("group_id", group.get("id", "未知"))
        name = group.get("name") or gid
        groups[gid] = name
        members = group.get("members", [])
        return f"{name} ({gid})，{len(members)} 人：{', '.join(display(m) for m in members) or '无'}"
    if typ == "auth_ok":
        return f"[系统] 已登录：{frame.get('name', frame.get('client_id', '未知'))} ({frame.get('client_id', '未知')})"
    if typ == "message":
        sender = f"{display(frame['from'])}: " if frame.get("from") else ""
        return f"[广播] {sender}{frame.get('payload', '')}"
    if typ == "dm":
        return f"[私聊] {display(frame.get('from'))}: {frame.get('payload', '')}"
    if typ == "group_message":
        gid = frame.get("group_id", "未知")
        return f"[群:{groups.get(gid, gid)}] {display(frame.get('from'))}: {frame.get('payload', '')}"
    if typ == "presence":
        return f"[系统] {display(frame.get('client_id'))}已{'上线' if frame.get('online') else '下线'}"
    if typ in ("group_created", "group_updated", "invited"):
        label = {"group_created": "群已创建", "group_updated": "群已更新", "invited": "收到群邀请"}[typ]
        return f"[系统] {label}：{group_summary(frame)}"
    if typ == "groups":
        items = [group_summary(group) for group in frame.get("groups", [])]
        return f"[群组] {len(items)} 个" + ("；" + "；".join(items) if items else "")
    if typ == "clients":
        clients = frame.get("clients", [])
        items = [f"{display(c.get('id'))} ({c.get('id', '未知')}, {'在线' if c.get('online') else '离线'})" for c in clients]
        return f"[客户端] {len(items)} 人" + ("：" + "、".join(items) if items else "")
    if typ == "error":
        return f"[错误] {frame.get('error', '未知错误')}"
    return json.dumps(frame, ensure_ascii=False)


async def main():
    key = os.getenv("CLIENT_KEY")
    if not key:
        raise SystemExit("Set CLIENT_KEY before starting the client")
    reader, writer = await asyncio.open_connection(os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "9000")))
    names, groups = {}, {}
    focus = None
    try:
        writer.write((json.dumps({"type": "auth", "key": key}) + "\n").encode())
        await writer.drain()
        response = await reader.readline()
        if not response:
            raise SystemExit("[错误] 认证失败：服务器断开连接")
        auth = json.loads(response)
        if auth.get("type") != "auth_ok":
            raise SystemExit(format_frame(auth, names))
        own_id = auth.get("client_id")
        print(format_frame(auth, names, own_id, groups), flush=True)
        print(HELP, flush=True)

        def prompt():
            if focus is None:
                return "广播> "
            kind, target = focus
            return f"{'群' if kind == 'g' else '私聊'}:{groups.get(target, target) if kind == 'g' else names.get(target, target)}> "

        async def receive():
            while line := await reader.readline():
                try:
                    frame = json.loads(line)
                    print("\n" + format_frame(frame, names, own_id, groups), flush=True)
                except (ValueError, UnicodeError, AttributeError, TypeError):
                    print("\n[错误] 收到无法解析的帧", flush=True)
                print(prompt(), end="", flush=True)
            print("\n[系统] 服务器已断开连接", flush=True)

        async def send():
            nonlocal focus
            loop = asyncio.get_running_loop()
            queue = asyncio.Queue()
            def read_input():
                for line in sys.stdin:
                    loop.call_soon_threadsafe(queue.put_nowait, line)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            threading.Thread(target=read_input, daemon=True).start()
            print(prompt(), end="", flush=True)
            while (line := await queue.get()) is not None:
                line = line.rstrip("\r\n")
                parts = line.split(maxsplit=2)
                frame = None
                if not parts:
                    pass
                elif line == "/help":
                    print(HELP)
                elif line in ("/broadcast", "/focus clear"):
                    focus = None
                    print("[系统] 已切换到广播")
                elif len(parts) == 3 and parts[0] == "/focus" and parts[1] in ("g", "dm") and len(parts[2].split()) == 1:
                    focus = (parts[1], parts[2])
                    print(f"[系统] 已切换到{prompt().rstrip('> ')}")
                elif line == "/groups":
                    frame = {"type": "list_groups"}
                elif line == "/clients":
                    frame = {"type": "list_clients"}
                elif parts[0] == "/create" and len(parts) >= 2:
                    frame = {"type": "create_group", "name": line[len('/create'):].strip()}
                elif len(parts) == 3 and parts[0] == "/invite" and len(parts[2].split()) == 1:
                    frame = {"type": "invite", "group_id": parts[1], "client_id": parts[2]}
                elif len(parts) == 2 and parts[0] == "/join":
                    frame = {"type": "join_group", "group_id": parts[1]}
                elif len(parts) == 3 and parts[0] == "/g":
                    frame = {"type": "group_message", "group_id": parts[1], "payload": parts[2]}
                elif len(parts) == 3 and parts[0] == "/dm":
                    frame = {"type": "dm", "to": parts[1], "payload": parts[2]}
                elif line.startswith("/"):
                    print("[错误] 命令无效，请输入 /help 查看用法")
                elif focus is None:
                    frame = {"type": "message", "payload": line}
                elif focus[0] == "g":
                    frame = {"type": "group_message", "group_id": focus[1], "payload": line}
                else:
                    frame = {"type": "dm", "to": focus[1], "payload": line}
                if frame:
                    writer.write((json.dumps(frame, ensure_ascii=False) + "\n").encode())
                    await writer.drain()
                    if frame["type"] in ("message", "group_message"):
                        print("[系统] 已发送")
                print(prompt(), end="", flush=True)

        tasks = [asyncio.create_task(receive()), asyncio.create_task(send())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
    finally:
        writer.close()
        await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
