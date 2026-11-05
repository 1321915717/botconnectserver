"""Interactive example: CLIENT_KEY=... python example_client.py."""
import asyncio
import json
import os
import sys


async def main():
    key = os.getenv("CLIENT_KEY")
    if not key:
        raise SystemExit("Set CLIENT_KEY before starting the client")
    reader, writer = await asyncio.open_connection(os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "9000")))
    try:
        writer.write((json.dumps({"type": "auth", "key": key}) + "\n").encode())
        await writer.drain()
        response = await reader.readline()
        if not response or json.loads(response).get("type") != "auth_ok":
            raise SystemExit("Authentication failed")
        print("Authenticated. Enter messages; Ctrl-D to exit.", flush=True)

        async def receive():
            while line := await reader.readline():
                print("Received:", line.decode().rstrip(), flush=True)
            print("Server disconnected.", flush=True)

        async def send():
            # Input runs in a daemon thread so shutdown does not wait for a blocked stdin.
            loop = asyncio.get_running_loop()
            import threading
            def read_input():
                for line in sys.stdin:
                    loop.call_soon_threadsafe(queue.put_nowait, line)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            queue = asyncio.Queue()
            threading.Thread(target=read_input, daemon=True).start()
            while (line := await queue.get()) is not None:
                writer.write((json.dumps({"type": "message", "payload": line.rstrip("\n")}, ensure_ascii=False) + "\n").encode())
                await writer.drain()

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
