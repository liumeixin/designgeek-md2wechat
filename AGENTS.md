# 文颜 Markdown 排版器 · md2wechat — Agent Context

> 本文件由 Agent 维护，记录项目架构、决策和进展。

## 📐 排版规范（改动前必读）

**微信公众平台编辑器插件开发规范**
<https://developers.weixin.qq.com/doc/service/guide/product/plugin_spec.html>

公众号编辑器会校验粘贴进去的 HTML。本项目所有「导出 HTML」的改动都必须对照此规范：

| 节 | 要点 |
|---|---|
| §1.3 | `line-height` 不要用会叠字的值 |
| §1.4 / §1.5 | 不内联固定 `width` / `height`（居中不一致、移动端被裁切） |
| **§1.6** | **`text-align` 只接受 `left`/`center`/`right`/`justify`**；`start`/`end` 是逻辑值，各端不一致（**本项目历史主诉 bug**） |
| §1.7 | SVG `<animate>` 的 `begin` 写法 |
| §1.8 | `<pre>` 用法 |
| §3 | **不建议设置任何 `font-family`**，平台默认字体栈已最优 |
| §4.1.1 | 颜色对比度（Dark Mode 可读性） |
| §4.5.2 | 不输出 `!important` |

自检：`python scripts/check_wechat_spec.py out.html --contrast`（退出码 0/1/2）。
完整审计报告：`docs/微信编辑器规范合规-2026-10-12.md`。

## 🔀 提交约定（用户 2026-10-12 定）

- 🔴 **改动后不要自行提交** —— 先**提醒用户确认**；用户确认后才提交并推送到 Gitea。
- 推送用 `python scripts/commit_and_push.py -m "提交说明"`：
  读 `D:/aiwork/services/credentials.env` 的 `GITEA_TOKEN`，走 `http.extraheader`
  （**token 不落盘到 `.git/config`**），网络操作前**剔除代理变量**，多通道自动回退。
- 不带 `-m` = 预览模式，只列出待提交改动，不写任何东西。

## 项目定位

微信公众号 Markdown 排版工具。核心能力：Markdown → 带主题样式的 HTML → 复制到微信公众号编辑器。
**同一份源码同时支持「Windows 桌面端」与「Docker 容器」两种运行方式。**

## 架构决策

### 前后端分离

- `frontend/`：纯前端，唯一外部依赖 marked.js CDN
- `backend/`：Flask API 服务，提供 Markdown 解析、主题 CSS 文件服务
- `scripts/`：本地脚本（html2png.mjs 截图、规范自检、提交推送）

### 两种使用模式（2026-10-12 合并为单仓库）

1. **Windows 桌面端**：双击 `文颜排版器.bat`（托盘）或运行 `run.bat`，默认端口 **18888**
2. **Docker 容器**：`docker compose up -d`，容器内监听 **8080**，映射到宿主 `18888:8080`

> ⚠️ 独立版 `standalone.html` **已于 2026-10-12 弃用并删除**（用户决定，避免双入口歧义）。
> `frontend/index.html` 是**唯一**前端交付物。

### 单仓库的由来（2026-10-12）

原先拆成 `wenyan-editor-win` / `wenyan-editor-docker` 两个仓库，靠脚本
`sync_docker_from_win.py` 手工同步。实测两仓库**约 95% 的文件完全相同**，
真正有差异的只有 6 个文件（`backend/app.py` 的 2 个值 + `Dockerfile` +
`docker-compose.yml` + 3 个文档）。手工同步**没有任何东西会拦截漂移**，已合并为单仓库。

合并时做的 3 处收敛（**容器运行时行为零变化**）：

| 项 | 处理 |
|---|---|
| `Dockerfile` / `docker-compose.yml` | 原 win 侧的是「WSL 版」遗留物（自带文档标注「旧版，可忽略」），已删除；统一用薄容器版 |
| `backend/app.py` | 端口仍默认 18888（桌面端），容器靠 compose 传 `PORT=8080` 覆盖；playwright 路径改为**自动探测** |
| `.dockerignore` | 新增 —— 挡掉 `.venv`（5.4 MB）、`*.bak`、桌面端启动器等，避免污染构建上下文 |

### 容器（薄镜像）

- 镜像名 **写死在 workflow 里**（`IMAGE_NAME: liumeixin/design-shi-md2wechat`），
  不用 `${{ github.repository }}` —— 这样仓库改名后镜像名保持稳定，下游无需跟着改。
- 镜像只打包 `backend/` + `frontend/`；`frontend/`、`backend/` 以**只读卷**挂载，
  `wenyan-data/` 为读写卷。**改主题 CSS 不需要重建镜像。**
- 🔴 `scripts/` **刻意不打进镜像也不挂载** —— `backend/app.py` 里 playwright 路径
  会自动回落到容器内置路径 `/opt/data/scripts_node/pw_runtime/html2png.mjs`。
  **不要**给镜像加 `COPY scripts/` 或给 compose 加 `./scripts` 挂载，否则容器内会
  去找一个没有 Playwright 的本地脚本。

### 截图 API

使用 Playwright + Chromium：
- 脚本：`scripts/html2png.mjs`
- Chromium 路径：自动检测（支持环境变量 `CHROME_PATH` 覆盖）
- 用法：`node scripts/html2png.mjs input.html output.png [width] [height]`

## 文件说明

| 文件 | 用途 |
|------|------|
| `frontend/index.html` | 编辑器主页面（Flask 模板）——**唯一**前端交付物 |
| `frontend/themes.json` | 19 个主题的完整 CSS（15 个主题的**真源**，见下） |
| `frontend/dimensions.json` | 18 个维度的混搭 CSS 片段 |
| `frontend/build.py` | 从 CSS 源文件构建 JSON（输出 `indent=2`，幂等） |
| `backend/app.py` | Flask 服务（API + 前端托管），桌面端/容器共用 |
| `backend/markdown_parser.py` | 正则 Markdown 解析器 |
| `backend/static/css/themes/` | 19 个主题 CSS 文件（其中 4 个是**真源**，见下） |
| `scripts/html2png.mjs` | Playwright 截图脚本（桌面端） |
| `scripts/check_wechat_spec.py` | 产出 HTML 的微信规范静态自检（§1.3–§1.6/§3/§4.1.1/§4.5.2） |
| `scripts/commit_and_push.py` | 提交并推送到 Gitea（多通道回退，token 不落盘） |
| `Dockerfile` | 薄容器定义 |
| `docker-compose.yml` | 容器编排（`image:` + `build:` 同时提供，可拉可建） |
| `.dockerignore` | 构建上下文排除规则 |
| `文颜排版器.bat` / `.vbs` | 双击启动脚本（托盘、静默） |
| `run.bat` | 命令行启动脚本（前台） |
| `start.vbs` / `install-autostart.bat` / `uninstall-autostart.bat` | 开机自启（`schtasks`，需管理员） |
| `tray.py` | 系统托盘程序 |
| `requirements.txt` | Python 依赖 |

> ⚠️ **主题「双源」陷阱**：`frontend/themes.json` 与 `backend/static/css/themes/*.css`
> 谁是权威取决于主题——
> **15 个主题**（claude/cli/color-pop/cyber/default/fireworks/girl-pink/grass/lavender-purple/
> macarons/newyear/parrotalk/purple-yellow-pop/sunrise/winter）的 CSS 是 `--wy-*` 占位文件，
> **themes.json 才是真源**；
> **4 个主题**（dark-green/notebook-blue/notebook-purple/ugreen）的 CSS 是真文件，
> **CSS 才是真源**，`build.py` 会用 CSS 覆盖 themes.json。
> 改配色前先确认，否则会被 `build.py` 冲掉。
> 详见 `docs/微信编辑器规范合规-2026-10-12.md` §七.5。
> （原第 5 个 `grass-nobg` 是零样式坏主题，已于 2026-10-12 删除。）

## 变更日志

### 2026-10-12（傍晚）：合并为单仓库 `design-shi-md2wechat`

- 仓库由 `wenyan-editor-win` + `wenyan-editor-docker` 合并为单仓库
  **`design-shi-md2wechat`**，镜像名同步为 `ghcr.io/liumeixin/design-shi-md2wechat`。
- 删除 win 侧的 WSL 遗留 `Dockerfile` / `docker-compose.yml`，改用薄容器版。
- `backend/app.py`：playwright 路径改自动探测（桌面端/容器共用一份）。
- 新增 `.dockerignore`；`.gitignore` 补 `.venv/`。
- 修正 `文颜排版器.bat`：原指向已退役的 Hermes venv 路径（**文件已不存在，启动器是坏的**），
  改为优先用仓库 `.venv`、回落到系统 `python`。
- 补 `requirements.txt` 缺失的托盘依赖（`pystray` / `pillow`）——
  原文件只有 `flask`，这正是旧 `.bat` 要去借 Hermes venv 的原因。
- 删除 `scripts/sync_docker_from_win.py`（合并后不再需要）。
- 删除历史备份 `frontend/themes.json.bak`、`frontend/index.html.bak.202607051732`。
- 新增 `scripts/commit_and_push.py`。
- 旧仓库 `wenyan-editor-docker` 已删除。

### 2026-10-12（下午）：删除 standalone 与坏主题

- **删除 `standalone.html`**（及生成脚本 `frontend/build-static.py`）：双入口易引起歧义，
  用户决定弃用，只保留 `frontend/index.html` 单入口。
- **删除坏主题 `grass-nobg`**：其 CSS 与 themes.json 条目只有 `--wy-*` 变量、
  无任何实际样式，渲染为裸排版。已从 `backend/static/css/themes/`、
  `build.py` 显示名表、`themes.json`/`dimensions.json`/`manifest.json` 全部移除。
  主题总数 **20 → 19**，真源主题 **5 → 4**。

### 2026-10-12（上午）：微信编辑器规范合规 + docker 同步

按[微信公众平台编辑器插件开发规范](https://developers.weixin.qq.com/doc/service/guide/product/plugin_spec.html)
做了一轮合规改造（用户主诉：公众号提示「文字对齐属性使用了非标准值」）：

- **§1.6 text-align**：`copyHtml()` 新增 `cleanValue()` 归一化，
  `start→left` / `end→right` / `match-parent→left`，只放行 `left/center/right/justify`。
  导出 HTML 里 `text-align:start` **666 → 0**（根因：`getComputedStyle()` 对未设对齐的
  元素返回初始值 `start`）。
- **§3 font-family**：正文一律不内联字体族（仅保留 `code/pre` 等宽例外）。
- **§1.4/§1.5**：不再内联固定 `width`/`height`；**§4.5.2**：不输出 `!important`。
- **§4.1.1 颜色对比度**：修 8 处（grass/color-pop 正文强调色 + macarons/grass/girl-pink/
  winter 序号徽章 + ugreen 强调绿），见报告 §六。
- **修既有严重缺陷**：`injectPseudoElements()` 的 `url()` 提取正则会把
  `content: url(data:image/svg+xml,…)` 的整条 URI 当正文文字输出（187 处 → 0）。
- **构建**：`build.py` 输出改 `indent=2`（幂等）；补 `notebook-purple` 主题（原缺 CSS 源）。
- **新增**：`scripts/check_wechat_spec.py`（规范自检）。

详见 `docs/微信编辑器规范合规-2026-10-12.md`。

### 2026-07-15：Windows 改造

- 从 WSL 环境迁移到 Windows 本地运行
- 修改 `scripts/html2png.mjs`，自动检测 Chromium 路径（兼容 Windows/Linux/Mac）
- 修改 `文颜排版器.bat`，去掉 WSL 调用，直接运行本地 Python
- 新增 `run.bat` 命令行启动脚本
- 新增自动依赖检查（首次运行自动安装 Flask、Playwright）
- 更新 README.md 和 Agent.md
- 删除 WSL 专用脚本（install.sh、uninstall.sh）
