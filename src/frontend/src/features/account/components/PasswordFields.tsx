import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type PasswordFieldItem = {
  autoComplete: string;
  error?: string;
  id: string;
  label: string;
  maxLength?: number;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
};

export function PasswordFields({ fields }: { fields: PasswordFieldItem[] }) {
  const [visibleFieldIds, setVisibleFieldIds] = useState<ReadonlySet<string>>(() => new Set());

  function togglePasswordVisibility(fieldId: string) {
    setVisibleFieldIds((currentFieldIds) => {
      const nextFieldIds = new Set(currentFieldIds);
      if (nextFieldIds.has(fieldId)) {
        nextFieldIds.delete(fieldId);
      } else {
        nextFieldIds.add(fieldId);
      }
      return nextFieldIds;
    });
  }

  return (
    <div className="grid gap-4">
      {fields.map((field) => {
        const passwordVisible = visibleFieldIds.has(field.id);
        const visibilityLabel = `${field.label}を${passwordVisible ? "非表示" : "表示"}`;
        return (
          <div className="grid gap-1.5" key={field.id}>
            <label className="text-sm font-[720] text-[var(--dc-text)]" htmlFor={field.id}>
              {field.label}
            </label>
            <div className="relative">
              <Input
                autoComplete={field.autoComplete}
                className={cn(
                  "dc-password-input h-11 pr-11",
                  field.error ? "border-[var(--dc-danger)]" : undefined,
                )}
                id={field.id}
                maxLength={field.maxLength ?? 30}
                placeholder={field.placeholder}
                type={passwordVisible ? "text" : "password"}
                value={field.value}
                aria-invalid={field.error ? "true" : undefined}
                onChange={(event) => field.onChange(event.target.value)}
              />
              <Button
                className="absolute top-1/2 right-1 grid size-9 -translate-y-1/2 place-items-center rounded-md bg-transparent p-0 text-[var(--dc-muted-strong)] hover:bg-[var(--dc-primary-softer)] hover:text-[var(--dc-primary-strong)]"
                type="button"
                variant="ghost"
                aria-label={visibilityLabel}
                onClick={() => togglePasswordVisibility(field.id)}
              >
                {passwordVisible ? <EyeOff size={19} /> : <Eye size={19} />}
              </Button>
            </div>
            {field.error ? (
              <p className="text-sm font-[650] text-[var(--dc-danger)]">{field.error}</p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
