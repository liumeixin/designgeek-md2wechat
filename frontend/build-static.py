#!/usr/bin/env python3
"""
Build single-file static HTML: inline themes.json + dimensions.json + manifest.json
into index.html → index.standalone.html
"""
import json
from pathlib import Path

BASE = Path(__file__).parent

# Load data
themes = json.loads((BASE / "themes.json").read_text(encoding="utf-8"))
dims = json.loads((BASE / "dimensions.json").read_text(encoding="utf-8"))
manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))

# Load HTML
html = (BASE / "index.html").read_text(encoding="utf-8")

# Replace fetch-based init with inline data
# The original init() does:
#   const [themesResp, dimsResp, manifestResp] = await Promise.all([
#     fetch('themes.json'), fetch('dimensions.json'), fetch('manifest.json'),
#   ]);
#   THEMES = await themesResp.json();
#   DIM_CSS = await dimsResp.json();
#   MANIFEST = await manifestResp.json();

inline_data_block = f"""
// ========== DATA (inline) ==========
const THEMES = {json.dumps(themes, ensure_ascii=False)};
const DIM_CSS = {json.dumps(dims, ensure_ascii=False)};
const MANIFEST = {json.dumps(manifest, ensure_ascii=False)};
"""

# Find and replace the fetch block in init()
old_fetch_block = """  // Load data
  const [themesResp, dimsResp, manifestResp] = await Promise.all([
    fetch('themes.json'),
    fetch('dimensions.json'),
    fetch('manifest.json'),
  ]);
  THEMES = await themesResp.json();
  DIM_CSS = await dimsResp.json();
  MANIFEST = await manifestResp.json();"""

new_init_block = """  // Data already inline (static build)"""

html = html.replace(old_fetch_block, new_init_block)

# Also replace the let declarations with const (since they're now inline)
html = html.replace(
    """let THEMES = {};
let DIM_CSS = {};
let MANIFEST = null;""",
    inline_data_block.strip()
)

# Write output
out_path = BASE / "index.standalone.html"
out_path.write_text(html, encoding="utf-8")
print(f"Done: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
