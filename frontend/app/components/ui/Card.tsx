/**
 * Card Component - Example Store Design System
 * 
 * Container component with optional title, subtitle, and action slot
 * Uses: Dark theme, rounded-sm (2px), #3a3a3a borders
 */

'use client';

import React from 'react';

interface CardProps {
    title?: React.ReactNode;
    subtitle?: React.ReactNode;
    action?: React.ReactNode;
    accent?: boolean;
    className?: string;
    children?: React.ReactNode;
    icon?: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
    title,
    subtitle,
    action,
    accent = false,
    className = '',
    children,
    icon
}) => {
    return (
        <div
            className={`
        bg-[#1a1a1a] rounded-sm border 
        ${accent ? 'border-[#F7B500]/50' : 'border-[#3a3a3a]'}
        ${className}
      `}
        >
            {(title || action || icon) && (
                <div className="flex items-center justify-between px-6 py-4 border-b border-[#3a3a3a]">
                    <div className="flex items-center gap-3">
                        {icon && <div>{icon}</div>}
                        <div>
                            {title && <h3 className="text-lg font-semibold text-white">{title}</h3>}
                            {subtitle && <p className="text-sm text-zinc-400 mt-0.5">{subtitle}</p>}
                        </div>
                    </div>
                    {action && <div>{action}</div>}
                </div>
            )}
            <div className="p-6">
                {children}
            </div>
        </div>
    );
};

