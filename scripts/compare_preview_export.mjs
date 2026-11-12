#!/usr/bin/env node
/**
 * compare_preview_export.mjs — 校验「导出结果 == 编辑器预览」
 *
 * 为什么需要它：
 *   微信不保留主题 CSS，所以导出的 HTML 必须把样式**内联**到每个元素上。
 *   一旦某个属性没被内联，粘贴到公众号后就会回退到继承值 —— 典型症状是
 *   「预览里 15px，粘贴过去变成 17px」。这个脚本就是把这类偏差量化出来。
 *
 * 做法：
 *   1. 在编辑器里套用主题、渲染样稿，采集 #wenyan 内若干选择器的计算样式
 *   2. 把 export_all.mjs 导出的 HTML 载入空白页，采集同名选择器的计算样式
 *   3. 逐项 diff，并把「渲染等价」的差异单列，避免噪音淹没真问题
 *
 * 用法：
 *   node scripts/compare_preview_export.mjs <页面URL> <样稿.md> <导出目录> [主题...]
 *
 * 示例：
 *   node scripts/compare_preview_export.mjs http://127.0.0.1:18888/ sample.md out/
 *     → 对比 out/ 下所有导出文件
 *   node scripts/compare_preview_export.mjs http://127.0.0.1:18888/ sample.md out/ zt-orange ugreen
 *     → 只对比指定的两套
 *   VERBOSE=1 ...  → 连「渲染等价」的差异也打出来
 *
 * 退出码：存在「实质差异」时为 1（便于串进验收流程），否则 0。
 */
import { readFileSync, readdirSync, existsSync } from 'fs';
import { join } from 'path';
import { loadChromium, launchBrowser, openApp } from './_pw.mjs';

const [,, url, mdFile, expDir, ...themeArgs] = process.argv;

if (!url || !mdFile || !expDir) {
  console.error('用法: node scripts/compare_preview_export.mjs <页面URL> <样稿.md> <导出目录> [主题...]');
  process.exit(1);
}

const PROPS = ['fontSize', 'lineHeight', 'color', 'letterSpacing', 'textAlign', 'fontWeight'];
const SELS = ['p', 'h1', 'h2', 'h3', 'h4', 'blockquote p', 'table th', 'table td',
              'li', 'code', 'pre code', 'strong', 'em', 'a', 'hr'];

// 渲染等价的对：text-align 的 start/end 在 LTR 下等同 left/right
const EQUIV = { textAlign: [['start', 'left'], ['end', 'right']] };

// 数值容差（px）：亚像素舍入不算问题。按属性区分 —— 字号差 1px 是真问题，
// 行高差 1px 看不出来（继承值取整造成的抖动常见 0.1~0.6px）。
const TOLERANCE = { fontSize: 0, lineHeight: 1, letterSpacing: 0.5, fontWeight: 0 };

const norm = v => String(v).replace(/\s+/g, ' ').trim();

function classify(prop, a, b) {
  const x = norm(a), y = norm(b);
  if (x === y) return 'same';
  for (const [p, q] of (EQUIV[prop] || [])) {
    if ((x === p && y === q) || (x === q && y === p)) return 'equiv';
  }
  const nx = parseFloat(x), ny = parseFloat(y);
  const tol = TOLERANCE[prop] ?? 0;
  if (tol > 0 && !isNaN(nx) && !isNaN(ny) && /px$/.test(x) && /px$/.test(y) &&
      Math.abs(nx - ny) <= tol) return 'equiv';
  return 'real';
}

/**
 * 在页面里采集样式。按**全部匹配元素**逐个采集（不是只取第一个）：
 * 预览与导出的 DOM 结构不完全相同（导出会加 .table-wrap、重排参考来源等），
 * 只比第一个容易张冠李戴，把结构差异误报成样式差异。
 */
const grabFn = ({ rootSel, PROPS, SELS }) => {
  const root = document.querySelector(rootSel) || document;
  const out = {};
  for (const sel of SELS) {
    const els = [...root.querySelectorAll(sel)];
    out[sel] = els.map(el => {
      const cs = getComputedStyle(el);
      const o = {};
      for (const p of PROPS) o[p] = cs[p];
      return o;
    });
  }
  return out;
};

const md = readFileSync(mdFile, 'utf8');
let themes = themeArgs;
if (!themes.length) {
  themes = readdirSync(expDir).filter(f => f.endsWith('.html')).map(f => f.slice(0, -5)).sort();
}
if (!themes.length) {
  console.error(`导出目录里没有 .html：${expDir}`);
  process.exit(1);
}

const chromium = loadChromium();
const browser = await launchBrowser(chromium);
const app = await browser.newPage({ viewport: { width: 900, height: 1200 } });
await openApp(app, url);

let totalReal = 0, totalEquiv = 0;
const summary = [];

for (const theme of themes) {
  const f = join(expDir, theme + '.html');
  if (!existsSync(f)) {
    console.log(`\n=== ${theme} === 跳过：缺少 ${f}`);
    summary.push([theme, '-', '-', '缺文件']);
    continue;
  }

  await app.evaluate(async ({ md, theme }) => {
    const ed = document.getElementById('editor');
    ed.value = md;
    ed.dispatchEvent(new Event('input', { bubbles: true }));
    applyTheme(theme);
    renderMarkdown();
    await new Promise(r => setTimeout(r, 300));
  }, { md, theme });
  const preview = await app.evaluate(grabFn, { rootSel: '#wenyan', PROPS, SELS });

  const page = await browser.newPage({ viewport: { width: 900, height: 1200 } });
  await page.setContent(
    `<!doctype html><meta charset="utf-8"><body style="margin:0">${readFileSync(f, 'utf8')}</body>`);
  const exported = await page.evaluate(grabFn, { rootSel: 'body', PROPS, SELS });
  await page.close();

  const real = [], equiv = [], struct = [];
  for (const sel of SELS) {
    const A = preview[sel] || [], B = exported[sel] || [];
    if (!A.length && !B.length) continue;
    if (A.length !== B.length) {
      struct.push(`${sel}: 元素数不同（预览 ${A.length} / 导出 ${B.length}），跳过样式对比`);
      continue;
    }
    for (let i = 0; i < A.length; i++) {
      for (const p of PROPS) {
        const k = classify(p, A[i][p], B[i][p]);
        if (k === 'same') continue;
        const line = `${sel}[${i}] ${p}: 预览=${norm(A[i][p])} 导出=${norm(B[i][p])}`;
        (k === 'real' ? real : equiv).push(line);
      }
    }
  }

  totalReal += real.length;
  totalEquiv += equiv.length;
  summary.push([theme, real.length, equiv.length, real.length ? 'FAIL' : 'OK']);

  console.log(`\n=== ${theme} ===  实质差异 ${real.length}，渲染等价 ${equiv.length}` +
              (struct.length ? `，结构差异 ${struct.length}` : ''));
  real.forEach(l => console.log('   ✗', l));
  if (struct.length) struct.forEach(l => console.log('   ·', l));
  if (process.env.VERBOSE) equiv.forEach(l => console.log('   ·', l));
}

console.log('\n主题                 实质   等价  结论');
console.log('-'.repeat(44));
for (const [t, r, e, s] of summary) {
  console.log(`${t.padEnd(20)} ${String(r).padStart(4)} ${String(e).padStart(6)}  ${s}`);
}
console.log(`\n合计：实质差异 ${totalReal}，渲染等价 ${totalEquiv}（${themes.length} 套主题）`);
if (totalEquiv && !process.env.VERBOSE) console.log('（渲染等价项加 VERBOSE=1 查看）');

await browser.close();
process.exit(totalReal ? 1 : 0);
