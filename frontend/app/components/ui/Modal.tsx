'use client';

import React, { useEffect, useRef } from 'react';
import { XIcon } from './Icons';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title?: string;
    children: React.ReactNode;
    size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
    showCloseButton?: boolean;
}

/**
 * Modal Component - Example Store Design System
 * Industrial aesthetic with #F7B500 brand accents
 */
export const Modal: React.FC<ModalProps> = ({
    isOpen,
    onClose,
    title,
    children,
    size = 'md',
    showCloseButton = true,
}) => {
    const modalRef = useRef<HTMLDivElement>(null);

    // Handle escape key
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                onClose();
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [isOpen, onClose]);

    // Prevent body scroll when modal is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => {
            document.body.style.overflow = 'unset';
        };
    }, [isOpen]);

    // Handle click outside
    const handleBackdropClick = (e: React.MouseEvent | React.KeyboardEvent) => {
        if (e.target === e.currentTarget) {
            onClose();
        }
    };

    // Keyboard fallback for click-outside-to-dismiss — Escape is primary
    // (handled above); this satisfies a11y when the backdrop itself is focused.
    const handleBackdropKeyDown = (e: React.KeyboardEvent) => {
        if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) {
            e.preventDefault();
            onClose();
        }
    };

    if (!isOpen) return null;

    const sizeClasses = {
        sm: 'max-w-sm',
        md: 'max-w-md',
        lg: 'max-w-2xl',
        xl: 'max-w-4xl',
        full: 'max-w-[90vw]',
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
            onClick={handleBackdropClick}
            onKeyDown={handleBackdropKeyDown}
            role="presentation"
        >
            <div
                ref={modalRef}
                role="dialog"
                aria-modal="true"
                aria-label={title || "Modal dialog"}
                className={`
          ${sizeClasses[size]} w-full
          bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm
          shadow-2xl shadow-black/50
          animate-in fade-in zoom-in-95 duration-200
          max-h-[90vh] overflow-hidden flex flex-col
        `}
            >
                {/* Header */}
                {(title || showCloseButton) && (
                    <div className="flex items-center justify-between px-6 py-4 border-b border-[#3a3a3a]">
                        {title && (
                            <h2 className="text-lg font-semibold text-white">{title}</h2>
                        )}
                        {showCloseButton && (
                            <button
                                onClick={onClose}
                                className="p-2 text-zinc-400 hover:text-white hover:bg-[#3a3a3a] rounded-sm transition-colors ml-auto"
                                aria-label="Close modal"
                            >
                                <XIcon size={20} />
                            </button>
                        )}
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {children}
                </div>
            </div>
        </div>
    );
};

