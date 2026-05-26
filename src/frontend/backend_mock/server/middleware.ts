import { createReadStream, existsSync } from "node:fs";
import { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import type { Connect } from "vite";

import type {
  ChangePasswordRequest,
  LoginRequest,
  RegisterAccountRequest,
} from "../../src/features/account/model/types";
import { artifactManifest } from "../data/artifactManifest";
import {
  acceptStubContinuedRun,
  acceptStubStartChat,
  applyStubSseEvent,
  cancelStubRun,
  changeStubPassword,
  changeStubUserName,
  createStubCanceledEvent,
  deleteStubAccount,
  deleteStubChat,
  getAuthenticatedUser,
  getStubAppConfig,
  getStubChatDetail,
  isStubRunCancelRequested,
  issueDefaultSession,
  listStubChatHistories,
  listStubSseEvents,
  loginStubAccount,
  logoutStubSession,
  registerStubAccount,
} from "./runtime";

const SSE_EVENT_DELAY_MS = 900;
const CANCEL_COMPLETION_DELAY_MS = 1800;
const SESSION_COOKIE_NAME = "d_concierge_session";
const SESSION_COOKIE_MAX_AGE_SECONDS = 34560000;

type UserInstructionBody = {
  user_instruction?: unknown;
};

type UserNameBody = {
  user_name?: unknown;
};

type ValidationErrorPayload = {
  error: "validation_error";
  field_errors: Record<string, string>;
  message: string;
};

export function createBackendMockMiddleware(mockRootDir: string): Connect.NextHandleFunction {
  return async (req, res, next) => {
    const method = req.method ?? "GET";
    const pathname = new URL(req.url ?? "/", "http://localhost").pathname;
    const sessionId = readSessionId(req);

    try {
      if (method === "GET" && pathname === "/api/auth/me") {
        const currentUser = getAuthenticatedUser(sessionId);
        if (currentUser) {
          sendJson(res, 200, currentUser);
          return;
        }

        const defaultSession = issueDefaultSession();
        if (defaultSession) {
          setSessionCookie(res, defaultSession.sessionId);
          sendJson(res, 200, defaultSession.response);
          return;
        }

        sendUnauthorized(res);
        return;
      }

      if (method === "POST" && pathname === "/api/auth/register") {
        const body = await readJsonBody<RegisterAccountRequestBody>(req);
        const registered = registerStubAccount(toRegisterRequest(body), sessionId);
        setSessionCookie(res, registered.sessionId);
        sendJson(res, 200, registered.response);
        return;
      }

      if (method === "POST" && pathname === "/api/auth/login") {
        const body = await readJsonBody<LoginRequestBody>(req);
        const loggedIn = loginStubAccount(toLoginRequest(body), sessionId);
        setSessionCookie(res, loggedIn.sessionId);
        sendJson(res, 200, loggedIn.response);
        return;
      }

      const currentUser = getAuthenticatedUser(sessionId);
      if (pathname.startsWith("/api/") && !currentUser) {
        sendUnauthorized(res);
        return;
      }

      const userId = currentUser?.user.user_id;

      if (method === "POST" && pathname === "/api/auth/logout") {
        logoutStubSession(sessionId);
        clearSessionCookie(res);
        sendNoContent(res);
        return;
      }

      if (method === "PATCH" && pathname === "/api/account/name") {
        const body = await readJsonBody<UserNameBody>(req);
        sendJson(res, 200, changeStubUserName(sessionId, readString(body.user_name)));
        return;
      }

      if (method === "PATCH" && pathname === "/api/account/password") {
        const body = await readJsonBody<ChangePasswordRequestBody>(req);
        changeStubPassword(sessionId, toChangePasswordRequest(body));
        sendNoContent(res);
        return;
      }

      if (method === "DELETE" && pathname === "/api/account") {
        const response = deleteStubAccount(sessionId);
        clearSessionCookie(res);
        sendJson(res, 202, response);
        return;
      }

      if (!userId) {
        next();
        return;
      }

      if (method === "GET" && pathname === "/api/app-config") {
        sendJson(res, 200, getStubAppConfig());
        return;
      }

      if (method === "GET" && pathname === "/api/chat-histories") {
        sendJson(res, 200, listStubChatHistories(userId));
        return;
      }

      if (method === "POST" && pathname === "/api/chats/start") {
        const body = await readJsonBody<UserInstructionBody>(req);
        const accepted = acceptStubStartChat(userId, readUserInstruction(body));
        sendJson(res, 202, accepted.response);
        return;
      }

      const continuedRunMatch = pathname.match(/^\/api\/chats\/([^/]+)\/runs$/);
      if (method === "POST" && continuedRunMatch) {
        const body = await readJsonBody<UserInstructionBody>(req);
        const accepted = acceptStubContinuedRun(
          userId,
          continuedRunMatch[1],
          readUserInstruction(body),
        );
        sendJson(res, 202, accepted.response);
        return;
      }

      const chatDetailMatch = pathname.match(/^\/api\/chats\/([^/]+)$/);
      if (method === "DELETE" && chatDetailMatch) {
        try {
          sendJson(res, 202, deleteStubChat(userId, chatDetailMatch[1]));
        } catch {
          sendJson(res, 404, {
            error: "not_found",
            message: "このチャットは削除されました。",
          });
        }
        return;
      }

      if (method === "GET" && chatDetailMatch) {
        sendJson(res, 200, getStubChatDetail(userId, chatDetailMatch[1]));
        return;
      }

      const sseMatch = pathname.match(/^\/api\/chats\/([^/]+)\/runs\/([^/]+)\/sse$/);
      if (method === "GET" && sseMatch) {
        await streamRunEvents(res, userId, sseMatch[2]);
        return;
      }

      const cancelMatch = pathname.match(/^\/api\/chats\/([^/]+)\/runs\/([^/]+)\/cancel$/);
      if (method === "POST" && cancelMatch) {
        sendJson(res, 202, cancelStubRun(userId, cancelMatch[2]));
        return;
      }

      const referenceMatch = pathname.match(/^\/api\/references\/([^/]+)$/);
      if (method === "GET" && referenceMatch) {
        serveFile(
          res,
          path.join(mockRootDir, "assets/references", `${referenceMatch[1]}.pdf`),
          "application/pdf",
        );
        return;
      }

      const artifactMatch = pathname.match(/^\/api\/artifacts\/([^/]+)$/);
      if (method === "GET" && artifactMatch) {
        const artifact = artifactManifest[artifactMatch[1]];
        if (!artifact) {
          sendText(res, 404, "artifact not found");
          return;
        }
        serveFile(
          res,
          path.join(mockRootDir, "assets/artifacts", artifact.fileName),
          artifact.mimeType,
        );
        return;
      }

      next();
    } catch (error) {
      if (isValidationErrorPayload(error)) {
        sendJson(res, 400, error);
        return;
      }
      if (error instanceof Error && error.message === "unauthorized") {
        sendUnauthorized(res);
        return;
      }
      sendText(res, 500, error instanceof Error ? error.message : "backend mock error");
    }
  };
}

type RegisterAccountRequestBody = {
  password?: unknown;
  password_confirmation?: unknown;
  user_id?: unknown;
  user_name?: unknown;
};

type LoginRequestBody = {
  password?: unknown;
  user_id?: unknown;
};

type ChangePasswordRequestBody = {
  current_password?: unknown;
  new_password?: unknown;
  new_password_confirmation?: unknown;
};

function toRegisterRequest(body: RegisterAccountRequestBody): RegisterAccountRequest {
  return {
    password: readString(body.password),
    passwordConfirmation: readString(body.password_confirmation),
    userId: readString(body.user_id),
    userName: readString(body.user_name),
  };
}

function toLoginRequest(body: LoginRequestBody): LoginRequest {
  return {
    password: readString(body.password),
    userId: readString(body.user_id),
  };
}

function toChangePasswordRequest(body: ChangePasswordRequestBody): ChangePasswordRequest {
  return {
    currentPassword: readString(body.current_password),
    newPassword: readString(body.new_password),
    newPasswordConfirmation: readString(body.new_password_confirmation),
  };
}

function readString(value: unknown) {
  return typeof value === "string" ? value : "";
}

function readUserInstruction(body: UserInstructionBody) {
  return typeof body.user_instruction === "string" ? body.user_instruction : "";
}

function readSessionId(req: IncomingMessage) {
  const cookieHeader = req.headers.cookie;
  if (!cookieHeader) {
    return undefined;
  }

  return cookieHeader
    .split(";")
    .map((cookie) => cookie.trim().split("="))
    .find((cookie) => cookie[0] === SESSION_COOKIE_NAME)?.[1];
}

function setSessionCookie(res: ServerResponse, sessionId: string) {
  res.setHeader(
    "Set-Cookie",
    `${SESSION_COOKIE_NAME}=${sessionId}; Path=/; Max-Age=${SESSION_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax; HttpOnly`,
  );
}

function clearSessionCookie(res: ServerResponse) {
  res.setHeader("Set-Cookie", `${SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax; HttpOnly`);
}

function sendUnauthorized(res: ServerResponse) {
  sendJson(res, 401, {
    error: "unauthorized",
    message: "ログインしてください。",
  });
}

function sendJson(res: ServerResponse, statusCode: number, body: unknown) {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(body));
}

function sendNoContent(res: ServerResponse) {
  res.statusCode = 204;
  res.setHeader("Cache-Control", "no-store");
  res.end();
}

function sendText(res: ServerResponse, statusCode: number, body: string) {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(body);
}

function serveFile(res: ServerResponse, filePath: string, mimeType: string) {
  if (!existsSync(filePath)) {
    sendText(res, 404, "backend mock asset not found");
    return;
  }

  res.statusCode = 200;
  res.setHeader("Content-Type", mimeType);
  res.setHeader("Cache-Control", "no-store");
  createReadStream(filePath).pipe(res);
}

async function streamRunEvents(res: ServerResponse, userId: string, runId: string) {
  let closed = false;
  res.on("close", () => {
    closed = true;
  });

  res.statusCode = 200;
  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  for (const event of listStubSseEvents(runId)) {
    if (closed) {
      return;
    }
    if (isStubRunCancelRequested(userId, runId)) {
      await streamCanceledEvent(res, userId, runId, () => closed);
      res.end();
      return;
    }
    writeSseEvent(res, event.event, event.payload);
    applyStubSseEvent(userId, event);
    await delay(SSE_EVENT_DELAY_MS);
  }

  if (!closed) {
    if (isStubRunCancelRequested(userId, runId)) {
      await streamCanceledEvent(res, userId, runId, () => closed);
    }
    res.end();
  }
}

async function streamCanceledEvent(
  res: ServerResponse,
  userId: string,
  runId: string,
  isClosed: () => boolean,
) {
  await delay(CANCEL_COMPLETION_DELAY_MS);
  if (isClosed()) {
    return;
  }

  const canceledEvent = createStubCanceledEvent(runId);
  writeSseEvent(res, canceledEvent.event, canceledEvent.payload);
  applyStubSseEvent(userId, canceledEvent);
}

function writeSseEvent(res: ServerResponse, eventName: string, payload: unknown) {
  res.write(`event: ${eventName}\n`);
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
}

function readJsonBody<T>(req: IncomingMessage) {
  return new Promise<T>((resolve, reject) => {
    let body = "";
    req.on("data", (chunk: Buffer) => {
      body += chunk.toString("utf8");
    });
    req.on("end", () => {
      try {
        resolve((body ? JSON.parse(body) : {}) as T);
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

function isValidationErrorPayload(error: unknown): error is ValidationErrorPayload {
  return (
    error !== null &&
    typeof error === "object" &&
    "error" in error &&
    error.error === "validation_error" &&
    "field_errors" in error &&
    "message" in error
  );
}

function delay(milliseconds: number) {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}
