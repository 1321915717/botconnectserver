#!/bin/bash
# 看门狗：muse.py 没在跑就启动它（用于虚拟机重启/重建后恢复监听）。
# 密钥从 /home/hatch/.config/muse-listener.env 读取，不写在这里。
# @MUSE_DIR@ 由 deploy.sh 安装时替换为 muse/ 目录的实际路径。
MUSE_DIR="@MUSE_DIR@"
ENV_FILE="/home/hatch/.config/muse-listener.env"

if pgrep -f "python3 $MUSE_DIR/muse.py" >/dev/null 2>&1; then
  exit 0
fi
set -a
. "$ENV_FILE"
set +a
cd "$MUSE_DIR" || exit 1
nohup /usr/bin/python3 "$MUSE_DIR/muse.py" >> "$MUSE_DIR/muse-listener.out" 2>&1 &
