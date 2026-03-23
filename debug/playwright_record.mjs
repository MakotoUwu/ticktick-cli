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

function stamp(now = new Date()) {
  return now.toISOString().replace(/[:.]/g, "-");
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

function shouldCapture(url, patterns) {
  return patterns.some((pattern) => url.includes(pattern));
}

async function maybeReadResponseBody(response) {
  const contentType = response.headers()["content-type"] || "";
  if (!contentType.includes("json")) {
    return null;
  }

  const text = await response.text();
  if (text.length > 50_000) {
    return { truncated: true, preview: text.slice(0, 50_000) };
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const url = String(args.get("url") ?? "https://ticktick.com/webapp/#q/all/tasks");
  const durationMs = Number(args.get("duration-ms") ?? 120000);
  const patterns = String(args.get("patterns") ?? "ms.ticktick.com,api.ticktick.com")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  if (!Number.isFinite(durationMs) || durationMs < 1000) {
    throw new Error("--duration-ms must be a number >= 1000");
  }

  const outputDir = path.join(repoRoot, "output", "playwright", "network");
  const outputPath = path.join(outputDir, `${stamp()}-capture.json`);
  const profileDir = path.join(repoRoot, ".codex-playwright", "chrome-profile");

  await ensureDir(outputDir);
  await ensureDir(profileDir);

  const { chromium } = loadPlaywright();
  const context = await chromium.launchPersistentContext(profileDir, {
    channel: "chrome",
    headless: false,
    viewport: { width: 1440, height: 900 },
  });

  const events = [];
  const startedAt = new Date().toISOString();

  context.on("response", (response) => {
    void (async () => {
      const request = response.request();
      const requestUrl = request.url();
      if (!shouldCapture(requestUrl, patterns)) {
        return;
      }
      if (!["xhr", "fetch"].includes(request.resourceType())) {
        return;
      }

      const body = await maybeReadResponseBody(response);
      const entry = {
        capturedAt: new Date().toISOString(),
        method: request.method(),
        url: requestUrl,
        resourceType: request.resourceType(),
        status: response.status(),
        requestHeaders: request.headers(),
        requestBody: request.postDataJSON?.() ?? request.postData() ?? null,
        responseHeaders: response.headers(),
        responseBody: body,
      };
      events.push(entry);
      console.log(`[capture] ${entry.method} ${entry.status} ${entry.url}`);
    })().catch((error) => {
      console.error(`[capture-error] ${error}`);
    });
  });

  let page = context.pages()[0];
  if (!page) {
    page = await context.newPage();
  }

  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);

  console.log(`Recording network for ${durationMs}ms`);
  console.log(`Start URL: ${url}`);
  console.log(`Patterns: ${patterns.join(", ")}`);
  console.log(`Output: ${outputPath}`);
  console.log("Use the opened Chrome window to perform the target TickTick action now.");

  await page.waitForTimeout(durationMs);

  const payload = {
    startedAt,
    finishedAt: new Date().toISOString(),
    url,
    patterns,
    count: events.length,
    events,
  };
  await fs.writeFile(outputPath, JSON.stringify(payload, null, 2));
  await context.close();

  console.log(JSON.stringify({ ok: true, output: outputPath, count: events.length }, null, 2));
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: String(error) }, null, 2));
  process.exit(1);
});
