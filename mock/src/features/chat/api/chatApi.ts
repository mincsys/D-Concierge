import type { ChatHistoryItem, ChatSession } from "@/features/chat/model/types";
import type { PdfReference } from "@/features/reference-viewer/model/types";
import { stubChatHistories, stubChatSession } from "@/stub/chatStub";
import { stubPdfReference } from "@/stub/referenceStub";

export async function listChatHistories(): Promise<ChatHistoryItem[]> {
  return stubChatHistories;
}

export async function getActiveChatSession(): Promise<ChatSession> {
  return stubChatSession;
}

export async function getPdfReference(): Promise<PdfReference> {
  return stubPdfReference;
}
