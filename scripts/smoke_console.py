#!/usr/bin/env python3
"""Exercise the operator console protocol against two TCP services."""
import asyncio
import base64
import json
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from botconnectserver.server import Config, Server


async def main():
    server = Server(Config('127.0.0.1', 0, ('service-a', 'service-b', 'console'), 0, {}, frozenset({'console'})))
    await server.start()
    writers = []

    async def tcp_send(writer, frame):
        writer.write(json.dumps(frame).encode() + b'\n')
        await writer.drain()

    async def tcp_until(reader, kind):
        while True:
            line = await asyncio.wait_for(reader.readline(), 3)
            if not line:
                raise RuntimeError('TCP connection closed')
            frame = json.loads(line)
            if frame['type'] == 'error':
                raise RuntimeError(frame)
            if frame['type'] == kind:
                return frame

    async def tcp(key):
        reader, writer = await asyncio.open_connection('127.0.0.1', server.server.sockets[0].getsockname()[1])
        writers.append(writer)
        await tcp_send(writer, {'type': 'auth', 'key': key})
        assert (await tcp_until(reader, 'auth_ok'))['client_id'] == key
        return reader

    try:
        a = await tcp('service-a')
        b = await tcp('service-b')
        reader, writer = await asyncio.open_connection('127.0.0.1', server.ws_server.sockets[0].getsockname()[1])
        writers.append(writer)
        key = base64.b64encode(os.urandom(16)).decode()
        writer.write((f'GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        await writer.drain()
        assert b'101 Switching Protocols' in await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 3)

        async def ws_send(frame):
            data = json.dumps(frame).encode()
            mask = os.urandom(4)
            length = len(data)
            header = bytes([0x81, 0x80 | length]) if length < 126 else bytes([0x81, 0x80 | 126]) + struct.pack('!H', length)
            writer.write(header + mask + bytes(byte ^ mask[i % 4] for i, byte in enumerate(data)))
            await writer.drain()

        async def ws_until(kind):
            while True:
                head = await asyncio.wait_for(reader.readexactly(2), 3)
                length = head[1] & 127
                if length == 126:
                    length = struct.unpack('!H', await reader.readexactly(2))[0]
                elif length == 127:
                    length = struct.unpack('!Q', await reader.readexactly(8))[0]
                frame = json.loads(await reader.readexactly(length))
                if frame['type'] == 'error':
                    raise RuntimeError(frame)
                if frame['type'] == kind:
                    return frame

        await ws_send({'type': 'auth', 'key': 'console'})
        assert (await ws_until('auth_ok'))['client_id'] == 'console'
        await ws_send({'type': 'list_clients'})
        clients = (await ws_until('clients'))['clients']
        assert {'service-a', 'service-b'} <= {c['id'] for c in clients if c['online']}
        await ws_send({'type': 'dm', 'to': 'service-a', 'payload': 'smoke dm'})
        assert (await tcp_until(a, 'dm'))['payload'] == 'smoke dm'
        assert (await ws_until('dm'))['to'] == 'service-a'
        await ws_send({'type': 'create_group', 'name': 'smoke'})
        group_id = (await ws_until('group_created'))['group_id']
        await ws_send({'type': 'invite', 'group_id': group_id, 'client_id': 'service-b'})
        assert 'service-b' in (await ws_until('group_updated'))['members']
        assert 'service-b' in (await tcp_until(b, 'group_updated'))['members']
        print('SMOKE_OK')
    finally:
        for writer in writers:
            writer.close()
        for writer in writers:
            await writer.wait_closed()
        await server.close()


if __name__ == '__main__':
    asyncio.run(main())
