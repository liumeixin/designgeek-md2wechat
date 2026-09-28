#!/usr/bin/env node
/**
 * html2png.mjs — Playwright 截图脚本（Windows 版）
 * 
 * 用法: node html2png.mjs <input.html> <output.png> [width] [height]
 * 
 * 使用 Playwright + Chromium 将 HTML 文件截图为 PNG。
 * 自动检测本地安装的 Chromium 路径。
 */
import { chromium } from 'playwright';
import { resolve } from 'path';

const [,, htmlPath, outputPath, widthStr, heightStr] = process.argv;

if (!htmlPath || !outputPath) {
  console.error('Usage: node html2png.mjs <input.html> <output.png> [width] [height]');
  process.exit(1);
}

const W = parseInt(widthStr || '1080', 10);
const H = parseInt(heightStr || '1440', 10);
const absHtml = resolve(htmlPath);
const absOut = resolve(outputPath);

// 自动检测 Chromium 路径（兼容 Windows/Linux/Mac）
let chromePath = process.env.CHROME_PATH;
if (!chromePath) {
  // 尝试使用 Playwright 内置的 Chromium
  try {
    const { execSync } = await import('child_process');
    // playwright install chromium 后的默认位置
    const result = execSync('npx playwright install --dry-run chromium', { 
      encoding: 'utf-8',
      timeout: 10000 
    });
    // 从输出中提取路径
    const match = result.match(/Install.*?:\s*(.+?)[\r\n]/);
    if (match) {
      chromePath = match[1].trim();
    }
  } catch (e) {
    // 忽略错误，使用默认路径
  }
  
  // 如果自动检测失败，使用常见默认路径
  if (!chromePath) {
    // Windows 常见路径
    const defaultPaths = [
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
      `${process.env.LOCALAPPDATA}\\Google\\Chrome\\Application\\chrome.exe`,
      // Playwright 默认安装路径
      `${process.env.USERPROFILE}\\AppData\\Local\\ms-playwright\\chromium-1155\\chrome-win\\chrome.exe`,
    ];
    
    const fs = await import('fs');
    for (const p of defaultPaths) {
      if (fs.existsSync(p)) {
        chromePath = p;
        break;
      }
    }
  }
}

console.log(`[screenshot] Using Chrome: ${chromePath || 'Playwright default'}`);

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath || undefined,
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
});

try {
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.goto(`file://${absHtml}`, { waitUntil: 'networkidle', timeout: 15000 });
  // 等待图片和字体加载
  await page.waitForTimeout(1500);
  await page.screenshot({ path: absOut, type: 'png' });
  console.log(`✅ Screenshot saved: ${absOut} (${W}x${H})`);
} catch (err) {
  console.error(`❌ Screenshot failed: ${err.message}`);
  process.exit(1);
} finally {
  await browser.close();
}
