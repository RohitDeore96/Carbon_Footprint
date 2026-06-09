/**
 * Toast — Accessible notification component for success/error feedback.
 * Uses aria-live="polite" for screen reader announcements.
 */

/* eslint-disable react-refresh/only-export-components */

import React, { useState, useCallback, useEffect } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ToastVariant = 'success' | 'error' | 'info';

export interface ToastMessage {
  readonly id: string;
  readonly message: string;
  readonly variant: ToastVariant;
}

// ---------------------------------------------------------------------------
// Toast context for global access
// ---------------------------------------------------------------------------

interface ToastContextValue {
  readonly addToast: (message: string, variant: ToastVariant) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = React.useContext(ToastContext);
  if (ctx === null) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Single Toast item
// ---------------------------------------------------------------------------

const AUTO_DISMISS_MS = 4000;

function ToastItem({ toast, onDismiss }: {
  readonly toast: ToastMessage;
  readonly onDismiss: (id: string) => void;
}): React.JSX.Element {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const variantClass = `toast--${toast.variant}`;
  return (
    <div
      role="status"
      aria-live="polite"
      className={`toast ${variantClass}`}
      id={`toast-${toast.id}`}
    >
      <span className="toast-icon" aria-hidden="true">
        {toast.variant === 'success' ? '✓' : toast.variant === 'error' ? '⚠' : 'ℹ'}
      </span>
      <span className="toast-message">{toast.message}</span>
      <button
        type="button"
        className="toast-dismiss"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
      >
        ✕
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toast Provider (wraps the app)
// ---------------------------------------------------------------------------

export function ToastProvider({ children }: { readonly children: React.ReactNode }): React.JSX.Element {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((message: string, variant: ToastVariant): void => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev, { id, message, variant }]);
  }, []);

  const dismissToast = useCallback((id: string): void => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div
        className="toast-container"
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
