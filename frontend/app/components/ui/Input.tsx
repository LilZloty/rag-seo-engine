'use client';

import React, { useId } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    icon?: React.ReactNode;
    label?: string;
    error?: string;
}

/**
 * Input Component - Example Store Design System
 * Industrial aesthetic with #F7B500 brand accents
 *
 * Always renders a stable `id` on the underlying <input> — uses the `id`
 * prop when provided, otherwise auto-generates via useId(). Callers can
 * therefore use `<label htmlFor={id}>` for explicit label association.
 */
export const Input: React.FC<InputProps> = ({
    icon,
    label,
    error,
    className = '',
    id: providedId,
    ...props
}) => {
    const generatedId = useId();
    const id = providedId || generatedId;
    return (
        <div className="w-full">
            {label && (
                <label htmlFor={id} className="block text-sm font-medium text-zinc-400 mb-2">
                    {label}
                </label>
            )}
            <div className="relative">
                {icon && (
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-400">
                        {icon}
                    </div>
                )}
                <input
                    id={id}
                    className={`
            w-full px-4 py-3
            ${icon ? 'pl-12' : ''}
            bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm
            text-white placeholder-zinc-500
            focus:outline-none focus:border-[#F7B500] focus:ring-1 focus:ring-[#F7B500]/20
            transition-all
            ${error ? 'border-red-500' : ''}
            ${className}
          `}
                    {...props}
                />
            </div>
            {error && (
                <p className="mt-2 text-sm text-red-400">{error}</p>
            )}
        </div>
    );
};

