import type { KeyboardEvent, ReactNode } from "react";
import { useEffect, useRef } from "react";

type ModalDialogProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  busy?: boolean;
};

export function ModalDialog({ open, title, onClose, children, footer, busy = false }: ModalDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const titleId = `dialog-${title.replace(/\s+/g, "-")}`;

  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    queueMicrotask(() => {
      const initial = panelRef.current?.querySelector<HTMLElement>("[data-autofocus]")
        ?? panelRef.current?.querySelector<HTMLElement>("button,input,select,textarea,a[href]");
      initial?.focus();
    });
    return () => {
      document.body.style.overflow = previousOverflow;
      openerRef.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && !busy) {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(panelRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]") ?? []);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="dialog-layer" role="presentation">
      <div ref={panelRef} className="dialog-panel" role="dialog" aria-modal="true" aria-labelledby={titleId} onKeyDown={handleKeyDown}>
        <header><p className="page-kicker">Guarded action</p><h2 id={titleId}>{title}</h2></header>
        <div className="dialog-content">{children}</div>
        {footer && <footer>{footer}</footer>}
      </div>
    </div>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  confirmLabel: string;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  children: ReactNode;
  busy?: boolean;
  destructive?: boolean;
};

export function ConfirmDialog({ open, title, confirmLabel, onClose, onConfirm, children, busy = false, destructive = false }: ConfirmDialogProps) {
  return (
    <ModalDialog open={open} title={title} onClose={onClose} busy={busy} footer={<><button type="button" className="secondary-action" data-autofocus onClick={onClose} disabled={busy}>返回</button><button type="button" className={destructive ? "danger-action" : "primary-action"} onClick={() => void onConfirm()} disabled={busy}>{busy ? "等待权威回执…" : confirmLabel}</button></>}>
      <div className="confirm-copy">{children}</div>
    </ModalDialog>
  );
}
