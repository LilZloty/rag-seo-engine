'use client';

import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckIcon, XIcon, WarningIcon, InfoIcon } from './Icons';

// Toast types
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
    id: string;
    type: ToastType;
    message: string;
    duration?: number;
}

interface ToastContextValue {
    toasts: Toast[];
    addToast: (type: ToastType, message: string, duration?: number) => void;
    removeToast: (id: string) => void;
    // Convenience methods
    success: (message: string, duration?: number) => void;
    error: (message: string, duration?: number) => void;
    warning: (message: string, duration?: number) => void;
    info: (message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

// Toast Provider Component
export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const removeToast = useCallback((id: string) => {
        setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, []);

    const addToast = useCallback((type: ToastType, message: string, duration = 4000) => {
        const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const newToast: Toast = { id, type, message, duration };

        setToasts((prev) => [...prev, newToast]);

        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => {
                removeToast(id);
            }, duration);
        }

        return id;
    }, [removeToast]);

    // Convenience methods
    const success = useCallback((message: string, duration?: number) => {
        addToast('success', message, duration);
    }, [addToast]);

    const error = useCallback((message: string, duration?: number) => {
        addToast('error', message, duration ?? 6000); // Errors stay longer
    }, [addToast]);

    const warning = useCallback((message: string, duration?: number) => {
        addToast('warning', message, duration);
    }, [addToast]);

    const info = useCallback((message: string, duration?: number) => {
        addToast('info', message, duration);
    }, [addToast]);

    return (
        <ToastContext.Provider value={{ toasts, addToast, removeToast, success, error, warning, info }}>
            {children}
            <ToastContainer toasts={toasts} removeToast={removeToast} />
        </ToastContext.Provider>
    );
}

// Hook to use toast
export function useToast() {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
}

// Toast Container Component
function ToastContainer({
    toasts,
    removeToast
}: {
    toasts: Toast[];
    removeToast: (id: string) => void;
}) {
    if (toasts.length === 0) return null;

    return (
        <div className="toast-container">
            {toasts.map((toast) => (
                <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
            ))}
        </div>
    );
}

// Individual Toast Item
function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
    const getIcon = () => {
        switch (toast.type) {
            case 'success':
                return <CheckIcon className="text-green-400" size={18} />;
            case 'error':
                return <XIcon className="text-red-400" size={18} />;
            case 'warning':
                return <WarningIcon className="text-yellow-400" size={18} />;
            case 'info':
                return <InfoIcon className="text-blue-400" size={18} />;
        }
    };

    const getBorderColor = () => {
        switch (toast.type) {
            case 'success':
                return 'border-l-green-400';
            case 'error':
                return 'border-l-red-400';
            case 'warning':
                return 'border-l-[#F7B500]';
            case 'info':
                return 'border-l-blue-400';
        }
    };

    return (
        <div
            className={`
        flex items-center gap-3 
        px-4 py-3 
        bg-[#1a1a1a] 
        border border-[#333] 
        border-l-[3px] ${getBorderColor()}
        shadow-lg shadow-black/40
        animate-slide-right
        min-w-[300px] max-w-[400px]
      `}
        >
            {getIcon()}
            <p className="flex-1 text-sm text-white">{toast.message}</p>
            <button
                onClick={onClose}
                className="text-zinc-500 hover:text-white transition-colors p-1"
                aria-label="Cerrar notificacion"
            >
                <XIcon size={14} />
            </button>
        </div>
    );
}

// Re-export for direct usage
export { ToastContext };
