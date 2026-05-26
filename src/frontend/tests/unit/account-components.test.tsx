import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Providers } from "@/app/providers";
import { AccountSettingsDialog } from "@/features/account/components/AccountSettingsDialog";
import { LoginPage } from "@/features/account/components/LoginPage";
import { RegisterPage } from "@/features/account/components/RegisterPage";
import type { AccountUser } from "@/features/account/model/types";

const accountApiMocks = vi.hoisted(() => ({
  changePassword: vi.fn(),
  changeUserName: vi.fn(),
  deleteAccount: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  registerAccount: vi.fn(),
}));

vi.mock("@/features/account/api/accountApi", () => ({
  changePassword: accountApiMocks.changePassword,
  changeUserName: accountApiMocks.changeUserName,
  deleteAccount: accountApiMocks.deleteAccount,
  isAccountApiError: (error: unknown) =>
    error !== null && typeof error === "object" && "status" in error,
  login: accountApiMocks.login,
  logout: accountApiMocks.logout,
  registerAccount: accountApiMocks.registerAccount,
}));

describe("account components", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    accountApiMocks.login.mockResolvedValue(user("login-user", "ログインユーザ"));
    accountApiMocks.registerAccount.mockResolvedValue(user("new-user", "新規ユーザ"));
    accountApiMocks.changeUserName.mockResolvedValue(user("demo-user", "変更後ユーザ"));
    accountApiMocks.changePassword.mockResolvedValue(undefined);
    accountApiMocks.logout.mockResolvedValue(undefined);
    accountApiMocks.deleteAccount.mockResolvedValue({ accountState: "deleting" });
  });

  it("観点：ログイン画面。確認：ロゴ、入力属性、パスワード表示切替、ボタン送信、登録リンクを表示する。", async () => {
    const testUser = userEvent.setup();
    const authenticated = vi.fn();
    render(
      <Providers>
        <MemoryRouter initialEntries={["/login"]}>
          <LoginPage onAuthenticated={authenticated} />
        </MemoryRouter>
      </Providers>,
    );

    expect(screen.getByText("D-Concierge")).toBeInTheDocument();
    expect(screen.getByLabelText("ユーザID")).toHaveAttribute("autoComplete", "username");
    expect(screen.getByLabelText("ユーザID")).toHaveAttribute("maxLength", "30");
    expect(screen.getByLabelText("ユーザID")).not.toHaveAttribute("placeholder");
    expect(screen.getByLabelText("パスワード")).toHaveAttribute("autoComplete", "current-password");
    expect(screen.getByLabelText("パスワード")).toHaveAttribute("maxLength", "30");
    expect(screen.getByLabelText("パスワード")).not.toHaveAttribute("placeholder");
    expect(screen.getByLabelText("パスワード")).toHaveClass("dc-password-input");
    expect(screen.getByRole("button", { name: "ログイン" })).toHaveClass(
      "bg-linear-to-b",
      "from-[var(--dc-primary)]",
      "to-[var(--dc-primary-strong)]",
      "shadow-xs",
    );
    expect(screen.getByRole("button", { name: "ログイン" })).not.toHaveClass(
      "shadow-[0_10px_18px_var(--dc-shadow-primary)]",
    );

    fireEvent.keyDown(screen.getByLabelText("パスワード"), { key: "Enter" });
    expect(accountApiMocks.login).not.toHaveBeenCalled();

    await testUser.click(screen.getByRole("button", { name: "パスワードを表示" }));
    expect(screen.getByLabelText("パスワード")).toHaveAttribute("type", "text");

    await testUser.type(screen.getByLabelText("ユーザID"), "login-user");
    await testUser.type(screen.getByLabelText("パスワード"), "password");
    await testUser.click(screen.getByRole("button", { name: "ログイン" }));

    await waitFor(() =>
      expect(authenticated).toHaveBeenCalledWith(user("login-user", "ログインユーザ")),
    );
    expect(screen.getByRole("link", { name: "アカウント登録" })).toHaveAttribute(
      "href",
      "/register",
    );
  });

  it("観点：登録画面。確認：登録項目、入力欄ごとのパスワード表示切替、ログインリンク、登録成功を扱う。", async () => {
    const testUser = userEvent.setup();
    const authenticated = vi.fn();
    render(
      <Providers>
        <MemoryRouter initialEntries={["/register"]}>
          <RegisterPage onAuthenticated={authenticated} />
        </MemoryRouter>
      </Providers>,
    );

    expect(screen.getByLabelText("ユーザ名")).toHaveAttribute("autoComplete", "name");
    expect(screen.getByLabelText("ユーザID")).toHaveAttribute(
      "placeholder",
      '半角英数字、"-"、"_" のみ使用可',
    );
    expect(screen.getByLabelText("ユーザ名")).toHaveAttribute(
      "placeholder",
      "任意の文字列を使用可",
    );
    expect(screen.getByLabelText("パスワード")).toHaveAttribute("autoComplete", "new-password");
    expect(screen.getByLabelText("パスワード")).toHaveAttribute(
      "placeholder",
      "5文字以上、半角英数字と記号を使用可",
    );
    expect(screen.getByLabelText("パスワード確認")).toHaveAttribute("autoComplete", "new-password");
    expect(screen.getByLabelText("パスワード確認")).toHaveAttribute(
      "placeholder",
      "同じパスワードを再入力",
    );

    await testUser.click(screen.getByRole("button", { name: "パスワードを表示" }));
    expect(screen.getByLabelText("パスワード")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("パスワード確認")).toHaveAttribute("type", "password");
    await testUser.click(screen.getByRole("button", { name: "パスワード確認を表示" }));
    expect(screen.getByLabelText("パスワード")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("パスワード確認")).toHaveAttribute("type", "text");
    await testUser.click(screen.getByRole("button", { name: "パスワードを非表示" }));
    expect(screen.getByLabelText("パスワード")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("パスワード確認")).toHaveAttribute("type", "text");

    await testUser.type(screen.getByLabelText("ユーザID"), "new-user");
    await testUser.type(screen.getByLabelText("ユーザ名"), "新規ユーザ");
    await testUser.type(screen.getByLabelText("パスワード"), "password");
    await testUser.type(screen.getByLabelText("パスワード確認"), "password");
    await testUser.click(screen.getByRole("button", { name: "登録" }));

    await waitFor(() => expect(authenticated).toHaveBeenCalledWith(user("new-user", "新規ユーザ")));
    expect(screen.getByRole("link", { name: "ログイン画面へ戻る" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("観点：フォーム異常系。確認：APIのfield_errorsを入力欄近くに表示し、送信中はボタンを無効化する。", async () => {
    const testUser = userEvent.setup();
    accountApiMocks.login.mockRejectedValueOnce({
      fieldErrors: {
        password: "パスワードが正しくありません。",
        userId: "ユーザIDが存在しません。",
      },
      message: "入力内容を確認してください。",
      status: 400,
    });

    render(
      <Providers>
        <MemoryRouter initialEntries={["/login"]}>
          <LoginPage onAuthenticated={vi.fn()} />
        </MemoryRouter>
      </Providers>,
    );

    await testUser.click(screen.getByRole("button", { name: "ログイン" }));
    expect(await screen.findByText("ユーザIDが存在しません。")).toBeInTheDocument();
    expect(screen.getByText("パスワードが正しくありません。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ログイン" })).toBeEnabled();
  });

  it("観点：設定ダイアログ。確認：一覧、ユーザ名変更、パスワード変更、戻る操作を扱う。", async () => {
    const testUser = userEvent.setup();
    const userChanged = vi.fn();
    renderSettings({ onUserChange: userChanged });

    expect(screen.getByRole("dialog", { name: "設定" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ユーザ名変更" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "パスワード変更" })).toBeInTheDocument();

    await testUser.click(screen.getByRole("button", { name: "ユーザ名変更" }));
    expect(screen.getByLabelText("新しいユーザ名")).not.toHaveAttribute("autoComplete");
    expect(screen.getByLabelText("新しいユーザ名")).toHaveAttribute(
      "placeholder",
      "任意の文字列を使用可",
    );
    await testUser.type(screen.getByLabelText("新しいユーザ名"), "変更後ユーザ");
    await testUser.click(screen.getByRole("button", { name: "変更する" }));
    await waitFor(() =>
      expect(userChanged).toHaveBeenCalledWith(user("demo-user", "変更後ユーザ")),
    );
    expect(screen.getByRole("button", { name: "ユーザ名変更" })).toBeInTheDocument();

    await testUser.click(screen.getByRole("button", { name: "パスワード変更" }));
    expect(screen.getByLabelText("現在のパスワード")).not.toHaveAttribute("placeholder");
    expect(screen.getByLabelText("新しいパスワード")).toHaveAttribute(
      "placeholder",
      "5文字以上、半角英数字と記号を使用可",
    );
    expect(screen.getByLabelText("新しいパスワード確認")).toHaveAttribute(
      "placeholder",
      "同じパスワードを再入力",
    );
    await testUser.click(screen.getByRole("button", { name: "現在のパスワードを表示" }));
    expect(screen.getByLabelText("現在のパスワード")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("新しいパスワード")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("新しいパスワード確認")).toHaveAttribute("type", "password");
    await testUser.click(screen.getByRole("button", { name: "新しいパスワードを表示" }));
    expect(screen.getByLabelText("現在のパスワード")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("新しいパスワード")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("新しいパスワード確認")).toHaveAttribute("type", "password");
    await testUser.click(screen.getByRole("button", { name: "戻る" }));
    await testUser.click(screen.getByRole("button", { name: "パスワード変更" }));
    expect(screen.getByLabelText("現在のパスワード")).toHaveValue("");
  });

  it("観点：設定ダイアログの破壊的操作。確認：ログアウトとアカウント削除の確認文言、キャンセル、成功通知を扱う。", async () => {
    const testUser = userEvent.setup();
    const loggedOut = vi.fn();
    renderSettings({ onLoggedOut: loggedOut });

    await testUser.click(screen.getByRole("button", { name: "ログアウト" }));
    expect(screen.getByRole("dialog", { name: "ログアウトしますか？" })).toBeInTheDocument();
    await testUser.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(accountApiMocks.logout).not.toHaveBeenCalled();

    await testUser.click(screen.getByRole("button", { name: "ログアウト" }));
    await testUser.click(screen.getByRole("button", { name: "ログアウト" }));
    await waitFor(() => expect(loggedOut).toHaveBeenCalledTimes(1));

    await testUser.click(screen.getByRole("button", { name: "アカウント削除" }));
    expect(
      screen.getByRole("dialog", { name: "アカウントを完全に削除しますか？" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "この操作は取り消せません。アカウントに紐づけられている全てのデータが完全に削除されます。",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "削除する" })).toHaveClass(
      "bg-[var(--dc-danger)]",
      "text-white",
      "shadow-xs",
    );
    expect(screen.getByRole("button", { name: "削除する" })).not.toHaveClass("bg-linear-to-b");
    expect(screen.getByRole("button", { name: "削除する" })).not.toHaveClass(
      "shadow-[0_8px_18px_rgba(211,63,73,0.22)]",
    );
    await testUser.click(screen.getByRole("button", { name: "削除する" }));
    await waitFor(() => expect(accountApiMocks.deleteAccount).toHaveBeenCalledTimes(1));
  });
});

function renderSettings({
  onLoggedOut = vi.fn(),
  onUserChange = vi.fn(),
}: {
  onLoggedOut?: () => void;
  onUserChange?: (nextUser: AccountUser) => void;
}) {
  return render(
    <Providers>
      <AccountSettingsDialog
        open
        user={user("demo-user", "デモユーザ")}
        onLoggedOut={onLoggedOut}
        onOpenChange={vi.fn()}
        onUserChange={onUserChange}
      />
    </Providers>,
  );
}

function user(userId: string, userName: string): AccountUser {
  return { userId, userName };
}
