import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE_URL = "http://127.0.0.1:5173";
const EVIDENCE_DIR = "docs/04_テスト/04_総合テスト/evidence";

const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const requests = [];
const consoleErrors = [];

page.on("request", (request) => {
  requests.push({ method: request.method(), url: request.url() });
});
page.on("console", (message) => {
  if (message.type() === "error") {
    consoleErrors.push(message.text());
  }
});

try {
  await openStart();
  await verifySuggestion();
  await verifyHistoryList();
  await verifyRichHistory();
  await verifyTerminalHistories();
  await verifyRunningHistory();
  await verifySidebarToggle();

  if (consoleErrors.length > 0) {
    throw new Error(`console error: ${consoleErrors.join("\n")}`);
  }

  console.log("system checks passed");
} finally {
  await browser.close();
}

async function openStart() {
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  await page.getByText("D-Conciergeへようこそ。調査したい内容を入力してください。").waitFor();
}

async function verifySuggestion() {
  await page.getByRole("button", { name: "資料の要点を整理してください。" }).click();
  const textarea = page.getByPlaceholder("指示を入力してください");
  await expectValue(textarea, "資料の要点を整理してください。");
  await textarea.fill("資料の要点を整理してください。追加確認です。");
  await expectValue(textarea, "資料の要点を整理してください。追加確認です。");
  await screenshot("ST-CHAT-003-suggestion.png");
}

async function verifyHistoryList() {
  const nav = page.getByRole("navigation", { name: "最近のチャット" });
  await nav.getByRole("button", { name: "総合テスト: 参照元と成果物" }).waitFor();
  for (const title of [
    "総合テスト: 中止ケース",
    "総合テスト: 時間超過ケース",
    "総合テスト: 生成失敗ケース",
    "総合テスト: 処理中ケース",
  ]) {
    await nav.getByRole("button", { name: title }).waitFor();
  }
  const navText = (await nav.textContent()) ?? "";
  for (const hiddenText of ["完了", "タイムアウト", "エラー", "実行中", "2026-"]) {
    if (navText.includes(hiddenText)) {
      throw new Error(`履歴一覧に状態または日時が表示されています: ${hiddenText}`);
    }
  }
  await screenshot("ST-HISTORY-001-history-list.png");
}

async function verifyRichHistory() {
  await page
    .getByRole("button", { name: "総合テスト: 参照元と成果物" })
    .click();
  await page.getByText("総合テスト用の参照元と成果物を表示してください。").waitFor();
  await page.getByText("総合テスト回答").waitFor();
  await page.getByRole("button", { name: "作業プロセス" }).click();
  await page.getByText("総合テスト用の保存済み中間メッセージです。").waitFor();
  await page.locator('img[alt="総合テスト成果物"]').waitFor();
  const bodyText = (await page.locator("body").textContent()) ?? "";
  if (bodyText.includes("codex/sessions")) {
    throw new Error("内部作業ディレクトリが画面に表示されています。");
  }
  await screenshot("ST-HISTORY-002-completed-detail.png");
  await screenshot("ST-HISTORY-007-artifact.png");

  await page.getByRole("button", { name: /総合テスト参照PDF p\.1/ }).click();
  await page.getByRole("dialog").waitFor();
  await page.getByText("参照元PDF").waitFor();
  await page.getByRole("heading", { name: "総合テスト参照PDF" }).waitFor();
  await page.getByText("参照元ページ p.1").waitFor();
  await screenshot("ST-HISTORY-006-reference-viewer.png");
  await page.keyboard.press("Escape");
}

async function verifyTerminalHistories() {
  await openTerminalHistory({
    title: "総合テスト: 中止ケース",
    instruction: "総合テスト用のキャンセル済み履歴です。",
    intermediate: "キャンセル前の保存済み中間メッセージです。",
    message: "処理をキャンセルしました。",
    screenshotName: "ST-CANCEL-009-canceled-history.png",
  });
  if (await page.getByLabel("キャンセル").count()) {
    throw new Error("終端済みrunにキャンセル操作が表示されています。");
  }
  await screenshot("ST-CANCEL-006-terminal-no-cancel.png");

  await openTerminalHistory({
    title: "総合テスト: 時間超過ケース",
    instruction: "総合テスト用のタイムアウト履歴です。",
    intermediate: "タイムアウト前の保存済み中間メッセージです。",
    message: "回答生成が時間内に完了しませんでした。ユーザ指示を絞って再度お試しください。",
    screenshotName: "ST-HISTORY-005-timeout.png",
  });

  await openTerminalHistory({
    title: "総合テスト: 生成失敗ケース",
    instruction: "総合テスト用のエラー履歴です。",
    intermediate: "エラー前の保存済み中間メッセージです。",
    message: "回答生成に失敗しました。ユーザ指示を見直して再度お試しください。",
    screenshotName: "ST-HISTORY-005-error.png",
  });
}

async function openTerminalHistory({ title, instruction, intermediate, message, screenshotName }) {
  await page.getByRole("button", { name: title }).click();
  await page.getByText(instruction).waitFor();
  await page.getByRole("button", { name: "作業プロセス" }).click();
  await page.getByText(intermediate).waitFor();
  await page.getByText(message).waitFor();
  await screenshot(screenshotName);
}

async function verifyRunningHistory() {
  const beforeRunPosts = countAppendRunPosts();
  const beforeSse = countSseRequests();
  await page.getByRole("button", { name: "総合テスト: 処理中ケース" }).click();
  await page.getByText("総合テスト用の継続中履歴です。").waitFor();
  await page.getByText("継続中の保存済み中間メッセージです。").waitFor();
  await page.getByLabel("キャンセル").waitFor();
  await waitForRequestCount(() => countSseRequests(), beforeSse + 1);
  await screenshot("ST-HISTORY-004-running-reconnect.png");

  const textarea = page.getByPlaceholder("指示を入力してください");
  await textarea.fill("未完了run中の追加指示です。");
  await textarea.press(process.platform === "darwin" ? "Meta+Enter" : "Control+Enter");
  await page.waitForTimeout(400);
  if (countAppendRunPosts() !== beforeRunPosts) {
    throw new Error("未完了runがあるチャットで継続指示POSTが送信されました。");
  }
  await screenshot("ST-CHAT-012-unfinished-run-conflict.png");
}

async function verifySidebarToggle() {
  await page.getByRole("button", { name: "サイドバー切替" }).click();
  await page.getByRole("button", { name: "サイドバーを展開" }).waitFor();
  await page.getByText("総合テスト用の継続中履歴です。").waitFor();
  await page.getByRole("button", { name: "サイドバーを展開" }).click();
  await page.getByRole("button", { name: "総合テスト: 処理中ケース" }).waitFor();
  await page.getByText("総合テスト用の継続中履歴です。").waitFor();
  await screenshot("ST-HISTORY-015-sidebar-toggle.png");
}

async function screenshot(name) {
  await page.screenshot({ path: `${EVIDENCE_DIR}/${name}`, fullPage: true });
}

async function expectValue(locator, expected) {
  const value = await locator.inputValue();
  if (value !== expected) {
    throw new Error(`入力値が一致しません。expected=${expected} actual=${value}`);
  }
}

function countSseRequests() {
  return requests.filter((request) => request.url.includes("/sse")).length;
}

function countAppendRunPosts() {
  return requests.filter(
    (request) => request.method === "POST" && /\/api\/chats\/[^/]+\/runs$/.test(request.url),
  ).length;
}

async function waitForRequestCount(getCount, expected) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 3000) {
    if (getCount() >= expected) {
      return;
    }
    await page.waitForTimeout(100);
  }
  throw new Error(`リクエスト数が期待値に到達しません。expected=${expected} actual=${getCount()}`);
}
