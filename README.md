# 文颜 Markdown 排版器 · md2wechat

微信公众号 Markdown 排版工具，支持 19 个主题 × 18 个维度的 CSS 混搭。
**同一份源码同时提供「Windows 桌面端」和「Docker 容器」两种运行方式。**

> 📐 **排版规范**：[微信公众平台编辑器插件开发规范](https://developers.weixin.qq.com/doc/service/guide/product/plugin_spec.html)
> —— 改动「导出 HTML」相关代码前**必读**（尤其 §1.6 `text-align`、§3 `font-family`、§4.1.1 对比度）。
> 自检：`python scripts/check_wechat_spec.py out.html --contrast`

## ✨ 功能特色

- **19 个主题**：涵盖文艺、科技、商务等多种风格
- **18 维度混搭**：字体、颜色、间距、边框等维度自由组合
- **手机预览模式**：实时模拟手机端阅读效果
- **XHS 小红书分页**：支持小红书风格的内容分页展示

## 📦 项目结构

```
.
├── frontend/                 # 编辑器前端（index.html / build.py / 三个 JSON）
├── backend/                  # Flask 服务 + Markdown 解析器 + 19 个主题 CSS
├── wenyan-data/              # 运行时数据卷（自定义主题等）
├── scripts/                  # 规范自检 / 提交推送 / 截图脚本
├── docs/                     # 开发文档与合规报告
├── Dockerfile                # 薄容器（不打 Playwright，前端/后端靠挂载）
├── docker-compose.yml        # 容器编排
├── 文颜排版器.bat / .vbs      # Windows 双击启动（托盘）
├── run.bat                   # Windows 命令行启动
└── requirements.txt          # 桌面端依赖
```

## 🚀 方式一：Windows 桌面端

### 前置条件

- Python 3.8+（[下载](https://www.python.org/downloads/)）
- Node.js（截图功能需要，[下载](https://nodejs.org/)）
- Python 依赖：`pip install -r requirements.txt`（flask + pystray + pillow）

### 启动

直接双击 **`文颜排版器.bat`**（托盘方式静默启动），或命令行：

```cmd
run.bat
```

启动后访问 <http://localhost:18888>。

### 开机自启（可选）

- 安装：双击 `install-autostart.bat`
- 卸载：双击 `uninstall-autostart.bat`

> ⚠️ 自启用的是 `schtasks` 计划任务，**需要管理员权限**。

## 🐳 方式二：Docker 容器

```bash
# 拉取已发布镜像（推荐）
docker compose up -d

# 或本地构建后启动
docker compose up -d --build
```

访问 <http://localhost:18888>（容器内监听 8080，映射到宿主 18888）。

镜像：`ghcr.io/liumeixin/design-shi-md2wechat:latest`

> 容器是**薄镜像**：只打包 `backend/` + `frontend/`，主题与数据靠卷挂载，
> 改主题 CSS **不需要重建镜像**。容器相关文件只有 `Dockerfile` + `docker-compose.yml`。

## 🎨 自定义主题

编辑 `wenyan-data/custom_themes.json` 添加自定义主题配置。

## 🔧 开发指南

修改主题 CSS 后需要重新构建：

```bash
cd frontend
python build.py           # 从 CSS 源文件更新 themes.json / dimensions.json / manifest.json
```

> ⚠️ **主题「双源」陷阱**：`build.py` 只保留「比 CSS 文件更长」的 themes.json 条目。
> 15 个主题的真源是 `frontend/themes.json`，另 4 个（dark-green / notebook-blue /
> notebook-purple / ugreen）的真源是 `backend/static/css/themes/*.css`。
> 改配色前先确认，否则会被 `build.py` 冲掉。详见 `AGENTS.md`。

### 提交约定

改动后**先提醒用户确认**，确认后再提交并推送到 Gitea：

```bash
python scripts/commit_and_push.py -m "提交说明"
```

不带 `-m` 时为**预览模式**，只列出各仓库的待提交改动，不写任何东西。

## 📄 License

MIT License
