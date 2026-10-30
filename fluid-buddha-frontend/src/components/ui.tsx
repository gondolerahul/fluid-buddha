"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

// ---- Toast -----------------------------------------------------------------
type Toast = { id: number; msg: string; kind: "ok" | "err" };
const ToastCtx = createContext<(msg: string, kind?: "ok" | "err") => void>(() => {});

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((msg: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind === "err" ? "err" : ""}`}>
          {t.msg}
        </div>
      ))}
    </ToastCtx.Provider>
  );
}
export function useToast() {
  return useContext(ToastCtx);
}

// ---- Spinner / loading -----------------------------------------------------
export function Spinner() {
  return <span className="spin" aria-label="loading" />;
}
export function LoadingScreen() {
  return (
    <div className="center-screen">
      <Spinner />
    </div>
  );
}

// ---- Modal -----------------------------------------------------------------
export function Modal({
  open,
  onClose,
  title,
  children,
  width = 520,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  width?: number;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(4px)",
        display: "grid",
        placeItems: "center",
        zIndex: 40,
        padding: 20,
        animation: "fade 0.2s ease",
      }}
      onClick={onClose}
    >
      <div
        className="card fade-in"
        style={{ width, maxWidth: "100%", maxHeight: "88vh", overflow: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="row between" style={{ marginBottom: 18 }}>
          <h2>{title}</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---- Badge helpers ---------------------------------------------------------
export function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "ingested" || status === "active"
      ? "ok"
      : status === "failed"
      ? "err"
      : status === "pending"
      ? "warn"
      : "";
  return (
    <span className={`badge ${cls}`}>
      <span className="dot" /> {status}
    </span>
  );
}

export function fmtUSD(n: number): string {
  if (n === 0) return "$0";
  if (n < 0.01) return "$" + n.toFixed(5);
  if (n < 1) return "$" + n.toFixed(4);
  return "$" + n.toFixed(2);
}
export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
