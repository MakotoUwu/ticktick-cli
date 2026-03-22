#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const require = createRequire(import.meta.url);

function loadPlaywright() {
  const modulePath = path.join(
    repoRoot,
    ".codex-playwright",
    "node_modules",
    "playwright",
  );
  return require(modulePath);
}

function usage() {
  console.error(
    [
      "Usage:",
      "  node debug/playwright_probe.mjs snapshot --url URL [--label NAME] [--headed]",
      "  node debug/playwright_probe.mjs text-present --url URL --text TEXT [--label NAME] [--headed]",
      "  node debug/playwright_probe.mjs focus-summary [--label NAME] [--headed]",
    ].join("\n"),
  );
}

function parseArgs(argv) {
  const args = new Map();
  const positionals = [];

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      positionals.push(token);
      continue;
    }

    const key = token.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args.set(key, true);
      continue;
    }

    args.set(key, next);
    index += 1;
  }

  return { args, positionals };
}

function stamp(now = new Date()) {
  return now.toISOString().replace(/[:.]/g, "-");
}

function sanitizeLabel(value) {
  return value.replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

async function withContext({ headed }, callback) {
  const { chromium } = loadPlaywright();
  const profileDir = path.join(repoRoot, ".codex-playwright", "chrome-profile");
  await ensureDir(profileDir);

  const context = await chromium.launchPersistentContext(profileDir, {
    channel: "chrome",
    headless: !headed,
    viewport: { width: 1440, height: 900 },
  });

  try {
    let page = context.pages()[0];
    if (!page) {
      page = await context.newPage();
    }
    return await callback(page);
  } finally {
    await context.close();
  }
}

async function capturePage(page, label) {
  const outputDir = path.join(repoRoot, "output", "playwright", "probes");
  await ensureDir(outputDir);

  const slug = sanitizeLabel(label || "probe") || "probe";
  const base = `${stamp()}-${slug}`;
  const screenshotPath = path.join(outputDir, `${base}.png`);
  const jsonPath = path.join(outputDir, `${base}.json`);

  await page.waitForLoadState("domcontentloaded");
  await page.screenshot({ path: screenshotPath, fullPage: false });

  const bodyText = (await page.locator("body").innerText()).trim();
  const buttons = (await page.getByRole("button").allTextContents())
    .map((value) => value.trim())
    .filter(Boolean);
  const textLines = bodyText
    .split("\n")
    .map((value) => value.trim())
    .filter(Boolean)
    .slice(0, 25);

  const payload = {
    capturedAt: new Date().toISOString(),
    title: await page.title(),
    url: page.url(),
    screenshot: screenshotPath,
    bodyTextExcerpt: bodyText.slice(0, 4000),
    textLines,
    buttons,
  };

  await fs.writeFile(jsonPath, JSON.stringify(payload, null, 2));
  return { ...payload, json: jsonPath };
}

async function settlePage(page, settleMs = 2500) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(settleMs);
}

async function runSnapshot(args) {
  const url = args.get("url");
  if (!url) {
    throw new Error("snapshot requires --url");
  }

  return withContext({ headed: Boolean(args.get("headed")) }, async (page) => {
    await page.goto(String(url), { waitUntil: "domcontentloaded" });
    await settlePage(page);
    return capturePage(page, String(args.get("label") || "snapshot"));
  });
}

async function runTextPresent(args) {
  const url = args.get("url");
  const text = args.get("text");
  if (!url || !text) {
    throw new Error("text-present requires --url and --text");
  }

  return withContext({ headed: Boolean(args.get("headed")) }, async (page) => {
    await page.goto(String(url), { waitUntil: "domcontentloaded" });
    await settlePage(page);
    const locator = page.getByText(String(text), { exact: false });
    const count = await locator.count();
    const capture = await capturePage(page, String(args.get("label") || "text-present"));
    return {
      ...capture,
      queryText: String(text),
      present: count > 0,
      matchCount: count,
    };
  });
}

async function runFocusSummary(args) {
  return withContext({ headed: Boolean(args.get("headed")) }, async (page) => {
    await page.goto("https://ticktick.com/webapp/#focus", {
      waitUntil: "domcontentloaded",
    });
    await settlePage(page);

    const capture = await capturePage(page, String(args.get("label") || "focus-summary"));
    const timerMatch = capture.bodyTextExcerpt.match(/\b\d{2}:\d{2}\b/);

    return {
      ...capture,
      timerText: timerMatch ? timerMatch[0] : "",
    };
  });
}

async function main() {
  const { args, positionals } = parseArgs(process.argv.slice(2));
  const command = positionals[0];
  if (!command) {
    usage();
    process.exit(2);
  }

  let result;
  if (command === "snapshot") {
    result = await runSnapshot(args);
  } else if (command === "text-present") {
    result = await runTextPresent(args);
  } else if (command === "focus-summary") {
    result = await runFocusSummary(args);
  } else {
    usage();
    process.exit(2);
  }

  console.log(JSON.stringify({ ok: true, data: result }, null, 2));
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: String(error) }, null, 2));
  process.exit(1);
});
