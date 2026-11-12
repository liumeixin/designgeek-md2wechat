#!/usr/bin/env node
/**
 * export_all.mjs — 批量导出：一次启动浏览器，把全部（或指定前缀的）主题各导出一份 HTML
 *
 * 为什么需要它：
 *   改主题 CSS 或导出管线后，要确认「每套主题都还能正确导出」。
 *   逐个主题重启浏览器约 20s/套，59 套要 20 分钟；本脚本复用同一个页面上下文，
 *   59 套约 1 分钟。产物可直接喂给 compare_preview_export.mjs 与 check_wechat_spec.py。
 *
 * 用法：
 *   node scripts/export_all.mjs <页面URL> <样稿.md> <输出目录> [slot=0|1] [主题前缀]
 *
 * 示例：
 *   node scripts/export_all.mjs http://127.0.0.1:18888/ sample.md out/ 1 zt-
 *     → 打开图片占位符，只导 zt- 开头的 35 套
 *
 * 前置：编辑器已在 <页面URL> 运行（run.bat 或 docker compose up）。
 * 说明：脚本通过劫持 navigator.clipboard.write 捕获 copyHtml() 的真实产物，
 *       所以拿到的是**用户按「复制」那一刻的 HTML**，不是预览 DOM。
 */
import { mkdirSync, writeFileSync, readFileSync } from 'fs';
import { join } from 'path';
import { loadChromium, launchBrowser, openApp } from './_pw.mjs';

const [,, url, mdFile, outDir, slotArg, prefixArg] = process.argv;

if (!url || !mdFile || !outDir) {
  console.error('用法: node scripts/export_all.mjs <页面URL> <样稿.md> <输出目录> [slot=0|1] [主题前缀]');
  process.exit(1);
}

const wantSlot = slotArg === '1';
const prefix = prefixArg || '';
const md = readFileSync(mdFile, 'utf8');
mkdirSync(outDir, { recursive: true });

const chromium = loadChromium();
const browser = await launchBrowser(chromium);
const page = await browser.newPage({ viewport: { width: 900, height: 1200 } });
page.on('pageerror', e => console.log('[pageerror]', e.message));

await openApp(page, url);

const ids = await page.evaluate(p => Object.keys(THEMES).filter(t => t.startsWith(p)).sort(), prefix);
console.log(`待导出主题数: ${ids.length}${prefix ? `（前缀 ${prefix}）` : ''}  图片占位符: ${wantSlot ? '开' : '关'}`);
if (!ids.length) {
  console.error('没有匹配的主题，检查前缀或确认 THEMES 已加载。');
  await browser.close();
  process.exit(1);
}

const fails = [];
for (const theme of ids) {
  try {
    const html = await page.evaluate(async ({ md, theme, wantSlot }) => {
      const ed = document.getElementById('editor');
      ed.value = md;
      ed.dispatchEvent(new Event('input', { bubbles: true }));
      applyTheme(theme);
      imgSlotOn = wantSlot;
      state.imgSlot = wantSlot;
      renderMarkdown();
      await new Promise(r => setTimeout(r, 120));

      // 劫持剪贴板，捕获 copyHtml() 真正写出的 HTML
      let captured = null;
      Object.defineProperty(navigator.clipboard, 'write', {
        configurable: true,
        value: async (items) => {
          const it = items[0];
          if (it && it.getType) captured = await (await it.getType('text/html')).text();
        },
      });
      copyHtml();
      await new Promise(r => setTimeout(r, 120));
      return captured;
    }, { md, theme, wantSlot });

    if (!html) { fails.push([theme, '捕获为空（copyHtml 未走剪贴板分支？）']); continue; }
    writeFileSync(join(outDir, theme + '.html'), html, 'utf8');
  } catch (e) {
    fails.push([theme, e.message]);
  }
}

console.log(`导出完成: ${ids.length - fails.length} / ${ids.length}  →  ${outDir}`);
if (fails.length) {
  fails.forEach(f => console.log(`  FAIL ${f[0]}: ${f[1]}`));
  await browser.close();
  process.exit(1);
}
await browser.close();
