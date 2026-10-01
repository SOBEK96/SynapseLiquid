// Loads the production bundle in headless Chrome against the LIVE contract and
// fails on any console error, uncaught exception or failed request.
//
//   npm run build && npm run console-check
//
// Env: CHROME_PATH (browser binary), CHECK_URL (check an already-hosted URL
// instead of serving ./dist), CHECK_REQUIRE_DATA=0 (skip the "pool data
// rendered" assertion, e.g. before a contract is deployed).
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const CANDIDATES = [
  process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean);
const chrome = CANDIDATES.find((p) => existsSync(p));
if (!chrome) {
  console.error("No Chrome/Chromium found. Set CHROME_PATH.");
  process.exit(2);
}

const PORT = 4173;
let server;
let url = process.env.CHECK_URL;
if (!url) {
  if (!existsSync(resolve(root, "dist/index.html"))) {
    console.error("dist/ missing: run `npm run build` first.");
    process.exit(2);
  }
  server = spawn("npx", ["vite", "preview", "--port", String(PORT), "--strictPort"], { cwd: root, stdio: "ignore" });
  url = `http://localhost:${PORT}/`;
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(url)).ok) break; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 250));
  }
}

const dep = existsSync(resolve(root, "src/deployment.json")) ? JSON.parse(readFileSync(resolve(root, "src/deployment.json"), "utf8")) : {};
const requireData = process.env.CHECK_REQUIRE_DATA !== "0" && !!dep.contract_address;

const problems = [];
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox"] });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console.error: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => problems.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`));
  page.on("response", (r) => { if (r.status() >= 400) problems.push(`HTTP ${r.status()}: ${r.url()}`); });

  await page.goto(url, { waitUntil: "networkidle2", timeout: 60000 });
  await page.waitForSelector("nav", { timeout: 10000 });

  if (requireData) {
    // The registry must populate from the live contract.
    await page.waitForFunction(
      () => document.body.innerText.includes("Total Pool Liquidity") && !document.body.innerText.includes("Reading borrower registry"),
      { timeout: 90000 },
    ).catch(() => problems.push("live contract data did not render within 90s"));
    const text = await page.evaluate(() => document.body.innerText);
    if (!/AAA|C\b/.test(text)) problems.push("no rated borrower rendered from the live contract");
  }
  // nav must stay a single 64px line
  const nav = await page.$eval("nav", (n) => ({ h: n.getBoundingClientRect().height, wrap: getComputedStyle(n).flexWrap }));
  if (Math.round(nav.h) !== 64 || nav.wrap !== "nowrap") problems.push(`navbar not a single 64px line: ${JSON.stringify(nav)}`);
  await new Promise((r) => setTimeout(r, 1500));
} finally {
  await browser.close();
  server?.kill();
}

if (problems.length) {
  console.error(`FAIL: ${problems.length} problem(s)`);
  for (const p of problems) console.error(" - " + p);
  process.exit(1);
}
console.log(`PASS: zero console errors loading ${url}${requireData ? " (live contract data rendered)" : " (no deployment: shell only)"}`);
