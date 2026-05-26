import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  changePassword,
  changeUserName,
  deleteAccount,
  getCurrentUser,
  login,
  logout,
  registerAccount,
} from "@/features/account/api/accountApi";

const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = String(input);

  if (url === "/api/auth/me") {
    return jsonResponse({ user: { user_id: "demo-user", user_name: "デモユーザ" } });
  }

  if (url === "/api/auth/login") {
    return jsonResponse({ user: { user_id: "login-user", user_name: "ログインユーザ" } });
  }

  if (url === "/api/auth/register") {
    return jsonResponse({ user: { user_id: "new-user", user_name: "新規ユーザ" } });
  }

  if (url === "/api/account/name") {
    return jsonResponse({ user: { user_id: "demo-user", user_name: "変更後ユーザ" } });
  }

  if (url === "/api/account/password" || url === "/api/auth/logout") {
    return Promise.resolve(new Response(null, { status: 204 }));
  }

  if (url === "/api/account" && init?.method === "DELETE") {
    return jsonResponse({ account_state: "deleting" }, 202);
  }

  return Promise.resolve(new Response("not found", { status: 404 }));
});

describe("accountApi", () => {
  beforeEach(() => {
    fetchMock.mockClear();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("観点：認証状態取得。確認：ログイン中ユーザを画面モデルへ変換する。", async () => {
    await expect(getCurrentUser()).resolves.toEqual({
      userId: "demo-user",
      userName: "デモユーザ",
    });
  });

  it("観点：ログイン・登録。確認：入力値をAPI項目名で送信し、ユーザ情報を返す。", async () => {
    await expect(login({ userId: "login-user", password: "password" })).resolves.toEqual({
      userId: "login-user",
      userName: "ログインユーザ",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        body: JSON.stringify({ user_id: "login-user", password: "password" }),
        method: "POST",
      }),
    );

    await expect(
      registerAccount({
        userId: "new-user",
        userName: "新規ユーザ",
        password: "password",
        passwordConfirmation: "password",
      }),
    ).resolves.toEqual({
      userId: "new-user",
      userName: "新規ユーザ",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/register",
      expect.objectContaining({
        body: JSON.stringify({
          user_id: "new-user",
          user_name: "新規ユーザ",
          password: "password",
          password_confirmation: "password",
        }),
        method: "POST",
      }),
    );
  });

  it("観点：アカウント変更。確認：ユーザ名変更、パスワード変更、ログアウト、削除の応答を扱う。", async () => {
    await expect(changeUserName("変更後ユーザ")).resolves.toEqual({
      userId: "demo-user",
      userName: "変更後ユーザ",
    });
    await expect(
      changePassword({
        currentPassword: "password",
        newPassword: "new-password",
        newPasswordConfirmation: "new-password",
      }),
    ).resolves.toBeUndefined();
    await expect(logout()).resolves.toBeUndefined();
    await expect(deleteAccount()).resolves.toEqual({ accountState: "deleting" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/account/name",
      expect.objectContaining({
        body: JSON.stringify({ user_name: "変更後ユーザ" }),
        method: "PATCH",
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/account/password",
      expect.objectContaining({
        body: JSON.stringify({
          current_password: "password",
          new_password: "new-password",
          new_password_confirmation: "new-password",
        }),
        method: "PATCH",
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/account",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("観点：API異常系。確認：HTTPエラー、401、field_errorsを例外へ保持する。", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: "validation_error",
          field_errors: {
            password: "パスワードが正しくありません。",
            user_id: "ユーザIDが存在しません。",
          },
          message: "入力内容を確認してください。",
        }),
        { headers: { "Content-Type": "application/json" }, status: 400 },
      ),
    );

    await expect(login({ userId: "missing-user", password: "bad" })).rejects.toMatchObject({
      error: "validation_error",
      fieldErrors: {
        password: "パスワードが正しくありません。",
        userId: "ユーザIDが存在しません。",
      },
      message: "入力内容を確認してください。",
      status: 400,
    });

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: "unauthorized", message: "ログインしてください。" }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      }),
    );

    await expect(getCurrentUser()).rejects.toMatchObject({
      error: "unauthorized",
      message: "ログインしてください。",
      status: 401,
    });
  });
});

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      headers: { "Content-Type": "application/json" },
      status,
    }),
  );
}
