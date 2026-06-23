import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type ConfirmAction = "logout" | "delete" | null;

export function ConfirmActionDialog({
  action,
  message,
  submitting,
  onCancel,
  onConfirm,
}: {
  action: ConfirmAction;
  message?: string | null;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={action !== null} onOpenChange={(nextOpen) => !nextOpen && onCancel()}>
      <DialogContent className="w-[min(460px,calc(100%-32px))] gap-5 p-6">
        <DialogHeader>
          <DialogTitle>
            {action === "delete" ? "アカウントを完全に削除しますか？" : "ログアウトしますか？"}
          </DialogTitle>
          {action === "delete" ? (
            <DialogDescription className="font-bold text-[var(--dc-danger)]">
              この操作は取り消せません。アカウントに紐づけられている全てのデータが完全に削除されます。
            </DialogDescription>
          ) : null}
        </DialogHeader>
        {message ? (
          <p className="text-sm font-[650] text-[var(--dc-danger)]">{message}</p>
        ) : null}
        <div className="flex justify-end gap-3">
          <Button disabled={submitting} type="button" variant="ghost" onClick={onCancel}>
            キャンセル
          </Button>
          <Button
            disabled={submitting}
            type="button"
            variant={action === "delete" ? "destructive" : undefined}
            onClick={onConfirm}
          >
            {action === "delete" ? "削除する" : "ログアウト"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
