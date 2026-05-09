import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE_URL = "http://127.0.0.1:5173";
const EVIDENCE_DIR = "docs/04_テスト/04_総合テスト/evidence";
const PROMPT = [
  "総合テスト用です。",
  "回答本文に「参照元総合テスト」を含めて、1文で回答してください。",
  "参照元は system-test-reference.pdf の1ページだけを使用してください。",
  "出力スキーマの references には source_type=pdf、locator.path=system-test-reference.pdf、start_page=1、end_page=1 を設定してください。",
].join("\n");

const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.setDefaultTimeout(360_000);

try {
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  const existingHistory = page
    .getByRole("button", { name: /総合テスト用です。 回答本文に/ })
    .first();
  if ((await existingHistory.count()) > 0) {
    await existingHistory.click();
  } else {
    await page.getByPlaceholder("指示を入力してください").fill(PROMPT);
    await page.getByLabel("送信").click();
  }
  await page.getByRole("button", { name: /system-test-reference\.pdf p\.1/ }).waitFor();
  await page.locator(".markdown-body").filter({ hasText: "参照元総合テスト" }).waitFor();
  await page.screenshot({
    path: `${EVIDENCE_DIR}/ST-CHAT-005-real-reference-complete.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: /system-test-reference\.pdf p\.1/ }).click();
  await page.getByRole("dialog").waitFor();
  await page.getByRole("heading", { name: "system-test-reference.pdf" }).waitFor();
  await page.screenshot({
    path: `${EVIDENCE_DIR}/ST-CHAT-009-real-reference-viewer.png`,
    fullPage: true,
  });
  console.log("real reference chat passed");
} finally {
  await browser.close();
}
