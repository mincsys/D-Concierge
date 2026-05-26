import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordFields } from "@/features/account/components/PasswordFields";
import type { AccountFieldErrors } from "@/features/account/model/types";
import { cn } from "@/lib/utils";

export function UserNameSettingsForm({
  fieldErrors,
  message,
  submitting,
  userName,
  onSubmit,
  onUserNameChange,
}: {
  fieldErrors: AccountFieldErrors;
  message: string | null;
  submitting: boolean;
  userName: string;
  onSubmit: () => void;
  onUserNameChange: (value: string) => void;
}) {
  return (
    <section className="pt-5" data-testid="user-name-settings-form">
      <div className="grid max-w-[360px] gap-1.5">
        <label className="text-sm font-[720]" htmlFor="settings-user-name">
          新しいユーザ名
        </label>
        <Input
          className={cn("h-11", fieldErrors.userName ? "border-[var(--dc-danger)]" : undefined)}
          id="settings-user-name"
          maxLength={30}
          placeholder="任意の文字列を使用可"
          value={userName}
          aria-invalid={fieldErrors.userName ? "true" : undefined}
          onChange={(event) => onUserNameChange(event.target.value)}
        />
        {fieldErrors.userName ? (
          <p className="text-sm font-[650] text-[var(--dc-danger)]">{fieldErrors.userName}</p>
        ) : null}
      </div>
      <FormErrorMessage fieldErrors={fieldErrors} message={message} />
      <div className="mt-5 flex justify-end">
        <Button disabled={submitting} type="button" onClick={onSubmit}>
          変更する
        </Button>
      </div>
    </section>
  );
}

export function PasswordSettingsForm({
  currentPassword,
  fieldErrors,
  message,
  newPassword,
  newPasswordConfirmation,
  submitting,
  onCurrentPasswordChange,
  onNewPasswordChange,
  onNewPasswordConfirmationChange,
  onSubmit,
}: {
  currentPassword: string;
  fieldErrors: AccountFieldErrors;
  message: string | null;
  newPassword: string;
  newPasswordConfirmation: string;
  submitting: boolean;
  onCurrentPasswordChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onNewPasswordConfirmationChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="pt-5" data-testid="password-settings-form">
      <div className="max-w-[360px]">
        <PasswordFields
          fields={[
            {
              autoComplete: "current-password",
              error: fieldErrors.currentPassword,
              id: "settings-current-password",
              label: "現在のパスワード",
              value: currentPassword,
              onChange: onCurrentPasswordChange,
            },
            {
              autoComplete: "new-password",
              error: fieldErrors.newPassword,
              id: "settings-new-password",
              label: "新しいパスワード",
              placeholder: "5文字以上、半角英数字と記号を使用可",
              value: newPassword,
              onChange: onNewPasswordChange,
            },
            {
              autoComplete: "new-password",
              error: fieldErrors.newPasswordConfirmation,
              id: "settings-new-password-confirmation",
              label: "新しいパスワード確認",
              placeholder: "同じパスワードを再入力",
              value: newPasswordConfirmation,
              onChange: onNewPasswordConfirmationChange,
            },
          ]}
        />
      </div>
      <FormErrorMessage fieldErrors={fieldErrors} message={message} />
      <div className="mt-5 flex justify-end">
        <Button disabled={submitting} type="button" onClick={onSubmit}>
          変更する
        </Button>
      </div>
    </section>
  );
}

function FormErrorMessage({
  fieldErrors,
  message,
}: {
  fieldErrors: AccountFieldErrors;
  message: string | null;
}) {
  if (!message || Object.keys(fieldErrors).length > 0) {
    return null;
  }
  return <p className="mt-4 text-sm font-[650] text-[var(--dc-danger)]">{message}</p>;
}
