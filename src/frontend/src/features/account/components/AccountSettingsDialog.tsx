import { ArrowLeft, KeyRound, LogOut, Trash2, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  changePassword,
  changeUserName,
  deleteAccount,
  logout,
} from "@/features/account/api/accountApi";
import type { AccountFieldErrors, AccountUser } from "@/features/account/model/types";
import { cn } from "@/lib/utils";
import { PasswordFields } from "./PasswordFields";
import { readAccountFieldErrors, readAccountMessage } from "./formErrors";

type AccountSettingsView = "list" | "name" | "password";
type ConfirmAction = "logout" | "delete" | null;

export function AccountSettingsDialog({
  open,
  user,
  onLoggedOut,
  onOpenChange,
  onUserChange,
}: {
  open: boolean;
  user: AccountUser;
  onLoggedOut: () => void;
  onOpenChange: (open: boolean) => void;
  onUserChange: (nextUser: AccountUser) => void;
}) {
  const [view, setView] = useState<AccountSettingsView>("list");
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<AccountFieldErrors>({});
  const [message, setMessage] = useState<string | null>(null);
  const [userName, setUserName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirmation, setNewPasswordConfirmation] = useState("");

  useEffect(() => {
    if (open) {
      return;
    }
    setView("list");
    setCurrentPassword("");
    setFieldErrors({});
    setMessage(null);
    setNewPassword("");
    setNewPasswordConfirmation("");
    setSubmitting(false);
    setUserName("");
    setConfirmAction(null);
  }, [open]);

  function resetFormState() {
    setCurrentPassword("");
    setFieldErrors({});
    setMessage(null);
    setNewPassword("");
    setNewPasswordConfirmation("");
    setSubmitting(false);
    setUserName("");
  }

  function moveToList() {
    resetFormState();
    setView("list");
  }

  async function handleChangeUserName() {
    setSubmitting(true);
    setFieldErrors({});
    setMessage(null);
    try {
      const nextUser = await changeUserName(userName);
      onUserChange(nextUser);
      moveToList();
    } catch (error) {
      setFieldErrors(readAccountFieldErrors(error));
      setMessage(readAccountMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleChangePassword() {
    setSubmitting(true);
    setFieldErrors({});
    setMessage(null);
    try {
      await changePassword({
        currentPassword,
        newPassword,
        newPasswordConfirmation,
      });
      moveToList();
    } catch (error) {
      setFieldErrors(readAccountFieldErrors(error));
      setMessage(readAccountMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirm() {
    if (!confirmAction) {
      return;
    }
    setSubmitting(true);
    try {
      if (confirmAction === "logout") {
        await logout();
      } else {
        await deleteAccount();
      }
      setConfirmAction(null);
      onOpenChange(false);
      onLoggedOut();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="grid w-[min(760px,calc(100%-32px))] grid-cols-[190px_minmax(0,1fr)] overflow-hidden p-0">
          <aside className="border-r border-[var(--dc-border-soft)] bg-[var(--dc-panel)] p-5">
            <DialogTitle className="mb-5 text-lg font-[780]">設定</DialogTitle>
            <div className="rounded-lg bg-white px-3 py-2.5 text-sm font-[760] text-[var(--dc-primary-strong)] shadow-xs">
              アカウント
            </div>
          </aside>
          <section className="min-h-[430px] p-6">
            {view === "list" ? (
              <AccountList
                onDelete={() => setConfirmAction("delete")}
                onLogout={() => setConfirmAction("logout")}
                onOpenName={() => {
                  resetFormState();
                  setUserName(user.userName);
                  setView("name");
                }}
                onOpenPassword={() => {
                  resetFormState();
                  setView("password");
                }}
              />
            ) : null}
            {view === "name" ? (
              <section>
                <ContentHeader title="ユーザ名変更" onBack={moveToList} />
                <div className="mt-6 grid max-w-[360px] gap-1.5">
                  <label className="text-sm font-[720]" htmlFor="settings-user-name">
                    新しいユーザ名
                  </label>
                  <Input
                    className={cn(
                      "h-11",
                      fieldErrors.userName ? "border-[var(--dc-danger)]" : undefined,
                    )}
                    id="settings-user-name"
                    maxLength={30}
                    placeholder="任意の文字列を使用可"
                    value={userName}
                    aria-invalid={fieldErrors.userName ? "true" : undefined}
                    onChange={(event) => setUserName(event.target.value)}
                  />
                  {fieldErrors.userName ? (
                    <p className="text-sm font-[650] text-[var(--dc-danger)]">
                      {fieldErrors.userName}
                    </p>
                  ) : null}
                </div>
                <FormErrorMessage fieldErrors={fieldErrors} message={message} />
                <Button
                  className="mt-5"
                  disabled={submitting}
                  type="button"
                  onClick={handleChangeUserName}
                >
                  変更する
                </Button>
              </section>
            ) : null}
            {view === "password" ? (
              <section>
                <ContentHeader title="パスワード変更" onBack={moveToList} />
                <div className="mt-6 max-w-[360px]">
                  <PasswordFields
                    fields={[
                      {
                        autoComplete: "current-password",
                        error: fieldErrors.currentPassword,
                        id: "settings-current-password",
                        label: "現在のパスワード",
                        value: currentPassword,
                        onChange: setCurrentPassword,
                      },
                      {
                        autoComplete: "new-password",
                        error: fieldErrors.newPassword,
                        id: "settings-new-password",
                        label: "新しいパスワード",
                        placeholder: "5文字以上、半角英数字と記号を使用可",
                        value: newPassword,
                        onChange: setNewPassword,
                      },
                      {
                        autoComplete: "new-password",
                        error: fieldErrors.newPasswordConfirmation,
                        id: "settings-new-password-confirmation",
                        label: "新しいパスワード確認",
                        placeholder: "同じパスワードを再入力",
                        value: newPasswordConfirmation,
                        onChange: setNewPasswordConfirmation,
                      },
                    ]}
                  />
                </div>
                <FormErrorMessage fieldErrors={fieldErrors} message={message} />
                <Button
                  className="mt-5"
                  disabled={submitting}
                  type="button"
                  onClick={handleChangePassword}
                >
                  変更する
                </Button>
              </section>
            ) : null}
          </section>
        </DialogContent>
      </Dialog>
      <Dialog
        open={confirmAction !== null}
        onOpenChange={(nextOpen) => !nextOpen && setConfirmAction(null)}
      >
        <DialogContent className="w-[min(460px,calc(100%-32px))] gap-5 p-6">
          <DialogHeader>
            <DialogTitle>
              {confirmAction === "delete"
                ? "アカウントを完全に削除しますか？"
                : "ログアウトしますか？"}
            </DialogTitle>
            {confirmAction === "delete" ? (
              <DialogDescription className="font-bold text-[var(--dc-danger)]">
                この操作は取り消せません。アカウントに紐づけられている全てのデータが完全に削除されます。
              </DialogDescription>
            ) : null}
          </DialogHeader>
          <div className="flex justify-end gap-3">
            <Button
              disabled={submitting}
              type="button"
              variant="ghost"
              onClick={() => setConfirmAction(null)}
            >
              キャンセル
            </Button>
            <Button
              disabled={submitting}
              type="button"
              variant={confirmAction === "delete" ? "destructive" : undefined}
              onClick={handleConfirm}
            >
              {confirmAction === "delete" ? "削除する" : "ログアウト"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function AccountList({
  onDelete,
  onLogout,
  onOpenName,
  onOpenPassword,
}: {
  onDelete: () => void;
  onLogout: () => void;
  onOpenName: () => void;
  onOpenPassword: () => void;
}) {
  return (
    <div>
      <h2 className="text-xl font-[780] text-[var(--dc-text-strong)]">アカウント</h2>
      <div className="mt-6 grid gap-3">
        <AccountActionButton
          icon={<UserRound size={20} />}
          label="ユーザ名変更"
          onClick={onOpenName}
        />
        <AccountActionButton
          icon={<KeyRound size={20} />}
          label="パスワード変更"
          onClick={onOpenPassword}
        />
        <AccountActionButton icon={<LogOut size={20} />} label="ログアウト" onClick={onLogout} />
        <AccountActionButton
          danger
          icon={<Trash2 size={20} />}
          label="アカウント削除"
          onClick={onDelete}
        />
      </div>
    </div>
  );
}

function AccountActionButton({
  danger = false,
  icon,
  label,
  onClick,
}: {
  danger?: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      className={cn(
        "h-12 justify-start rounded-lg border border-[var(--dc-border)] bg-white px-4 text-[15px] font-[760] text-[var(--dc-text)] hover:bg-[var(--dc-primary-softer)]",
        danger ? "text-[var(--dc-danger)] hover:text-[var(--dc-danger)]" : undefined,
      )}
      type="button"
      variant="outline"
      onClick={onClick}
    >
      {icon}
      {label}
    </Button>
  );
}

function ContentHeader({ onBack, title }: { onBack: () => void; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <Button
        className="grid size-9 place-items-center rounded-lg bg-transparent p-0"
        type="button"
        variant="ghost"
        aria-label="戻る"
        onClick={onBack}
      >
        <ArrowLeft size={22} />
      </Button>
      <h2 className="text-xl font-[780] text-[var(--dc-text-strong)]">{title}</h2>
    </div>
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
