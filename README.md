# BotConnect 服务与操作员控制台

基于 Python 3.10+ 标准库的 TCP NDJSON 与 WebSocket 聊天服务，配套 Vue 3 操作员控制台。支持在线状态、私聊、群聊和旧版广播；服务端无需安装运行时依赖。

## 角色与连接

- 服务端是连接枢纽，负责认证、在线状态和消息转发。
- 后端服务或机器人使用 **TCP + key** 连接服务端。
- 操作员使用浏览器中的 Vue 控制台，通过 **WebSocket + 控制台 key** 连接服务端。控制台列出服务端当前在线的其他客户端，可选择服务私聊，或创建群聊并从在线服务中邀请成员。

## 启动服务

```sh
export CLIENT_KEYS='alice-secret,bob-secret,console-secret'
export CLIENT_NAMES='alice-secret:服务 A,bob-secret:服务 B,console-secret:控制台'
export HOST=0.0.0.0 PORT=9000 WS_PORT=9001
python3 -m botconnectserver
# 或 pip install . 后运行 botconnectserver
```

也可以通过 `CLIENT_KEYS_FILE` 指定 UTF-8 文件，与 `CLIENT_KEYS` 合并。文件每行是一个 key 或 `key=显示名`，空行和以 `#` 开头的行会忽略。`CLIENT_NAMES` 使用逗号分隔的 `key:显示名`，优先于文件内显示名；未设置时显示 key。每个 key 就是稳定的 `client_id`，多个连接可使用同一身份。配置变更需要重启。参见 `config.example`。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| HOST | 0.0.0.0 | TCP 和 WebSocket 监听地址 |
| PORT | 9000 | TCP 端口 |
| WS_PORT | 9001 | WebSocket 端口 |
| CLIENT_KEYS | 空 | 逗号分隔的密钥 |
| CLIENT_KEYS_FILE | 空 | 密钥文件路径 |
| CLIENT_NAMES | 空 | 逗号分隔的 `key:显示名` |
| LOG_LEVEL | INFO | 日志级别 |

## 前端

需要 Node.js 18+（建议使用当前 LTS）。Vite 是 Vue 官方推荐的现代开发工具，启动和构建快速，适合这个独立前端项目。

```sh
cd web
npm ci
npm run dev
# 生产构建
npm run build
```

打开开发服务器输出的地址，输入 WebSocket URL 和 key。默认地址使用当前页面主机名及 9001 端口，可按部署环境修改。构建结果在 `web/dist`，可由任意静态服务器托管；Python 服务不托管前端。

左侧选择在线服务进行私聊；创建群聊后，通过群顶部的「邀请服务」从在线服务列表选择成员。群 ID 显示在标题下方。客户端列表包含所有配置身份，界面只展示当前在线且不是本控制台的客户端。

## 双服务与控制台联调

先按上面的配置启动服务端，再分别在两个终端运行：

```sh
CLIENT_KEY='alice-secret' HOST=127.0.0.1 PORT=9000 python3 example_client.py
```

```sh
CLIENT_KEY='bob-secret' HOST=127.0.0.1 PORT=9000 python3 example_client.py
```

保持两个客户端在线，启动前端开发服务器，在浏览器打开其输出地址，用 `ws://localhost:9001` 和 `console-secret` 登录。侧栏应显示服务 A 和服务 B；选择服务 A 发送私聊，再创建群聊并从在线服务中邀请服务 B。TCP 客户端可查看收到的消息和群更新。

自动协议冒烟（启动临时服务、两个 TCP 客户端和一个 WebSocket 控制台，验证列表、私聊及群邀请）：

```sh
python3 scripts/smoke_console.py
# 成功输出 SMOKE_OK
```

## TCP 示例客户端

```sh
CLIENT_KEY='alice-secret' HOST=127.0.0.1 PORT=9000 python3 example_client.py
```

启动后默认为广播模式，提示符显示当前会话。用 `/focus g 群ID` 切换到群聊，或用 `/focus dm 客户端ID` 切换到私聊；之后输入的普通文本会发往该会话。用 `/focus clear` 或 `/broadcast` 返回广播模式。群 ID 和客户端 ID 可分别通过 `/groups`、`/clients` 查看。

其他命令：`/create 群名` 创建群，`/invite 群ID 客户端ID` 邀请成员，`/join 群ID` 加入群，`/g 群ID 内容` 和 `/dm 客户端ID 内容` 直接发送消息（不改变当前会话），`/help` 查看帮助。按 Ctrl-D 退出。

## 协议摘要

TCP 为 UTF-8 NDJSON（每个 JSON 对象以换行结束，单帧最多 65536 字节，含换行）；WebSocket 每个文本帧是一个 JSON 对象，最多 65536 字节。首帧须在 10 秒内发送 `{"type":"auth","key":"..."}`，成功返回 `auth_ok`（含 `client_id`、`name`），失败返回 `error` 并关闭。WebSocket 支持文本帧和 ping/pong，不支持分片或二进制帧。

认证后：

- `message` 带 `payload`：保持旧行为，原样广播给所有其他在线连接，不向发送连接回显。
- `dm` 带 `to`、`payload`：转发给目标及发送身份的在线连接，返回 `from`、`to`、`payload`；目标离线时报错。
- `create_group` 带 `name`：创建者自动加入，返回 `group_created`（`group_id`、`name`、`members`）。
- `invite` 带 `group_id`、`client_id`：任何群成员可直接添加已配置身份，在线成员收到 `group_updated`。`join_group` 带 `group_id`：任何知道群 ID 的身份可加入。
- `group_message` 带 `group_id`、`payload`：发送给群内其他在线连接，带 `from`；发送连接不回显。
- `list_groups` 返回自己所在的 `groups`（每项 `id`、`name`、`members`）；`list_clients` 返回所有配置身份及在线状态。
- 身份上线和最后一个连接下线时广播 `presence`（`client_id`、`name`、`online`）。业务错误返回 `{"type":"error","error":"..."}`，通常保持连接。

旧客户端仍可使用 auth 和 message，忽略额外的认证字段以及 presence 等新类型即可。消息不持久化；群及成员关系仅存内存，服务重启后丢失。发送不保证投递，离线消息不会保存。

## 安全与测试

TCP 和 WebSocket 本身没有 TLS，密钥和消息在网络上明文传输。公网使用时应配置 TLS 终止代理或加密隧道、限制直连并使用随机独立密钥。客户端 ID 就是密钥，用户列表和群成员会向已认证客户端暴露这些 ID；只应在可信客户端之间使用。已知群 ID 的客户端可以加入群。服务不提供速率限制和持久化。

```sh
python3 -m unittest discover -s tests -v
```
