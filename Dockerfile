# BotConnect 服务镜像：标准库 TCP + WebSocket + 内置前端静态托管
# 基于官方 Python 3.12 slim，依赖仅 python-dotenv
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 先拷贝依赖清单，利用 Docker 缓存层
COPY pyproject.toml ./
COPY botconnectserver ./botconnectserver

# 安装（含包内 web_dist 静态资源）
RUN pip install --no-cache-dir .

# 运行用户（非 root，安全）
RUN useradd --create-home --uid 10001 appuser
USER appuser

# 端口：9100 TCP、9101 WebSocket、9102 静态页面
EXPOSE 9100 9101 9102

# 启动入口
ENTRYPOINT ["botconnectserver"]
