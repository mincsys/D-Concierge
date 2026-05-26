import type {
  AccountFieldErrors,
  AccountUser,
  AccountUserResponse,
  ChangePasswordRequest,
  DeletedAccount,
  DeleteAccountResponse,
  LoginRequest,
  RegisterAccountRequest,
} from "@/features/account/model/types";

type ErrorPayload = {
  error?: string;
  field_errors?: Record<string, string>;
  message?: string;
};

export class AccountApiError extends Error {
  readonly error?: string;
  readonly fieldErrors?: AccountFieldErrors;
  readonly status: number;

  constructor(status: number, message: string, error?: string, fieldErrors?: AccountFieldErrors) {
    super(message);
    this.name = "AccountApiError";
    this.status = status;
    this.error = error;
    this.fieldErrors = fieldErrors;
  }
}

export function isAccountApiError(error: unknown): error is AccountApiError {
  return error instanceof AccountApiError;
}

export function isUnauthorizedAccountError(error: unknown) {
  return isAccountApiError(error) && error.status === 401;
}

export async function getCurrentUser(): Promise<AccountUser> {
  return toAccountUser(await requestJson<AccountUserResponse>("/api/auth/me"));
}

export async function login(request: LoginRequest): Promise<AccountUser> {
  return toAccountUser(
    await requestJson<AccountUserResponse>("/api/auth/login", {
      body: JSON.stringify({
        user_id: request.userId,
        password: request.password,
      }),
      method: "POST",
    }),
  );
}

export async function registerAccount(request: RegisterAccountRequest): Promise<AccountUser> {
  return toAccountUser(
    await requestJson<AccountUserResponse>("/api/auth/register", {
      body: JSON.stringify({
        user_id: request.userId,
        user_name: request.userName,
        password: request.password,
        password_confirmation: request.passwordConfirmation,
      }),
      method: "POST",
    }),
  );
}

export async function logout(): Promise<void> {
  await requestNoContent("/api/auth/logout", { method: "POST" });
}

export async function changeUserName(userName: string): Promise<AccountUser> {
  return toAccountUser(
    await requestJson<AccountUserResponse>("/api/account/name", {
      body: JSON.stringify({ user_name: userName }),
      method: "PATCH",
    }),
  );
}

export async function changePassword(request: ChangePasswordRequest): Promise<void> {
  await requestNoContent("/api/account/password", {
    body: JSON.stringify({
      current_password: request.currentPassword,
      new_password: request.newPassword,
      new_password_confirmation: request.newPasswordConfirmation,
    }),
    method: "PATCH",
  });
}

export async function deleteAccount(): Promise<DeletedAccount> {
  const response = await requestJson<DeleteAccountResponse>("/api/account", { method: "DELETE" });
  return { accountState: response.account_state };
}

export function toAccountUser(response: AccountUserResponse): AccountUser {
  return {
    userId: response.user.user_id,
    userName: response.user.user_name,
  };
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, buildRequestInit(init));
  if (!response.ok) {
    throw await buildAccountApiError(response);
  }
  return response.json() as Promise<T>;
}

async function requestNoContent(url: string, init?: RequestInit): Promise<void> {
  const response = await fetch(url, buildRequestInit(init));
  if (!response.ok) {
    throw await buildAccountApiError(response);
  }
}

function buildRequestInit(init?: RequestInit): RequestInit {
  return {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  };
}

async function buildAccountApiError(response: Response) {
  const payload = await parseErrorPayload(response);
  return new AccountApiError(
    response.status,
    payload?.message ?? `API request failed: ${response.status}`,
    payload?.error,
    toAccountFieldErrors(payload?.field_errors),
  );
}

async function parseErrorPayload(response: Response): Promise<ErrorPayload | null> {
  try {
    const payload: unknown = await response.json();
    if (payload === null || typeof payload !== "object") {
      return null;
    }
    return {
      error: readString(payload, "error"),
      field_errors: readStringRecord(payload, "field_errors"),
      message: readString(payload, "message"),
    };
  } catch {
    return null;
  }
}

function readString(payload: object, key: string) {
  return key in payload && typeof payload[key as keyof typeof payload] === "string"
    ? (payload[key as keyof typeof payload] as string)
    : undefined;
}

function readStringRecord(payload: object, key: string) {
  const value = key in payload ? payload[key as keyof typeof payload] : undefined;
  if (value === null || typeof value !== "object") {
    return undefined;
  }

  return Object.fromEntries(
    Object.entries(value).filter(
      (entry): entry is [string, string] => typeof entry[1] === "string",
    ),
  );
}

function toAccountFieldErrors(
  fieldErrors?: Record<string, string>,
): AccountFieldErrors | undefined {
  if (!fieldErrors) {
    return undefined;
  }

  return {
    currentPassword: fieldErrors.current_password,
    newPassword: fieldErrors.new_password,
    newPasswordConfirmation: fieldErrors.new_password_confirmation,
    password: fieldErrors.password,
    passwordConfirmation: fieldErrors.password_confirmation,
    userId: fieldErrors.user_id,
    userName: fieldErrors.user_name,
  };
}
