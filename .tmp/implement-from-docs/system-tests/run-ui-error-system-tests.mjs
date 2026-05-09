import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE_URL = "http://127.0.0.1:5173";
const EVIDENCE_DIR = "docs/04_テスト/04_総合テスト/evidence";
const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);
const referencePdf = await readFile("codex/readonly/system-test-reference.pdf");

const browser = await chromium.launch({ channel: "chrome", headless: true });

try {
  await verifyAppConfigFailure();
  await verifyHistoryListFailure();
  await verifyStartFailure();
  await verifySseConnectionFailure();
  await verifySseMidDisconnect();
  await verifyRichAnswerAndContinuation();
  await verifyTerminalErrors();
  await verifyReferenceAndArtifactFailures();
  await verifyHistoryOrderAndContinuation();
  await verifyContinuationFailure();
  await verifyHistoryDetailFailure();
  await verifyHistorySseSwitchAndReturn();
  await verifyCancelAccepted();
  await verifyCancelDuringValidation();
  await verifyCancelFailure();

  console.log("ui error system checks passed");
} finally {
  await browser.close();
}

async function verifyAppConfigFailure() {
  await withPage(
    {
      appConfig: () => ({ status: 500, body: "error" }),
      histories: () => [],
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await page.getByPlaceholder("指示を入力してください").waitFor();
      await expectHidden(page, "D-Conciergeへようこそ。調査したい内容を入力してください。");
      await expectHidden(page, "資料の要点を整理してください。");
      await screenshot(page, "ST-CHAT-002-app-config-fallback.png");
    },
  );
}

async function verifyHistoryListFailure() {
  await withPage(
    {
      histories: () => ({ status: 500, body: "error" }),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await page.getByText("チャット履歴を読み込めませんでした。").waitFor();
      await page.getByPlaceholder("指示を入力してください").waitFor();
      await screenshot(page, "ST-HISTORY-009-history-list-failure.png");
    },
  );
}

async function verifyStartFailure() {
  await withPage(
    {
      histories: () => [],
      start: () => ({ status: 500, body: "error" }),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await submitStartInstruction(page, "受付失敗テストです。");
      await page
        .getByText("ユーザ指示を受け付けられませんでした。時間を置いて再度お試しください。")
        .waitFor();
      await page.getByPlaceholder("指示を入力してください").waitFor();
      await screenshot(page, "ST-CHAT-013-start-failure.png");
    },
  );
}

async function verifySseConnectionFailure() {
  await withPage(
    {
      histories: () => [],
      start: () => startResponse("chat-sse-fail", "run-sse-fail", "/api/test-sse/immediate"),
      detail: () => chatDetail("chat-sse-fail", [pendingRun("run-sse-fail", "SSE接続失敗テスト")]),
      sse: () => ({ status: 500, body: "error" }),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await submitStartInstruction(page, "SSE接続失敗テストです。");
      await page.getByText("回答生成中の接続が切れました。再度お試しください。").waitFor();
      await screenshot(page, "ST-CHAT-015-sse-connection-failure.png");
    },
  );
}

async function verifySseMidDisconnect() {
  await withPage(
    {
      histories: () => [],
      start: () => startResponse("chat-sse-mid", "run-sse-mid", "/api/test-sse/mid"),
      detail: () => chatDetail("chat-sse-mid", [pendingRun("run-sse-mid", "SSE途中切断テスト")]),
      sse: () =>
        eventStream([
          { event: "state", data: { run_id: "run-sse-mid", state: "実行中" } },
          { event: "message", data: { run_id: "run-sse-mid", text: "途中の中間メッセージです。" } },
        ]),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await submitStartInstruction(page, "SSE途中切断テストです。");
      await page.getByText("途中の中間メッセージです。").waitFor();
      await page.getByText("回答生成中の接続が切れました。再度お試しください。").waitFor();
      await screenshot(page, "ST-CHAT-016-sse-mid-disconnect.png");
    },
  );
}

async function verifyRichAnswerAndContinuation() {
  let appended = false;
  await withPage(
    {
      histories: () => [history("chat-rich", "検証用: リッチ回答", "完了", "run-rich")],
      start: () => startResponse("chat-rich", "run-rich", "/api/test-sse/rich"),
      detail: () =>
        chatDetail(
          "chat-rich",
          appended
            ? [
                completedRun("run-rich", "リッチ回答テスト", richMarkdown()),
                pendingRun("run-continued", "前回を踏まえて続けてください。"),
              ]
            : [pendingRun("run-rich", "リッチ回答テスト")],
        ),
      append: () => {
        appended = true;
        return startResponse("chat-rich", "run-continued", "/api/test-sse/continued");
      },
      artifact: () => ({ status: 200, body: PNG_1X1, contentType: "image/png" }),
      sse: (path) => {
        if (path.endsWith("/continued")) {
          return eventStream([
            { event: "state", data: { run_id: "run-continued", state: "実行中" } },
            {
              event: "answer",
              data: {
                answer: { markdown: "継続回答です。前回の要点を踏まえました。" },
                run_id: "run-continued",
                state: "完了",
              },
            },
          ]);
        }
        return eventStream([
          { event: "state", data: { run_id: "run-rich", state: "実行中" } },
          { event: "message", data: { run_id: "run-rich", text: "表示用中間メッセージです。" } },
          {
            event: "answer",
            data: {
              answer: { markdown: richMarkdown() },
              run_id: "run-rich",
              state: "完了",
            },
          },
        ]);
      },
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await submitStartInstruction(page, "リッチ回答テストです。");
      await page.getByText("Markdown見出し").waitFor();
      await page.getByAltText("Codex成果物").waitFor();
      await page.getByRole("button", { name: "作業プロセス" }).click();
      await page.getByText("表示用中間メッセージです。").waitFor();
      await screenshot(page, "ST-CHAT-006-sse-state-message.png");
      await screenshot(page, "ST-CHAT-007-rich-answer.png");
      await screenshot(page, "ST-CHAT-010-artifact.png");

      const dangerousScriptExecuted = await page.evaluate(
        () => globalThis.__dConciergeDangerousScript === true,
      );
      if (dangerousScriptExecuted) {
        throw new Error("危険HTML内のscriptが実行されました。");
      }
      if ((await page.locator('a[href^="javascript:"]').count()) > 0) {
        throw new Error("javascript: URLがリンクとして残っています。");
      }
      await screenshot(page, "ST-CHAT-008-dangerous-html-suppressed.png");

      await page.getByPlaceholder("指示を入力してください").fill("前回を踏まえて続けてください。");
      await page.getByLabel("送信").click();
      await page.getByText("継続回答です。前回の要点を踏まえました。").waitFor();
      await screenshot(page, "ST-CHAT-011-continued.png");
    },
  );
}

async function verifyTerminalErrors() {
  await verifyTerminalError({
    chatId: "chat-generation-error",
    instruction: "生成失敗テストです。",
    message: "回答生成に失敗しました。ユーザ指示を見直して再度お試しください。",
    runId: "run-generation-error",
    screenshotName: "ST-CHAT-017-generation-error.png",
    state: "エラー",
  });
  await verifyTerminalError({
    chatId: "chat-validation-error",
    instruction: "検証失敗上限テストです。",
    message: "回答の確認に失敗したため、回答を表示できませんでした。ユーザ指示を具体化して再度お試しください。",
    runId: "run-validation-error",
    screenshotName: "ST-CHAT-018-validation-limit.png",
    state: "エラー",
  });
  await verifyTerminalError({
    chatId: "chat-timeout",
    instruction: "タイムアウトテストです。",
    message: "回答生成が時間内に完了しませんでした。ユーザ指示を絞って再度お試しください。",
    runId: "run-timeout",
    screenshotName: "ST-CHAT-019-timeout.png",
    state: "タイムアウト",
  });
}

async function verifyTerminalError({ chatId, instruction, message, runId, screenshotName, state }) {
  await withPage(
    {
      histories: () => [],
      start: () => startResponse(chatId, runId, `/api/test-sse/${runId}`),
      detail: () => chatDetail(chatId, [pendingRun(runId, instruction)]),
      sse: () =>
        eventStream([
          { event: "state", data: { run_id: runId, state: "実行中" } },
          { event: "message", data: { run_id: runId, text: "終端前の中間メッセージです。" } },
          { event: "error", data: { run_id: runId, state, user_message: message } },
        ]),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await submitStartInstruction(page, instruction);
      await page.getByText(message).waitFor();
      await expectHidden(page, "未検証回答");
      await screenshot(page, screenshotName);
    },
  );
}

async function verifyReferenceAndArtifactFailures() {
  await withPage(
    {
      histories: () => [history("chat-missing-assets", "検証用: 欠損参照成果物", "完了", "run-missing")],
      detail: () =>
        chatDetail("chat-missing-assets", [
          {
            ...completedRun("run-missing", "欠損参照成果物テスト", missingAssetsMarkdown()),
            answer: {
              markdown: missingAssetsMarkdown(),
              references: [
                reference("欠損参照", "/api/references/missing.pdf", 1, 1),
                reference("不正位置参照", "/api/references/invalid-location.pdf", 99, 99),
              ],
            },
          },
        ]),
      reference: (path) =>
        path.endsWith("/invalid-location.pdf")
          ? { status: 200, body: referencePdf, contentType: "application/pdf" }
          : { status: 404, body: "missing" },
      artifact: () => ({ status: 404, body: "missing" }),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await page.getByRole("button", { name: "検証用: 欠損参照成果物" }).click();
      await page.getByText("欠損参照成果物テスト").first().waitFor();
      await page.getByText("一部のCodex成果物を表示できませんでした。").waitFor();
      await screenshot(page, "ST-CHAT-022-artifact-missing.png");
      await screenshot(page, "ST-HISTORY-012-artifact-missing.png");

      await page.getByRole("button", { name: /欠損参照 p\.1/ }).click();
      await page.getByText("参照元を表示できませんでした。").waitFor();
      await screenshot(page, "ST-CHAT-020-reference-missing.png");
      await screenshot(page, "ST-HISTORY-011-reference-missing.png");
      await page.keyboard.press("Escape");

      await page.getByRole("button", { name: /不正位置参照 p\.99/ }).click();
      await page.getByText("参照元の位置情報を表示できませんでした。").waitFor();
      await screenshot(page, "ST-CHAT-021-invalid-reference-location.png");
    },
  );
}

async function verifyHistoryOrderAndContinuation() {
  let appended = false;
  await withPage(
    {
      histories: () => [history("chat-multi", "検証用: 複数run", appended ? "完了" : "完了", "run-second")],
      detail: () =>
        chatDetail(
          "chat-multi",
          appended
            ? [
                completedRun("run-first", "1回目の指示", "1回目の回答"),
                completedRun("run-second", "2回目の指示", "2回目の回答"),
                pendingRun("run-third", "履歴から継続してください。"),
              ]
            : [
                completedRun("run-first", "1回目の指示", "1回目の回答"),
                completedRun("run-second", "2回目の指示", "2回目の回答"),
              ],
        ),
      append: () => {
        appended = true;
        return startResponse("chat-multi", "run-third", "/api/test-sse/history-continued");
      },
      sse: () =>
        eventStream([
          { event: "state", data: { run_id: "run-third", state: "実行中" } },
          {
            event: "answer",
            data: {
              answer: { markdown: "履歴からの継続回答です。" },
              run_id: "run-third",
              state: "完了",
            },
          },
        ]),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await page.getByRole("button", { name: "検証用: 複数run" }).click();
      await page.getByText("1回目の回答").waitFor();
      await page.getByText("2回目の回答").waitFor();
      const firstBox = await page.getByText("1回目の指示").boundingBox();
      const secondBox = await page.getByText("2回目の指示").boundingBox();
      if (!firstBox || !secondBox || firstBox.y >= secondBox.y) {
        throw new Error("複数runの表示順が開始順になっていません。");
      }
      await screenshot(page, "ST-HISTORY-003-multi-run-order.png");

      await page.getByPlaceholder("指示を入力してください").fill("履歴から継続してください。");
      await page.getByLabel("送信").click();
      await page.getByText("履歴からの継続回答です。").waitFor();
      await screenshot(page, "ST-HISTORY-008-history-continuation.png");
    },
  );
}

async function verifyContinuationFailure() {
  await withPage(
    {
      histories: () => [history("chat-append-fail", "検証用: 継続失敗", "完了", "run-completed")],
      detail: () =>
        chatDetail("chat-append-fail", [
          completedRun("run-completed", "保存済み指示", "保存済み回答です。"),
        ]),
      append: () => ({ status: 500, body: "error" }),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await page.getByRole("button", { name: "検証用: 継続失敗" }).click();
      await page.getByText("保存済み回答です。").waitFor();
      await page.getByPlaceholder("指示を入力してください").fill("追加指示です。");
      await page.getByLabel("送信").click();
      await page
        .getByText("ユーザ指示を受け付けられませんでした。時間を置いて再度お試しください。")
        .waitFor();
      await page.getByText("保存済み回答です。").waitFor();
      await screenshot(page, "ST-CHAT-014-append-failure.png");
    },
  );
}

async function verifyHistoryDetailFailure() {
  await withPage(
    {
      histories: () => [
        history("chat-current", "検証用: 表示中", "完了", "run-current"),
        history("chat-detail-fail", "検証用: 詳細失敗", "完了", "run-detail-fail"),
      ],
      detail: (chatId) =>
        chatId === "chat-detail-fail"
          ? { status: 500, body: "error" }
          : chatDetail("chat-current", [completedRun("run-current", "表示中の指示", "表示中の回答")]),
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await page.getByRole("button", { name: "検証用: 表示中" }).click();
      await page.getByText("表示中の回答").waitFor();
      await page.getByRole("button", { name: "検証用: 詳細失敗" }).click();
      await page.getByText("選択したチャットを読み込めませんでした。").waitFor();
      await page.getByText("表示中の回答").waitFor();
      await screenshot(page, "ST-HISTORY-010-detail-failure.png");
    },
  );
}

async function verifyHistorySseSwitchAndReturn() {
  let sseCount = 0;
  await withPage(
    {
      histories: () => [
        history("chat-running", "検証用: 回答中", "実行中", "run-running"),
        history("chat-completed", "検証用: 完了履歴", "完了", "run-completed"),
      ],
      detail: (chatId) =>
        chatId === "chat-running"
          ? chatDetail("chat-running", [
              completedRun("run-before", "完了済み指示", "完了済み回答"),
              {
                intermediate_messages: [{ text: "保存済み中間メッセージです。" }],
                run_id: "run-running",
                state: "実行中",
                user_instruction: "回答中の指示",
              },
            ])
          : chatDetail("chat-completed", [
              completedRun("run-completed", "別履歴の指示", "別履歴の回答"),
            ]),
      sse: async () => {
        sseCount += 1;
        if (sseCount === 1) {
          await delay(800);
          return eventStream([
            { event: "message", data: { run_id: "run-running", text: "切替前の遅延メッセージ" } },
          ]);
        }
        return eventStream([
          { event: "state", data: { run_id: "run-running", state: "実行中" } },
          { event: "message", data: { run_id: "run-running", text: "戻った後の中間メッセージです。" } },
        ]);
      },
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await page.getByRole("button", { name: "検証用: 回答中" }).click();
      await page.getByText("保存済み中間メッセージです。").waitFor();
      await page.getByRole("button", { name: "検証用: 完了履歴" }).click();
      await page.getByText("別履歴の回答").waitFor();
      await page.waitForTimeout(1000);
      await expectHidden(page, "回答生成中の接続が切れました。再度お試しください。");
      await screenshot(page, "ST-HISTORY-013-sse-switch.png");

      await page.getByRole("button", { name: "検証用: 回答中" }).click();
      await page.getByText("保存済み中間メッセージです。").waitFor();
      await page.getByText("戻った後の中間メッセージです。").waitFor();
      await screenshot(page, "ST-HISTORY-014-running-return.png");
    },
  );
}

async function verifyCancelAccepted() {
  let cancelRequested;
  const cancelPromise = new Promise((resolve) => {
    cancelRequested = resolve;
  });
  await withPage(
    {
      histories: () => [],
      start: () => startResponse("chat-cancel", "run-cancel", "/api/test-sse/cancel"),
      detail: () => chatDetail("chat-cancel", [pendingRun("run-cancel", "受付直後キャンセルテスト")]),
      cancel: async () => {
        cancelRequested();
        await delay(900);
        return {
          run_id: "run-cancel",
          state: "キャンセル要求中",
          user_message: "処理をキャンセルしています。",
        };
      },
      sse: async () => {
        await cancelPromise;
        return eventStream([
          {
            event: "canceled",
            data: {
              run_id: "run-cancel",
              state: "キャンセル済み",
              user_message: "処理をキャンセルしました。",
            },
          },
          {
            event: "answer",
            data: {
              answer: { markdown: "遅延回答です。" },
              run_id: "run-cancel",
              state: "完了",
            },
          },
        ]);
      },
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await submitStartInstruction(page, "受付直後キャンセルテストです。");
      await page.getByLabel("キャンセル").click();
      const cancelingButton = page.getByLabel("キャンセル処理中");
      await cancelingButton.waitFor();
      if (!(await cancelingButton.isDisabled())) {
        throw new Error("キャンセル要求中ボタンが無効化されていません。");
      }
      await screenshot(page, "ST-CANCEL-004-canceling-button.png");
      await screenshot(page, "ST-CANCEL-005-cancel-repeat-guard.png");
      await page.getByText("処理をキャンセルしました。").waitFor();
      await expectHidden(page, "遅延回答です。");
      await screenshot(page, "ST-CANCEL-001-accepted-cancel.png");
      await screenshot(page, "ST-CANCEL-008-delayed-answer-ignored.png");
    },
  );
}

async function verifyCancelDuringValidation() {
  await withPage(
    {
      histories: () => [],
      start: () => startResponse("chat-validation-cancel", "run-validation-cancel", "/api/test-sse/validation-cancel"),
      detail: () =>
        chatDetail("chat-validation-cancel", [
          {
            ...pendingRun("run-validation-cancel", "検証中キャンセルテスト"),
            state: "検証中",
          },
        ]),
      cancel: () => ({
        run_id: "run-validation-cancel",
        state: "キャンセル要求中",
        user_message: "処理をキャンセルしています。",
      }),
      sse: async () => {
        await delay(1000);
        return eventStream([
          {
            event: "canceled",
            data: {
              run_id: "run-validation-cancel",
              state: "キャンセル済み",
              user_message: "処理をキャンセルしました。",
            },
          },
        ]);
      },
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await submitStartInstruction(page, "検証中キャンセルテストです。");
      await page.getByText("検証中").waitFor();
      await page.getByLabel("キャンセル").click();
      await page.getByText("処理をキャンセルしました。").waitFor();
      await screenshot(page, "ST-CANCEL-003-validation-cancel.png");
    },
  );
}

async function verifyCancelFailure() {
  await withPage(
    {
      histories: () => [],
      start: () => startResponse("chat-cancel-fail", "run-cancel-fail", "/api/test-sse/cancel-fail"),
      detail: () =>
        chatDetail("chat-cancel-fail", [
          {
            ...pendingRun("run-cancel-fail", "キャンセル失敗テスト"),
            state: "実行中",
          },
        ]),
      cancel: () => ({ status: 500, body: "error" }),
      sse: async () => {
        await delay(1200);
        return eventStream([]);
      },
    },
    async (page) => {
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
      await submitStartInstruction(page, "キャンセル失敗テストです。");
      await page.getByLabel("キャンセル").click();
      await page.getByText("キャンセルできませんでした。処理状態を確認してください。").waitFor();
      await page.getByLabel("キャンセル").waitFor();
      await screenshot(page, "ST-CANCEL-007-cancel-failure.png");
    },
  );
}

async function withPage(router, action) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.route(/^http:\/\/127\.0\.0\.1:5173\/api\//, (route) =>
    handleApiRoute(route, router),
  );
  try {
    await action(page);
  } finally {
    await page.close();
  }
}

async function handleApiRoute(route, router) {
  const request = route.request();
  const path = new URL(request.url()).pathname;

  let response;
  if (path === "/api/app-config") {
    response = router.appConfig?.() ?? {
      input_suggestions: ["資料の要点を整理してください。"],
      welcome_message: "D-Conciergeへようこそ。調査したい内容を入力してください。",
    };
  } else if (path === "/api/chat-histories") {
    response = router.histories?.() ?? [];
  } else if (path === "/api/chats/start") {
    response = router.start?.(safePostJson(request)) ?? {
      status: 500,
      body: "start route is not configured",
    };
  } else if (/^\/api\/chats\/[^/]+\/runs\/[^/]+\/sse$/.test(path) || path.startsWith("/api/test-sse/")) {
    response = await router.sse?.(path);
  } else if (/^\/api\/chats\/[^/]+\/runs\/[^/]+\/cancel$/.test(path)) {
    response = await router.cancel?.(path);
  } else if (/^\/api\/chats\/[^/]+\/runs$/.test(path)) {
    const chatId = path.split("/")[3];
    response = router.append?.(chatId, safePostJson(request)) ?? {
      status: 500,
      body: "append route is not configured",
    };
  } else if (/^\/api\/chats\/[^/]+$/.test(path)) {
    const chatId = path.split("/")[3];
    response = router.detail?.(chatId) ?? chatDetail(chatId, []);
  } else if (path.startsWith("/api/references/")) {
    response = router.reference?.(path) ?? { status: 404, body: "reference route is not configured" };
  } else if (path.startsWith("/api/artifacts/")) {
    response = router.artifact?.(path) ?? { status: 404, body: "artifact route is not configured" };
  } else {
    response = { status: 404, body: `unknown route: ${path}` };
  }

  await fulfill(route, response);
}

async function fulfill(route, response) {
  const status = response?.status ?? 200;
  const contentType = response?.contentType ?? "application/json";
  const body = response?.body ?? response;
  if (Buffer.isBuffer(body)) {
    await route.fulfill({ body, contentType, status });
    return;
  }
  if (contentType === "application/json" && typeof body !== "string") {
    await route.fulfill({
      body: JSON.stringify(body),
      contentType,
      status,
    });
    return;
  }
  await route.fulfill({ body: String(body), contentType, status });
}

function eventStream(events) {
  return {
    body: events
      .map((event) => `event: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`)
      .join(""),
    contentType: "text/event-stream",
  };
}

function safePostJson(request) {
  const body = request.postData();
  if (!body) {
    return {};
  }
  return JSON.parse(body);
}

async function submitStartInstruction(page, text) {
  await page.getByPlaceholder("指示を入力してください").fill(text);
  await page.getByLabel("送信").click();
}

async function screenshot(page, name) {
  await page.screenshot({ path: `${EVIDENCE_DIR}/${name}`, fullPage: true });
}

async function expectHidden(page, text) {
  if ((await page.getByText(text).count()) > 0) {
    throw new Error(`表示されない想定の文字列が表示されています: ${text}`);
  }
}

function startResponse(chatId, runId, sseUrl) {
  return {
    chat_id: chatId,
    run_id: runId,
    sse_url: sseUrl,
    state: "受付",
  };
}

function history(chatId, title, latestState, latestRunId) {
  return {
    chat_id: chatId,
    latest_run_id: latestRunId,
    latest_state: latestState,
    title,
    updated_at: "2026-05-09T13:00:00+09:00",
  };
}

function chatDetail(chatId, runs) {
  return {
    chat_id: chatId,
    runs,
    title: "検証用チャット",
  };
}

function pendingRun(runId, userInstruction) {
  return {
    intermediate_messages: [],
    run_id: runId,
    state: "受付",
    user_instruction: userInstruction,
  };
}

function completedRun(runId, userInstruction, markdown) {
  return {
    answer: {
      markdown,
      references: [],
    },
    intermediate_messages: [],
    run_id: runId,
    state: "完了",
    user_instruction: userInstruction,
  };
}

function reference(label, url, pageStart, pageEnd) {
  return {
    label,
    locator: { page_end: pageEnd, page_start: pageStart },
    source_type: "pdf",
    url,
  };
}

function richMarkdown() {
  return `# Markdown見出し

- 箇条書き

| 列 | 値 |
| --- | --- |
| 確認 | OK |

\`\`\`ts
const ok = true;
\`\`\`

\`\`\`mermaid
graph TD;A[開始]-->B[完了];
\`\`\`

<span>許可HTML</span>

![Codex成果物](/api/artifacts/rich.png)

<script>globalThis.__dConciergeDangerousScript = true;</script>
<a href="javascript:alert('x')">危険リンク</a>`;
}

function missingAssetsMarkdown() {
  return `欠損参照成果物テスト

![欠損成果物](/api/artifacts/missing.png)`;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
