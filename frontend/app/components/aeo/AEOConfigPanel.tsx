'use client';

import React from 'react';
import { Card } from '../';
import { AEOConfig } from '@/lib/api';

interface AEOConfigPanelProps {
    config: AEOConfig | null;
}

export const AEOConfigPanel: React.FC<AEOConfigPanelProps> = ({ config }) => {
    if (!config) return null;

    return (
        <Card
            title="AEO Configuration"
            subtitle="Settings for your AI optimization"
        >
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                    <label className="block">
                        <span className="block text-sm text-zinc-400 mb-2">Store Name</span>
                        <input
                            type="text"
                            value={config.store_name}
                            className="w-full bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm px-5 py-4 text-white focus:border-[#F7B500] focus:outline-none"
                            readOnly
                        />
                    </label>
                    <label className="block">
                        <span className="block text-sm text-zinc-400 mb-2">Store Description</span>
                        <textarea
                            value={config.store_description}
                            className="w-full bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm px-5 py-4 text-white h-32 focus:border-[#F7B500] focus:outline-none resize-none"
                            readOnly
                        />
                    </label>
                </div>

                <div className="space-y-4">
                    <div className="flex items-center justify-between bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm px-5 py-4">
                        <span className="text-zinc-300">Include Blogs</span>
                        <span className={config.include_blogs ? 'text-[#F7B500] font-medium' : 'text-zinc-600'}>
                            {config.include_blogs ? 'Yes' : 'No'}
                        </span>
                    </div>
                    <div className="flex items-center justify-between bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm px-5 py-4">
                        <span className="text-zinc-300">Include Collections</span>
                        <span className={config.include_collections ? 'text-[#F7B500] font-medium' : 'text-zinc-600'}>
                            {config.include_collections ? 'Yes' : 'No'}
                        </span>
                    </div>
                    <div className="flex items-center justify-between bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm px-5 py-4">
                        <span className="text-zinc-300">Max Products Per Category</span>
                        <span className="font-mono text-[#F7B500] text-lg">{config.max_products_per_category}</span>
                    </div>
                </div>
            </div>
        </Card>
    );
};
