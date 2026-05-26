import { ArrowLeft, ChevronRight, LogOut, Trash2 } from "lucide-react";
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
        <DialogContent className="grid w-[min(700px,calc(100%-32px))] grid-cols-[190px_minmax(0,1fr)] gap-0 overflow-hidden bg-[var(--dc-app-bg)]">
          <aside className="border-r border-[var(--dc-border-soft)] bg-linear-to-b from-[var(--dc-sidebar-from)] via-[var(--dc-sidebar-via)] to-[var(--dc-sidebar-to)] p-5">
            <DialogTitle className="mb-5 text-lg font-[780]">設定</DialogTitle>
            <div className="-mx-5 min-h-[46px] border-y border-l-[5px] border-y-[var(--dc-border-soft)] border-l-[var(--dc-primary)] bg-transparent px-5 py-3 pl-[22px] text-[15.5px] font-[620] text-[var(--dc-primary)]">
              アカウント
            </div>
          </aside>
          <section className="min-h-[430px] bg-[var(--dc-app-bg)] p-5">
            {view === "list" ? (
              <AccountList
                user={user}
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
                <div className="mt-5 flex justify-end">
                  <Button disabled={submitting} type="button" onClick={handleChangeUserName}>
                    変更する
                  </Button>
                </div>
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
                <div className="mt-5 flex justify-end">
                  <Button disabled={submitting} type="button" onClick={handleChangePassword}>
                    変更する
                  </Button>
                </div>
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
  user,
  onDelete,
  onLogout,
  onOpenName,
  onOpenPassword,
}: {
  user: AccountUser;
  onDelete: () => void;
  onLogout: () => void;
  onOpenName: () => void;
  onOpenPassword: () => void;
}) {
  return (
    <div>
      <h2 className="mb-5 text-lg font-[780]">アカウント</h2>
      <div className="border-y border-[var(--dc-border-soft)]">
        <DisplayAccountRow label="ユーザID" value={user.userId} />
        <NavigationAccountRow label="ユーザ名" value={user.userName} onClick={onOpenName} />
        <NavigationAccountRow label="パスワード変更" onClick={onOpenPassword} />
        <ActionAccountRow
          buttonLabel="ログアウト"
          icon={<LogOut size={17} />}
          label="ログアウト"
          onClick={onLogout}
        />
        <ActionAccountRow
          danger
          actionLabel="アカウント削除"
          buttonLabel="削除する"
          icon={<Trash2 size={17} />}
          label="アカウント削除"
          onClick={onDelete}
        />
      </div>
    </div>
  );
}

function DisplayAccountRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-h-[60px] grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 border-b border-[var(--dc-border-soft)]">
      <span className="min-w-0 truncate text-[15px] text-[var(--dc-text-strong)]">{label}</span>
      <span className="min-w-0 truncate">{value}</span>
      <span className="ml-5 w-6" aria-hidden="true" />
    </div>
  );
}

function NavigationAccountRow({
  label,
  value,
  onClick,
}: {
  label: string;
  value?: string;
  onClick: () => void;
}) {
  return (
    <Button
      className="grid min-h-[60px] w-full grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 rounded-none border-b border-[var(--dc-border-soft)] bg-transparent px-0 text-left text-[15px] font-[760] text-[var(--dc-text-strong)] shadow-none hover:bg-[var(--dc-primary-hover)]"
      type="button"
      variant="ghost"
      onClick={onClick}
    >
      <span className="min-w-0 truncate">{label}</span>
      {value ? <span className="min-w-0 truncate">{value}</span> : <span />}
      <ChevronRight className="ml-5 text-[var(--dc-muted-strong)]" size={24} />
    </Button>
  );
}

function ActionAccountRow({
  actionLabel,
  buttonLabel,
  danger = false,
  icon,
  label,
  onClick,
}: {
  actionLabel?: string;
  buttonLabel: string;
  danger?: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <div className="grid min-h-[60px] grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-b border-[var(--dc-border-soft)] last:border-b-0">
      <span className="min-w-0 truncate text-[15px] text-[var(--dc-text-strong)]">
        {label}
      </span>
      <Button
        className={cn("gap-2", danger ? "px-4" : undefined)}
        type="button"
        variant={danger ? "destructive" : undefined}
        aria-label={actionLabel ?? buttonLabel}
        onClick={onClick}
      >
        {icon}
        {buttonLabel}
      </Button>
    </div>
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
      <h2 className="text-lg font-[780] text-[var(--dc-text-strong)]">{title}</h2>
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
