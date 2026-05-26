import { isAccountApiError } from "@/features/account/api/accountApi";
import type { AccountFieldErrors } from "@/features/account/model/types";

export function readAccountFieldErrors(error: unknown): AccountFieldErrors {
  return isAccountApiError(error) ? (error.fieldErrors ?? {}) : {};
}

export function readAccountMessage(error: unknown): string | null {
  if (isAccountApiError(error)) {
    return error.message;
  }
  return error instanceof Error ? error.message : "処理に失敗しました。";
}
