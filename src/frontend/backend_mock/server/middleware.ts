import { createReadStream, existsSync } from "node:fs";
import { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import type { Connect } from "vite";

import { artifactManifest } from "../data/artifactManifest";
import {
  acceptStubContinuedRun,
  acceptStubStartChat,
  applyStubSseEvent,
  cancelStubRun,
  createStubCanceledEvent,
  getStubAppConfig,
  getStubChatDetail,
  isStubRunCancelRequested,
  listStubChatHistories,
  listStubSseEvents,
} from "./runtime";

const SSE_EVENT_DELAY_MS = 900;
const CANCEL_COMPLETION_DELAY_MS = 1800;

type UserInstructionBody = {
  user_instruction?: unknown;
};

export function createBackendMockMiddleware(mockRootDir: string): Connect.NextHandleFunction {
  return async (req, res, next) => {
    const method = req.method ?? "GET";
    const pathname = new URL(req.url ?? "/", "http://localhost").pathname;

    try {
      if (method === "GET" && pathname === "/api/app-config") {
        sendJson(res, 200, getStubAppConfig());
        return;
      }

      if (method === "GET" && pathname === "/api/chat-histories") {
        sendJson(res, 200, listStubChatHistories());
        return;
      }

      if (method === "POST" && pathname === "/api/chats/start") {
        const body = await readJsonBody<UserInstructionBody>(req);
        const accepted = acceptStubStartChat(readUserInstruction(body));
        sendJson(res, 202, accepted.response);
        return;
      }

      const continuedRunMatch = pathname.match(/^\/api\/chats\/([^/]+)\/runs$/);
      if (method === "POST" && continuedRunMatch) {
        const body = await readJsonBody<UserInstructionBody>(req);
        const accepted = acceptStubContinuedRun(continuedRunMatch[1], readUserInstruction(body));
        sendJson(res, 202, accepted.response);
        return;
      }

      const chatDetailMatch = pathname.match(/^\/api\/chats\/([^/]+)$/);
      if (method === "GET" && chatDetailMatch) {
        sendJson(res, 200, getStubChatDetail(chatDetailMatch[1]));
        return;
      }

      const sseMatch = pathname.match(/^\/api\/chats\/([^/]+)\/runs\/([^/]+)\/sse$/);
      if (method === "GET" && sseMatch) {
        await streamRunEvents(res, sseMatch[2]);
        return;
      }

      const cancelMatch = pathname.match(/^\/api\/chats\/([^/]+)\/runs\/([^/]+)\/cancel$/);
      if (method === "POST" && cancelMatch) {
        sendJson(res, 202, cancelStubRun(cancelMatch[2]));
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
      sendText(res, 500, error instanceof Error ? error.message : "backend mock error");
    }
  };
}

function readUserInstruction(body: UserInstructionBody) {
  return typeof body.user_instruction === "string" ? body.user_instruction : "";
}

function sendJson(res: ServerResponse, statusCode: number, body: unknown) {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(body));
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

async function streamRunEvents(res: ServerResponse, runId: string) {
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
    if (isStubRunCancelRequested(runId)) {
      await streamCanceledEvent(res, runId, () => closed);
      res.end();
      return;
    }
    writeSseEvent(res, event.event, event.payload);
    applyStubSseEvent(event);
    await delay(SSE_EVENT_DELAY_MS);
  }

  if (!closed) {
    if (isStubRunCancelRequested(runId)) {
      await streamCanceledEvent(res, runId, () => closed);
    }
    res.end();
  }
}

async function streamCanceledEvent(res: ServerResponse, runId: string, isClosed: () => boolean) {
  await delay(CANCEL_COMPLETION_DELAY_MS);
  if (isClosed()) {
    return;
  }

  const canceledEvent = createStubCanceledEvent(runId);
  writeSseEvent(res, canceledEvent.event, canceledEvent.payload);
  applyStubSseEvent(canceledEvent);
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

function delay(milliseconds: number) {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}
