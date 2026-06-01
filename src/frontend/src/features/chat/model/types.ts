import type { DisplayReference } from "@/features/reference-viewer/model/types";

export type ViewMode = "start" | "answer";

export type ChatState = "active" | "deleting";

export type ChatRunState =
  | "accepted"
  | "running"
  | "validating"
  | "cancel_requested"
  | "canceled"
  | "completed"
  | "error"
  | "timed_out";

export type AppConfigResponse = {
  welcome_message?: string;
  sub_welcome_message?: string;
  input_suggestions?: string[];
};

export type ChatHistoryResponseItem = {
  chat_id: string;
  title: string;
  latest_run_id?: string;
  latest_state: ChatRunState;
  updated_at: string;
};

export type ChatStartResponse = {
  chat_id: string;
  run_id: string;
  sse_url: string;
  state: ChatRunState;
};

export type CancelChatRunResponse = {
  run_id: string;
  state: "cancel_requested";
  user_message: string;
};

export type DeleteChatResponse = {
  chat_id: string;
  chat_state: "deleting";
};

export type DeletedChat = {
  chatId: string;
  chatState: "deleting";
};

export type ChatRunResponse = {
  run_id: string;
  state: ChatRunState;
  user_instruction: string;
  intermediate_messages?: IntermediateMessageResponse[];
  answer?: AnswerResponse;
  user_message?: string;
};

export type ChatDetailResponse = {
  chat_id: string;
  title: string;
  runs: ChatRunResponse[];
};

export type IntermediateMessageResponse = {
  text: string;
};

export type AnswerResponse = {
  blocks: AnswerBlockResponse[];
};

export type AnswerBlockResponse = {
  markdown: string;
  references?: DisplayReference[];
};

export type SseEvent =
  | {
      event: "state";
      payload: {
        run_id: string;
        state: ChatRunState;
      };
    }
  | {
      event: "message";
      payload: {
        run_id: string;
        text: string;
      };
    }
  | {
      event: "answer";
      payload: {
        run_id: string;
        state: "completed";
        answer: AnswerResponse;
      };
    }
  | {
      event: "error";
      payload: {
        run_id: string;
        state: "error" | "timed_out";
        user_message: string;
      };
    }
  | {
      event: "canceled";
      payload: {
        run_id: string;
        state: "canceled";
        user_message: string;
      };
    };

export type ChatHistoryItem = {
  chatId: string;
  title: string;
  latestRunId?: string;
  latestState: ChatRunState;
  updatedAt: string;
};

export type IntermediateMessage = {
  id: string;
  text: string;
};

export type ChatAnswer = {
  blocks: ChatAnswerBlock[];
};

export type ChatAnswerBlock = {
  markdown: string;
  references: DisplayReference[];
};

export type ChatRun = {
  runId: string;
  state: ChatRunState;
  userInstruction: string;
  intermediateMessages: IntermediateMessage[];
  answer?: ChatAnswer;
  statusMessage?: string;
};

export type ChatSession = {
  id: string;
  title: string;
  runs: ChatRun[];
};
