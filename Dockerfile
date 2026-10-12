FROM python:3.11-slim

LABEL maintainer="design-shi"
LABEL description="文颜 Markdown 排版器 md2wechat"

WORKDIR /app

RUN pip install --no-cache-dir flask

# Create data directory for persistent storage
RUN mkdir -p /app/data

ENV DATA_DIR=/app/data

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
