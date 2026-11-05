"""Authenticated TCP NDJSON and WebSocket chat server (standard library only)."""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import signal
import struct
import uuid
from dataclasses import dataclass, field
from pathlib import Path

LOG = logging.getLogger('botconnectserver')
MAX_FRAME = 64 * 1024
AUTH_TIMEOUT = 10
WRITE_TIMEOUT = 5


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    keys: tuple[str, ...]
    ws_port: int = 9001
    names: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls):
        names = {}
        keys = [k.strip() for k in os.getenv('CLIENT_KEYS', '').split(',') if k.strip()]
        path = os.getenv('CLIENT_KEYS_FILE')
        if path:
            for line in Path(path).read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, sep, name = line.partition('=')
                key = key.strip()
                if key:
                    keys.append(key)
                    if sep and name.strip():
                        names[key] = name.strip()
        for entry in os.getenv('CLIENT_NAMES', '').split(','):
            key, sep, name = entry.partition(':')
            if sep and key.strip() and name.strip():
                names[key.strip()] = name.strip()
        if not keys:
            raise ValueError('Configure at least one key using CLIENT_KEYS or CLIENT_KEYS_FILE')
        port, ws_port = int(os.getenv('PORT', '9000')), int(os.getenv('WS_PORT', '9001'))
        if not all(0 <= p <= 65535 for p in (port, ws_port)):
            raise ValueError('PORT and WS_PORT must be between 0 and 65535')
        return cls(os.getenv('HOST', '0.0.0.0'), port, tuple(dict.fromkeys(keys)), ws_port, names)


class Session:
    def __init__(self, reader, writer, websocket=False):
        self.reader, self.writer, self.websocket = reader, writer, websocket
        self.id = None
        self.lock = asyncio.Lock()

    async def send(self, frame):
        data = json.dumps(frame, ensure_ascii=False, separators=(',', ':')).encode()
        if self.websocket:
            n = len(data)
            header = bytes([0x81, n]) if n < 126 else bytes([0x81, 126]) + struct.pack('!H', n) if n < 65536 else bytes([0x81, 127]) + struct.pack('!Q', n)
            data = header + data
        else:
            data += b'\n'
        async with self.lock:
            self.writer.write(data)
            await asyncio.wait_for(self.writer.drain(), WRITE_TIMEOUT)

    async def read(self):
        if not self.websocket:
            raw = await self.reader.readline()
            if not raw:
                return None
            if len(raw) > MAX_FRAME or not raw.endswith(b'\n'):
                raise ValueError('frame too large or incomplete')
        else:
            while True:
                head = await self.reader.readexactly(2)
                fin, opcode, masked, length = bool(head[0] & 128), head[0] & 15, bool(head[1] & 128), head[1] & 127
                if head[0] & 0x70 or not fin or not masked:
                    raise ValueError('invalid WebSocket frame')
                if length == 126:
                    length = struct.unpack('!H', await self.reader.readexactly(2))[0]
                elif length == 127:
                    length = struct.unpack('!Q', await self.reader.readexactly(8))[0]
                if length > MAX_FRAME or (opcode >= 8 and length > 125):
                    raise ValueError('frame too large')
                mask = await self.reader.readexactly(4)
                data = await self.reader.readexactly(length)
                raw = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
                if opcode == 8:
                    return None
                if opcode == 9:
                    async with self.lock:
                        self.writer.write(bytes([0x8a, len(raw)]) + raw)
                        await asyncio.wait_for(self.writer.drain(), WRITE_TIMEOUT)
                    continue
                if opcode == 10:
                    continue
                if opcode != 1:
                    raise ValueError('text frames required')
                break
        frame = json.loads(raw.decode('utf-8'))
        if not isinstance(frame, dict):
            raise ValueError('frame must be an object')
        return frame


class Server:
    def __init__(self, config):
        self.config = config
        self.clients = set()
        self.groups = {}
        self.tasks = set()
        self.server = None
        self.ws_server = None

    async def start(self):
        self.server = await asyncio.start_server(self.connected, self.config.host, self.config.port, limit=MAX_FRAME + 1)
        try:
            self.ws_server = await asyncio.start_server(self.ws_connected, self.config.host, self.config.ws_port, limit=MAX_FRAME + 1)
        except Exception:
            self.server.close()
            await self.server.wait_closed()
            raise
        LOG.info('TCP listening on %s; WebSocket listening on %s', self.server.sockets[0].getsockname(), self.ws_server.sockets[0].getsockname())

    def connected(self, reader, writer):
        self.spawn(self.handle(Session(reader, writer)))

    def ws_connected(self, reader, writer):
        self.spawn(self.upgrade(reader, writer))

    def spawn(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def upgrade(self, reader, writer):
        try:
            raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), AUTH_TIMEOUT)
            if len(raw) > 16384:
                raise ValueError('headers too large')
            lines = raw.decode('ascii').split('\r\n')
            if not lines[0].startswith('GET ') or not lines[0].endswith(' HTTP/1.1'):
                raise ValueError('invalid request')
            headers = {}
            for line in lines[1:]:
                if line:
                    key, value = line.split(':', 1)
                    headers[key.lower()] = value.strip()
            key = headers.get('sec-websocket-key', '')
            if (headers.get('upgrade', '').lower() != 'websocket' or
                'upgrade' not in [x.strip() for x in headers.get('connection', '').lower().split(',')] or
                headers.get('sec-websocket-version') != '13' or len(base64.b64decode(key, validate=True)) != 16):
                raise ValueError('invalid upgrade')
            accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            writer.write(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + '\r\n\r\n').encode())
            await writer.drain()
            await self.handle(Session(reader, writer, True))
            return
        except (ValueError, UnicodeError, OSError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            pass
        writer.close()
        await writer.wait_closed()

    def name(self, key):
        return self.config.names.get(key, key)

    async def deliver(self, sessions, frame):
        async def send(session):
            try:
                await session.send(frame)
            except (OSError, ConnectionError, asyncio.TimeoutError):
                session.writer.close()
        await asyncio.gather(*(send(s) for s in tuple(sessions)))

    async def presence(self, key, online):
        await self.deliver(self.clients, {'type': 'presence', 'client_id': key, 'name': self.name(key), 'online': online})

    def group_frame(self, group, kind='group_updated'):
        return {'type': kind, 'group_id': group['id'], 'name': group['name'], 'members': sorted(group['members'])}

    async def handle(self, session):
        try:
            try:
                frame = await asyncio.wait_for(session.read(), AUTH_TIMEOUT)
                key = frame.get('key') if frame and frame.get('type') == 'auth' else None
            except (ValueError, UnicodeError, json.JSONDecodeError):
                key = None
            valid = isinstance(key, str) and any(hmac.compare_digest(key.encode(), candidate.encode()) for candidate in self.config.keys)
            if not valid:
                await session.send({'type': 'error', 'error': 'authentication failed'})
                return
            session.id = key
            was_online = any(s.id == key for s in self.clients)
            await session.send({'type': 'auth_ok', 'client_id': key, 'name': self.name(key)})
            self.clients.add(session)
            if not was_online:
                await self.presence(key, True)
            while True:
                try:
                    frame = await session.read()
                except (json.JSONDecodeError, UnicodeError):
                    await session.send({'type': 'error', 'error': 'invalid JSON'})
                    continue
                if frame is None:
                    break
                await self.dispatch(session, frame)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ValueError, ConnectionError, OSError):
            pass
        finally:
            self.clients.discard(session)
            session.writer.close()
            try:
                await session.writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            if session.id and not any(s.id == session.id for s in self.clients):
                await self.presence(session.id, False)

    async def dispatch(self, s, f):
        typ = f.get('type')
        error = None
        if typ == 'message' and 'payload' in f:
            await self.deliver((c for c in self.clients if c is not s), {'type': 'message', 'payload': f['payload']})
        elif typ == 'list_clients':
            await s.send({'type': 'clients', 'clients': [{'id': k, 'name': self.name(k), 'online': any(c.id == k for c in self.clients)} for k in self.config.keys]})
        elif typ == 'list_groups':
            await s.send({'type': 'groups', 'groups': [{'id': g['id'], 'name': g['name'], 'members': sorted(g['members'])} for g in self.groups.values() if s.id in g['members']]})
        elif typ == 'dm' and 'payload' in f and isinstance(f.get('to'), str):
            target = f['to']
            if target not in self.config.keys:
                error = 'unknown client'
            elif not any(c.id == target for c in self.clients):
                error = 'client offline'
            else:
                await self.deliver((c for c in self.clients if c.id in (s.id, target)), {'type': 'dm', 'from': s.id, 'to': target, 'payload': f['payload']})
        elif typ == 'create_group' and isinstance(f.get('name'), str) and f['name'].strip():
            gid = uuid.uuid4().hex[:12]
            group = {'id': gid, 'name': f['name'].strip()[:100], 'members': {s.id}}
            self.groups[gid] = group
            await self.deliver((c for c in self.clients if c.id == s.id), self.group_frame(group, 'group_created'))
        elif typ in ('invite', 'join_group', 'group_message'):
            gid = f.get('group_id')
            group = self.groups.get(gid) if isinstance(gid, str) else None
            if not group:
                error = 'unknown group'
            elif typ != 'join_group' and s.id not in group['members']:
                error = 'not a group member'
            elif typ == 'group_message':
                if 'payload' not in f:
                    error = 'payload required'
                else:
                    await self.deliver((c for c in self.clients if c.id in group['members'] and c is not s), {'type': 'group_message', 'group_id': gid, 'from': s.id, 'payload': f['payload']})
            else:
                target = s.id if typ == 'join_group' else f.get('client_id')
                if not isinstance(target, str) or target not in self.config.keys:
                    error = 'unknown client'
                else:
                    group['members'].add(target)
                    await self.deliver((c for c in self.clients if c.id in group['members']), self.group_frame(group))
        else:
            error = 'unsupported or invalid frame'
        if error:
            await s.send({'type': 'error', 'error': error})

    async def close(self):
        for server in (self.server, self.ws_server):
            if server:
                server.close()
        for task in tuple(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
        for server in (self.server, self.ws_server):
            if server:
                await server.wait_closed()


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


def main():
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO').upper(), format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    try:
        asyncio.run(run(Config.from_env()))
    except (ValueError, OSError) as exc:
        LOG.error('Cannot start server: %s', exc)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        pass
