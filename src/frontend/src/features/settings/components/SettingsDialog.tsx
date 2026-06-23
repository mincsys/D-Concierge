import { useEffect, useState } from "react";

import {
  changePassword,
  changeUserName,
  deleteAccount,
  isUnauthorizedAccountError,
  logout,
} from "@/features/account/api/accountApi";
import type { AccountFieldErrors, AccountUser } from "@/features/account/model/types";
import { readAccountFieldErrors, readAccountMessage } from "@/features/account/lib/formErrors";
import { PasswordSettingsForm, UserNameSettingsForm } from "./AccountSettingsForms";
import { AccountSettingsPanel } from "./AccountSettingsPanel";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { SettingsShell } from "./SettingsShell";

type SettingsView = "account" | "userName" | "password";
type ConfirmAction = "logout" | "delete" | null;

export function SettingsDialog({
  open,
  user,
  onLoggedOut,
  onOpenChange,
  onUnauthorized,
  onUserChange,
}: {
  open: boolean;
  user: AccountUser;
  onLoggedOut: () => void;
  onOpenChange: (open: boolean) => void;
  onUnauthorized?: () => void;
  onUserChange: (nextUser: AccountUser) => void;
}) {
  const [view, setView] = useState<SettingsView>("account");
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
    setView("account");
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

  function moveToAccountPanel() {
    resetFormState();
    setView("account");
  }

  async function handleChangeUserName() {
    setSubmitting(true);
    setFieldErrors({});
    setMessage(null);
    try {
      const nextUser = await changeUserName(userName);
      onUserChange(nextUser);
      moveToAccountPanel();
    } catch (error) {
      if (handleUnauthorizedError(error, onUnauthorized)) {
        return;
      }
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
      moveToAccountPanel();
    } catch (error) {
      if (handleUnauthorizedError(error, onUnauthorized)) {
        return;
      }
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
    } catch (error) {
      if (handleUnauthorizedError(error, onUnauthorized)) {
        return;
      }
      setMessage(readAccountMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <SettingsShell
        title={viewTitle(view)}
        open={open}
        onBack={view === "account" ? undefined : moveToAccountPanel}
        onOpenChange={onOpenChange}
      >
        {view === "account" ? (
          <AccountSettingsPanel
            user={user}
            onDelete={() => setConfirmAction("delete")}
            onLogout={() => setConfirmAction("logout")}
            onOpenPassword={() => {
              resetFormState();
              setView("password");
            }}
            onOpenUserName={() => {
              resetFormState();
              setUserName(user.userName);
              setView("userName");
            }}
          />
        ) : null}
        {view === "userName" ? (
          <UserNameSettingsForm
            fieldErrors={fieldErrors}
            message={message}
            submitting={submitting}
            userName={userName}
            onSubmit={handleChangeUserName}
            onUserNameChange={setUserName}
          />
        ) : null}
        {view === "password" ? (
          <PasswordSettingsForm
            currentPassword={currentPassword}
            fieldErrors={fieldErrors}
            message={message}
            newPassword={newPassword}
            newPasswordConfirmation={newPasswordConfirmation}
            submitting={submitting}
            onCurrentPasswordChange={setCurrentPassword}
            onNewPasswordChange={setNewPassword}
            onNewPasswordConfirmationChange={setNewPasswordConfirmation}
            onSubmit={handleChangePassword}
          />
        ) : null}
      </SettingsShell>
      <ConfirmActionDialog
        action={confirmAction}
        message={message}
        submitting={submitting}
        onCancel={() => setConfirmAction(null)}
        onConfirm={handleConfirm}
      />
    </>
  );
}

function handleUnauthorizedError(error: unknown, onUnauthorized: (() => void) | undefined): boolean {
  if (!isUnauthorizedAccountError(error)) {
    return false;
  }
  onUnauthorized?.();
  return true;
}

function viewTitle(view: SettingsView): string {
  if (view === "userName") {
    return "ユーザ名変更";
  }
  if (view === "password") {
    return "パスワード変更";
  }
  return "アカウント";
}
