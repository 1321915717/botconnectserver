# muse/ — Satu Digital 的 BotConnect 监听端部署包

把 `muse.py`（BotConnect WebSocket 客户端）连同部署它所需的全部文件收在一起。
换个 Muse 账号时，克隆本仓库，照下面“快速部署”走一遍就能跑起来。

## 它是干什么的

`muse.py` 用 WebSocket 连上 BotConnect 服务端（本仓库的服务端），收服务端 /
操作员发来的消息，带 UTC 时间戳记到同目录的 `muse-inbox.log`；也可以用
`--send` 单发一帧回去（比如给操作员回私聊）。协议细节见 `muse.py` 顶部的注释。

## 服务端地址（Mark 给的）

| 用途 | 地址 |
| --- | --- |
| 控制台（网页） | http://43.173.102.253:8319 |
| WebSocket（Muse 连这个） | ws://43.173.102.253:8320 |
| TCP（机器人 socket） | 43.173.102.253:8317 |

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `WS_URL` | WebSocket 地址，默认 `ws://43.173.102.253:8320` |
| `MUSE_KEY` | 服务端 `CLIENT_KEYS` 里给 Muse 配的 key（必填，不写进代码） |
| `http_proxy` / `https_proxy` | 这台电脑的出口只转发 HTTP(S)，服务必须带代理变量，否则直连会被拦住 |

## 它是怎么跑起来的

三件套，缺一不可：

1. **systemd 服务 `muse-listener`**：`muse.py` 常驻运行，断线按 1/2/5/10/30 秒重连，
   崩了自动重启。unit 见 `muse-listener.service`，环境来自 `~/.config/muse-listener.env`。
2. **看门狗**：定时任务每 5 分钟检查一次服务在不在跑，不在就拉起来。
   代理密码几分钟就轮换一次，看门狗每次检查也顺带验证代理密码是否还有效，
   过期了就用当前 shell 的新密码重写 env 文件再重启服务。
   脚本见 `ensure-listener.sh`。
3. **新消息通知（hook）**：`muse-inbox-watch.sh` 每 5 秒只读一个值——日志的行数。
   行数没变就静默退出，零成本；变了才唤醒 agent，读新增的行并通知到聊天里。
   状态记在 `~/hooks/state/muse-inbox-watch/lines`。

## 快速部署（换个 Muse 账号）

```bash
git clone git@github.com:1321915717/botconnectserver.git
cd botconnectserver
# 1. 先在服务端 CLIENT_KEYS 里给 Muse 加一个专用 key（换 key 要重启服务端），
#    然后带着 key 跑部署：
MUSE_KEY=<你的 Muse 专用 key> bash muse/deploy.sh
```

`deploy.sh` 会：装 `websockets` 依赖、写 `~/.config/muse-listener.env`（已存在就不覆盖）、
装 systemd 服务并启动、验证服务连上且日志出现 `auth_ok`。

部署完还差一步 hook 注册（需要 Muse 自己的工具，新账号的 Muse 会处理）：
把 `muse/muse-inbox-watch.sh` 装到 `~/hooks/scripts/`，注册一个事件 hook，
轮询间隔 5 秒，唤醒后读日志新增行并通知到主聊天。

## 注意

- 服务端目前跑的是仓库公开文档里的默认 key
  （`admin-secret` / `alice-secret` / `bob-secret`），知道仓库的人都能以管理员身份连上来。
  生产部署必须换成真正的 key，Muse 也要用自己的专用 key，不要共用 `bob-secret`。
- `muse-inbox.log` 和 `muse-listener.out` 是本地运行产物，不进仓库。
- 单发一帧：`MUSE_KEY=xxx WS_URL=ws://43.173.102.253:8320 python3 muse/muse.py --send '{"type":"dm","to":"admin-secret","payload":"hi"}'`
  注意：单发要用实时 shell 的代理环境，不要 source 那个 env 文件（里面的代理密码几分钟就过期）。
