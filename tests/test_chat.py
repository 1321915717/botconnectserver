import asyncio
import base64
import json
import os
import struct
import unittest

from botconnectserver.server import Config, Server


class ChatTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = Server(Config('127.0.0.1', 0, ('alice', 'bob'), 0, {'alice': 'Alice'}, frozenset({'alice'})))
        await self.server.start()
        self.port = self.server.server.sockets[0].getsockname()[1]
        self.ws_port = self.server.ws_server.sockets[0].getsockname()[1]
        self.writers = []

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
            await writer.wait_closed()
        await self.server.close()

    async def tcp(self, key):
        r, w = await asyncio.open_connection('127.0.0.1', self.port)
        self.writers.append(w)
        await self.send(w, {'type': 'auth', 'key': key})
        self.assertEqual((await self.until(r, 'auth_ok'))['client_id'], key)
        return r, w

    async def send(self, writer, frame):
        writer.write(json.dumps(frame).encode() + b'\n')
        await writer.drain()

    async def until(self, reader, typ):
        for _ in range(20):
            line = await asyncio.wait_for(reader.readline(), 2)
            self.assertTrue(line)
            frame = json.loads(line)
            if frame['type'] == typ:
                return frame
        self.fail('frame not received: ' + typ)

    async def test_tcp_groups_and_compatibility(self):
        a, aw = await self.tcp('alice')
        b, bw = await self.tcp('bob')
        await self.send(aw, {'type': 'message', 'payload': 'legacy'})
        self.assertEqual((await self.until(b, 'message'))['payload'], 'legacy')
        await self.send(aw, {'type': 'create_group', 'name': 'Team'})
        gid = (await self.until(a, 'group_created'))['group_id']
        await self.send(aw, {'type': 'invite', 'group_id': gid, 'client_id': 'bob'})
        self.assertIn('bob', (await self.until(b, 'group_updated'))['members'])
        await self.send(bw, {'type': 'group_message', 'group_id': gid, 'payload': 'hello'})
        self.assertEqual((await self.until(a, 'group_message'))['from'], 'bob')
        await self.send(aw, {'type': 'dm', 'to': 'bob', 'payload': 'private'})
        self.assertEqual((await self.until(a, 'dm'))['payload'], 'private')
        self.assertEqual((await self.until(b, 'dm'))['payload'], 'private')
        await self.send(bw, {'type': 'list_groups'})
        self.assertEqual((await self.until(b, 'groups'))['groups'][0]['id'], gid)

    async def test_websocket_to_tcp(self):
        tcp, _ = await self.tcp('bob')
        reader, writer = await asyncio.open_connection('127.0.0.1', self.ws_port)
        self.writers.append(writer)
        key = base64.b64encode(os.urandom(16)).decode()
        writer.write((f'GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        await writer.drain()
        self.assertIn(b'101 Switching Protocols', await reader.readuntil(b'\r\n\r\n'))
        async def ws_send(frame):
            data = json.dumps(frame).encode()
            mask = os.urandom(4)
            writer.write(bytes([0x81, 0x80 | len(data)]) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
            await writer.drain()
        async def ws_read():
            head = await asyncio.wait_for(reader.readexactly(2), 2)
            length = head[1] & 127
            if length == 126:
                length = struct.unpack('!H', await reader.readexactly(2))[0]
            return json.loads(await reader.readexactly(length))
        await ws_send({'type': 'auth', 'key': 'alice'})
        self.assertEqual((await ws_read())['type'], 'auth_ok')
        await ws_send({'type': 'dm', 'to': 'bob', 'payload': 'from websocket'})
        self.assertEqual((await self.until(tcp, 'dm'))['payload'], 'from websocket')
        while (frame := await ws_read())['type'] != 'dm':
            pass
        self.assertEqual(frame['to'], 'bob')

    async def test_bad_auth(self):
        r, w = await asyncio.open_connection('127.0.0.1', self.port)
        self.writers.append(w)
        await self.send(w, {'type': 'auth', 'key': 'wrong'})
        self.assertEqual((await self.until(r, 'error'))['error'], 'authentication failed')
        self.assertEqual(await r.read(), b'')

    async def test_client_permissions_restricted(self):
        # bob 是客户端（非服务端），不能广播、不能建群、不能邀请
        a, aw = await self.tcp('alice')  # 服务端
        b, bw = await self.tcp('bob')    # 客户端
        # 客户端发 message：应作为上报只送达服务端，不广播给其他客户端
        await self.send(bw, {'type': 'message', 'payload': 'report'})
        report = await self.until(a, 'message')
        self.assertEqual(report['payload'], 'report')
        self.assertEqual(report['from'], 'bob')
        # 客户端不能建群
        await self.send(bw, {'type': 'create_group', 'name': 'nope'})
        self.assertEqual((await self.until(b, 'error'))['error'], 'create_group requires server')
        # 客户端 list_clients 只返回自己，不暴露服务端
        await self.send(bw, {'type': 'list_clients'})
        clients = (await self.until(b, 'clients'))['clients']
        self.assertEqual([c['id'] for c in clients], ['bob'])
        # 服务端 list_clients 返回全部（含离线）
        await self.send(aw, {'type': 'list_clients'})
        server_clients = (await self.until(a, 'clients'))['clients']
        self.assertEqual({c['id'] for c in server_clients}, {'alice', 'bob'})
