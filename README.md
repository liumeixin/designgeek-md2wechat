# 文颜 Markdown 排版器 (Windows 版)

微信公众号 Markdown 排版工具，支持 15+ 主题 × 18 个维度的 CSS 混搭。

## ✨ 功能特色

- **15+ 主题**：涵盖文艺、科技、商务等多种风格
- **18 维度混搭**：字体、颜色、间距、边框等维度自由组合
- **手机预览模式**：实时模拟手机端阅读效果
- **XHS 小红书分页**：支持小红书风格的内容分页展示
- **独立模式**：无需后端服务，双击即可使用

## 🚀 Windows 安装

### 前置条件

- Python 3.8+（[下载](https://www.python.org/downloads/)）
- Node.js（截图功能需要，[下载](https://nodejs.org/)）

### 方式一：双击启动（推荐）

直接双击 `文颜排版器.bat`，首次运行会自动安装依赖。

### 方式二：命令行启动

```cmd
# 进入项目目录
cd D:\aiwork\workspace\Projects\wenyan-editor-win

# 运行
run.bat
```

启动后访问：http://localhost:18888

### 停止服务

- 关闭标题为「文颜服务」的窗口
- 或在任务管理器中结束 `python` 进程

## 📦 其他使用方式

### 独立版（无需后端）

直接在浏览器打开 `frontend/standalone.html`，所有功能本地运行。

**注意**：独立版不支持截图功能。

### Docker

```cmd
docker compose up -d
# 访问 http://localhost:18888
```

### Flask 后端

```cmd
pip install flask
python backend/app.py
# 访问 http://localhost:18888
```

## 🎨 自定义主题

编辑 `wenyan-data/custom_themes.json` 添加自定义主题配置。

## 🔧 开发指南

修改主题 CSS 后需要重新构建：

```cmd
cd frontend
python build.py           # 从 CSS 源文件更新 themes.json / dimensions.json
python build-static.py    # 重新生成 standalone.html
```

## 📄 License

MIT License
