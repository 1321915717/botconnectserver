import unittest

from example_client import format_frame


class ConsoleFormattingTest(unittest.TestCase):
    def test_names_and_chat_frames(self):
        names, groups = {}, {}
        self.assertIn('Alice (alice)', format_frame({'type': 'auth_ok', 'name': 'Alice', 'client_id': 'alice'}, names, 'alice', groups))
        format_frame({'type': 'clients', 'clients': [{'id': 'bob', 'name': 'Bob', 'online': True}]}, names, 'alice', groups)
        self.assertEqual(format_frame({'type': 'dm', 'from': 'bob', 'payload': '你好'}, names, 'alice', groups), '[私聊] Bob: 你好')
        self.assertEqual(format_frame({'type': 'dm', 'from': 'alice', 'payload': '嗨'}, names, 'alice', groups), '[私聊] 我: 嗨')
        format_frame({'type': 'group_created', 'group_id': 'g1', 'name': '团队', 'members': ['alice', 'bob']}, names, 'alice', groups)
        self.assertEqual(format_frame({'type': 'group_message', 'group_id': 'g1', 'from': 'bob', 'payload': '早'}, names, 'alice', groups), '[群:团队] Bob: 早')
        self.assertEqual(format_frame({'type': 'presence', 'client_id': 'bob', 'name': '鲍勃', 'online': False}, names, 'alice', groups), '[系统] 鲍勃已下线')
        self.assertEqual(format_frame({'type': 'message', 'payload': '公告'}, names), '[广播] 公告')
        self.assertEqual(format_frame({'type': 'error', 'error': 'client offline'}, names), '[错误] client offline')


if __name__ == '__main__':
    unittest.main()
