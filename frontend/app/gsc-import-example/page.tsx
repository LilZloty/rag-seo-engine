/**
 * Example: GSC Prompt Importer Integration
 * 
 * This page demonstrates how to integrate the GSCPromptImporter
 * component into your AEO dashboard.
 */

'use client';

import React, { useState } from 'react';
import { GSCPromptImporter } from '../components/aeo';
import { Card, Button, Badge } from '../components';

export default function GSCImportPage() {
    const [importCount, setImportCount] = useState(0);

    const handleImportComplete = () => {
        setImportCount(prev => prev + 1);
    };

    return (
        <div className="min-h-screen bg-[#0f0f0f] p-6">
            <div className="max-w-7xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-semibold text-white">
                            🎯 GSC Query Import
                        </h1>
                        <p className="text-zinc-400 mt-1">
                            Import Google Search Console queries into your Prompt Library
                        </p>
                    </div>
                    {importCount > 0 && (
                        <Badge className="bg-green-500/20 text-green-400 border-green-500/50">
                            {importCount} batch(es) imported
                        </Badge>
                    )}
                </div>

                {/* Info Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Card className="bg-[#1a1a1a] border-[#333] p-4">
                        <div className="flex items-start gap-3">
                            <div className="size-10 rounded-full bg-blue-500/20 flex items-center justify-center shrink-0">
                                <span className="text-blue-400 text-lg">📊</span>
                            </div>
                            <div>
                                <h3 className="text-white font-medium">Real User Data</h3>
                                <p className="text-zinc-400 text-sm mt-1">
                                    Import actual search queries your users type into Google
                                </p>
                            </div>
                        </div>
                    </Card>

                    <Card className="bg-[#1a1a1a] border-[#333] p-4">
                        <div className="flex items-start gap-3">
                            <div className="size-10 rounded-full bg-[#F7B500]/20 flex items-center justify-center shrink-0">
                                <span className="text-[#F7B500] text-lg">🎯</span>
                            </div>
                            <div>
                                <h3 className="text-white font-medium">High Opportunity</h3>
                                <p className="text-zinc-400 text-sm mt-1">
                                    Target queries where you rank 5-20 with low CTR
                                </p>
                            </div>
                        </div>
                    </Card>

                    <Card className="bg-[#1a1a1a] border-[#333] p-4">
                        <div className="flex items-start gap-3">
                            <div className="size-10 rounded-full bg-green-500/20 flex items-center justify-center shrink-0">
                                <span className="text-green-400 text-lg">🤖</span>
                            </div>
                            <div>
                                <h3 className="text-white font-medium">AI Visibility</h3>
                                <p className="text-zinc-400 text-sm mt-1">
                                    Track if LLMs recommend you for these queries
                                </p>
                            </div>
                        </div>
                    </Card>
                </div>

                {/* Main Component */}
                <GSCPromptImporter onImportComplete={handleImportComplete} />

                {/* API Documentation */}
                <Card className="bg-[#1a1a1a] border-[#333] p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">API Endpoints</h3>
                    <div className="space-y-3 text-sm">
                        <div className="bg-[#0f0f0f] p-3 rounded-sm font-mono">
                            <span className="text-green-400">GET</span>
                            <span className="text-zinc-300 ml-2">/api/v1/aeo/visibility/prompts/gsc-suggestions</span>
                            <p className="text-zinc-500 mt-1">Get GSC query suggestions for import</p>
                        </div>
                        <div className="bg-[#0f0f0f] p-3 rounded-sm font-mono">
                            <span className="text-yellow-400">POST</span>
                            <span className="text-zinc-300 ml-2">/api/v1/aeo/visibility/prompts/import-from-gsc</span>
                            <p className="text-zinc-500 mt-1">Import selected queries to library</p>
                        </div>
                        <div className="bg-[#0f0f0f] p-3 rounded-sm font-mono">
                            <span className="text-yellow-400">POST</span>
                            <span className="text-zinc-300 ml-2">/api/v1/aeo/visibility/prompts/bulk-import-gsc</span>
                            <p className="text-zinc-500 mt-1">Auto-import top 20 opportunities</p>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
}
