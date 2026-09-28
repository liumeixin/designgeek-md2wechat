# 文言排版器 — 开发者参考文档

> 从 wechat-markdown-styler 技能降级而来，供 Agent 和开发者参考。

## 项目结构（2026.05 最终版）

```
wenyan-editor/                    # GitHub 仓库根目录
├── .github/workflows/docker-publish.yml  # GHCR 自动构建
├── docker-compose.yml            # 根目录（旧版，可忽略）
├── backend/
│   ├── app.py                    # Flask 应用（12 个 API）
│   ├── markdown_parser.py        # MD → 语义化 HTML / 内联样式 HTML
│   └── static/css/themes/        # 16 个主题 CSS 文件
├── frontend/
│   ├── index.html                # 前端 UI
│   ├── themes.json               # 主题 CSS 集合（key-value，CSS 字符串）
│   ├── dimensions.json           # 维度混搭配置（CSS 片段 per theme per dimension）
│   └── ...
└── wenyan-data/                  # Docker 部署目录（可独立运行）
    ├── app.py, markdown_parser.py, ...
    ├── docker-compose.yml        # image: ghcr.io/liumeixin/wenyan-data:latest
    └── custom_themes.json        # 自定义主题持久化
```

### 关键路径映射
- GitHub 仓库：`liumeixin/wenyan-editor`
- Docker 镜像：`ghcr.io/liumeixin/wenyan-data:latest`
- NAS 部署：`wenyan-editor/wenyan-data/` 目录
- 端口：NAS 18080 → 容器 8080

## 双层主题系统
1. **内置主题**：`frontend/themes.json` 存储 CSS 字符串（key=主题名，value=完整 CSS）
2. **维度混搭**：`frontend/dimensions.json` 存储 CSS 片段（key=维度名，value={主题名: CSS片段}）
3. **自定义主题**：`wenyan-data/custom_themes.json` 服务端持久化

### 19 个维度（dimensions.json）
background, text-color, h1, h2, h3h6, bold, italic, blockquote, inline-code, code-block, ul, ol, links, table, image, hr, footnote, spacing, typography

### 17 个内置主题
claude, cli, color-pop, cyber, dark-green, default, fireworks, girl-pink, grass, lavender-purple, macarons, newyear, notebook-blue, notebook-purple, parrotalk, purple-yellow-pop, sunrise, winter

### 8 个 API
- POST `/convert` — MD → 语义化 HTML（预览）
- POST `/convert-inline` — MD → 内联样式 HTML（公众号，剥离 `<style>` 标签）
- GET `/api/themes` — 主题列表
- GET `/api/dimensions` — 维度配置
- GET `/api/theme-css/<id>` — 主题 CSS
- GET/POST `/api/custom-themes` — 自定义主题 CRUD
- DELETE `/api/custom-themes/<id>` — 删除自定义主题

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
- **源文件目录**：`/opt/data/cache/documents/xhs-css-extract/`
- 每个主题一个 `.css` 文件，命名即主题 ID

### 构建流程
```bash
# 1. 在源文件目录创建 CSS
# 2. 从 repo 根目录运行 build：
cd /path/to/wenyan-editor
python3 frontend/build.py
# 输出：themes.json, dimensions.json, manifest.json
# 3. 提交并推送
git add -A && git commit -m "feat: add XXX theme" && git push
```

### build.py 关键配置
- `CSS_DIR = Path("/opt/data/cache/documents/xhs-css-extract")` — CSS 源文件目录
- `theme_display` 字典 — 主题显示名（需手动添加）
- `DIMENSIONS` 字典 — 18 个维度的 CSS 选择器匹配规则

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

**涉及文件**：`frontend/standalone.html` 和 `frontend/index.html` 的 `copyHtml()` 函数，两文件要同步修改。

## 手机预览模式（2026-05-16）

预览栏「📱 手机」按钮，切换 375px 手机外壳模拟：
- 动态创建 `.phone-frame` div（圆角 32px + 刘海 + 状态栏）
- CSS：`#preview-scroll.phone-mode #wenyan { max-width: 100% !important; }`
- 涉及文件：`frontend/standalone.html`、`frontend/index.html`

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

**JS 函数**（两文件同步）：
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

## 图片代理（CORS 修复）

Aliyun OSS 图片直链无 CORS 头，Canvas/Image 无法使用。添加后端代理：
```
GET /api/image-proxy?url=https://xxx.oss-cn-beijing.aliyuncs.com/xxx.webp
→ 后端 requests.get() → 返回 bytes + Access-Control-Allow-Origin: *
```

前端 `normalizeImageUrls` 将 OSS URL 替换为 `/api/image-proxy?url=...`。

## 常见问题

### Flask 找不到模块
venv 里没装 flask → `/opt/hermes/.venv/bin/python3 -m pip install flask`

### Git push 失败 "could not read Password"
用 `/opt/data/workspace/Projects/wenyan-editor`（remote URL 内嵌 token），不要用 `/tmp` 克隆的副本。
⚠️ `/opt/data/.env` 里的 `GITHUB_TOKEN` 已过期（401）。

### Flask 304 缓存问题
在 `app.py` 的 `after_request` 中对 JSON 文件加 no-cache 头。

### 剪贴板 API 调试注意
- `document.addEventListener('copy', ...)` 只能拦截 `document.execCommand('copy')`
- `navigator.clipboard.read()` 需要页面焦点

### `__pycache__` 导致旧代码
`rm -rf __pycache__` 后重启

### patch 操作引入多余 `}`
拼接函数时容易多一个闭合花括号，导致整个 `<script>` 解析失败。用 `grep -c` 验证函数数量一致性。
