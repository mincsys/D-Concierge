import type { ChatHistoryItem, ChatSession } from "@/features/chat/model/types";
import { stubChatHistories, stubChatSession } from "@/stub/chatStub";

export async function listChatHistories(): Promise<ChatHistoryItem[]> {
  return stubChatHistories;
}

export async function getActiveChatSession(): Promise<ChatSession> {
  return stubChatSession;
}
