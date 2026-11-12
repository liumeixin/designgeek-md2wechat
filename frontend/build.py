#!/usr/bin/env python3
"""
Build script: Parse 16 Wenyan CSS themes → extract per-dimension snippets → generate editor HTML
"""
import os
import re
import json
from pathlib import Path

CSS_DIR = Path(os.environ.get("WENYAN_CSS_DIR", str(Path(__file__).parent / ".." / "backend" / "static" / "css" / "themes")))
OUTPUT = Path(__file__).parent

# Dimension → selector patterns (regex matching)
DIMENSIONS = {
    "background": {
        "name": "页面背景",
        "icon": "🎨",
        "selectors": [
            r"^#wenyan\s*$",
        ],
        "properties": ["background", "background-color", "background-image", "background-repeat", "background-attachment", "background-position"],
        "also_include_selectors": [r"^#wenyan::before", r"^#wenyan::after"],
    },
    "text-color": {
        "name": "文字颜色",
        "icon": "✏️",
        "selectors": [r"^#wenyan\s*$"],
        "properties": ["color", "font-family", "line-height", "font-size"],
    },
    "h1": {
        "name": "一级标题",
        "icon": "📌",
        "selectors": [
            r"#wenyan\s+h1(?:\s|,|$|\>)",
            r"#wenyan\s+h1\s+span",
            r"#wenyan\s+h1::before",
            r"#wenyan\s+h1::after",
        ],
    },
    "h2": {
        "name": "二级标题",
        "icon": "🔷",
        "selectors": [
            r"#wenyan\s+h2(?:\s|,|$|\>)",
            r"#wenyan\s+h2::before",
            r"#wenyan\s+h2::after",
        ],
    },
    "h3h6": {
        "name": "H3-H6 标题",
        "icon": "🔹",
        "selectors": [
            r"#wenyan\s+h[3-6](?:\s|,|$|\>)",
        ],
    },
    "bold": {
        "name": "加粗文字",
        "icon": "🅱️",
        "selectors": [
            r"#wenyan\s+(?:p\s+)?strong(?:\s|,|$|\>)",
            r"#wenyan\s+strong(?:\s|,|$|\>)",
        ],
    },
    "italic": {
        "name": "斜体文字",
        "icon": "𝐼",
        "selectors": [
            r"#wenyan\s+(?:p\s+)?em(?:\s|,|$|\>)",
        ],
    },
    "blockquote": {
        "name": "引用块",
        "icon": "💬",
        "selectors": [
            r"#wenyan\s+blockquote(?:\s|,|$|\>)",
            r"#wenyan\s+blockquote\s+p",
            r"#wenyan\s+blockquote::before",
            r"#wenyan\s+blockquote::after",
        ],
    },
    "inline-code": {
        "name": "行内代码",
        "icon": "⌨️",
        "selectors": [
            r"#wenyan\s+(?:p\s+)?code(?:\s|,|$|\>)",
            r"#wenyan\s+li\s+code",
        ],
        "exclude_selectors": [
            r"#wenyan\s+pre\s+code",
        ],
    },
    "code-block": {
        "name": "代码块",
        "icon": "💻",
        "selectors": [
            r"#wenyan\s+pre(?:\s|,|$|\>)",
            r"#wenyan\s+pre\s+code",
            r"#wenyan\s+pre::before",
            r"#wenyan\s+pre::after",
        ],
    },
    "ul": {
        "name": "无序列表",
        "icon": "📋",
        "selectors": [
            r"#wenyan\s+ul(?:\s|,|$|\>)",
            r"#wenyan\s+ul\s+li",
            r"#wenyan\s+ul\s+li::before",
            r"#wenyan\s+ul\s+li::marker",
            r"#wenyan\s+ul\s+ul",
        ],
    },
    "ol": {
        "name": "有序列表",
        "icon": "🔢",
        "selectors": [
            r"#wenyan\s+ol(?:\s|,|$|\>)",
            r"#wenyan\s+ol\s+li",
            r"#wenyan\s+ol\s*>\s*li::before",
            r"#wenyan\s+ol\s+li::marker",
        ],
    },
    "links": {
        "name": "链接",
        "icon": "🔗",
        "selectors": [
            r"#wenyan\s+a(?:\s|,|$|\>)",
            r"#wenyan\s+a:hover",
        ],
    },
    "table": {
        "name": "表格",
        "icon": "📊",
        "selectors": [
            r"#wenyan\s+table(?:\s|,|$|\>)",
            r"#wenyan\s+table\s+th",
            r"#wenyan\s+table\s+td",
            r"#wenyan\s+table\s+tr",
            r"#wenyan\s+table\s+tr:nth-child",
            r"#wenyan\s+table\s+thead",
        ],
    },
    "image": {
        "name": "图片",
        "icon": "🖼️",
        "selectors": [
            r"#wenyan\s+img(?:\s|,|$|\>)",
        ],
    },
    "hr": {
        "name": "分割线",
        "icon": "➖",
        "selectors": [
            r"#wenyan\s+hr(?:\s|,|$|\>)",
            r"#wenyan\s+hr::before",
            r"#wenyan\s+hr::after",
        ],
    },
    "footnote": {
        "name": "脚注",
        "icon": "📝",
        "selectors": [
            r"\.footnote",
            r"#footnotes",
            r"\.footnote-num",
            r"\.footnote-txt",
        ],
    },
    "spacing": {
        "name": "段落间距",
        "icon": "↔️",
        "selectors": [r"#wenyan\s+p"],
        "properties": ["letter-spacing"],
    },
}


def parse_css_blocks(css_text):
    """Parse CSS into list of (selectors_str, body_str) blocks."""
    blocks = []
    # Remove comments
    css_text = re.sub(r'/\*.*?\*/', '', css_text, flags=re.DOTALL)
    # Split by } and pair up
    depth = 0
    current = ""
    for char in css_text:
        if char == '{':
            depth += 1
            current += char
        elif char == '}':
            depth -= 1
            current += char
            if depth == 0:
                current = current.strip()
                if current:
                    # Split selector from body
                    brace_pos = current.find('{')
                    if brace_pos > 0:
                        selectors = current[:brace_pos].strip()
                        body = current[brace_pos+1:-1].strip()
                        if selectors and body:
                            blocks.append((selectors, body))
                current = ""
        else:
            current += char
    return blocks


def parse_properties(body):
    """Extract property names from a CSS rule body."""
    props = set()
    for line in body.split('\n'):
        line = line.strip().rstrip(';')
        if ':' in line:
            prop = line.split(':')[0].strip()
            if prop:
                props.add(prop)
    return props


def selector_matches_dimension(selector, dim_config):
    """Check if a CSS selector matches any pattern for this dimension."""
    all_patterns = dim_config["selectors"]
    exclude = dim_config.get("exclude_selectors", [])

    for pattern in exclude:
        if re.search(pattern, selector):
            return False

    for pattern in all_patterns:
        if re.search(pattern, selector):
            return True
    return False


def classify_block(selectors_str, body_str, dim_config):
    """Check if a CSS block belongs to a specific dimension."""
    # Handle comma-separated selectors
    individual_selectors = [s.strip() for s in selectors_str.split(',')]

    # Check if any selector matches
    matched = False
    for sel in individual_selectors:
        if selector_matches_dimension(sel, dim_config):
            matched = True
            break

    if not matched:
        return False

    # If dimension specifies property filters, check them
    if "properties" in dim_config:
        props = parse_properties(body_str)
        target_props = set(dim_config["properties"])
        if not props & target_props:
            return False

    if "exclude_properties" in dim_config:
        props = parse_properties(body_str)
        exclude_props = set(dim_config["exclude_properties"])
        # If ALL properties are excluded, skip
        if props and props <= exclude_props:
            return False

    return True


def extract_theme_css(css_text):
    """Extract a full theme CSS, removing font variables but keeping everything else."""
    return css_text


def build():
    """Main build function."""
    # Collect all CSS files
    css_files = sorted(CSS_DIR.glob("*.css"))

    themes = {}
    dimension_data = {dim: {} for dim in DIMENSIONS}

    for css_file in css_files:
        theme_name = css_file.stem
        if theme_name == "default (1)":
            continue  # Skip duplicate

        css_text = css_file.read_text(encoding='utf-8')
        themes[theme_name] = css_text

        # Parse CSS blocks
        blocks = parse_css_blocks(css_text)

        for dim_key, dim_config in DIMENSIONS.items():
            dim_rules = []
            for selectors, body in blocks:
                if classify_block(selectors, body, dim_config):
                    dim_rules.append(f"{selectors} {{\n  {body}\n}}")
            dimension_data[dim_key][theme_name] = "\n".join(dim_rules)

    # Build output
    theme_names = sorted(themes.keys())
    theme_display = {
        "default": "Default",
        "sunrise": "Sunrise 日出",
        "winter": "Winter 冬日",
        "girl-pink": "Girl Pink 粉红",
        "grass": "Grass 草地",
        "lavender-purple": "Lavender 薰衣草",
        "macarons": "Macarons 马卡龙",
        "newyear": "New Year 新年",
        "parrotalk": "Parrotalk 鹦鹉语",
        "purple-yellow-pop": "Purple Yellow Pop 紫黄",
        "claude": "Claude",
        "color-pop": "Color Pop 波普",
        "fireworks": "Fireworks 烟花",
        "cli": "CLI 终端",
        "cyber": "Cyber 赛博",
        "notebook-purple": "笔记紫 Notebook Purple",
        "notebook-blue": "笔记蓝 Notebook Blue",
        "dark-green": "暗夜绿 Dark Green",
        "ugreen": "UGREEN 绿联杂志",
        # 2026-11-02：移植自 pafa/WeDraft（MIT）的 5 套阅读模板
        "wedraft-plain-paper": "素笺 暖灰留白",
        "wedraft-ink-journal": "墨刊 黑白刊物",
        "wedraft-jade-notes": "青岚 松青书页",
        "wedraft-blueprint": "蓝图 理性蓝调",
        "wedraft-cinnabar": "朱砂 砖红篇章",
        # 2026-11-12：移植自 zhaotab（找Tab）公众号排版 https://www.zhaotab.com/typeset
        # 装饰为 CSS 近似（原实现靠 <span> 包裹），非像素级复刻
        "zt-simple": "找Tab 简约",
        "zt-orange": "找Tab 橙心",
        "zt-mint": "找Tab 薄荷",
        "zt-green": "找Tab 墨绿",
        "zt-forest": "找Tab 森林",
        "zt-blue": "找Tab 科技蓝",
        "zt-ocean": "找Tab 海洋",
        "zt-violet": "找Tab 紫罗兰",
        "zt-rose": "找Tab 玫瑰",
        "zt-sakura": "找Tab 樱花",
        "zt-lemon": "找Tab 柠檬",
        "zt-notebook": "找Tab 手账",
        "zt-coffee": "找Tab 咖啡",
        "zt-ink": "找Tab 书香",
        "zt-gold": "找Tab 黑金",
        "zt-news": "找Tab 报纸",
        "zt-grid": "找Tab 方格本",
        "zt-blush": "找Tab 粉笺",
        "zt-festival": "找Tab 国潮",
        "zt-terminal": "找Tab 终端",
        "zt-docs": "找Tab 文档",
        "zt-magazine": "找Tab 杂志",
        "zt-pop": "找Tab 波普",
        "zt-timeline": "找Tab 时间轴",
        "zt-seal": "找Tab 朱印",
        "zt-whisper": "找Tab 留白",
        "zt-neon": "找Tab 霓虹",
        "zt-kraft": "找Tab 牛皮纸",
        "zt-briefing": "找Tab 简报",
        "zt-bubble": "找Tab 对话框",
        "zt-inkwash": "找Tab 水墨",
        "zt-nordic": "找Tab 北欧",
        "zt-candy": "找Tab 糖果",
        "zt-feed": "找Tab 卡片流",
        "zt-checklist": "找Tab 清单",
    }

    # Generate theme CSS map as JS
    theme_css_js = {}
    for name, css in themes.items():
        theme_css_js[name] = css

    # Generate dimension CSS map as JS
    dim_css_js = {}
    for dim_key in DIMENSIONS:
        dim_css_js[dim_key] = {}
        for theme_name in themes:
            if dimension_data[dim_key].get(theme_name):
                dim_css_js[dim_key][theme_name] = dimension_data[dim_key][theme_name]

    # Write JSON data files for the HTML to consume
    #
    # 🔴 themes.json 是「双源」的，合并规则必须区分两类主题（2026-10-12 踩坑）：
    #   ① 15 个主题：CSS 文件只是 --wy-* 设计令牌调色板（约 1.5 KB），
    #      完整主题（含 ::after 装饰、SVG 背景）只存在于 themes.json（4~12 KB）
    #      ⇒ 必须保留 themes.json 的现有条目，否则手写主题会被短调色板冲掉
    #   ② 4 个主题：CSS 文件本身就是完整主题，与 themes.json 条目逐字节一致
    #      ⇒ 必须让 CSS 胜出，否则改 CSS 会被静默回退
    #        （2026-10-12 改 ugreen h1 字号时正是这样被吃掉的）
    # 判据：显式名单。两类主题的长度比分别是 1.0 与 2.7+，用「谁更长」当判据
    # 在边界上不可靠（差 2 个字符就会翻转），所以不再依赖长度比较。
    # CSS 文件本身就是完整主题的名单 —— 这些主题以 CSS 为准，不参与「谁更长」比较。
    # · 4 个手写主题：dark-green / notebook-blue / notebook-purple / ugreen
    # · wedraft-* / zt-*：从外部模板移植的完整主题，CSS 是唯一源
    # 其余 15 个主题的 CSS 只是 --wy-* 令牌调色板，完整主题在 themes.json 里，
    # 所以不能一刀切「有 CSS 就以 CSS 为准」。
    CSS_AUTHORITATIVE = {"dark-green", "notebook-blue", "notebook-purple", "ugreen"}
    CSS_PREFIX_AUTHORITATIVE = ("wedraft-", "zt-")
    existing_themes_path = OUTPUT / "themes.json"
    if existing_themes_path.exists():
        try:
            existing_themes = json.loads(existing_themes_path.read_text(encoding='utf-8'))
            for name, css in theme_css_js.items():
                if name in CSS_AUTHORITATIVE or name.startswith(CSS_PREFIX_AUTHORITATIVE):
                    continue  # 以 CSS 文件为准（theme_css_js 里已是 CSS 原文）
                # 其余主题：保留更长的现有条目（手写 > 自动抽取）
                if name in existing_themes and len(existing_themes[name]) > len(css):
                    theme_css_js[name] = existing_themes[name]
            # Preserve themes that exist in file but not in CSS dir
            for name, css in existing_themes.items():
                if name not in theme_css_js:
                    theme_css_js[name] = css
        except (json.JSONDecodeError, Exception):
            pass
    (OUTPUT / "themes.json").write_text(json.dumps(theme_css_js, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT / "dimensions.json").write_text(json.dumps(dim_css_js, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT / "manifest.json").write_text(json.dumps({
        "themes": [{"id": t, "name": theme_display.get(t, t)} for t in theme_names],
        "dimensions": [{"id": k, "name": v["name"], "icon": v["icon"]} for k, v in DIMENSIONS.items()],
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    # Print summary
    print(f"✅ Processed {len(theme_names)} themes")
    print(f"✅ Extracted {len(DIMENSIONS)} dimensions")
    for dim_key in DIMENSIONS:
        count = len([t for t in dimension_data[dim_key] if dimension_data[dim_key][t]])
        print(f"   {DIMENSIONS[dim_key]['icon']} {DIMENSIONS[dim_key]['name']}: {count} themes with data")

    print(f"\n📁 Output: {OUTPUT}")


if __name__ == "__main__":
    build()
