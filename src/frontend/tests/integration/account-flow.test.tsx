import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/app/App";

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(() => Promise.resolve({ svg: "<svg />" })),
  },
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: vi.fn(),
}));

vi.mock("react-zoom-pan-pinch", () => ({
  TransformComponent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TransformWrapper: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  useControls: () => ({
    setTransform: vi.fn(),
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
  }),
}));

type MockUser = {
  userId: string;
  userName: string;
};

let currentUser: MockUser | null = null;
let chatHistoriesShouldReturnUnauthorized = false;
let userNameChangeShouldFail = false;
let passwordChangeShouldFail = false;
let logoutShouldFail = false;
let accountDeleteShouldFail = false;
let accountOperationShouldReturnUnauthorized = false;

const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = String(input);

  if (url === "/api/auth/me") {
    if (!currentUser) {
      return jsonResponse({ error: "unauthorized", message: "ログインしてください。" }, 401);
    }
    return jsonResponse({ user: toUserResponse(currentUser) });
  }

  if (url === "/api/auth/login" && init?.method === "POST") {
    currentUser = { userId: "switch-user", userName: "切替ユーザ" };
    return jsonResponse({ user: toUserResponse(currentUser) });
  }

  if (url === "/api/auth/register" && init?.method === "POST") {
    currentUser = { userId: "new-user", userName: "新規ユーザ" };
    return jsonResponse({ user: toUserResponse(currentUser) });
  }

  if (url === "/api/app-config") {
    return jsonResponse({ welcome_message: "ようこそ", input_suggestions: [] });
  }

  if (url === "/api/chat-histories") {
    if (chatHistoriesShouldReturnUnauthorized) {
      return jsonResponse({ error: "unauthorized", message: "ログインしてください。" }, 401);
    }
    if (currentUser?.userId === "demo-user") {
      return jsonResponse([
        {
          chat_id: "chat-demo",
          latest_run_id: "run-demo",
          latest_state: "completed",
          title: "デモ履歴",
          updated_at: "2026-05-09T10:00:00+09:00",
        },
      ]);
    }
    return jsonResponse([]);
  }

  if (url === "/api/account/name" && init?.method === "PATCH") {
    if (accountOperationShouldReturnUnauthorized) {
      currentUser = null;
      return jsonResponse({ error: "unauthorized", message: "ログインしてください。" }, 401);
    }
    if (userNameChangeShouldFail) {
      return jsonResponse(
        { error: "system_error", message: "ユーザ名を変更できませんでした。" },
        500,
      );
    }
    currentUser = { userId: "demo-user", userName: "変更後ユーザ" };
    return jsonResponse({ user: toUserResponse(currentUser) });
  }

  if (url === "/api/account/password" && init?.method === "PATCH") {
    if (passwordChangeShouldFail) {
      return jsonResponse(
        { error: "system_error", message: "パスワードを変更できませんでした。" },
        500,
      );
    }
    return jsonResponse({}, 204);
  }

  if (url === "/api/auth/logout" && init?.method === "POST") {
    if (logoutShouldFail) {
      return jsonResponse(
        { error: "system_error", message: "ログアウトできませんでした。" },
        500,
      );
    }
    currentUser = null;
    return jsonResponse({}, 204);
  }

  if (url === "/api/account" && init?.method === "DELETE") {
    if (accountDeleteShouldFail) {
      return jsonResponse(
        { error: "system_error", message: "アカウントを削除できませんでした。" },
        500,
      );
    }
    currentUser = null;
    return jsonResponse({ account_state: "deleting" }, 202);
  }

  if (url === "/api/chats/chat-demo") {
    return jsonResponse({
      chat_id: "chat-demo",
      runs: [
        {
          answer: { blocks: [{ markdown: "デモ回答" }] },
          run_id: "run-demo",
          state: "completed",
          user_instruction: "デモ依頼",
        },
      ],
      title: "デモ履歴",
    });
  }

  return jsonResponse({ error: "not_found", message: "not found" }, 404);
});

describe("account flow integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
    currentUser = { userId: "demo-user", userName: "デモユーザ" };
    chatHistoriesShouldReturnUnauthorized = false;
    userNameChangeShouldFail = false;
    passwordChangeShouldFail = false;
    logoutShouldFail = false;
    accountDeleteShouldFail = false;
    accountOperationShouldReturnUnauthorized = false;
    window.history.pushState({}, "", "/");
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1280,
      writable: true,
    });
  });

  it("観点：認証済み初期表示。確認：現在ユーザとユーザ別チャット履歴を読み込んでメイン画面を表示する。", async () => {
    render(<App />);

    expect(await screen.findByText("デモユーザ")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "デモ履歴" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("観点：未ログインの保護画面。確認：現在表示を破棄してログイン画面へ遷移する。", async () => {
    currentUser = null;

    render(<App />);

    expect(await screen.findByRole("heading", { name: "ログイン" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });

  it("観点：認証画面の直接表示。確認：ログイン済みでもログイン画面と登録画面を表示できる。", async () => {
    window.history.pushState({}, "", "/login");
    const { unmount } = render(<App />);

    expect(await screen.findByRole("heading", { name: "ログイン" })).toBeInTheDocument();
    unmount();

    window.history.pushState({}, "", "/register");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "アカウント登録" })).toBeInTheDocument();
  });

  it("観点：ログイン切替。確認：別ユーザでログイン成功後、表示状態を読み直してメイン画面へ遷移する。", async () => {
    const testUser = userEvent.setup();
    window.history.pushState({}, "", "/login");
    render(<App />);

    await testUser.type(await screen.findByLabelText("ユーザID"), "switch-user");
    await testUser.type(screen.getByLabelText("パスワード"), "password");
    await testUser.click(screen.getByRole("button", { name: "ログイン" }));

    expect(await screen.findByText("切替ユーザ")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "デモ履歴" })).not.toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("観点：登録切替。確認：登録成功後、新規ユーザでログインして履歴なしの開始画面を表示する。", async () => {
    const testUser = userEvent.setup();
    window.history.pushState({}, "", "/register");
    render(<App />);

    await testUser.type(await screen.findByLabelText("ユーザID"), "new-user");
    await testUser.type(screen.getByLabelText("ユーザ名"), "新規ユーザ");
    await testUser.type(screen.getByLabelText("パスワード"), "password");
    await testUser.type(screen.getByLabelText("パスワード確認"), "password");
    await testUser.click(screen.getByRole("button", { name: "登録" }));

    expect(await screen.findByText("新規ユーザ")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "デモ履歴" })).not.toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("観点：保護APIの401。確認：どの画面からでもログイン画面へ遷移する。", async () => {
    chatHistoriesShouldReturnUnauthorized = true;

    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
    expect(screen.getByRole("heading", { name: "ログイン" })).toBeInTheDocument();
  });

  it("観点：設定API失敗。確認：ユーザ名、パスワード、ログアウト、削除失敗を設定画面へ表示する。", async () => {
    const testUser = userEvent.setup();
    render(<App />);

    await testUser.click(await screen.findByLabelText("設定"));

    userNameChangeShouldFail = true;
    await testUser.click(screen.getByRole("button", { name: /ユーザ名/ }));
    await testUser.clear(screen.getByLabelText("新しいユーザ名"));
    await testUser.type(screen.getByLabelText("新しいユーザ名"), "変更後ユーザ");
    await testUser.click(screen.getByRole("button", { name: "変更する" }));
    expect(await screen.findByText("ユーザ名を変更できませんでした。")).toBeInTheDocument();
    expect(screen.getByText("デモユーザ")).toBeInTheDocument();
    userNameChangeShouldFail = false;

    await testUser.click(screen.getByRole("button", { name: "戻る" }));
    passwordChangeShouldFail = true;
    await testUser.click(screen.getByRole("button", { name: "パスワード変更" }));
    await testUser.type(screen.getByLabelText("現在のパスワード"), "password");
    await testUser.type(screen.getByLabelText("新しいパスワード"), "new-password");
    await testUser.type(screen.getByLabelText("新しいパスワード確認"), "new-password");
    await testUser.click(screen.getByRole("button", { name: "変更する" }));
    expect(await screen.findByText("パスワードを変更できませんでした。")).toBeInTheDocument();
    passwordChangeShouldFail = false;

    await testUser.click(screen.getByRole("button", { name: "戻る" }));
    logoutShouldFail = true;
    await testUser.click(screen.getByRole("button", { name: "ログアウト" }));
    await testUser.click(screen.getByRole("button", { name: "ログアウト" }));
    expect(await screen.findByText("ログアウトできませんでした。")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "ログアウトしますか？" })).toBeInTheDocument();
    logoutShouldFail = false;

    await testUser.click(screen.getByRole("button", { name: "キャンセル" }));
    accountDeleteShouldFail = true;
    await testUser.click(screen.getByRole("button", { name: "アカウント削除" }));
    await testUser.click(screen.getByRole("button", { name: "削除する" }));
    expect(await screen.findByText("アカウントを削除できませんでした。")).toBeInTheDocument();
    expect(
      screen.getByRole("dialog", { name: "アカウントを完全に削除しますか？" }),
    ).toBeInTheDocument();
  });

  it("観点：設定操作中のセッション切れ。確認：設定操作が401になった場合はログイン画面へ遷移する。", async () => {
    const testUser = userEvent.setup();
    render(<App />);

    await testUser.click(await screen.findByLabelText("設定"));
    accountOperationShouldReturnUnauthorized = true;
    await testUser.click(screen.getByRole("button", { name: /ユーザ名/ }));
    await testUser.clear(screen.getByLabelText("新しいユーザ名"));
    await testUser.type(screen.getByLabelText("新しいユーザ名"), "変更後ユーザ");
    await testUser.click(screen.getByRole("button", { name: "変更する" }));

    expect(await screen.findByRole("heading", { name: "ログイン" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });
});

function toUserResponse(user: MockUser) {
  return {
    user_id: user.userId,
    user_name: user.userName,
  };
}

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      headers: { "Content-Type": "application/json" },
      status,
    }),
  );
}
