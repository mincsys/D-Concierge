export type AccountUserResponse = {
  user: {
    user_id: string;
    user_name: string;
  };
};

export type AccountUser = {
  userId: string;
  userName: string;
};

export type AccountFieldErrorKey =
  | "userId"
  | "userName"
  | "password"
  | "passwordConfirmation"
  | "currentPassword"
  | "newPassword"
  | "newPasswordConfirmation";

export type AccountFieldErrors = Partial<Record<AccountFieldErrorKey, string>>;

export type LoginRequest = {
  userId: string;
  password: string;
};

export type RegisterAccountRequest = {
  userId: string;
  userName: string;
  password: string;
  passwordConfirmation: string;
};

export type ChangePasswordRequest = {
  currentPassword: string;
  newPassword: string;
  newPasswordConfirmation: string;
};

export type DeleteAccountResponse = {
  account_state: "deleting";
};

export type DeletedAccount = {
  accountState: "deleting";
};
