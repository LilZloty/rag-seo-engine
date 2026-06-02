/**
 * Tabs Component
 * 
 * A horizontal tab navigation component with icons
 * Uses Example Store Design System: #F7B500 brand color, rounded-sm (2px)
 */

'use client';

import React from 'react';

interface Tab {
    id: string;
    label: string;
    icon?: React.ReactNode;
}

interface TabsProps {
    tabs: Tab[];
    activeTab: string;
    onChange: (tabId: string) => void;
    className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
    tabs,
    activeTab,
    onChange,
    className = ''
}) => {
    return (
        <div className={`flex flex-wrap gap-2 border-b border-[#3a3a3a] pb-4 ${className}`}>
            {tabs.map((tab) => (
                <button
                    key={tab.id}
                    onClick={() => onChange(tab.id)}
                    className={`
            flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-sm transition-all
            ${activeTab === tab.id
                            ? 'bg-[#F7B500] text-black'
                            : 'bg-[#1a1a1a] text-zinc-400 hover:text-white hover:bg-[#2a2a2a]'
                        }
          `}
                >
                    {tab.icon && <span className="size-5">{tab.icon}</span>}
                    {tab.label}
                </button>
            ))}
        </div>
    );
};

