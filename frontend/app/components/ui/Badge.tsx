/**
 * Badge Component - Example Store Design System
 * 
 * Small label/tag for status indicators
 * Uses: Various color variants with subtle backgrounds
 */

'use client';

import React from 'react';

interface BadgeProps {
    variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'brand' | 'outline';
    className?: string;
    style?: React.CSSProperties;
    children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
    variant = 'default',
    className = '',
    style,
    children
}) => {
    const variants = {
        default: 'bg-[#3a3a3a] text-zinc-300',
        success: 'bg-green-500/20 text-green-400',
        warning: 'bg-yellow-500/20 text-yellow-400',
        danger: 'bg-red-500/20 text-red-400',
        info: 'bg-blue-500/20 text-blue-400',
        brand: 'bg-[#F7B500]/20 text-[#F7B500]',
        outline: 'bg-transparent border border-[#3a3a3a] text-zinc-300',
    };

    return (
        <span
            style={style}
            className={`
        inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm
        ${variants[variant]}
        ${className}
      `}
        >
            {children}
        </span>
    );
};

