import type { DisplayReference } from "@/features/reference-viewer/model/types";

export type ViewMode = "start" | "answer";

export type ChatRunState =
  | "受付"
  | "実行中"
  | "検証中"
  | "キャンセル要求中"
  | "キャンセル済み"
  | "完了"
  | "エラー"
  | "タイムアウト";

export type AppConfigResponse = {
  welcome_message?: string;
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
        state: "完了";
        answer: AnswerResponse;
      };
    }
  | {
      event: "error";
      payload: {
        run_id: string;
        state: "エラー" | "タイムアウト";
        user_message: string;
      };
    }
  | {
      event: "canceled";
      payload: {
        run_id: string;
        state: "キャンセル済み";
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
