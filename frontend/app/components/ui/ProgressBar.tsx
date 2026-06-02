/**
 * ProgressBar Component - Example Store Design System
 * 
 * Horizontal progress indicator
 * Uses: #F7B500 brand color for fill, dark background
 */

'use client';

import React from 'react';

interface ProgressBarProps {
    value: number;  // 0-100
    max?: number;
    color?: 'brand' | 'green' | 'blue' | 'red';
    size?: 'sm' | 'md' | 'lg';
    showLabel?: boolean;
    className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
    value,
    max = 100,
    color = 'brand',
    size = 'md',
    showLabel = false,
    className = ''
}) => {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

    const colors = {
        brand: 'bg-[#F7B500]',
        green: 'bg-green-500',
        blue: 'bg-blue-500',
        red: 'bg-red-500',
    };

    const sizes = {
        sm: 'h-1',
        md: 'h-2',
        lg: 'h-3',
    };

    return (
        <div className={`w-full ${className}`}>
            {showLabel && (
                <div className="flex justify-between text-xs text-zinc-400 mb-1">
                    <span>{value}</span>
                    <span>{max}</span>
                </div>
            )}
            <div className={`w-full bg-[#3a3a3a] rounded-sm overflow-hidden ${sizes[size]}`}>
                <div
                    className={`${sizes[size]} ${colors[color]} transition-all duration-500 rounded-sm`}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    );
};

