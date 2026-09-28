FROM python:3.11-slim

LABEL maintainer="design-shi"
LABEL description="文颜 Markdown 排版器 (WSL 版)"

WORKDIR /app

RUN pip install --no-cache-dir flask

# Playwright + Chromium for screenshot API
RUN pip install --no-cache-dir playwright && \
    playwright install chromium --with-deps

# Create data directory for persistent storage
RUN mkdir -p /app/data

ENV DATA_DIR=/app/data

EXPOSE 8080

# Copy all files
COPY backend/app.py ./backend/app.py
COPY backend/markdown_parser.py ./backend/markdown_parser.py
COPY backend/static/ ./backend/static/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/

CMD ["python", "backend/app.py"]
