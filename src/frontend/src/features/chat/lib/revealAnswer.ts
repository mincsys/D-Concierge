import type { ChatAnswer } from "@/features/chat/model/types";

const DEFAULT_THOUGHT_COLLAPSE_DELAY_MS = 500;
const DEFAULT_ANSWER_CHUNK_DELAY_MS = 30;
const DEFAULT_ANSWER_BLOCK_DELAY_MS = 220;

type RevealSubmittedAnswerOptions = {
  runId: string;
  answer: ChatAnswer;
  isCurrent: () => boolean;
  onThoughtComplete: () => void;
  onAnswerStart: (runId: string, answer: ChatAnswer) => void;
  onAnswerMarkdown: (runId: string, markdown: string) => void;
  onAnswerComplete: (runId: string, answer: ChatAnswer) => void;
};

export async function revealSubmittedAnswer({
  runId,
  answer,
  isCurrent,
  onThoughtComplete,
  onAnswerStart,
  onAnswerMarkdown,
  onAnswerComplete,
}: RevealSubmittedAnswerOptions) {
  await delay(DEFAULT_THOUGHT_COLLAPSE_DELAY_MS);

  if (!isCurrent()) {
    return;
  }

  onThoughtComplete();
  onAnswerStart(runId, answer);

  let visibleMarkdown = "";
  for (const chunk of splitRevealChunks(answer.markdown)) {
    if (!isCurrent()) {
      return;
    }

    visibleMarkdown += chunk;
    onAnswerMarkdown(runId, visibleMarkdown);
    await delay(DEFAULT_ANSWER_CHUNK_DELAY_MS);
  }

  if (!isCurrent()) {
    return;
  }

  onAnswerComplete(runId, answer);
  await delay(DEFAULT_ANSWER_BLOCK_DELAY_MS);
}

export function splitRevealChunks(markdown: string) {
  const chunks: string[] = [];
  const mermaidBlockPattern = /```mermaid[\s\S]*?```/g;
  let cursor = 0;

  for (const match of markdown.matchAll(mermaidBlockPattern)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      chunks.push(...splitTextChunks(markdown.slice(cursor, start)));
    }
    chunks.push(match[0]);
    cursor = start + match[0].length;
  }

  if (cursor < markdown.length) {
    chunks.push(...splitTextChunks(markdown.slice(cursor)));
  }

  return chunks;
}

function splitTextChunks(text: string) {
  return text.match(/[\s\S]{1,8}/g) ?? [];
}

function delay(milliseconds: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}
