'use client';

import React from 'react';
import { Button, Card, Badge } from '../';
import { RefreshIcon } from '../ui/Icons';
import { FaultCode, Solution, RecommendedProduct } from '@/lib/api';

interface AEOKnowledgeGraphProps {
    faultCodes: FaultCode[];
    solutions: Solution[];
    productsByFaultCode: Record<string, RecommendedProduct[]>;
    onSync: () => void;
    onRefresh: () => void;
    syncing: boolean;
}

export const AEOKnowledgeGraph: React.FC<AEOKnowledgeGraphProps> = ({
    faultCodes,
    solutions,
    productsByFaultCode,
    onSync,
    onRefresh,
    syncing
}) => {
    const getSeverityBadge = (severity: string) => {
        const variants = {
            high: 'danger' as const,
            medium: 'warning' as const,
            low: 'success' as const,
        };
        return <Badge variant={variants[severity as keyof typeof variants] || 'default'}>{severity}</Badge>;
    };

    return (
        <Card
            title="Technical Knowledge Graph (GEO)"
            subtitle="Mapping technical issues (Fault Codes) to product solutions (SKUs)"
            action={
                <div className="flex gap-2">
                    <Button
                        variant={syncing ? 'secondary' : 'primary'}
                        size="sm"
                        onClick={onSync}
                        loading={syncing}
                        icon={<RefreshIcon size={16} />}
                    >
                        {syncing ? 'Syncing...' : 'Sync Graph'}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onRefresh}
                        icon={<RefreshIcon size={16} />}
                    >
                        Refresh
                    </Button>
                </div>
            }
        >
            <div className="space-y-4">
                {faultCodes.map((fc) => {
                    const fcSolutions = solutions.filter(s => s.fault_code === fc.code);
                    const products = productsByFaultCode[fc.code] || [];

                    return (
                        <div
                            key={fc.code}
                            className="bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm overflow-hidden"
                        >
                            <div className="p-5 bg-[#1a1a1a]/50 border-b border-[#3a3a3a] flex justify-between items-center">
                                <div className="flex items-center gap-4">
                                    <span className="text-3xl font-mono font-bold text-[#F7B500]">{fc.code}</span>
                                    <div>
                                        <h3 className="font-semibold text-white text-lg">{fc.name}</h3>
                                        <div className="flex items-center gap-2 text-sm text-zinc-400 mt-1">
                                            <span className="px-2 py-0.5 bg-[#3a3a3a] rounded text-zinc-400">
                                                {fc.monthly_clicks.toLocaleString()} clicks/mo
                                            </span>
                                            <span>•</span>
                                            <span className="truncate max-w-[200px]">{fc.transmissions.slice(0, 3).join(', ')}...</span>
                                        </div>
                                    </div>
                                </div>
                                {getSeverityBadge(fc.severity)}
                            </div>

                            <div className="p-5">
                                <p className="text-zinc-300 text-sm mb-6 leading-relaxed">{fc.description}</p>

                                <div className="space-y-3">
                                    <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                                        Recommended Products (Real Inventory)
                                    </h4>

                                    {products.length === 0 ? (
                                        <p className="text-sm text-zinc-500 italic">
                                            No products found for transmissions: {fc.transmissions.slice(0, 3).join(', ')}
                                        </p>
                                    ) : (
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                            {products.map((product) => (
                                                <div
                                                    key={product.id}
                                                    className="bg-[#1a1a1a] border border-[#3a3a3a] p-4 rounded-sm"
                                                >
                                                    <h5 className="font-medium text-[#F7B500] text-sm mb-2 line-clamp-2">
                                                        {product.title}
                                                    </h5>
                                                    <div className="flex items-center gap-2 text-xs text-zinc-400 mb-2">
                                                        <span className="font-mono bg-[#F7B500]/10 text-[#F7B500] px-2 py-0.5 rounded">
                                                            {product.sku}
                                                        </span>
                                                        {product.price && <span>${product.price}</span>}
                                                    </div>
                                                    <div className="flex items-center justify-between text-xs text-zinc-500">
                                                        <span>{product.vendor}</span>
                                                        <span>{product.total_sold} sold</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </Card>
    );
};
