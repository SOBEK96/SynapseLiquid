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
      () => document.body.textContent.includes("Total Pool Liquidity") && !document.body.textContent.includes("Reading borrower registry"),
      { timeout: 90000 },
    ).catch(() => problems.push("live contract data did not render within 90s"));
    // Pool metrics must show the live (non-placeholder) liquidity figure.
    const liquidity = await page.evaluate(() => {
      const cell = [...document.querySelectorAll("div")].find((d) => d.textContent === "Total Pool Liquidity");
      return cell?.nextElementSibling?.textContent ?? "";
    });
    if (!/^\d+\.\d+/.test(liquidity)) problems.push(`pool liquidity did not render from chain (got "${liquidity}")`);
    else console.log(`live pool liquidity: ${liquidity} GEN`);
  }
  // nav must stay a single 64px line
  const nav = await page.$eval("nav", (n) => ({ h: n.getBoundingClientRect().height, wrap: getComputedStyle(n).flexWrap }));
  if (Math.round(nav.h) !== 64 || nav.wrap !== "nowrap") problems.push(`navbar not a single 64px line: ${JSON.stringify(nav)}`);
  // The About drawer: opens, every tab renders, ESC and backdrop both close it.
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const dialogOpen = () => page.$('[role="dialog"][aria-label="Protocol specifications"]').then(Boolean);
  await page.click('button[aria-label="Protocol Specs"]');
  await page.waitForSelector('[role="dialog"] [role="tablist"]', { timeout: 5000 }).catch(() => problems.push("About drawer did not open"));
  for (const id of ["overview", "arch", "risk", "safe"]) {
    await page.click(`#about-tab-${id}`).catch(() => problems.push(`About tab ${id} missing`));
    const sel = await page.$eval(`#about-tab-${id}`, (b) => b.getAttribute("aria-selected")).catch(() => null);
    const txt = await page.$eval("[role=tabpanel]", (p) => p.textContent ?? "").catch(() => "");
    if (sel !== "true" || txt.length < 200) problems.push(`About tab ${id} did not render`);
  }
  await page.click("#about-tab-risk");
  const risk = await page.$eval("[role=tabpanel]", (p) => p.textContent ?? "");
  if (!/Net Operating Income/.test(risk) || !/Net Monthly Burn/.test(risk) || !/35\.00%/.test(risk)) problems.push("risk tab missing formulas or tiers");
  await page.keyboard.press("Escape");
  await sleep(500);
  if (await dialogOpen()) problems.push("ESC did not close the About drawer");
  await page.click('button[aria-label="Protocol Specs"]');
  await sleep(400);
  await page.mouse.click(40, 450); // backdrop, left of the slide-over
  await sleep(500);
  if (await dialogOpen()) problems.push("backdrop click did not close the About drawer");
  await sleep(1000);
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
