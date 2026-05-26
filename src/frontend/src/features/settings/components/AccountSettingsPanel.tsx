import { LogOut, Trash2 } from "lucide-react";

import type { AccountUser } from "@/features/account/model/types";
import { ActionSettingsRow, DisplaySettingsRow, NavigationSettingsRow } from "./SettingsRows";

export function AccountSettingsPanel({
  user,
  onDelete,
  onLogout,
  onOpenPassword,
  onOpenUserName,
}: {
  user: AccountUser;
  onDelete: () => void;
  onLogout: () => void;
  onOpenPassword: () => void;
  onOpenUserName: () => void;
  }) {
  return (
    <div className="border-b border-[var(--dc-border-soft)]" data-testid="account-settings-list">
      <DisplaySettingsRow label="ユーザID" value={user.userId} />
      <NavigationSettingsRow label="ユーザ名" value={user.userName} onClick={onOpenUserName} />
      <NavigationSettingsRow label="パスワード変更" onClick={onOpenPassword} />
      <ActionSettingsRow
        buttonLabel="ログアウト"
        icon={<LogOut size={17} />}
        label="ログアウト"
        onClick={onLogout}
      />
      <ActionSettingsRow
        danger
        actionLabel="アカウント削除"
        buttonLabel="削除する"
        icon={<Trash2 size={17} />}
        label="アカウント削除"
        onClick={onDelete}
      />
    </div>
  );
}
