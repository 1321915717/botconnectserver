#!/bin/bash
# muse/ 一键部署：把 Satu Digital 的 BotConnect 监听端装成 systemd 服务并启动。
# 用法：MUSE_KEY=<服务端 CLIENT_KEYS 里给 Muse 配的 key> bash muse/deploy.sh
#       或 bash muse/deploy.sh <key>
# 幂等：已存在的东西不会被覆盖（env 文件、已装好的服务只会重装配置并重启验证）。
set -euo pipefail

MUSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HOME/.config/muse-listener.env"
WS_URL="${WS_URL:-ws://43.173.102.253:8320}"
MUSE_KEY="${1:-${MUSE_KEY:-}}"

if [[ -z "$MUSE_KEY" ]]; then
  echo "错误：请给 MUSE_KEY（服务端 CLIENT_KEYS 里给 Muse 配的 key）。"
  echo "用法：MUSE_KEY=<key> bash muse/deploy.sh"
  exit 2
fi

echo "== 1. 检查 websockets 依赖 =="
if ! python3 -c "import websockets" 2>/dev/null; then
  echo "正在安装 websockets..."
  pip install --break-system-packages websockets
else
  echo "websockets 已安装。"
fi

echo "== 2. 写环境文件 $ENV_FILE =="
mkdir -p "$(dirname "$ENV_FILE")"
if [[ -f "$ENV_FILE" ]]; then
  echo "环境文件已存在，不覆盖（要换 key 请手动编辑它）。"
else
  umask 077
  {
    printf 'WS_URL=%s\n' "$WS_URL"
    printf 'MUSE_KEY=%s\n' "$MUSE_KEY"
    printf 'http_proxy=%s\n' "${http_proxy:-}"
    printf 'https_proxy=%s\n' "${https_proxy:-}"
    printf 'HTTP_PROXY=%s\n' "${http_proxy:-}"
    printf 'HTTPS_PROXY=%s\n' "${https_proxy:-}"
  } > "$ENV_FILE"
  echo "环境文件已创建（600 权限）。"
fi

echo "== 3. 安装 systemd 服务 =="
sed "s|@MUSE_DIR@|$MUSE_DIR|g" "$MUSE_DIR/muse-listener.service" > /etc/systemd/system/muse-listener.service
cp /etc/systemd/system/muse-listener.service "$HOME/.config/muse-listener.service"
sed "s|@MUSE_DIR@|$MUSE_DIR|g" "$MUSE_DIR/ensure-listener.sh" > /home/hatch/bin/ensure-muse-listener.sh
chmod 700 /home/hatch/bin/ensure-muse-listener.sh
mkdir -p "$HOME/hooks/scripts"
sed "s|@MUSE_DIR@|$MUSE_DIR|g" "$MUSE_DIR/muse-inbox-watch.sh" > "$HOME/hooks/scripts/muse-inbox-watch.sh"
chmod +x "$HOME/hooks/scripts/muse-inbox-watch.sh"
systemctl daemon-reload
systemctl enable --now muse-listener.service

echo "== 4. 验证服务 =="
LOG_FILE="$MUSE_DIR/muse-inbox.log"
before=0
[[ -f "$LOG_FILE" ]] && before="$(wc -l < "$LOG_FILE" | tr -d ' ')"
ok=0
for _ in $(seq 1 18); do
  sleep 5
  if [[ "$(systemctl is-active muse-listener.service)" == "active" ]] \
    && [[ -f "$LOG_FILE" ]] \
    && tail -n "+$((before + 1))" "$LOG_FILE" 2>/dev/null | grep -q "auth_ok"; then
    ok=1
    break
  fi
done
if [[ "$ok" != "1" ]]; then
  echo "验证失败：服务没有在 90 秒内登录成功。"
  echo "看一下状态：systemctl status muse-listener.service --no-pager"
  echo "看一下输出：tail $MUSE_DIR/muse-listener.out"
  exit 1
fi
echo "服务已启动并登录成功，日志：$LOG_FILE"

echo
echo "== 后续一步（需要 Muse 自己的工具） =="
echo "注册新消息通知 hook：脚本已装到 ~/hooks/scripts/muse-inbox-watch.sh，"
echo "让 Muse 注册一个事件 hook，轮询间隔 5 秒，唤醒后读日志新增行并通知到主聊天。"
echo "测试：从控制台给 Muse 发一条私聊，聊天里应该在几秒内收到通知。"
