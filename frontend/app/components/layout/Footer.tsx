'use client';

import React from 'react';

interface FooterProps {
    darkMode: boolean;
}

export function Footer({ darkMode }: FooterProps) {
    const theme = {
        border: darkMode ? 'border-zinc-800' : 'border-zinc-200',
        text: darkMode ? 'text-white' : 'text-zinc-900',
        textMuted: darkMode ? 'text-zinc-500' : 'text-zinc-400',
    };

    return (
        <footer className={`border-t ${theme.border} py-6`}>
            <div className="max-w-7xl mx-auto px-8 flex items-center justify-between">
                <div className="flex items-baseline gap-1">
                    <span className={`font-bold ${theme.text}`}>RAG SEO</span>
                    <span className="font-bold text-[#F7B500]">ENGINE</span>
                    <span className={`${theme.textMuted} ml-2`}>v1.0</span>
                </div>
                <p className={`text-sm ${theme.textMuted}`}>Powered by Claude AI + RAG</p>
            </div>
        </footer>
    );
}
