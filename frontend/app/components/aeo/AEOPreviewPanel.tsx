'use client';

import React from 'react';
import { Button, Card } from '../';
import { CopyIcon, RefreshIcon, DownloadIcon } from '../ui/Icons';
import { LLMSTxtPreview } from '@/lib/api';

interface AEOPreviewPanelProps {
    preview: LLMSTxtPreview | null;
    onCopy: () => void;
    onRebuild: () => void;
    onDownload: () => void;
    copied: boolean;
    loading: boolean;
}

export const AEOPreviewPanel: React.FC<AEOPreviewPanelProps> = ({
    preview,
    onCopy,
    onRebuild,
    onDownload,
    copied,
    loading
}) => {
    return (
        <Card
            title="llms.txt Preview"
            subtitle="AI-optimized content file for answer engines"
            action={
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onCopy}
                        icon={<CopyIcon size={16} />}
                    >
                        {copied ? 'Copied!' : 'Copy'}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onRebuild}
                        icon={<RefreshIcon size={16} />}
                    >
                        Rebuild
                    </Button>
                    <Button
                        variant="primary"
                        size="sm"
                        onClick={onDownload}
                        icon={<DownloadIcon size={16} />}
                    >
                        Download
                    </Button>
                </div>
            }
        >
            <div className="bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm p-6 max-h-[500px] overflow-auto">
                <pre className="whitespace-pre-wrap text-sm text-zinc-300 font-mono">
                    {preview?.content || 'No content generated. Approve some chunks first.'}
                </pre>
            </div>
        </Card>
    );
};
