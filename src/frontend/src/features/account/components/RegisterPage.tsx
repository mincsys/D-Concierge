import { Link, useNavigate } from "react-router";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { registerAccount } from "@/features/account/api/accountApi";
import { readAccountFieldErrors, readAccountMessage } from "@/features/account/lib/formErrors";
import type { AccountFieldErrors, AccountUser } from "@/features/account/model/types";
import { cn } from "@/lib/utils";
import { AuthLayout } from "./AuthLayout";
import { PasswordFields } from "./PasswordFields";

export function RegisterPage({
  onAuthenticated,
}: {
  onAuthenticated: (user: AccountUser) => void;
}) {
  const navigate = useNavigate();
  const [userId, setUserId] = useState("");
  const [userName, setUserName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<AccountFieldErrors>({});
  const [message, setMessage] = useState<string | null>(null);

  async function handleRegister() {
    setSubmitting(true);
    setFieldErrors({});
    setMessage(null);
    try {
      const authenticatedUser = await registerAccount({
        password,
        passwordConfirmation,
        userId,
        userName,
      });
      onAuthenticated(authenticatedUser);
      navigate("/", { replace: true });
    } catch (error) {
      setFieldErrors(readAccountFieldErrors(error));
      setMessage(readAccountMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="アカウント登録">
      <div className="grid gap-4">
        <TextField
          autoComplete="username"
          error={fieldErrors.userId}
          id="register-user-id"
          label="ユーザID"
          placeholder={'半角英数字、"-"、"_" のみ使用可'}
          value={userId}
          onChange={setUserId}
        />
        <TextField
          autoComplete="name"
          error={fieldErrors.userName}
          id="register-user-name"
          label="ユーザ名"
          placeholder="任意の文字列を使用可"
          value={userName}
          onChange={setUserName}
        />
        <PasswordFields
          fields={[
            {
              autoComplete: "new-password",
              error: fieldErrors.password,
              id: "register-password",
              label: "パスワード",
              placeholder: "5文字以上、半角英数字と記号を使用可",
              value: password,
              onChange: setPassword,
            },
            {
              autoComplete: "new-password",
              error: fieldErrors.passwordConfirmation,
              id: "register-password-confirmation",
              label: "パスワード確認",
              placeholder: "同じパスワードを再入力",
              value: passwordConfirmation,
              onChange: setPasswordConfirmation,
            },
          ]}
        />
        {message && Object.keys(fieldErrors).length === 0 ? (
          <p className="text-sm font-[650] text-[var(--dc-danger)]">{message}</p>
        ) : null}
        <Button
          className="mt-1 h-11 font-bold"
          disabled={submitting}
          type="button"
          onClick={handleRegister}
        >
          登録
        </Button>
        <Link
          className="text-center text-sm font-[720] text-[var(--dc-primary-strong)] hover:underline"
          to="/login"
        >
          ログイン画面へ戻る
        </Link>
      </div>
    </AuthLayout>
  );
}

function TextField({
  autoComplete,
  error,
  id,
  label,
  placeholder,
  value,
  onChange,
}: {
  autoComplete: string;
  error?: string;
  id: string;
  label: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-1.5">
      <label className="text-sm font-[720] text-[var(--dc-text)]" htmlFor={id}>
        {label}
      </label>
      <Input
        autoComplete={autoComplete}
        className={cn("h-11", error ? "border-[var(--dc-danger)]" : undefined)}
        id={id}
        maxLength={30}
        placeholder={placeholder}
        value={value}
        aria-invalid={error ? "true" : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <p className="text-sm font-[650] text-[var(--dc-danger)]">{error}</p> : null}
    </div>
  );
}
