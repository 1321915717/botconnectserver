# grok/ — Grok Bot 的 BotConnect 监听端部署包

把 `grok.py`（BotConnect WebSocket 客户端）连同部署它所需的全部文件收在一起。
换个 Grok 账号时，克隆本仓库，照下面「快速部署」走一遍就能跑起来。

## 它是干什么的

`grok.py` 用 WebSocket 连上 BotConnect 服务端（本仓库的服务端），收服务端 /
操作员发来的消息，带 UTC 时间戳记到同目录的 `grok-inbox.log`；也可以用
`--send` 单发一帧回去（比如给操作员回私聊）。协议细节见 `grok.py` 顶部的注释。

## 服务端地址

| 用途 | 地址 |
| --- | --- |
| 控制台（网页） | http://43.173.102.253:8319 |
| WebSocket（Grok 连这个） | ws://43.173.102.253:8320 |
| TCP（机器人 socket） | 43.173.102.253:8317 |

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `WS_URL` | WebSocket 地址，默认 `ws://43.173.102.253:8320` |
| `GROK_KEY` | 服务端 `CLIENT_KEYS` 里给 Grok 配的**专用 key**（必填，不写进代码） |
| `http_proxy` / `https_proxy` | 这台电脑的出口只转发 HTTP(S)，服务必须带代理变量，否则直连会被拦住 |

## 它是怎么跑起来的

三件套，缺一不可：

1. **systemd 服务 `grok-listener`**：`grok.py` 常驻运行，断线按 1/2/5/10/30 秒重连，
   崩了自动重启。unit 见 `grok-listener.service`，环境来自 `~/.config/grok-listener.env`。
2. **看门狗**：定时任务每 5 分钟检查一次服务在不在跑，不在就拉起来。
   代理密码几分钟就轮换一次，看门狗每次检查也顺带验证代理密码是否还有效，
   过期了就用当前 shell 的新密码重写 env 文件再重启服务。
   脚本见 `ensure-listener.sh`。
3. **新消息通知（hook）**：`grok-inbox-watch.sh` 每 5 秒只读一个值——日志的行数。
   行数没变就静默退出，零成本；变了才唤醒 agent，读新增的行并通知到聊天里。
   状态记在 `~/hooks/state/grok-inbox-watch/lines`。

## 快速部署

```bash
git clone git@github.com:1321915717/botconnectserver.git
cd botconnectserver
# 1. 先在服务端 CLIENT_KEYS 里给 Grok 加一个专用 key（换 key 要重启服务端），
#    然后带着 key 跑部署：
GROK_KEY=<你的 Grok 专用 key> bash grok/deploy.sh
```

`deploy.sh` 会：装 `websockets` 依赖、写 `~/.config/grok-listener.env`（已存在就不覆盖）、
装 systemd 服务并启动、验证服务连上且日志出现 `auth_ok`。

部署完还差一步 hook 注册（需要 Grok Bot 自己的工具）：
把 `grok/grok-inbox-watch.sh` 装到 `~/hooks/scripts/`，注册一个事件 hook，
轮询间隔 5 秒，唤醒后读日志新增行并通知到主聊天。

## 注意

- **不要用 `bob-secret` / `alice-secret` 当 Grok 的 key。** 给 Grok 配自己的专用 key，
  生产部署必须换成真正的独立密钥，不要共用文档里的示例 key。
- `grok-inbox.log` 和 `grok-listener.out` 是本地运行产物，不进仓库。
- 单发一帧：`GROK_KEY=xxx WS_URL=ws://43.173.102.253:8320 python3 grok/grok.py --send '{"type":"dm","to":"admin-secret","payload":"hi"}'`
  注意：单发要用实时 shell 的代理环境，不要 source 那个 env 文件（里面的代理密码几分钟就过期）。
