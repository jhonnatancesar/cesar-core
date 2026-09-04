import * as Dialog from "@radix-ui/react-dialog";
import { Moon, Sun, X } from "lucide-react";
import type { ReactNode } from "react";

export function ThemeToggle({
  dark,
  onChange,
}: {
  dark: boolean;
  onChange: () => void;
}) {
  return (
    <button
      className="btn-secondary !p-2.5"
      onClick={onChange}
      aria-label={dark ? "Usar tema claro" : "Usar tema escuro"}
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}

export function Status({ value }: { value: string }) {
  const ok = ["active", "available", "healthy", "ok", "success"].includes(
    value,
  );
  const warn = ["reserved", "disabled", "not_configured"].includes(value);
  return (
    <span
      className={`badge ${ok ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-300" : warn ? "bg-amber-100 text-amber-700 dark:bg-amber-400/10 dark:text-amber-300" : "bg-rose-100 text-rose-700 dark:bg-rose-400/10 dark:text-rose-300"}`}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="p-10 text-center text-sm text-slate-500">{children}</div>
  );
}

export function Modal({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/55 backdrop-blur-sm" />
        <Dialog.Content className="panel fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-auto p-6">
          <div className="mb-5 flex items-center justify-between">
            <Dialog.Title className="text-xl font-bold">{title}</Dialog.Title>
            <Dialog.Close className="btn-secondary !p-2">
              <X size={16} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
    </label>
  );
}
