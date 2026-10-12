# 文颜 Markdown 排版器 · md2wechat — 开发者参考文档

> 从 wechat-markdown-styler 技能降级而来，供 Agent 和开发者参考。

## 单仓库（2026-10-12 合并）

本仓库同时承载**桌面端**与**容器**两个发行版，不再是两个仓库互相同步。

> 合并前是 `wenyan-editor-win`（主源）+ `wenyan-editor-docker`（同步镜像），
> 靠 `scripts/sync_docker_from_win.py` 手工同步 —— 该脚本已随合并删除。
> 合并理由：两仓库约 95% 文件相同，实际差异只有 6 个文件，而手工同步
> **没有任何机制拦截漂移**。

- 容器相关文件只有 `Dockerfile` + `docker-compose.yml` + `.dockerignore`，改动面极小。
- ⚠️ 改主题配色前先看
  `docs/微信编辑器规范合规-2026-10-12.md` §七.5：19 个主题里 **15 个以 `frontend/themes.json`
  为真源、4 个以 `backend/static/css/themes/*.css` 为真源**，改错地方会被 `build.py` 冲掉。

## 提交约定（2026-10-12）

改动后**先提醒用户确认**，确认后再提交并推送到 Gitea：

```bash
python scripts/commit_and_push.py -m "提交说明"   # 提交 + 推送
python scripts/commit_and_push.py                 # 预览：只列出待提交改动
```

## 排版规范（改动前必读）

**微信公众平台编辑器插件开发规范**
<https://developers.weixin.qq.com/doc/service/guide/product/plugin_spec.html>

公众号编辑器会校验粘贴进去的 HTML。**所有「导出 HTML」相关的改动都必须对照此规范**，
重点：§1.3 `line-height`、§1.4/§1.5 固定宽高、**§1.6 `text-align`（只接受
`left`/`center`/`right`/`justify`）**、§1.7 SVG `animate`、§1.8 `<pre>`、
**§3 不建议设置 `font-family`**、§4.1.1 颜色对比度、§4.5.2 不输出 `!important`。

```bash
python scripts/check_wechat_spec.py out.html --contrast   # 静态自检，退出码 0/1/2
```

完整审计报告：`docs/微信编辑器规范合规-2026-10-12.md`。

## 项目结构（2026-10-12）

```
designgeek-md2wechat/                     # 单仓库（桌面端 + 容器共用）
├── .github/workflows/docker-publish.yml  # GHCR 自动构建（IMAGE_NAME 已写死）
├── .dockerignore                         # 构建上下文排除（挡 .venv / *.bak / 桌面端文件）
├── Dockerfile                            # 薄容器（不含 Playwright）
├── docker-compose.yml                    # image: + build: 同时提供
├── backend/
│   ├── app.py                            # Flask 应用（桌面端/容器共用，端口由 PORT 覆盖）
│   ├── markdown_parser.py                # MD → 语义化 HTML / 内联样式 HTML
│   └── static/css/themes/                # 19 个主题 CSS 文件
├── frontend/
│   ├── index.html                        # 前端 UI（唯一入口）
│   ├── build.py                          # CSS → 三个 JSON
│   ├── themes.json                       # 主题 CSS 集合（key-value，CSS 字符串）
│   ├── dimensions.json                   # 维度混搭配置（CSS 片段 per theme per dimension）
│   └── manifest.json                     # 主题/维度清单
├── scripts/                              # html2png.mjs / check_wechat_spec.py / commit_and_push.py
├── docs/                                 # 本文档 + 合规报告
├── wenyan-data/                          # 运行时数据卷（custom_themes.json 等）
├── 文颜排版器.bat / .vbs, run.bat         # 桌面端启动器
└── requirements.txt                      # 桌面端依赖
```

### 关键路径映射
- Gitea 仓库：`Agent/designgeek-md2wechat`（`https://dx4700-gitea.tocmcc.cn`）
- Docker 镜像：`ghcr.io/liumeixin/designgeek-md2wechat:latest`
- 端口：桌面端 **18888**；容器内 **8080**，映射宿主 `18888:8080`
- ⚠️ 旧值已作废：`liumeixin/wenyan-editor`、`ghcr.io/liumeixin/wenyan-data`、
  以及「NAS 18080 → 容器 8080」的旧部署口径。

## 双层主题系统
1. **内置主题**：`frontend/themes.json` 存储 CSS 字符串（key=主题名，value=完整 CSS）
2. **维度混搭**：`frontend/dimensions.json` 存储 CSS 片段（key=维度名，value={主题名: CSS片段}）
3. **自定义主题**：`wenyan-data/custom_themes.json` 服务端持久化

### 18 个维度（dimensions.json）
background, text-color, h1, h2, h3h6, bold, italic, blockquote, inline-code, code-block, ul, ol, links, table, image, hr, footnote, spacing

### 19 个内置主题
claude, cli, color-pop, cyber, dark-green, default, fireworks, girl-pink, grass, lavender-purple, macarons, newyear, notebook-blue, notebook-purple, parrotalk, purple-yellow-pop, sunrise, ugreen, winter

> `grass-nobg`（零样式坏主题）已于 2026-10-12 删除。

### API
- POST `/convert` — MD → 语义化 HTML（预览）
- POST `/convert-inline` — MD → 内联样式 HTML（公众号，剥离 `<style>` 标签）
- POST `/api/screenshot` — HTML → PNG（Playwright，桌面端/容器路径自动探测）
- GET `/api/themes` — 主题列表
- GET `/api/dimensions` — 维度配置
- GET `/api/theme-css/<id>` — 主题 CSS
- GET/POST `/api/custom-themes` — 自定义主题 CRUD
- DELETE `/api/custom-themes/<id>` — 删除自定义主题
- GET `/api/proxy-image?url=…` — 图片代理（绕 OSS CORS）
- GET `/<path:filename>` — 前端静态文件

## dimensions.json 结构（重要！）

不是 CSS 变量，是 **CSS 片段 per theme**：
```json
{
  "background": {
    "claude": "#wenyan { background-color: #FAFAF8; }",
    "cli": "#wenyan { background-color: #121212; }"
  },
  "typography": {
    "default": "#wenyan { font-size: 16px; line-height: 1.75; }"
  }
}
```

## 新建主题工作流

### CSS 源文件位置
- **源文件目录**：`backend/static/css/themes/`（每个主题一个 `.css`，文件名即主题 ID）
- 可用环境变量 `WENYAN_CSS_DIR` 覆盖

### 构建流程
```bash
# 1. 在 backend/static/css/themes/ 下创建或修改 CSS
# 2. 从 repo 根目录运行 build：
cd frontend && python build.py
# 输出：themes.json, dimensions.json, manifest.json
# 3. 提交并推送（先提醒用户确认）
python scripts/commit_and_push.py -m "feat: add XXX theme"
```

### build.py 关键配置
- `CSS_DIR = Path(os.environ.get("WENYAN_CSS_DIR", .../backend/static/css/themes))` — **相对路径**（旧版硬编码 `/opt/data/cache/documents/xhs-css-extract`，已废）
- `theme_display` 字典 — 主题显示名（需手动添加）
- `DIMENSIONS` 字典 — 18 个维度的 CSS 选择器匹配规则
- 🔴 **合并回退块**：若 `themes.json` 已存在，会保留「比 CSS 更长」的条目，并保留
  「只存在于 JSON、不存在于 CSS 目录」的主题 —— **删主题时必须同时删 JSON 条目**，
  否则会被这个回退块重新加回来。

### CSS 文件格式规范
```css
#wenyan { font-family: ...; line-height: 1.8; font-size: 16px; color: #333; }
#wenyan h1 { /* ... */ }
#wenyan h1::before { /* 标题前缀 */ }
#wenyan h1::after { /* 标题后缀 */ }
#wenyan h2::before { /* 二级标题前缀 */ }
#wenyan p strong { /* 加粗 */ }
#wenyan blockquote { /* 引用块 */ }
#wenyan pre code { /* 代码块 */ }
#wenyan ul > li::marker { /* 列表标记 */ }
#wenyan a { /* 链接 */ }
#wenyan img { /* 图片 */ }
#wenyan table, #wenyan table th, #wenyan table td { /* 表格 */ }
```

## 维度匹配规则（DIMENSIONS 字典）
build.py 通过选择器正则将 CSS 块分类到 18 个维度：
- background: `#wenyan`（仅背景相关属性）
- text-color: `#wenyan`（color/font-family/font-size）
- h1: `#wenyan h1`, `#wenyan h1 span`, `#wenyan h1::before/after`
- h2: `#wenyan h2`, `#wenyan h2::before/after`
- h3h6: `#wenyan h[3-6]`
- bold: `#wenyan strong`
- italic: `#wenyan em`
- blockquote: `#wenyan blockquote`, `#wenyan blockquote p`, `blockquote::before/after`
- inline-code: `#wenyan p code`, `#wenyan li code`（排除 `pre code`）
- code-block: `#wenyan pre`, `#wenyan pre code`, `pre::before/after`
- ul: `#wenyan ul`, `#wenyan ul li`, `ul li::before/marker`
- ol: `#wenyan ol`, `#wenyan ol li`, `ol li::before/marker`
- links: `#wenyan a`
- table: `#wenyan table`, `table th/td/tr/thead`
- image: `#wenyan img`
- hr: `#wenyan hr`, `hr::before/after`
- footnote: `.footnote`, `#footnotes`, `.footnote-num/txt`
- spacing: `#wenyan p`（仅 letter-spacing）

## 微信公众号复制修复

### 问题 1：style 标签不支持
`parse_markdown_for_wechat` 输出混入 `<style>` 标签，微信不支持。
```python
html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
```

### 问题 2：复制按钮粘贴出纯文本代码
**根因**：`copyHtml()` 用 `navigator.clipboard.writeText(fullHtml)` 把 HTML 当 text/plain。
**修复**：改用 selection + `execCommand('copy')`，浏览器以 text/html MIME 写入剪贴板。
```javascript
const tmp = document.createElement('div');
tmp.innerHTML = fullHtml;
tmp.style.position = 'fixed';
tmp.style.left = '-9999px';
document.body.appendChild(tmp);
const range = document.createRange();
range.selectNodeContents(tmp);
const sel = window.getSelection();
sel.removeAllRanges();
sel.addRange(range);
document.execCommand('copy');
sel.removeAllRanges();
document.body.removeChild(tmp);
```

**涉及文件**：`frontend/index.html` 的 `copyHtml()` 函数（独立版 `standalone.html` 已于 2026-10-12 弃用删除，现只有这一个入口）。

## 手机预览模式（2026-05-16）

预览栏「📱 手机」按钮，切换 375px 手机外壳模拟：
- 动态创建 `.phone-frame` div（圆角 32px + 刘海 + 状态栏）
- CSS：`#preview-scroll.phone-mode #wenyan { max-width: 100% !important; }`
- 涉及文件：`frontend/index.html`

## 小红书排版截图模式（2026-05-20）

预览栏「📷 小红书」按钮，Markdown 自动分页为小红书图文格式。

**架构**：纯前端，CDN 加载 `html-to-image@1.11.11` + `jszip@3.10.1`。

**分页算法**：
```javascript
// 1. 创建隐藏测量容器（440px 宽度 + 主题 CSS）
// 2. 遍历所有顶级块级子元素，测量 offsetHeight
// 3. 贪心填充：当前页累计高度 + 下一块高度 > (586 - 24px padding) 时换页
// 4. 返回 HTML 字符串数组，每项为一页内容
```

**JS 函数**（均在 `frontend/index.html`）：
- `toggleXhsMode()` — 切换 XHS 模式
- `generateXhsPages()` — 生成分页 + 渲染卡片
- `splitContentIntoPages(html, css, w, h)` — 分页算法（返回 Promise，需等待图片加载）
- `downloadXhsPage(index)` / `downloadAllXhsPages()` — 下载

**踩坑记录**：
- 小红书图片实际分辨率远低于 1080px，按 440×586 更接近手机屏幕模拟效果
- padding 必须按宽度比例动态计算（5.5%），硬编码 60px 在小分辨率下太大
- 图床图片不显示（2026-05-20 修复）：
  1. CSS 缺失：需 `img { max-width:100%; height:auto; display:block; }`
  2. 测量时图片未加载：`splitContentIntoPages` 改为返回 Promise，`Promise.all(imgPromises)` 等待加载

## 微信公众号背景兼容性（最终结论）

微信公众号编辑器**只支持 `background-color`（纯色）**，所有背景图方案被剥离：
- `background-image: linear-gradient(...)` — ❌
- SVG data URI → 内联 `<svg>` — ❌
- `<style>` 标签内 CSS — ❌

**copyHtml()**：只提取 `background-color` 和 `padding`，跳过 `background-image`。

## 导出 HTML 属性白名单（`copyHtml()` 的 `copyProps`）

导出 HTML 的内联样式由 `frontend/index.html` 的 `copyHtml()` **统一生成**，规则不在主题里。
主题 CSS 只是「期望值」，能不能进导出要看这张白名单 —— 这是最容易踩的坑。

| 类别 | 属性 | 说明 |
|---|---|---|
| 全局白名单 | `color` `font-size` `font-weight` `font-style` `font-family` `letter-spacing` `text-align` `text-decoration(-line)` `background-*` `border` `border-radius` `box-shadow` `opacity` `vertical-align` | 逐元素取 `getComputedStyle` 内联 |
| **定向白名单**（2026-10-12 新增） | `border-collapse` → 仅 `<table>`；`list-style-type` → 仅 `ul/ol/li`；`padding` → `blockquote`/`pre`/`code`；`line-height` → `blockquote`/`pre`；`display` + `overflow-x` → **代码块上下文**（`<pre>` 及其内部 `<code>`） | 见下 |
| 永不内联 | `margin` `width` `height` `position` `z-index` `float` | 固定宽高会让公众号编辑器报「不同屏幕下宽度差异 / 居中不一致」；`display` 全局内联会导致正文文字重叠 |

- **`border-<方向>`**：只有与 `border` 简写**不同**时才输出（表格单元格因此省掉 4/5 的边框声明）。
- **代码块长行**：按用户 2026-10-12 拍板采用**横向滚动**（`overflow-x:auto`，不换行），
  与主题 `#wenyan pre code { display:block; overflow-x:auto }` 的意图一致。
- **`NOOP_RULES`**：计算值等于属性初始值的声明会被丢弃（`border-collapse:separate`、
  `padding:0`、`line-height:normal`、`background-image:none` …），避免导出臃肿。

> 🔴 改这张白名单**必须**用真实浏览器跑一遍导出再复检，纯静态看代码判断不出来：
> ```bash
> cd frontend && python -m http.server 8899 --bind 127.0.0.1   # 另开终端
> node D:/aiwork/scripts/_out/export_probe.cjs http://127.0.0.1:8899/index.html ugreen sample.md out.html
> python scripts/check_wechat_spec.py out.html --contrast
> ```
> 依据与实测数据 → `docs/微信编辑器规范复核-表格引用代码-2026-10-12.md`。

## 图片代理（CORS 修复）

Aliyun OSS 图片直链无 CORS 头，Canvas/Image 无法使用。添加后端代理：
```
GET /api/image-proxy?url=https://xxx.oss-cn-beijing.aliyuncs.com/xxx.webp
→ 后端 requests.get() → 返回 bytes + Access-Control-Allow-Origin: *
```

前端 `normalizeImageUrls` 将 OSS URL 替换为 `/api/image-proxy?url=...`。

## 常见问题

### Flask 找不到模块
桌面端 venv 里没装 flask → `.venv\Scripts\python.exe -m pip install flask`

### Git push 失败
非交互 shell 拿不到凭据 → **一律用 `python scripts/commit_and_push.py`**
（它从 `D:/aiwork/services/credentials.env` 读 `GITEA_TOKEN` 走 `http.extraheader`）。
⚠️ Bash 工具恒注入 `http_proxy`，会让 git 看到「代理的假 502」—— 脚本内已自动剔除。

### 容器里截图功能
容器**不打包 Playwright**，`backend/app.py` 会自动把截图脚本回落到
`/opt/data/scripts_node/pw_runtime/html2png.mjs`。若该路径不存在，截图 API 会失败 ——
这是既有状态，不是合并引入的。

### Flask 304 缓存问题
在 `app.py` 的 `after_request` 中对 JSON 文件加 no-cache 头。

### 剪贴板 API 调试注意
- `document.addEventListener('copy', ...)` 只能拦截 `document.execCommand('copy')`
- `navigator.clipboard.read()` 需要页面焦点

### `__pycache__` 导致旧代码
`rm -rf __pycache__` 后重启

### patch 操作引入多余 `}`
拼接函数时容易多一个闭合花括号，导致整个 `<script>` 解析失败。用 `grep -c` 验证函数数量一致性。
