'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { formatDateTime } from '@/app/lib/dates';
import { optimizerAPI, collectionsAIAPI, CollectionOptimizer } from '../../../../lib/api';
import { CannibalizationGuard } from '../../../components/seo/collections/CannibalizationGuard';
import { CollectionRecommendations } from '../../../components/seo/collections/CollectionRecommendations';
import { CollectionContentDrafts } from '../../../components/seo/collections/CollectionContentDrafts';
import { CollectionTrends } from '../../../components/seo/collections/CollectionTrends';

// Icons
const ArrowLeft = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
);

const ExternalLink = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
);

const RefreshIcon = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
);

const SparklesIcon = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
    </svg>
);

const CheckIcon = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
);

const LoadingSpinner = () => (
    <svg className="animate-spin size-4" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
);

// Status badge component
const STATUS_COLORS: Record<string, string> = {
    pending:   'bg-[#333333] text-[#888888]',
    analyzed:  'bg-blue-500/20 text-blue-400',
    ready:     'bg-[#f7b500]/20 text-[#f7b500]',
    published: 'bg-green-500/20 text-green-400',
};

const StatusBadge = ({ status }: { status: string }) => (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status] || STATUS_COLORS.pending}`}>
        {status}
    </span>
);

// Types for generated content
interface GeneratedContent {
    educational_content: string;
    faq: Array<{ question: string; answer: string; source_query?: string }>;
    schema_markup: string;
    generated_at: string;
}

interface CollectionQueries {
    collection_id: number;
    queries: Array<{
        query: string;
        clicks: number;
        impressions: number;
        ctr: number;
        position: number;
        type: string;
        intent: string;
        priority_score: number;
    }>;
}

export default function CollectionDetailPage() {
    const params = useParams();
    const router = useRouter();
    const collectionId = Number(params.id);

    const [collection, setCollection] = useState<CollectionOptimizer | null>(null);
    const [queries, setQueries] = useState<CollectionQueries | null>(null);
    const [generatedContent, setGeneratedContent] = useState<GeneratedContent | null>(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Load collection data
    const loadCollection = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await optimizerAPI.getCollection(collectionId);
            setCollection(data);
        } catch (err: any) {
            console.error('Failed to load collection:', err);
            setError(err.message || 'Failed to load collection. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    // Load collection queries
    const loadQueries = async () => {
        try {
            const data = await optimizerAPI.getCollectionQueries(collectionId);
            setQueries(data);
        } catch (err) {
            console.error('Failed to load queries:', err);
        }
    };

    // Load preview content if available
    const loadPreview = async () => {
        try {
            const data = await optimizerAPI.previewContent(collectionId);
            setGeneratedContent(data);
        } catch (err) {
            // Preview might not exist yet, that's ok
            console.log('No preview content yet');
        }
    };

    useEffect(() => {
        if (collectionId) {
            loadCollection();
            loadQueries();
            loadPreview();
        }
    }, [collectionId]);

    // Analyze collection
    const handleAnalyze = async () => {
        setActionLoading('analyze');
        setError(null);
        try {
            await optimizerAPI.analyzeCollection(collectionId);
            setSuccess('Analysis complete!');
            await loadCollection();
            await loadQueries();
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            setError(err.message || 'Analysis failed');
        } finally {
            setActionLoading(null);
        }
    };

    // Generate content
    const handleGenerate = async () => {
        setActionLoading('generate');
        setError(null);
        try {
            await optimizerAPI.generateContent(collectionId);
            setSuccess('Content generated!');
            await loadCollection();
            await loadPreview();
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            setError(err.message || 'Generation failed');
        } finally {
            setActionLoading(null);
        }
    };

    // Deploy content
    const handleDeploy = async (dryRun: boolean = true) => {
        setActionLoading(dryRun ? 'preview-deploy' : 'deploy');
        setError(null);
        try {
            const result = await optimizerAPI.deployContent(collectionId, dryRun);
            if (dryRun) {
                setSuccess('Deployment preview ready! Check Shopify admin for changes.');
            } else {
                setSuccess('Content deployed to Shopify!');
                await loadCollection();
            }
            setTimeout(() => setSuccess(null), 5000);
        } catch (err: any) {
            setError(err.message || 'Deployment failed');
        } finally {
            setActionLoading(null);
        }
    };

    // Run full workflow
    const handleWorkflow = async () => {
        setActionLoading('workflow');
        setError(null);
        try {
            await optimizerAPI.runWorkflow(collectionId);
            setSuccess('Full workflow complete!');
            await loadCollection();
            await loadQueries();
            await loadPreview();
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            setError(err.message || 'Workflow failed');
        } finally {
            setActionLoading(null);
        }
    };

    // Run DataForSEO
    const handleDataForSEO = async () => {
        setActionLoading('dataforseo');
        setError(null);
        try {
            await optimizerAPI.runDataForSEOCollection(collectionId);
            setSuccess('DataForSEO sync complete!');
            await loadCollection();
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            setError(err.message || 'DataForSEO sync failed');
        } finally {
            setActionLoading(null);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-[#0a0a0a] text-white flex items-center justify-center">
                <div className="flex items-center gap-3">
                    <LoadingSpinner />
                    <span className="text-[#888888]">Loading collection…</span>
                </div>
            </div>
        );
    }

    if (error && !collection) {
        return (
            <div className="min-h-screen bg-[#0a0a0a] text-white flex items-center justify-center">
                <div className="text-center">
                    <p className="text-red-400 mb-4">{error}</p>
                    <Link href="/seo/collections" className="text-[#f7b500] hover:underline">
                        Back to collections
                    </Link>
                </div>
            </div>
        );
    }

    if (!collection) return null;

    const shopifyUrl = `https://example-store.com/collections/${collection.handle}`;

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white">
            {/* Header */}
            <div className="border-b border-[#222]">
                <div className="max-w-[1400px] mx-auto px-6 py-4">
                    <div className="flex items-center gap-4 mb-4">
                        <Link href="/seo/collections" className="flex items-center gap-1 text-[#888888] hover:text-white transition-colors text-sm">
                            <ArrowLeft />
                            Collections
                        </Link>
                        <span className="text-[#444444]">/</span>
                        <StatusBadge status={collection.status} />
                    </div>

                    <div className="flex items-start justify-between">
                        <div>
                            <h1 className="text-3xl font-semibold text-white mb-2">{collection.title}</h1>
                            <p className="text-[#666666]">/{collection.handle} · {collection.category}</p>
                        </div>
                        <div className="flex items-center gap-3">
                            <a
                                href={shopifyUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] border border-[#333333] rounded-lg text-white hover:border-[#555555] transition-colors text-sm"
                            >
                                View Live
                                <ExternalLink />
                            </a>
                        </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-wrap items-center gap-3 mt-6">
                        {collection.status === 'pending' && (
                            <button
                                onClick={handleAnalyze}
                                disabled={!!actionLoading}
                                className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-lg hover:bg-blue-500/30 transition-colors text-sm font-medium disabled:opacity-50"
                            >
                                {actionLoading === 'analyze' ? <LoadingSpinner /> : <RefreshIcon />}
                                Analyze GSC Data
                            </button>
                        )}

                        {collection.status === 'analyzed' && (
                            <button
                                onClick={handleGenerate}
                                disabled={!!actionLoading}
                                className="flex items-center gap-2 px-4 py-2 bg-[#f7b500]/20 text-[#f7b500] border border-[#f7b500]/30 rounded-lg hover:bg-[#f7b500]/30 transition-colors text-sm font-medium disabled:opacity-50"
                            >
                                {actionLoading === 'generate' ? <LoadingSpinner /> : <SparklesIcon />}
                                Generate Content
                            </button>
                        )}

                        {collection.status === 'ready' && (
                            <>
                                <button
                                    onClick={() => handleDeploy(true)}
                                    disabled={!!actionLoading}
                                    className="flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] border border-[#333333] text-white rounded-lg hover:border-[#555555] transition-colors text-sm font-medium disabled:opacity-50"
                                >
                                    {actionLoading === 'preview-deploy' ? <LoadingSpinner /> : null}
                                    Preview Deploy
                                </button>
                                <button
                                    onClick={() => handleDeploy(false)}
                                    disabled={!!actionLoading}
                                    className="flex items-center gap-2 px-4 py-2 bg-green-500/20 text-green-400 border border-green-500/30 rounded-lg hover:bg-green-500/30 transition-colors text-sm font-medium disabled:opacity-50"
                                >
                                    {actionLoading === 'deploy' ? <LoadingSpinner /> : <CheckIcon />}
                                    Deploy to Shopify
                                </button>
                            </>
                        )}

                        {collection.status === 'published' && (
                            <button
                                onClick={handleGenerate}
                                disabled={!!actionLoading}
                                className="flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] border border-[#333333] text-white rounded-lg hover:border-[#555555] transition-colors text-sm font-medium disabled:opacity-50"
                            >
                                {actionLoading === 'generate' ? <LoadingSpinner /> : <SparklesIcon />}
                                Regenerate Content
                            </button>
                        )}

                        <button
                            onClick={async () => {
                                setActionLoading('sync-all');
                                try {
                                    await collectionsAIAPI.syncAllDataSources(collection.id);
                                    setSuccess('All 4 data sources synced (GSC, GA4, Shopify, DataForSEO)');
                                    await loadCollection();
                                } catch (e: any) {
                                    setError(e.message || 'Sync failed');
                                } finally {
                                    setActionLoading(null);
                                }
                            }}
                            disabled={!!actionLoading}
                            className="flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] border border-[#f7b500]/30 text-[#f7b500] rounded-lg hover:bg-[#f7b500]/10 transition-colors text-sm font-medium disabled:opacity-50 ml-auto"
                        >
                            {actionLoading === 'sync-all' ? <LoadingSpinner /> : <RefreshIcon />}
                            Sync All Sources
                        </button>

                        <button
                            onClick={handleDataForSEO}
                            disabled={!!actionLoading}
                            className="flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] border border-[#10b981]/30 text-[#10b981] rounded-lg hover:bg-[#10b981]/10 transition-colors text-sm font-medium disabled:opacity-50"
                        >
                            {actionLoading === 'dataforseo' ? <LoadingSpinner /> : null}
                            Sync DataForSEO
                        </button>

                        <button
                            onClick={handleWorkflow}
                            disabled={!!actionLoading}
                            className="flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] border border-[#333333] text-white rounded-lg hover:border-[#555555] transition-colors text-sm font-medium disabled:opacity-50"
                        >
                            {actionLoading === 'workflow' ? <LoadingSpinner /> : null}
                            Run Full Workflow
                        </button>
                    </div>

                    {/* Success/Error messages */}
                    {success && (
                        <div className="mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
                            {success}
                        </div>
                    )}
                    {error && (
                        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                            {error}
                        </div>
                    )}
                </div>
            </div>

            {/* Main content */}
            <div className="max-w-[1400px] mx-auto p-6">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left column - Stats & Data */}
                    <div className="lg:col-span-1 space-y-6">
                        {/* GSC Stats */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <h3 className="text-[#4285f4] text-xs font-semibold uppercase tracking-wider mb-3">Search Console</h3>
                            <div className="space-y-3">
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Impressions</span>
                                    <span className="text-white font-mono">{(collection.impressions || 0).toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Clicks</span>
                                    <span className="text-white font-mono">{(collection.clicks || 0).toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">CTR</span>
                                    <span className="text-white font-mono">{(collection.ctr || 0).toFixed(1)}%</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Position</span>
                                    <span className={`font-mono ${collection.position <= 10 ? 'text-green-400' : collection.position <= 20 ? 'text-[#f7b500]' : 'text-red-400'}`}>
                                        {(collection.position || 0).toFixed(1)}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* GA4 Stats */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <h3 className="text-[#ff6d00] text-xs font-semibold uppercase tracking-wider mb-3">Google Analytics 4</h3>
                            <div className="space-y-3">
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Sessions</span>
                                    <span className="text-white font-mono">{(collection.ga4_sessions || 0).toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Conversions</span>
                                    <span className="text-white font-mono">{(collection.ga4_conversions || 0).toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Conv. Rate</span>
                                    <span className="text-white font-mono">{((collection.ga4_conversion_rate || 0)).toFixed(2)}%</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Bounce Rate</span>
                                    <span className="text-white font-mono">{((collection.ga4_bounce_rate || 0) * 100).toFixed(0)}%</span>
                                </div>
                            </div>
                        </div>

                        {/* Shopify Revenue */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <h3 className="text-[#f7b500] text-xs font-semibold uppercase tracking-wider mb-3">Shopify Attribution</h3>
                            <div className="space-y-3">
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Revenue</span>
                                    <span className="text-[#f7b500] font-mono">${(collection.shopify_attributed_revenue || 0).toLocaleString('en-MX', { maximumFractionDigits: 0 })}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">Orders</span>
                                    <span className="text-white font-mono">{(collection.shopify_attributed_orders || 0).toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-[#666666] text-sm">LLM Revenue</span>
                                    <span className="text-purple-400 font-mono">${(collection.shopify_llm_revenue || 0).toLocaleString('en-MX', { maximumFractionDigits: 0 })}</span>
                                </div>
                            </div>
                        </div>

                        {/* DataForSEO */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <h3 className="text-[#10b981] text-xs font-semibold uppercase tracking-wider mb-3">DataForSEO</h3>
                            {collection.dataforseo_primary_keyword ? (
                                <div className="space-y-3">
                                    <div>
                                        <span className="text-[#666666] text-sm">Primary Keyword</span>
                                        <p className="text-white text-sm mt-1">{collection.dataforseo_primary_keyword}</p>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-[#666666] text-sm">Volume</span>
                                        <span className="text-[#10b981] font-mono">{(collection.dataforseo_volume || 0).toLocaleString()}/mo</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-[#666666] text-sm">Competition</span>
                                        <span className={`font-mono ${collection.dataforseo_competition === 'LOW' ? 'text-green-400' : collection.dataforseo_competition === 'HIGH' ? 'text-red-400' : 'text-[#f7b500]'}`}>
                                            {collection.dataforseo_competition}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-[#666666] text-sm">CPC</span>
                                        <span className="text-white font-mono">${(collection.dataforseo_cpc || 0).toFixed(2)}</span>
                                    </div>
                                    {collection.dataforseo_top_competitor && (
                                        <div>
                                            <span className="text-[#666666] text-sm">Top Competitor</span>
                                            <p className="text-white text-sm mt-1">{collection.dataforseo_top_competitor}</p>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <p className="text-[#666666] text-sm">No DataForSEO data yet. Click &quot;Sync DataForSEO&quot; to fetch keyword data.</p>
                            )}
                        </div>
                    </div>

                    {/* Right column - Content & Queries */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Top Queries */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <h3 className="text-white text-sm font-semibold mb-4">Top Search Queries</h3>
                            {queries && queries.queries.length > 0 ? (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-[#666666] text-xs">
                                                <th className="text-left pb-2 font-medium">Query</th>
                                                <th className="text-right pb-2 font-medium">Impressions</th>
                                                <th className="text-right pb-2 font-medium">Clicks</th>
                                                <th className="text-right pb-2 font-medium">CTR</th>
                                                <th className="text-right pb-2 font-medium">Position</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {queries.queries.slice(0, 10).map((q, i) => (
                                                <tr key={q.query || `query-${i}`} className="border-t border-[#222]">
                                                    <td className="py-2 pr-4 text-[#cccccc]">{q.query}</td>
                                                    <td className="py-2 text-right text-white font-mono">{q.impressions.toLocaleString()}</td>
                                                    <td className="py-2 text-right text-white font-mono">{q.clicks}</td>
                                                    <td className="py-2 text-right text-[#888888] font-mono">{(q.ctr * 100).toFixed(1)}%</td>
                                                    <td className="py-2 text-right font-mono">
                                                        <span className={q.position <= 10 ? 'text-green-400' : q.position <= 20 ? 'text-[#f7b500]' : 'text-red-400'}>
                                                            {q.position.toFixed(1)}
                                                        </span>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <p className="text-[#666666] text-sm">No query data available. Run &quot;Analyze GSC Data&quot; first.</p>
                            )}
                        </div>

                        {/* Cannibalization Guard */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <h3 className="text-white text-sm font-semibold mb-3">Cannibalization Guard</h3>
                            <CannibalizationGuard collectionId={collection.id} />
                        </div>

                        {/* Smart Recommendations */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <CollectionRecommendations collectionId={collection.id} />
                        </div>

                        {/* Content Drafts */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <h3 className="text-white text-sm font-semibold mb-3">Content Drafts</h3>
                            <CollectionContentDrafts collectionId={collection.id} onDraftApproved={() => loadCollection()} />
                        </div>

                        {/* Trends */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                            <h3 className="text-white text-sm font-semibold mb-3">Performance Trends (30 days)</h3>
                            <CollectionTrends collectionId={collection.id} />
                        </div>

                        {/* Generated Content */}
                        {generatedContent && (
                            <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-white text-sm font-semibold">Generated Content</h3>
                                    <span className="text-[#666666] text-xs">
                                        Generated {formatDateTime(generatedContent.generated_at)}
                                    </span>
                                </div>

                                {/* Educational Content */}
                                {generatedContent.educational_content && (
                                    <div className="mb-6">
                                        <h4 className="text-[#888888] text-xs uppercase tracking-wider mb-2">Educational Content</h4>
                                        <div className="bg-[#0f0f0f] border border-[#222] rounded-lg p-4">
                                            <div
                                                className="prose prose-invert prose-sm max-w-none text-[#cccccc]"
                                                dangerouslySetInnerHTML={{ __html: generatedContent.educational_content }}
                                            />
                                        </div>
                                    </div>
                                )}

                                {/* FAQ */}
                                {generatedContent.faq && generatedContent.faq.length > 0 && (
                                    <div className="mb-6">
                                        <h4 className="text-[#888888] text-xs uppercase tracking-wider mb-2">FAQ Section ({generatedContent.faq.length} items)</h4>
                                        <div className="space-y-3">
                                            {generatedContent.faq.map((item, i) => (
                                                <div key={item.question || `faq-${i}`} className="bg-[#0f0f0f] border border-[#222] rounded-lg p-3">
                                                    <p className="text-white font-medium text-sm mb-1">{item.question}</p>
                                                    <p className="text-[#888888] text-sm">{item.answer}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Schema Markup */}
                                {generatedContent.schema_markup && (
                                    <div>
                                        <h4 className="text-[#888888] text-xs uppercase tracking-wider mb-2">Schema Markup</h4>
                                        <pre className="bg-[#0f0f0f] border border-[#222] rounded-lg p-3 text-xs text-[#888888] overflow-x-auto">
                                            {generatedContent.schema_markup}
                                        </pre>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* People Also Ask */}
                        {collection.dataforseo_people_also_ask && collection.dataforseo_people_also_ask.length > 0 && (
                            <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                                <h3 className="text-white text-sm font-semibold mb-4">People Also Ask</h3>
                                <div className="space-y-2">
                                    {collection.dataforseo_people_also_ask.map((paa, i) => (
                                        <div key={paa.question || `paa-${i}`} className="bg-[#0f0f0f] border border-[#222] rounded p-3">
                                            <p className="text-white text-sm font-medium">{paa.question}</p>
                                            {paa.answer_snippet && (
                                                <p className="text-[#888888] text-xs mt-1">{paa.answer_snippet}</p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
