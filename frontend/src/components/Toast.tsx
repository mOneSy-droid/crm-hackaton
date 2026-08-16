import { Check, X, AlertTriangle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export type ToastKind = "success" | "error";

export function useToast() {
  const [toast, setToast] = useState<{ text: string; kind: ToastKind } | null>(null);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(timer);
  }, [toast]);

  const show = useCallback((text: string, kind: ToastKind = "success") => {
    setToast({ text, kind });
  }, []);

  const dismiss = useCallback(() => setToast(null), []);

  return { toast, show, dismiss };
}

export function Toast({
  toast,
  dismiss,
}: {
  toast: { text: string; kind: ToastKind } | null;
  dismiss: () => void;
}) {
  if (!toast) return null;
  return (
    <div className="toast" role="status">
      <span className="toast-mark" style={toast.kind === "error" ? { background: "#ef4444" } : undefined}>
        {toast.kind === "error" ? <AlertTriangle size={14} /> : <Check size={14} />}
      </span>
      {toast.text}
      <button onClick={dismiss} aria-label="Yopish">
        <X size={14} />
      </button>
    </div>
  );
}
