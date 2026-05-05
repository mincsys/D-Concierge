import type { PdfReference } from "@/features/reference-viewer/model/types";

export type ViewMode = "start" | "answer";

export type ChatHistoryItem = {
  id: string;
  title: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

export type ThoughtStep = {
  id: string;
  text: string;
};

export type ChatAnswerBlock = {
  id: string;
  markdown: string;
  references: PdfReference[];
};

export type ChatAnswer = {
  blocks: ChatAnswerBlock[];
};

export type ChatSession = {
  id: string;
  userMessage: ChatMessage;
  thoughtSteps: ThoughtStep[];
  answer: ChatAnswer;
};
