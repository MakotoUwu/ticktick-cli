#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const args = new Map();

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
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

  return args;
}

function utcStamp(now = new Date()) {
  return now.toISOString().replace(/[:.]/g, "-");
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

function loadPlaywright() {
  const modulePath = path.join(
    repoRoot,
    ".codex-playwright",
    "node_modules",
    "playwright",
  );

  try {
    return require(modulePath);
  } catch (error) {
    const hint = [
      "Playwright is not available in the repo-local tool dir.",
      `Expected module path: ${modulePath}`,
      "Install it with:",
      "  cd .codex-playwright",
      "  npm install playwright",
    ].join("\n");
    throw new Error(`${hint}\n\nOriginal error: ${error}`);
  }
}

async function capturePage(page, capturePath, latestPath, latestMetaPath, sessionDir, index) {
  await page.screenshot({ path: capturePath, fullPage: false });
  await fs.copyFile(capturePath, latestPath);

  const meta = {
    capture_index: index,
    captured_at: new Date().toISOString(),
    file: capturePath,
    latest_file: latestPath,
    session_dir: sessionDir,
    title: await page.title(),
    url: page.url(),
  };
  await fs.writeFile(latestMetaPath, JSON.stringify(meta, null, 2));

  return meta;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const intervalMs = Number(args.get("interval") ?? 5000);
  if (!Number.isFinite(intervalMs) || intervalMs < 1000) {
    throw new Error("--interval must be a number >= 1000");
  }

  const targetUrl = String(args.get("url") ?? "https://ticktick.com/webapp");
  const outputRoot = path.join(repoRoot, "output", "playwright");
  const sessionDir = path.join(outputRoot, `ticktick-watch-${utcStamp()}`);
  const latestPath = path.join(outputRoot, "latest.png");
  const latestMetaPath = path.join(outputRoot, "latest.json");
  const tracePath = path.join(sessionDir, "trace.zip");
  const profileDir = path.join(repoRoot, ".codex-playwright", "chrome-profile");

  await ensureDir(outputRoot);
  await ensureDir(sessionDir);
  await ensureDir(profileDir);

  const { chromium } = loadPlaywright();
  const context = await chromium.launchPersistentContext(profileDir, {
    channel: "chrome",
    headless: false,
    viewport: { width: 1440, height: 900 },
  });

  await context.tracing.start({ screenshots: true, snapshots: true });

  let page = context.pages()[0];
  if (!page) {
    page = await context.newPage();
  }

  await page.goto(targetUrl, { waitUntil: "domcontentloaded" });

  console.log(`Watching ${targetUrl}`);
  console.log(`Session dir: ${sessionDir}`);
  console.log(`Latest screenshot: ${latestPath}`);
  console.log(`Latest metadata: ${latestMetaPath}`);
  console.log("Log in manually in the opened Chrome window if needed.");

  let captureIndex = 0;
  const takeCapture = async () => {
    captureIndex += 1;
    const capturePath = path.join(
      sessionDir,
      `${String(captureIndex).padStart(4, "0")}.png`,
    );

    const meta = await capturePage(
      page,
      capturePath,
      latestPath,
      latestMetaPath,
      sessionDir,
      captureIndex,
    );
    console.log(
      `Captured #${meta.capture_index}: ${meta.file} (${meta.title || "untitled"})`,
    );
  };

  await takeCapture();
  const timer = setInterval(() => {
    void takeCapture().catch((error) => {
      console.error(`Capture failed: ${error}`);
    });
  }, intervalMs);

  const shutdown = async (signal) => {
    clearInterval(timer);
    console.log(`Stopping watcher (${signal})`);

    try {
      await context.tracing.stop({ path: tracePath });
      console.log(`Trace saved: ${tracePath}`);
    } catch (error) {
      console.error(`Could not save trace: ${error}`);
    }

    await context.close();
    process.exit(0);
  };

  process.on("SIGINT", () => {
    void shutdown("SIGINT");
  });
  process.on("SIGTERM", () => {
    void shutdown("SIGTERM");
  });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
