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

export type AnswerPoint = {
  id: string;
  title: string;
  description: string;
  referenceLabel: string;
};

export type ChatAnswer = {
  intro: string;
  points: AnswerPoint[];
  workflowTitle: string;
  imageTitle: string;
  htmlTitle: string;
  html: string;
  note: string;
};

export type ChatSession = {
  id: string;
  userMessage: ChatMessage;
  thoughtSteps: ThoughtStep[];
  answer: ChatAnswer;
  composerPlaceholder: string;
};
