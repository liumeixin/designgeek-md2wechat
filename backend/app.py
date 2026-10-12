#!/usr/bin/env python3
"""
文颜 Markdown 排版器 — Flask Web 应用
====================================
支持一键换肤 + 单元素混搭

用法: python app.py
访问: http://localhost:18888

端口可用环境变量 PORT 覆盖（容器里 docker-compose 传 PORT=8080）。
"""

import os
import json
import uuid
import tempfile
import shutil
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file

# --- Paths ---
BACKEND_DIR = Path(__file__).parent
FRONTEND_DIR = BACKEND_DIR / '..' / 'frontend'
THEMES_DIR = BACKEND_DIR / "static" / "css" / "themes"
CUSTOM_THEMES_FILE = Path(os.environ.get("DATA_DIR", str(BACKEND_DIR))) / "custom_themes.json"

# Playwright 截图脚本路径（桌面端 / 容器共用同一份 app.py）：
#   桌面端 —— 仓库内的 scripts/html2png.mjs 存在，直接用；
#   容器   —— scripts/ 既不打进镜像也不挂载，自动回落到容器内置路径。
_LOCAL_PW_SCRIPT = BACKEND_DIR / '..' / 'scripts' / 'html2png.mjs'
PW_SCRIPT = str(_LOCAL_PW_SCRIPT) if _LOCAL_PW_SCRIPT.exists() \
    else '/opt/data/scripts_node/pw_runtime/html2png.mjs'

app = Flask(__name__, template_folder=str(FRONTEND_DIR))


def _load_custom_themes():
    """读取自定义主题"""
    if CUSTOM_THEMES_FILE.exists():
        with open(CUSTOM_THEMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_custom_themes(themes):
    """保存自定义主题"""
    with open(CUSTOM_THEMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(themes, f, ensure_ascii=False, indent=2)


# 解除图片加载限制 + 禁止 JSON 缓存（避免 304 导致前端拿到旧数据）
@app.after_request
def after_request(response):
    response.headers['Content-Security-Policy'] = "img-src * data: blob:;"
    if request.path.endswith('.json'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


@app.route('/')
def index():
    """主页"""
    return send_file(FRONTEND_DIR / 'index.html')


@app.route('/convert', methods=['POST'])
def convert():
    """转换 Markdown 为 HTML"""
    try:
        data = request.get_json()
        markdown = data.get('markdown', '')

        if not markdown:
            return jsonify({'success': False, 'error': '输入为空'})

        from markdown_parser import parse_markdown
        html = parse_markdown(markdown)

        return jsonify({'success': True, 'html': html})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/convert-inline', methods=['POST'])
def convert_inline():
    """转换为微信公众号内联样式 HTML"""
    try:
        data = request.get_json()
        markdown = data.get('markdown', '')

        if not markdown:
            return jsonify({'success': False, 'error': '输入为空'})

        from markdown_parser import parse_markdown_for_wechat
        html = parse_markdown_for_wechat(markdown)

        return jsonify({'success': True, 'html': html})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/themes')
def api_themes():
    """返回主题列表"""
    themes_path = FRONTEND_DIR / "themes.json"
    with open(themes_path, 'r', encoding='utf-8') as f:
        themes = json.load(f)
        theme_index = [{"id": name, "name": name} for name in sorted(themes.keys())]
        return jsonify(theme_index)


@app.route('/api/dimensions')
def api_dimensions():
    """返回维度配置（用于混搭面板）"""
    config_path = FRONTEND_DIR / "dimensions.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/theme-css/<theme_id>')
def api_theme_css(theme_id):
    """返回指定主题的 CSS"""
    css_path = THEMES_DIR / f"{theme_id}.css"
    if css_path.exists():
        return send_from_directory(THEMES_DIR, f"{theme_id}.css", mimetype='text/css')
    return "Not found", 404


@app.route('/api/custom-themes', methods=['GET'])
def api_get_custom_themes():
    """获取所有自定义主题"""
    return jsonify(_load_custom_themes())


@app.route('/api/custom-themes', methods=['POST'])
def api_save_custom_theme():
    """保存自定义主题"""
    data = request.get_json()
    theme_id = data.get('id')
    theme_data = data.get('theme')
    if not theme_id or not theme_data:
        return jsonify({'success': False, 'error': '缺少 id 或 theme 数据'}), 400

    themes = _load_custom_themes()
    themes[theme_id] = theme_data
    _save_custom_themes(themes)
    return jsonify({'success': True})


@app.route('/api/custom-themes/<theme_id>', methods=['DELETE'])
def api_delete_custom_theme(theme_id):
    """删除自定义主题"""
    themes = _load_custom_themes()
    if theme_id in themes:
        del themes[theme_id]
        _save_custom_themes(themes)
    return jsonify({'success': True})


@app.route('/api/proxy-image')
def proxy_image():
    """图片代理 - 解决 OSS CORS 问题"""
    url = request.args.get('url')
    if not url:
        return jsonify({'success': False, 'error': '缺少 url 参数'}), 400
    
    # 验证 URL 是图片
    if not any(url.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp']):
        return jsonify({'success': False, 'error': '无效的图片 URL'}), 400
    
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            content_type = response.headers.get('Content-Type', 'image/png')
        
        # 保存到临时文件
        suffix = Path(url).suffix or '.png'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        
        return send_file(tmp_path, mimetype=content_type, as_attachment=False)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/<path:filename>')
def serve_frontend(filename):
    """Serves frontend static files (themes.json, dimensions.json, etc.)"""
    file_path = FRONTEND_DIR / filename
    if file_path.exists() and file_path.is_file():
        return send_file(file_path)
    return "Not found", 404


# === 截图 API (Playwright) ===
import subprocess
import asyncio

@app.route('/api/screenshot', methods=['POST'])
def screenshot_api():
    """截图 API - 接收 HTML 内容，返回 PNG"""
    data = request.json
    html_content = data.get('html', '')
    width = data.get('width', 1080)
    height = data.get('height', 1440)
    
    print(f"[screenshot] Received HTML: {len(html_content)} chars, size: {width}x{height}")
    
    if not html_content:
        return jsonify({'success': False, 'error': 'Empty HTML'})
    
    # 创建临时 HTML 文件
    tmp_dir = tempfile.mkdtemp()
    html_path = os.path.join(tmp_dir, 'page.html')
    output_path = os.path.join(tmp_dir, 'page.png')
    
    try:
        # 写入临时 HTML 文件
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 调用 playwright 截图
        print(f"[screenshot] Running playwright: {PW_SCRIPT}")
        result = subprocess.run(
            ['node', PW_SCRIPT,
             html_path, output_path, str(width), str(height)],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(f"[screenshot] Playwright output: {result.stdout}")
        if result.stderr:
            print(f"[screenshot] Playwright error: {result.stderr}")
        
        if result.returncode != 0:
            return jsonify({'success': False, 'error': result.stderr})
        
        if not os.path.exists(output_path):
            return jsonify({'success': False, 'error': 'Screenshot failed'})
        
        # 返回 PNG
        return send_file(output_path, mimetype='image/png')
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        # 清理临时文件
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    port = int(os.environ.get('PORT', 18888))
    host = os.environ.get('HOST', '0.0.0.0')

    print(f"""
╔══════════════════════════════════════════════════╗
║  文颜 Markdown 排版器                              ║
║  访问地址: http://localhost:{port:<20}║
╚══════════════════════════════════════════════════╝
""")

    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    main()