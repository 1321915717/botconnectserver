#!/bin/bash
# 看门狗：grok.py 没在跑就启动它（用于虚拟机重启/重建后恢复监听）。
# 密钥从 /home/hatch/.config/grok-listener.env 读取，不写在这里。
# @GROK_DIR@ 由 deploy.sh 安装时替换为 grok/ 目录的实际路径。
GROK_DIR="@GROK_DIR@"
ENV_FILE="/home/hatch/.config/grok-listener.env"

if pgrep -f "python3 $GROK_DIR/grok.py" >/dev/null 2>&1; then
  exit 0
fi
set -a
. "$ENV_FILE"
set +a
cd "$GROK_DIR" || exit 1
nohup /usr/bin/python3 "$GROK_DIR/grok.py" >> "$GROK_DIR/grok-listener.out" 2>&1 &
