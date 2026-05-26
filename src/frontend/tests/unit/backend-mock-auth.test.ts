import { describe, expect, it, vi } from "vitest";

describe("backend mock auth runtime", () => {
  it("観点：初回デモセッション。確認：同時初期表示相当の複数回確認では同じデモセッションを返し、ログアウト後は再発行しない。", async () => {
    vi.resetModules();
    const runtime = await import("../../backend_mock/server/runtime");

    const firstSession = runtime.issueDefaultSession();
    const secondSession = runtime.issueDefaultSession();

    expect(firstSession?.response.user).toEqual({
      user_id: "demo-user",
      user_name: "デモユーザ",
    });
    expect(secondSession?.sessionId).toBe(firstSession?.sessionId);

    runtime.logoutStubSession(firstSession?.sessionId);

    expect(runtime.issueDefaultSession()).toBeNull();
  });
});
