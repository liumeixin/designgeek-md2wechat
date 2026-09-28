# Wenyan Editor (Windows) — Agent Context

> 本文件由 Hermes Agent 维护，记录项目架构、决策和进展。人不要手动改。

## 项目定位

微信公众号 Markdown 排版工具。核心能力：Markdown → 带主题样式的 HTML → 复制到微信公众号编辑器。

## Windows 改造说明

本项目从 WSL 环境迁移到 Windows 本地运行，主要变化：

| 项目 | WSL 版 | Windows 版 |
|------|--------|------------|
| 运行方式 | `run.sh` + systemd | 双击 `文颜排版器.bat` |
| 截图脚本 | `scripts/html2png.mjs`（WSL Playwright） | `scripts/html2png.mjs`（自动检测 Chromium） |
| 启动命令 | `python3 backend/app.py` | `python backend/app.py` |
| 服务管理 | systemd user service | 手动启动/停止 |
| 自启功能 | 有（systemctl enable） | 无（手动启动） |

## 架构决策

### 前后端分离

- `frontend/`：纯前端，standalone.html 可独立运行（唯一外部依赖 marked.js CDN）
- `backend/`：Flask API 服务，提供 Markdown 解析、主题 CSS 文件服务
- `scripts/`：Windows 本地脚本（html2png.mjs 截图）

### 两种使用模式

1. **standalone.html**（推荐）：双击即用，无后端，所有 CSS 数据内联
2. **Python 直接运行**：双击 `文颜排版器.bat` 或运行 `run.bat`
3. **Docker**：`docker compose up -d`（需要先 `docker build`）

### 截图 API

使用 Playwright + Chromium：
- 脚本：`scripts/html2png.mjs`
- Chromium 路径：自动检测（支持环境变量 `CHROME_PATH` 覆盖）
- 用法：`node scripts/html2png.mjs input.html output.png [width] [height]`

## 文件说明

| 文件 | 用途 |
|------|------|
| `frontend/index.html` | 编辑器主页面（Flask 模板） |
| `frontend/standalone.html` | 独立版（数据内联） |
| `frontend/themes.json` | 15 个主题的完整 CSS |
| `frontend/dimensions.json` | 18 个维度的混搭 CSS 片段 |
| `frontend/build.py` | 从 CSS 源文件构建 JSON |
| `frontend/build-static.py` | 从 index.html + JSON 构建 standalone |
| `backend/app.py` | Flask 服务（API + 前端托管） |
| `backend/markdown_parser.py` | 正则 Markdown 解析器 |
| `backend/static/css/themes/` | 15 个主题 CSS 文件 |
| `scripts/html2png.mjs` | Playwright 截图脚本（Windows 版） |
| `文颜排版器.bat` | 双击启动脚本（后台运行） |
| `run.bat` | 命令行启动脚本（前台运行） |
| `requirements.txt` | Python 依赖 |

## 变更日志

### 2026-07-15：Windows 改造

- 从 WSL 环境迁移到 Windows 本地运行
- 修改 `scripts/html2png.mjs`，自动检测 Chromium 路径（兼容 Windows/Linux/Mac）
- 修改 `文颜排版器.bat`，去掉 WSL 调用，直接运行本地 Python
- 新增 `run.bat` 命令行启动脚本
- 新增自动依赖检查（首次运行自动安装 Flask、Playwright）
- 更新 README.md 和 Agent.md
- 删除 WSL 专用脚本（install.sh、uninstall.sh）
- 修改 docker-compose.yml 容器名为 `wenyan-editor-win`
