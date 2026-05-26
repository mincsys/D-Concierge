import { Link, useNavigate } from "react-router";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login } from "@/features/account/api/accountApi";
import type { AccountFieldErrors, AccountUser } from "@/features/account/model/types";
import { cn } from "@/lib/utils";
import { AuthLayout } from "./AuthLayout";
import { PasswordFields } from "./PasswordFields";
import { readAccountFieldErrors, readAccountMessage } from "./formErrors";

export function LoginPage({ onAuthenticated }: { onAuthenticated: (user: AccountUser) => void }) {
  const navigate = useNavigate();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<AccountFieldErrors>({});
  const [message, setMessage] = useState<string | null>(null);

  async function handleLogin() {
    setSubmitting(true);
    setFieldErrors({});
    setMessage(null);
    try {
      const authenticatedUser = await login({ password, userId });
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
    <AuthLayout title="ログイン">
      <div className="grid gap-4">
        <div className="grid gap-1.5">
          <label className="text-sm font-[720] text-[var(--dc-text)]" htmlFor="login-user-id">
            ユーザID
          </label>
          <Input
            autoComplete="username"
            className={cn("h-11", fieldErrors.userId ? "border-[var(--dc-danger)]" : undefined)}
            id="login-user-id"
            maxLength={30}
            value={userId}
            aria-invalid={fieldErrors.userId ? "true" : undefined}
            onChange={(event) => setUserId(event.target.value)}
          />
          {fieldErrors.userId ? (
            <p className="text-sm font-[650] text-[var(--dc-danger)]">{fieldErrors.userId}</p>
          ) : null}
        </div>
        <PasswordFields
          fields={[
            {
              autoComplete: "current-password",
              error: fieldErrors.password,
              id: "login-password",
              label: "パスワード",
              value: password,
              onChange: setPassword,
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
          onClick={handleLogin}
        >
          ログイン
        </Button>
        <Link
          className="text-center text-sm font-[720] text-[var(--dc-primary-strong)] hover:underline"
          to="/register"
        >
          アカウント登録
        </Link>
      </div>
    </AuthLayout>
  );
}
