#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众平台编辑器插件开发规范 —— 产出 HTML 静态自检
====================================================
规范原文：
https://developers.weixin.qq.com/doc/service/guide/product/plugin_spec.html
官方检测实现（真实浏览器 + 布局测量）：
https://github.com/wechatjs/verify-article-structure-spec

本脚本只做**静态**可判定的规则，不依赖浏览器，适合放进 CI / 提交前自检。
需要真实布局测量的规则（width 居中差异、height 溢出、line-height 叠字）
请用官方 CLI 跑。

用法：
    python scripts/check_wechat_spec.py out.html [more.html ...]
    python scripts/check_wechat_spec.py out.html --json
    python scripts/check_wechat_spec.py out.html --contrast   # 额外做 §4.1.1 对比度审计

退出码：0 通过 / 1 存在违规 / 2 参数或读取异常
"""

import json
import re
import sys
from html.parser import HTMLParser

# ---------------------------------------------------------------- 规则定义

ALIGN_ALLOWED = {"left", "center", "right", "justify"}
# §1.6 text-align：start / end 为逻辑值，各终端兼容性不一致
ALIGN_MAP = {"start": "left", "end": "right", "match-parent": "left"}

# §3 字体使用规范：不建议设置任何 font-family。
# 等宽字体是代码块的语义需求，视为合理例外。
FONT_EXEMPT_TAGS = {"code", "pre", "kbd", "samp"}

# 这些标签内部的元素不参与部分检测（规范中的排除场景）
SVG_INTERNAL = {"svg"}

# 空元素：不参与嵌套栈
VOID_TAGS = {"img", "br", "hr", "input", "meta", "link", "area", "base",
             "col", "embed", "source", "track", "wbr"}

# 行内元素：width / height 对其不生效，不参与 §1.4 / §1.5 判定
INLINE_TAGS = {"span", "strong", "em", "b", "i", "u", "s", "del", "ins",
               "a", "code", "kbd", "samp", "sub", "sup", "small", "mark",
               "label", "abbr", "cite", "q", "time"}


class SpecChecker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.issues = []          # [{rule, level, tag, detail}]
        self.stack = []           # [(tag, style, has_text)]
        self.text_depth = 0       # 当前累计文本量（用于 height/pre 判定）

    # ---------------------------------------------------------- 工具
    def _add(self, rule, level, tag, detail):
        self.issues.append({"rule": rule, "level": level, "tag": tag, "detail": detail})

    @staticmethod
    def _parse_style(style):
        out = {}
        for decl in (style or "").split(";"):
            if ":" not in decl:
                continue
            k, v = decl.split(":", 1)
            out[k.strip().lower()] = v.strip()
        return out

    @staticmethod
    def _css_len_px(value):
        """把 12px / 12pt 粗略换算成 px；无单位/em/% 等需要上下文，返回 None。"""
        m = re.match(r"^(-?[\d.]+)\s*(px|pt|em|rem|%)$", (value or "").strip().lower())
        if not m:
            return None
        num, unit = float(m.group(1)), m.group(2)
        if unit == "px":
            return num
        if unit == "pt":
            return num * 4 / 3
        return None  # em/rem/% 需要上下文，静态无法判定

    @staticmethod
    def _line_height_px(value, font_px):
        """line-height 支持无单位倍数，单独处理。"""
        v = (value or "").strip().lower()
        if re.match(r"^-?[\d.]+$", v):          # 无单位 → 倍数
            return float(v) * font_px if font_px else None
        return SpecChecker._css_len_px(v)

    # ---------------------------------------------------------- 事件
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        style = self._parse_style(a.get("style"))
        in_svg = any(n["tag"] in SVG_INTERNAL for n in self.stack)

        # §1.6 text-align 非标准值
        if "text-align" in style:
            v = style["text-align"].lower()
            if v in ALIGN_MAP:
                self._add("§1.6 text-align", "error", tag,
                          f'使用了非标准值 text-align:{v} → 应改为 {ALIGN_MAP[v]}'
                          "（start/end 在不同终端渲染不一致）")
            elif v not in ALIGN_ALLOWED:
                self._add("§1.6 text-align", "error", tag,
                          f"text-align:{v} 不在允许集合 {sorted(ALIGN_ALLOWED)}")

        # §3 font-family
        if "font-family" in style and tag not in FONT_EXEMPT_TAGS:
            self._add("§3 字体使用规范", "warn", tag,
                      f"正文元素设置了 font-family:{style['font-family']}"
                      "（规范不建议，平台默认字体栈已最优）")

        # §4.5.2 !important
        if "!important" in (a.get("style") or ""):
            self._add("§4.5.2 !important", "error", tag, "内联样式使用了 !important")

        # §1.4 固定宽度（媒体 / 行内元素 / data-ignore-width 豁免）
        blockish = tag not in INLINE_TAGS and tag not in ("img", "video", "svg")
        if not in_svg and blockish and "data-ignore-width" not in a:
            if "width" in style:
                px = self._css_len_px(style["width"])
                if px is not None:
                    self._add("§1.4 width", "warn", tag,
                              f"width:{style['width']} 为固定宽度，"
                              "不同屏宽下居中状态可能不一致")

        # §1.5 height
        if not in_svg and "height" in style:
            px = self._css_len_px(style["height"])
            if px is not None and px == 0:
                self._add("§1.5 height", "error", tag, "height:0 会导致移动端文字不可见")
            elif px is not None and px > 0 and blockish:
                self._add("§1.5 height", "info", tag,
                          f"固定 height:{style['height']}，请确认内容不会溢出被裁切")

        # §1.3 line-height 小于字号
        if "line-height" in style:
            fs = self._css_len_px(style.get("font-size", ""))
            lh = self._line_height_px(style["line-height"], fs)
            if lh is not None and fs is not None and lh < fs:
                self._add("§1.3 line-height", "warn", tag,
                          f"line-height({style['line-height']}) 小于 font-size({style['font-size']})，"
                          "多行文字会重叠")

        # 记录 code 归属，供 §1.8 判定 <pre> 内是否有 <code>
        if tag == "code":
            for node in self.stack:
                if node["tag"] == "pre":
                    node["has_code"] = True

        if tag not in VOID_TAGS:
            self.stack.append({"tag": tag, "style": style, "has_text": False, "has_code": False})

    def handle_startendtag(self, tag, attrs):
        # <img/> 等自闭合：只查属性，不入栈
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1]["tag"] == tag:
            self.stack.pop()

    def handle_data(self, data):
        if data.strip():
            for node in self.stack:
                node["has_text"] = True

    def handle_endtag(self, tag):
        # 找到最近的同名开标签
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                node = self.stack[i]
                # §1.8 <pre> 内含文本但无 <code> → 普通段落误用 pre
                if tag == "pre" and node["has_text"] and not node["has_code"]:
                    self._add("§1.8 pre", "error", tag,
                              "<pre> 包裹了普通文本（无 <code>），移动端会不换行被截断")
                del self.stack[i:]
                break


# ---------------------------------------------------------------- §4.1.1 对比度

NAMED_COLORS = {
    "transparent": (0, 0, 0, 0.0), "white": (255, 255, 255, 1.0),
    "black": (0, 0, 0, 1.0), "red": (255, 0, 0, 1.0), "green": (0, 128, 0, 1.0),
    "blue": (0, 0, 255, 1.0), "gray": (128, 128, 128, 1.0),
    "grey": (128, 128, 128, 1.0), "silver": (192, 192, 192, 1.0),
    "yellow": (255, 255, 0, 1.0), "orange": (255, 165, 0, 1.0),
    "purple": (128, 0, 128, 1.0), "pink": (255, 192, 203, 1.0),
    "inherit": None, "initial": None,
}


def parse_color(v):
    """返回 (r,g,b,a) 或 None（无法解析 / 非颜色）。"""
    if not v:
        return None
    s = v.strip().lower()
    if s in NAMED_COLORS:
        return NAMED_COLORS[s]
    m = re.match(r"^#([0-9a-f]{3})$", s)
    if m:
        h = m.group(1)
        return tuple(int(c * 2, 16) for c in h) + (1.0,)
    m = re.match(r"^#([0-9a-f]{6})$", s)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.match(r"^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+%?))?\s*\)$", s)
    if m:
        r, g, b = (float(m.group(i)) for i in (1, 2, 3))
        a = m.group(4)
        if a is None:
            alpha = 1.0
        else:
            alpha = float(a[:-1]) / 100 if a.endswith("%") else float(a)
        return (r, g, b, alpha)
    return None


def _lum(c):
    def f(x):
        x /= 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast_ratio(fg, bg):
    l1, l2 = _lum(fg), _lum(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _blend(fg, bg):
    """把带透明度的前景色合成到不透明背景上。"""
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))


class ContrastWalker(HTMLParser):
    """沿 DOM 栈累积前景色 / 最近的不透明背景色，检查文字对比度（§4.1.1）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []      # [{'color':(r,g,b), 'bg':(r,g,b)|None}]
        self.issues = []

    def handle_starttag(self, tag, attrs):
        style = {}
        for decl in (dict(attrs).get("style") or "").split(";"):
            if ":" in decl:
                k, v = decl.split(":", 1)
                style[k.strip().lower()] = v.strip()
        parent = self.stack[-1] if self.stack else {"color": (0, 0, 0), "bg": None}
        color = parent["color"]
        bg = parent["bg"]
        c = parse_color(style.get("color"))
        if c and c[3] > 0:
            color = _blend(c, bg) if bg else tuple(c[:3])
        b = parse_color(style.get("background-color"))
        if b and b[3] > 0.9:                     # 只看不透明背景
            bg = tuple(b[:3])
        if tag not in VOID_TAGS:
            self.stack.append({"_t": tag, "color": color, "bg": bg})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1].get("_t") == tag:
            self.stack.pop()

    def handle_data(self, data):
        if not data.strip() or not self.stack:
            return
        node = self.stack[-1]
        if node["bg"] is None:
            return                               # 没有背景色 → 交给 Dark Mode 算法，不判定
        ratio = contrast_ratio(node["color"], node["bg"])
        if ratio < 4.5:
            self.issues.append({
                "rule": "§4.1.1 颜色对比度", "level": "warn" if ratio >= 3 else "error",
                "tag": "text",
                "detail": (f"文字色 rgb{tuple(round(x) for x in node['color'])} / "
                           f"背景色 rgb{tuple(round(x) for x in node['bg'])} "
                           f"对比度 {ratio:.2f}:1（<4.5:1，Dark Mode 下可能难以辨识）"),
            })

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].get("_t") == tag:
                del self.stack[i:]
                break


def check_contrast(html):
    w = ContrastWalker()
    w.feed(html)
    w.close()
    seen, out = set(), []
    for it in w.issues:
        if it["detail"] not in seen:
            seen.add(it["detail"])
            out.append(it)
    return out


def check_animate_begin(html):
    """§1.7 SVG animate 的 begin 只写 touchstart 时 PC 端不触发"""
    issues = []
    for m in re.finditer(r"<animate\b[^>]*>", html, re.I):
        tag = m.group(0)
        b = re.search(r'begin\s*=\s*"([^"]*)"', tag, re.I)
        if b and "touchstart" in b.group(1).lower() and "click" not in b.group(1).lower():
            issues.append({
                "rule": "§1.7 begin", "level": "error", "tag": "animate",
                "detail": f'begin="{b.group(1)}" 缺少 click 事件，PC 端动画不会触发',
            })
    return issues


def check_file(path, with_contrast=False):
    with open(path, encoding="utf-8", errors="replace") as f:
        html = f.read()
    c = SpecChecker()
    c.feed(html)
    c.close()
    issues = c.issues + check_animate_begin(html)
    if with_contrast:
        issues += check_contrast(html)
    # 去重（同一节点同类问题只报一次）
    seen, uniq = set(), []
    for it in issues:
        key = (it["rule"], it["level"], it["tag"], it["detail"])
        if key not in seen:
            seen.add(key)
            uniq.append(it)
    return html, uniq


LEVEL_ICON = {"error": "✗", "warn": "!", "info": "·"}


def main(argv):
    files = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    with_contrast = "--contrast" in argv
    if not files:
        print(__doc__)
        return 2

    total = 0
    report = {}
    for path in files:
        try:
            html, issues = check_file(path, with_contrast)
        except OSError as e:
            print(f"读取失败 {path}: {e}", file=sys.stderr)
            return 2
        report[path] = issues
        errors = [i for i in issues if i["level"] == "error"]
        total += len(errors)
        if not as_json:
            print(f"\n{'=' * 62}\n{path}  ({len(html)} bytes)")
            if not issues:
                print("  ✓ 静态规则全部通过")
                continue
            for it in sorted(issues, key=lambda x: (x["level"] != "error", x["rule"])):
                print(f"  {LEVEL_ICON.get(it['level'], '?')} [{it['rule']}] <{it['tag']}> {it['detail']}")
            print(f"  —— 违规 {len(errors)} 项，提示 {len(issues) - len(errors)} 项")

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'=' * 62}\n合计硬违规（error）：{total}")
        print("注：width 居中差异 / height 溢出 / line-height 叠字 / 嵌套层级\n"
              "    需要真实布局测量，请用官方 CLI：\n"
              "    https://github.com/wechatjs/verify-article-structure-spec")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
