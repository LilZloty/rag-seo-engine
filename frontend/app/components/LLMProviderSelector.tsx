'use client';

import React, { useState, useEffect, useRef } from 'react';

interface LLMProvider {
    name: string;
    display_name: string;
    model: string;
    factory_provider: string;
    configured: boolean;
    active: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
const BRAND_YELLOW = '#f7b500';

const providerStyles: Record<string, { icon: string }> = {
    'grok-4.3': { icon: '✨' },
    grok: { icon: '🤖' },
    'grok-fast': { icon: '⚡' },
    grok3: { icon: '🤖' },
    'grok3-mini': { icon: '🤖' },
    grok420: { icon: '🧪' },
    anthropic: { icon: '🧠' },
    kimi: { icon: '🌙' },
    mistral: { icon: '🌀' },
    minimax: { icon: '💡' },
    ollama: { icon: '🦙' },
};

/**
 * LLMProviderSelector - Clean Minimal Design
 * 
 * No background containers, clean floating design
 */
export function LLMProviderSelector() {
    const [providers, setProviders] = useState<LLMProvider[]>([]);
    const [activeProvider, setActiveProvider] = useState<string>('');
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        fetchProviders();
    }, []);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const fetchProviders = async () => {
        try {
            const res = await fetch(`${API_BASE}/settings/llm-providers`);
            if (res.ok) {
                const data = await res.json();
                setProviders(data.providers);
                setActiveProvider(data.active);
            }
        } catch (error) {
            console.error('Failed to fetch LLM providers:', error);
        }
    };

    const selectProvider = async (name: string) => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/settings/llm-provider`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: name }),
            });
            if (res.ok) {
                setActiveProvider(name);
                setProviders(prev => prev.map(p => ({ ...p, active: p.name === name })));
                // Notify other components (e.g. generate page) about the change
                const activeInfo = providers.find(p => p.name === name);
                window.dispatchEvent(new CustomEvent('llm-provider-changed', {
                    detail: {
                        provider: name,
                        factory_provider: activeInfo?.factory_provider || name,
                        model: activeInfo?.model,
                    }
                }));
            }
        } catch (error) {
            console.error('Failed to set provider:', error);
        } finally {
            setLoading(false);
            setIsOpen(false);
        }
    };

    const activeProviderInfo = providers.find(p => p.active);
    const style = providerStyles[activeProvider] || { icon: '🤖' };

    return (
        <div ref={dropdownRef} className="relative">
            {/* Trigger - Clean, no background */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                disabled={loading}
                className={`
                    flex items-center gap-2 px-3 py-2
                    text-[#999999] hover:text-white
                    transition-all duration-200
                    disabled:opacity-50
                `}
            >
                <span className="text-base">{style.icon}</span>
                <span className="text-sm font-medium hidden sm:inline">
                    {activeProviderInfo?.display_name || 'IA'}
                </span>
                <svg
                    className={`w-4 h-4 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {/* Dropdown - Clean card */}
            {isOpen && (
                <div 
                    className="absolute right-0 mt-2 w-56 bg-[#0f0f0f] border border-[#1a1a1a] overflow-hidden"
                    style={{ boxShadow: '0 20px 40px -10px rgba(0, 0, 0, 0.9)' }}
                >
                    {/* Provider List */}
                    <div className="py-2">
                        {providers.map((provider) => {
                            const pStyle = providerStyles[provider.name] || { icon: '🤖' };
                            return (
                                <button
                                    key={provider.name}
                                    onClick={() => provider.configured && selectProvider(provider.name)}
                                    disabled={!provider.configured || loading}
                                    className={`
                                        w-full flex items-center gap-3 px-4 py-3
                                        text-left transition-all duration-200
                                        ${provider.active
                                            ? 'text-[#f7b500] bg-[#f7b500]/5'
                                            : provider.configured
                                                ? 'text-[#999999] hover:text-white hover:bg-white/5'
                                                : 'opacity-40 cursor-not-allowed text-[#666666]'
                                        }
                                    `}
                                >
                                    <span className="text-lg">{pStyle.icon}</span>
                                    <div className="flex-1 min-w-0">
                                        <span className="text-sm font-medium block truncate">
                                            {provider.display_name}
                                        </span>
                                        <span className="text-xs text-[#666666] block truncate">
                                            {provider.model}
                                        </span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}

