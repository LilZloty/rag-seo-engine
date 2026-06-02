'use client';

import { ToastProvider } from './ui/Toast';

// Client-side wrapper for providers that need client-side features
export function Providers({ children }: { children: React.ReactNode }) {
    return (
        <ToastProvider>
            {children}
        </ToastProvider>
    );
}
