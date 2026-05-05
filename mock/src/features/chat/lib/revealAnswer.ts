import type { ChatAnswerBlock, ChatSession, ThoughtStep } from "@/features/chat/model/types";

const DEFAULT_THOUGHT_STEP_DELAY_MS = 450;
const DEFAULT_THOUGHT_COLLAPSE_DELAY_MS = 500;
const DEFAULT_ANSWER_CHUNK_DELAY_MS = 30;
const DEFAULT_ANSWER_BLOCK_DELAY_MS = 220;

type RevealSubmittedSessionOptions = {
  completedSession: ChatSession;
  isCurrent: () => boolean;
  onThoughtStep: (step: ThoughtStep) => void;
  onThoughtComplete: () => void;
  onAnswerBlockStart: (block: ChatAnswerBlock) => void;
  onAnswerBlockMarkdown: (blockId: string, markdown: string) => void;
  onAnswerBlockComplete: (block: ChatAnswerBlock) => void;
};

export async function revealSubmittedSession({
  completedSession,
  isCurrent,
  onThoughtStep,
  onThoughtComplete,
  onAnswerBlockStart,
  onAnswerBlockMarkdown,
  onAnswerBlockComplete,
}: RevealSubmittedSessionOptions) {
  for (const step of completedSession.thoughtSteps) {
    if (!isCurrent()) {
      return;
    }

    onThoughtStep(step);
    await delay(DEFAULT_THOUGHT_STEP_DELAY_MS);
  }

  if (!isCurrent()) {
    return;
  }

  await delay(DEFAULT_THOUGHT_COLLAPSE_DELAY_MS);

  if (!isCurrent()) {
    return;
  }

  onThoughtComplete();

  for (const block of completedSession.answer.blocks) {
    if (!isCurrent()) {
      return;
    }

    onAnswerBlockStart(block);

    let visibleMarkdown = "";
    for (const chunk of splitRevealChunks(block.markdown)) {
      if (!isCurrent()) {
        return;
      }

      visibleMarkdown += chunk;
      onAnswerBlockMarkdown(block.id, visibleMarkdown);
      await delay(DEFAULT_ANSWER_CHUNK_DELAY_MS);
    }

    if (!isCurrent()) {
      return;
    }

    onAnswerBlockComplete(block);
    await delay(DEFAULT_ANSWER_BLOCK_DELAY_MS);
  }
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
