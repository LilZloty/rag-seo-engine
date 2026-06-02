/**
 * Button Component - Example Store Design System
 * 
 * Primary interactive element with multiple variants
 * Uses: #F7B500 brand color, rounded-sm (2px)
 */

'use client';

import React from 'react';
import { SpinnerIcon } from './Icons';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    loading?: boolean;
    icon?: React.ReactNode;
    children?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
    variant = 'primary',
    size = 'md',
    loading = false,
    icon,
    children,
    className = '',
    disabled,
    ...props
}) => {
    const baseStyles = 'inline-flex items-center justify-center font-medium rounded-sm transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-black';

    const variants = {
        primary: 'bg-[#F7B500] text-black hover:bg-[#ffc933] focus:ring-[#F7B500]',
        secondary: 'bg-[#3a3a3a] text-white hover:bg-[#4a4a4a] focus:ring-[#3a3a3a]',
        outline: 'border border-[#3a3a3a] text-white hover:border-[#F7B500] hover:text-[#F7B500] focus:ring-[#F7B500]',
        danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
        ghost: 'text-zinc-400 hover:text-white hover:bg-[#3a3a3a] focus:ring-[#3a3a3a]',
    };

    const sizes = {
        sm: 'px-3 py-1.5 text-sm gap-1.5',
        md: 'px-4 py-2.5 text-sm gap-2',
        lg: 'px-6 py-3 text-base gap-2',
    };

    const isDisabled = disabled || loading;

    return (
        <button
            className={`
        ${baseStyles}
        ${variants[variant]}
        ${sizes[size]}
        ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}
      `}
            disabled={isDisabled}
            {...props}
        >
            {loading ? (
                <SpinnerIcon size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} />
            ) : icon ? (
                <span className="flex-shrink-0">{icon}</span>
            ) : null}
            {children}
        </button>
    );
};

