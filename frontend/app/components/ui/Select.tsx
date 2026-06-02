'use client';

import React, { useId } from 'react';

interface SelectOption {
    value: string;
    label: string;
}

interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
    options: SelectOption[];
    label?: string;
    error?: string;
}

/**
 * Select Component - Example Store Design System
 * Industrial aesthetic with #F7B500 brand accents
 *
 * Renders a stable `id` on the underlying <select> — uses the `id` prop
 * when provided, otherwise auto-generates via useId(). Callers can use
 * `<label htmlFor={id}>` for explicit label association.
 */
export const Select: React.FC<SelectProps> = ({
    options,
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
            <select
                id={id}
                className={`
          w-full px-4 py-3 
          bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm
          text-white
          focus:outline-none focus:border-[#F7B500] focus:ring-1 focus:ring-[#F7B500]/20
          transition-all
          appearance-none
          cursor-pointer
          ${error ? 'border-red-500' : ''}
          ${className}
        `}
                style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%239ca3af'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`,
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'right 12px center',
                    backgroundSize: '20px',
                    paddingRight: '44px'
                }}
                {...props}
            >
                {options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
            {error && (
                <p className="mt-2 text-sm text-red-400">{error}</p>
            )}
        </div>
    );
};

