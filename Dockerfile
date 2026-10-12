FROM python:3.11-slim

LABEL maintainer="designgeek"
LABEL description="文颜 Markdown 排版器 md2wechat"

WORKDIR /app

RUN pip install --no-cache-dir flask

# Create data directory for persistent storage
RUN mkdir -p /app/data

ENV DATA_DIR=/app/data

# 🔴 容器内必须固定 8080：
#   app.py 的默认端口是 18888（桌面端用），而镜像对外声明 EXPOSE 8080。
#   若不显式设 PORT，容器内实际监听 18888 → 与端口映射/EXPOSE 不一致
#   → 绿联云(UGOS)等平台打开链接会报 "failed to forward request"。
#   docker-compose 里也传了 PORT=8080，这里再兜一层，保证「直接跑镜像」也不会错。
ENV PORT=8080
ENV HOST=0.0.0.0

EXPOSE 8080

# Thin image: only the app code is baked in.
# With docker-compose, frontend/ and backend/ are bind-mounted (read-only)
# and wenyan-data/ is the read-write volume.
# NOTE: scripts/ is deliberately NOT copied — the screenshot feature falls back
# to the container path in backend/app.py when scripts/html2png.mjs is absent.
COPY backend/app.py ./backend/app.py
COPY backend/markdown_parser.py ./backend/markdown_parser.py
COPY backend/static/ ./backend/static/
COPY frontend/ ./frontend/

CMD ["python", "backend/app.py"]
