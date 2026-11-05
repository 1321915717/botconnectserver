# BotConnect 服务与操作员控制台

基于 Python 3.10+ 标准库的 TCP NDJSON 与 WebSocket 聊天服务，配套 Vue 3 操作员控制台。支持在线状态、私聊、群聊、广播与单向上报；服务端无需安装运行时依赖。

## 角色与连接

- 服务端是连接枢纽，负责认证、在线状态和消息转发。
- 后端服务或机器人使用 **TCP + key** 连接服务端。
- 操作员使用浏览器中的 Vue 控制台，通过 **WebSocket + 控制台 key** 连接服务端。控制台列出服务端当前在线的其他客户端，可选择服务私聊，或创建群聊并从在线服务中邀请成员。

## 启动服务

```sh
export CLIENT_KEYS='admin-secret,alice-secret,bob-secret'
export SERVER_KEYS='admin-secret'
export CLIENT_NAMES='admin-secret:服务端,alice-secret:服务 A,bob-secret:服务 B'
export HOST=0.0.0.0 PORT=9100 WS_PORT=9101
export STATIC_PORT=9102   # 可选：托管包内前端页面
python3 -m botconnectserver
# 或 pip install . 后运行 botconnectserver
```

也支持 `.env` 文件：`main()` 启动时会自动加载项目根目录的 `.env`（需 `python-dotenv`，`uv sync` 自动安装）。

**服务端 / 客户端权限模型**：`SERVER_KEYS` 标记哪些 key 是「服务端（人）」，其余为「客户端（AI Agent）」。服务端拥有管理权限，可广播、创建群聊、邀请成员、查看全部客户端（含离线）；客户端只能通过 `message` 单向上报给服务端、互相 `dm`、在群内发言，不能建群或邀请，且 `list_clients` 只会返回它自己（不暴露服务端 key）。

也可以通过 `CLIENT_KEYS_FILE` 指定 UTF-8 文件，与 `CLIENT_KEYS` 合并。文件每行是一个 key 或 `key=显示名`，空行和以 `#` 开头的行会忽略。`CLIENT_NAMES` 使用逗号分隔的 `key:显示名`，优先于文件内显示名；未设置时显示 key。每个 key 就是稳定的 `client_id`，多个连接可使用同一身份。配置变更需要重启。参见 `config.example`。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| HOST | 0.0.0.0 | TCP 和 WebSocket 监听地址 |
| PORT | 9000 | TCP 端口 |
| WS_PORT | 9001 | WebSocket 端口 |
| CLIENT_KEYS | 空 | 逗号分隔的密钥（全部身份） |
| SERVER_KEYS | 空 | 逗号分隔的服务端（人）key，拥有管理权限 |
| CLIENT_KEYS_FILE | 空 | 密钥文件路径 |
| CLIENT_NAMES | 空 | 逗号分隔的 `key:显示名` |
| STATIC_PORT | 0 | 前端静态托管端口，0 表示不托管 |
| STATIC_PORT | 0 | 前端静态托管端口，0 表示不托管 |
| LOG_LEVEL | INFO | 日志级别 |

> 上表为代码内置默认值；本项目 `.env` 使用 `PORT=9100`、`WS_PORT=9101`（9000/9001 易与常见服务冲突）。

## 前端

需要 Node.js 18+（建议使用当前 LTS）。Vite 是 Vue 官方推荐的现代开发工具，启动和构建快速，适合这个独立前端项目。

```sh
cd web
npm ci
npm run dev
# 生产构建
npm run build
```

`npm run build` 会把产物直接输出到 Python 包内的 `botconnectserver/web_dist/`（见 `vite.config.js` 的 `build.outDir`），打包后前端随包一起分发，服务端自包含。

### 由 Python 服务托管前端（推荐）

打包产物已内置到 Python 包，服务启动时用 `importlib.resources` 从包内读取，无需单独跑 `npm run dev` 或 nginx。只需在 `.env` 中设置静态端口：

```ini
STATIC_PORT=9102
```

启动服务后，浏览器打开 `http://localhost:9102` 即可访问打包好的控制台。前端默认 WebSocket 地址指向同主机 9101 端口，与服务端对齐。静态托管基于标准库 `http.server` + `importlib.resources`，不引入额外依赖，`pip install .` 后也能自带前端。

打开控制台后，输入 WebSocket URL 和 key。默认地址使用当前页面主机名及 9101 端口，可按部署环境修改。

左侧客户端列表展示所有配置的客户端（含离线状态，离线项置灰）。选择客户端进行私聊；客户端通过 `message` 上报的消息会归入对应客户端的私聊会话。创建群聊后，通过群顶部的「邀请服务」从客户端列表选择成员。群 ID 显示在标题下方。

## 双服务与控制台联调

先按上面的配置启动服务端，再分别在两个终端运行：

```sh
CLIENT_KEY='alice-secret' HOST=127.0.0.1 PORT=9100 python3 example_client.py
```

```sh
CLIENT_KEY='bob-secret' HOST=127.0.0.1 PORT=9100 python3 example_client.py
```

保持两个客户端在线，启动前端开发服务器，在浏览器打开其输出地址，用 `ws://localhost:9101` 和 `admin-secret` 登录。侧栏应显示服务 A 和服务 B；选择服务 A 发送私聊，再创建群聊并从客户端列表中邀请服务 B。TCP 客户端可查看收到的消息和群更新。

自动协议冒烟（启动临时服务、两个 TCP 客户端和一个 WebSocket 控制台，验证列表、私聊及群邀请）：

```sh
python3 scripts/smoke_console.py
# 成功输出 SMOKE_OK
```

## TCP 示例客户端

```sh
CLIENT_KEY='alice-secret' HOST=127.0.0.1 PORT=9100 python3 example_client.py
```

启动后默认为广播模式，提示符显示当前会话。用 `/focus g 群ID` 切换到群聊，或用 `/focus dm 客户端ID` 切换到私聊；之后输入的普通文本会发往该会话。用 `/focus clear` 或 `/broadcast` 返回广播模式。群 ID 和客户端 ID 可分别通过 `/groups`、`/clients` 查看。

其他命令：`/create 群名` 创建群，`/invite 群ID 客户端ID` 邀请成员，`/join 群ID` 加入群，`/g 群ID 内容` 和 `/dm 客户端ID 内容` 直接发送消息（不改变当前会话），`/help` 查看帮助。按 Ctrl-D 退出。

## 协议摘要

TCP 为 UTF-8 NDJSON（每个 JSON 对象以换行结束，单帧最多 65536 字节，含换行）；WebSocket 每个文本帧是一个 JSON 对象，最多 65536 字节。首帧须在 10 秒内发送 `{"type":"auth","key":"..."}`，成功返回 `auth_ok`（含 `client_id`、`name`），失败返回 `error` 并关闭。WebSocket 支持文本帧和 ping/pong，不支持分片或二进制帧。

认证后：

- `message` 带 `payload`：服务端发 → 广播给所有其他在线连接；客户端发 → 作为**单向上报**只送达所有在线服务端（带 `from`，不广播给其他客户端）。
- `dm` 带 `to`、`payload`：转发给目标及发送身份的在线连接，返回 `from`、`to`、`payload`；目标离线时报错。任何身份可互发。
- `create_group` 带 `name`：仅服务端可创建，创建者自动加入，返回 `group_created`（`group_id`、`name`、`members`）。
- `invite` 带 `group_id`、`client_id`：仅服务端可邀请已配置身份，在线成员收到 `group_updated`。`join_group` 带 `group_id`：任何知道群 ID 的身份可加入。
- `group_message` 带 `group_id`、`payload`：发送给群内其他在线连接，带 `from`；发送连接不回显。
- `list_groups` 返回自己所在的 `groups`（每项 `id`、`name`、`members`）；`list_clients`：服务端返回所有配置身份及在线状态（含离线），客户端只返回自己。
- 身份上线和最后一个连接下线时广播 `presence`（`client_id`、`name`、`online`）。业务错误返回 `{"type":"error","error":"..."}`，通常保持连接。

旧客户端仍可使用 auth 和 message，忽略额外的认证字段以及 presence 等新类型即可。消息不持久化；群及成员关系仅存内存，服务重启后丢失。发送不保证投递，离线消息不会保存。

## 安全与测试

TCP 和 WebSocket 本身没有 TLS，密钥和消息在网络上明文传输。公网使用时应配置 TLS 终止代理或加密隧道、限制直连并使用随机独立密钥。客户端 ID 就是密钥，服务端（`SERVER_KEYS`）可见全部客户端 ID，客户端只能看到自己；只应在可信客户端之间使用。已知群 ID 的客户端可以加入群。服务不提供速率限制和持久化。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/smoke_console.py   # 协议冒烟，成功输出 SMOKE_OK
```
