'use client';

import React from 'react';
import { Button, Card, Badge } from '../';
import { CheckIcon, XIcon, RefreshIcon } from '../ui/Icons';
import { ProductChunk as APIProductChunk } from '@/lib/api';

interface AEOChunksGridProps {
    chunks: APIProductChunk[];
    onApprove: (productType: string, approved: boolean) => void;
    onAutoApprove: () => void;
    onRefresh: () => void;
    loading: boolean;
}

export const AEOChunksGrid: React.FC<AEOChunksGridProps> = ({
    chunks,
    onApprove,
    onAutoApprove,
    onRefresh,
    loading
}) => {
    return (
        <Card
            title="Product Type Chunks"
            subtitle="Manage content chunks by product category"
            action={
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onAutoApprove}
                        icon={<CheckIcon size={16} />}
                    >
                        Auto-Approve Top 15
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
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {chunks.map((chunk) => (
                    <div
                        key={chunk.product_type}
                        className={`p-5 rounded-sm border transition-all ${chunk.approved
                            ? 'bg-[#0a0a0a] border-[#F7B500]'
                            : 'bg-[#0a0a0a] border-[#3a3a3a]'
                            }`}
                    >
                        <div className="flex justify-between items-start mb-3">
                            <h3 className="font-semibold text-lg text-white">{chunk.product_type}</h3>
                            {chunk.approved && (
                                <Badge variant="success">Approved</Badge>
                            )}
                        </div>
                        <p className="text-zinc-400 text-sm mb-4">
                            {chunk.product_count} products
                        </p>
                        <div className="flex gap-2">
                            <Button
                                variant={chunk.approved ? 'secondary' : 'primary'}
                                size="sm"
                                className="flex-1"
                                onClick={() => onApprove(chunk.product_type, true)}
                                disabled={chunk.approved}
                                icon={<CheckIcon size={16} />}
                            >
                                Approve
                            </Button>
                            <Button
                                variant={!chunk.approved ? 'secondary' : 'danger'}
                                size="sm"
                                className="flex-1"
                                onClick={() => onApprove(chunk.product_type, false)}
                                disabled={!chunk.approved}
                                icon={<XIcon size={16} />}
                            >
                                Reject
                            </Button>
                        </div>
                    </div>
                ))}
            </div>
        </Card>
    );
};
