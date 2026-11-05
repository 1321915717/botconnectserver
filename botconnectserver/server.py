"""Concurrent newline-delimited JSON message server."""
import asyncio
import hmac
import json
import logging
import os
import signal
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger("botconnectserver")
MAX_FRAME = 64 * 1024
AUTH_TIMEOUT = 10
WRITE_TIMEOUT = 5


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    keys: tuple[str, ...]

    @classmethod
    def from_env(cls):
        keys = [key.strip() for key in os.getenv("CLIENT_KEYS", "").split(",") if key.strip()]
        path = os.getenv("CLIENT_KEYS_FILE")
        if path:
            keys.extend(line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()
                        if line.strip() and not line.lstrip().startswith("#"))
        if not keys:
            raise ValueError("Configure at least one key using CLIENT_KEYS or CLIENT_KEYS_FILE")
        port = int(os.getenv("PORT", "9000"))
        if not 0 <= port <= 65535:
            raise ValueError("PORT must be between 0 and 65535")
        return cls(os.getenv("HOST", "0.0.0.0"), port, tuple(keys))


class Server:
    def __init__(self, config):
        self.config = config
        self.clients = set()
        self.tasks = set()
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(self.connected, self.config.host, self.config.port,
                                                 limit=MAX_FRAME + 1)
        LOG.info("Listening on %s", ", ".join(str(s.getsockname()) for s in self.server.sockets))

    def connected(self, reader, writer):
        task = asyncio.create_task(self.handle(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def send(self, writer, frame):
        writer.write(json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
        await asyncio.wait_for(writer.drain(), WRITE_TIMEOUT)

    async def read_frame(self, reader):
        raw = await reader.readline()
        if not raw:
            return None
        if len(raw) > MAX_FRAME or not raw.endswith(b"\n"):
            raise ValueError("frame too large or incomplete")
        frame = json.loads(raw.decode("utf-8"))
        if not isinstance(frame, dict):
            raise ValueError("frame must be an object")
        return frame

    async def handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        authenticated = False
        try:
            frame = await asyncio.wait_for(self.read_frame(reader), AUTH_TIMEOUT)
            key = frame.get("key") if frame and frame.get("type") == "auth" else None
            # Compare bytes to support non-ASCII keys and avoid timing-sensitive equality.
            valid = isinstance(key, str) and any(
                hmac.compare_digest(key.encode("utf-8"), candidate.encode("utf-8"))
                for candidate in self.config.keys
            )
            if not valid:
                await self.send(writer, {"type": "error", "error": "authentication failed"})
                return
            await self.send(writer, {"type": "auth_ok"})
            self.clients.add(writer)
            authenticated = True
            LOG.info("Client authenticated: %s", peer)
            while True:
                frame = await self.read_frame(reader)
                if frame is None:
                    break
                if frame.get("type") != "message" or "payload" not in frame:
                    await self.send(writer, {"type": "error", "error": "expected message with payload"})
                    continue
                LOG.info("Message from %s: %s", peer, json.dumps(frame["payload"], ensure_ascii=True))
                outgoing = {"type": "message", "payload": frame["payload"]}
                # Independent sends prevent a slow peer from blocking other recipients indefinitely.
                await asyncio.gather(*(self.send_to_client(client, outgoing)
                                       for client in tuple(self.clients) if client is not writer))
        except (asyncio.TimeoutError, ValueError, UnicodeError, json.JSONDecodeError, ConnectionError, OSError) as exc:
            LOG.info("Connection closed for %s: %s", peer, type(exc).__name__)
        finally:
            self.clients.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            if authenticated:
                LOG.info("Client disconnected: %s", peer)

    async def send_to_client(self, writer, frame):
        try:
            await self.send(writer, frame)
        except (ConnectionError, OSError, asyncio.TimeoutError):
            self.clients.discard(writer)
            writer.close()

    async def close(self):
        if self.server:
            self.server.close()
        for task in tuple(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
        if self.server:
            await self.server.wait_closed()


async def run(config):
    server = Server(config)
    await server.start()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    try:
        await stop.wait()
    finally:
        await server.close()
        LOG.info("Server stopped")


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(run(Config.from_env()))
    except (ValueError, OSError) as exc:
        LOG.error("Cannot start server: %s", exc)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        pass
