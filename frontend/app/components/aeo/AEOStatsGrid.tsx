'use client';

import React from 'react';
import { ChipIcon, CheckIcon, SparklesIcon, DatabaseIcon } from '../ui/Icons';

interface AEOStatsGridProps {
    totalChunks: number;
    approvedChunks: number;
    tokenEstimate: number;
    fileSizeKB: number;
}

export const AEOStatsGrid: React.FC<AEOStatsGridProps> = ({
    totalChunks,
    approvedChunks,
    tokenEstimate,
    fileSizeKB
}) => {
    return (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                <div className="flex items-center gap-3">
                    <div className="p-3 bg-[#F7B500]/10 rounded-sm">
                        <ChipIcon className="text-[#F7B500]" size={24} />
                    </div>
                    <div>
                        <p className="text-sm text-zinc-400">Total Chunks</p>
                        <p className="text-2xl font-bold text-white">{totalChunks}</p>
                    </div>
                </div>
            </div>

            <div className="bg-[#1a1a1a] rounded-sm border border-[#F7B500]/50 p-6">
                <div className="flex items-center gap-3">
                    <div className="p-3 bg-[#F7B500]/20 rounded-sm">
                        <CheckIcon className="text-[#F7B500]" size={24} />
                    </div>
                    <div>
                        <p className="text-sm text-zinc-400">Approved</p>
                        <p className="text-2xl font-bold text-[#F7B500]">{approvedChunks}</p>
                    </div>
                </div>
            </div>

            <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                <div className="flex items-center gap-3">
                    <div className="p-3 bg-green-500/10 rounded-sm">
                        <SparklesIcon className="text-green-400" size={24} />
                    </div>
                    <div>
                        <p className="text-sm text-zinc-400">Token Estimate</p>
                        <p className="text-2xl font-bold text-white">{tokenEstimate.toLocaleString()}</p>
                    </div>
                </div>
            </div>

            <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                <div className="flex items-center gap-3">
                    <div className="p-3 bg-blue-500/10 rounded-sm">
                        <DatabaseIcon className="text-blue-400" size={24} />
                    </div>
                    <div>
                        <p className="text-sm text-zinc-400">File Size</p>
                        <p className="text-2xl font-bold text-white">{fileSizeKB.toFixed(1)} KB</p>
                    </div>
                </div>
            </div>
        </div>
    );
};
