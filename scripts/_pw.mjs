/**
 * _pw.mjs — 主题验证脚本共用的 Playwright 启动helper
 *
 * 为什么单独抽出来：
 *   1. `scripts/` 目录刻意不打进 Docker 镜像（见 AGENTS.md「容器（薄镜像）」），
 *      所以这里的脚本只服务于**桌面端**的主题开发/验收流程。
 *   2. 本机可能装的是 `playwright-core`（无浏览器下载）也可能装的是 `playwright`，
 *      两种都试，避免为了一个脚本去改全局依赖。
 *   3. ESM 的 `import` **不认 NODE_PATH**，但 `createRequire` 认 —— 所以用 CJS
 *      解析器来 require，这样 `NODE_PATH=... node scripts/xxx.mjs` 也能跑通。
 */
import { createRequire } from 'module';
import { existsSync, readdirSync } from 'fs';
import { join } from 'path';

const require = createRequire(import.meta.url);

/** 加载 chromium（playwright-core 优先，回退 playwright） */
export function loadChromium() {
  const errs = [];
  for (const mod of ['playwright-core', 'playwright']) {
    try {
      return require(mod).chromium;
    } catch (e) {
      errs.push(`  ${mod}: ${e.code || e.message}`);
    }
  }
  throw new Error(
    '未找到 playwright / playwright-core。\n' + errs.join('\n') +
    '\n请执行 `npm i -D playwright` 或设置 NODE_PATH 指向已安装的 node_modules。'
  );
}

/**
 * 解析 Chromium 可执行文件路径。
 * 优先级：CHROME_PATH 环境变量 → Playwright 下载的 chromium（版本号最大者）
 *        → 系统 Chrome → undefined（交给 Playwright 默认解析）
 */
export function resolveChromium() {
  if (process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH)) {
    return process.env.CHROME_PATH;
  }

  // Playwright 自己下载的 chromium：目录名带版本号，取最大的那个
  const pwBase = join(process.env.LOCALAPPDATA || '', 'ms-playwright');
  if (existsSync(pwBase)) {
    const dirs = readdirSync(pwBase)
      .filter(d => /^chromium-\d+$/.test(d))
      .sort((a, b) => parseInt(b.split('-')[1], 10) - parseInt(a.split('-')[1], 10));
    for (const d of dirs) {
      for (const sub of ['chrome-win64/chrome.exe', 'chrome-win/chrome.exe', 'chrome-linux/chrome']) {
        const p = join(pwBase, d, sub);
        if (existsSync(p)) return p;
      }
    }
  }

  // 系统 Chrome
  const local = process.env.LOCALAPPDATA || '';
  for (const p of [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    local ? join(local, 'Google/Chrome/Application/chrome.exe') : '',
  ]) {
    if (p && existsSync(p)) return p;
  }

  return undefined;
}

/** 统一启动参数 */
export async function launchBrowser(chromium) {
  return chromium.launch({
    executablePath: resolveChromium(),
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
}

/** 等待编辑器就绪（THEMES 由 build.py 注入） */
export async function waitForApp(page) {
  await page.waitForFunction(
    () => typeof THEMES !== 'undefined' && Object.keys(THEMES).length > 0,
    null, { timeout: 30000 });
}

/**
 * 打开编辑器页面。
 * 实测 Flask 开发服务器偶尔会出现一次 goto 卡满 30s 的情况（重试即好），
 * 所以这里带一次重试，避免偶发抖动把整批验证打断。
 */
export async function openApp(page, url) {
  let lastErr;
  for (let i = 0; i < 2; i++) {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await waitForApp(page);
      return;
    } catch (e) {
      lastErr = e;
      if (i === 0) console.log('[retry] 页面加载超时，重试一次…');
    }
  }
  throw lastErr;
}
