'use client';

import React from 'react';
import { Button, Card, Badge } from '../';
import { ChipIcon, CheckIcon, XIcon, DatabaseIcon, SparklesIcon, RefreshIcon, ChartIcon } from '../ui/Icons';
import { LLM_SOURCE_COLORS } from './constants';
import { ProductWhyAnalysis } from '@/lib/api';

// Types
interface ProductContentAttributes {
    description_length: number;
    has_aeo_chunks: boolean;
    chunk_count: number;
    in_llms_txt: boolean;
    has_images: boolean;
    image_count: number;
}

interface LLMReferencedProduct {
    id: string;
    shopify_id: string;
    title: string;
    sku: string;
    handle: string;
    product_type: string;
    orders_from_llm: number;
    revenue_from_llm: number;
    sources: string[];
    content_attributes: ProductContentAttributes;
}

interface OptimizationOpportunity {
    id: string;
    shopify_id: string;
    title: string;
    sku: string;
    handle: string;
    product_type: string;
    total_sold: number;
    total_revenue: number;
    current_attributes: ProductContentAttributes;
    issues: string[];
    recommendation: string;
}

interface SuccessPatterns {
    avg_description_length: number;
    products_with_aeo_chunks_pct: number;
    total_products_referenced: number;
    most_common_sources: Array<{ source: string; count: number }>;
}

interface AEOProductIntelligenceProps {
    productsFromLLM: LLMReferencedProduct[];
    optimizationOpportunities: OptimizationOpportunity[];
    successPatterns: SuccessPatterns | null;
    whyAnalysis?: ProductWhyAnalysis | null;
    onRefresh: () => void;
    loading: boolean;
}

// Source badge colors for Product Intelligence
const SOURCE_COLORS: Record<string, string> = {
    chatgpt: '#10A37F',
    gemini: '#4285F4',
    perplexity: '#20B2AA',
    claude: '#D97706',
    copilot: '#0078D4',
    grok: '#000000',
};

export const AEOProductIntelligence: React.FC<AEOProductIntelligenceProps> = ({
    productsFromLLM,
    optimizationOpportunities,
    successPatterns,
    whyAnalysis,
    onRefresh,
    loading
}) => {
    const [expandedProduct, setExpandedProduct] = React.useState<string | null>(null);
    const [activeSection, setActiveSection] = React.useState<'products' | 'opportunities' | 'why'>('products');

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('es-MX', {
            style: 'currency',
            currency: 'MXN',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value);
    };

    const avgDescLen = successPatterns?.avg_description_length || 0;
    const avgChunks  = successPatterns && successPatterns.total_products_referenced > 0
        ? Math.round(productsFromLLM.reduce((sum, p) => sum + p.content_attributes.chunk_count, 0) / productsFromLLM.length)
        : 0;

    return (
        <div className="space-y-6">

            {/* Sync warning — shown when no LLM products found */}
            {!loading && productsFromLLM.length === 0 && (
                <div className="flex items-start gap-3 bg-[#1a1a1a] border border-yellow-600/30 rounded-sm px-4 py-3">
                    <span className="text-yellow-500 text-sm shrink-0 mt-0.5">⚠</span>
                    <div>
                        <p className="text-xs text-yellow-400 font-medium mb-1">No LLM-attributed products found</p>
                        <p className="text-xs text-zinc-400 leading-relaxed">
                            Products appear here when Shopify orders contain UTM parameters or referrers from AI sources
                            (chatgpt.com, perplexity.ai, claude.ai, etc.). Make sure your store is synced and LLM UTM
                            tracking is active. Try expanding the date range or syncing Shopify orders.
                        </p>
                    </div>
                </div>
            )}

            {/* Success Patterns Summary */}
            {successPatterns && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="bg-[#1a1a1a] rounded-sm border border-[#F7B500]/50 p-6">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-[#F7B500]/20 rounded-sm">
                                <ChipIcon className="text-[#F7B500]" size={24} />
                            </div>
                            <div>
                                <p className="text-sm text-zinc-400">Products Referenced</p>
                                <p className="text-2xl font-bold text-[#F7B500]">
                                    {successPatterns.total_products_referenced}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-green-500/10 rounded-sm">
                                <CheckIcon className="text-green-400" size={24} />
                            </div>
                            <div>
                                <p className="text-sm text-zinc-400">With AEO Chunks</p>
                                <p className="text-2xl font-bold text-white">
                                    {successPatterns.products_with_aeo_chunks_pct.toFixed(0)}%
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-blue-500/10 rounded-sm">
                                <DatabaseIcon className="text-blue-400" size={24} />
                            </div>
                            <div>
                                <p className="text-sm text-zinc-400">Avg Description</p>
                                <p className="text-2xl font-bold text-white">
                                    {successPatterns.avg_description_length} chars
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                        <div className="flex items-start gap-3">
                            <div className="p-3 bg-purple-500/10 rounded-sm shrink-0">
                                <SparklesIcon className="text-purple-400" size={24} />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm text-zinc-400 mb-2">LLM Sources</p>
                                {successPatterns.most_common_sources.length > 0 ? (
                                    <div className="flex flex-wrap gap-1.5">
                                        {successPatterns.most_common_sources.map((s) => (
                                            <span
                                                key={s.source}
                                                className="px-2 py-0.5 text-xs rounded text-white font-medium"
                                                style={{ backgroundColor: SOURCE_COLORS[s.source] || '#4b5563' }}
                                            >
                                                {s.source} ({s.count})
                                            </span>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-zinc-600">N/A</p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Section Tabs */}
            <div className="flex gap-2 border-b border-[#3a3a3a] pb-4">
                <Button
                    variant={activeSection === 'products' ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => setActiveSection('products')}
                >
                    📦 Products from LLMs ({productsFromLLM.length})
                </Button>
                <Button
                    variant={activeSection === 'opportunities' ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => setActiveSection('opportunities')}
                >
                    🎯 Opportunities ({optimizationOpportunities.length})
                </Button>
                <Button
                    variant={activeSection === 'why' ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => setActiveSection('why')}
                >
                    🔍 Why Recommended ({whyAnalysis?.total_products_analyzed || 0})
                </Button>
                <div className="ml-auto">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onRefresh}
                        loading={loading}
                        icon={<RefreshIcon size={16} />}
                    >
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Products Referenced by LLMs */}
            {activeSection === 'products' && (
                <Card
                    title="Products Referenced by LLMs"
                    subtitle="Products that have sold via ChatGPT, Gemini, Perplexity, and other AI assistants"
                >
                    {productsFromLLM.length === 0 ? (
                        <div className="text-center py-16 text-zinc-400 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a]">
                            <ChipIcon size={48} className="mx-auto mb-4 opacity-50" />
                            <p>No products found from LLM-attributed orders.</p>
                            <p className="text-sm text-zinc-500 mt-2">
                                This could mean no LLM-attributed orders in the selected period.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {productsFromLLM.map((product) => (
                                <div
                                    key={product.id}
                                    className="bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm overflow-hidden"
                                >
                                    {/* Product Header */}
                                    <div
                                        role="button"
                                        tabIndex={0}
                                        aria-expanded={expandedProduct === product.id}
                                        aria-label={`Toggle detail for ${product.title}`}
                                        className="flex items-center gap-4 p-4 cursor-pointer hover:bg-[#1a1a1a] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
                                        onClick={() => setExpandedProduct(expandedProduct === product.id ? null : product.id)}
                                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedProduct(expandedProduct === product.id ? null : product.id); } }}
                                    >
                                        <div className="flex-1">
                                            <h3 className="font-medium text-white line-clamp-1">{product.title}</h3>
                                            <div className="flex items-center gap-2 text-xs text-zinc-400 mt-1">
                                                <span className="font-mono bg-[#F7B500]/10 text-[#F7B500] px-2 py-0.5 rounded">
                                                    {product.sku || 'No SKU'}
                                                </span>
                                                <span>{product.product_type}</span>
                                            </div>
                                        </div>

                                        {/* LLM Source Badges */}
                                        <div className="flex gap-1">
                                            {product.sources.slice(0, 3).map((source) => (
                                                <span
                                                    key={source}
                                                    className="px-2 py-1 text-xs rounded text-white"
                                                    style={{ backgroundColor: SOURCE_COLORS[source] || '#666' }}
                                                >
                                                    {source}
                                                </span>
                                            ))}
                                        </div>

                                        <div className="text-right">
                                            <div className="font-mono text-[#F7B500] font-bold">
                                                {formatCurrency(product.revenue_from_llm)}
                                            </div>
                                            <div className="text-xs text-zinc-400">
                                                {product.orders_from_llm} orders
                                            </div>
                                        </div>

                                        <div className="w-6 text-zinc-500">
                                            {expandedProduct === product.id ? '▼' : '▶'}
                                        </div>
                                    </div>

                                    {/* Expanded Content Attributes */}
                                    {expandedProduct === product.id && (
                                        <div className="border-t border-[#3a3a3a] p-4 bg-[#111]">
                                            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-4">
                                                Why this product gets recommended by AI
                                            </h4>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                {/* Signal scores */}
                                                <div className="space-y-3">
                                                    <p className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold">Content Signals</p>
                                                    {[
                                                        {
                                                            label: 'In llms.txt',
                                                            active: product.content_attributes.in_llms_txt,
                                                            detail: product.content_attributes.in_llms_txt ? 'LLMs can crawl this product' : 'Add to llms.txt to boost visibility',
                                                            weight: 'High impact',
                                                        },
                                                        {
                                                            label: `AEO Chunks (${product.content_attributes.chunk_count})`,
                                                            active: product.content_attributes.has_aeo_chunks,
                                                            detail: product.content_attributes.chunk_count > 0
                                                                ? `${product.content_attributes.chunk_count} chunks vs avg ${avgChunks}`
                                                                : 'No AEO chunks — create structured content',
                                                            weight: 'High impact',
                                                        },
                                                        {
                                                            label: `Description (${product.content_attributes.description_length} chars)`,
                                                            active: product.content_attributes.description_length >= 300,
                                                            detail: product.content_attributes.description_length >= 300
                                                                ? `Good length (avg winner: ${avgDescLen} chars)`
                                                                : `Too short — aim for 300+ chars (avg winner: ${avgDescLen})`,
                                                            weight: 'Medium impact',
                                                        },
                                                        {
                                                            label: `Images (${product.content_attributes.image_count})`,
                                                            active: product.content_attributes.has_images,
                                                            detail: product.content_attributes.has_images ? 'Visual content helps AI understand product' : 'Add product images',
                                                            weight: 'Low impact',
                                                        },
                                                    ].map((sig) => (
                                                        <div key={sig.label} className="flex items-start gap-2.5">
                                                            <div className="mt-0.5">
                                                                {sig.active ? (
                                                                    <CheckIcon className="text-green-400" size={15} />
                                                                ) : (
                                                                    <XIcon className="text-red-400" size={15} />
                                                                )}
                                                            </div>
                                                            <div>
                                                                <p className="text-sm text-zinc-200 font-medium">{sig.label}</p>
                                                                <p className="text-[10px] text-zinc-500 mt-0.5">{sig.detail}</p>
                                                            </div>
                                                            <span className="ml-auto text-[9px] text-zinc-600 whitespace-nowrap">{sig.weight}</span>
                                                        </div>
                                                    ))}
                                                </div>

                                                {/* Sources + LLM breakdown */}
                                                <div>
                                                    <p className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold mb-3">AI Sources Driving Sales</p>
                                                    <div className="space-y-2">
                                                        {product.sources.map((source) => (
                                                            <div key={source} className="flex items-center gap-2">
                                                                <span
                                                                    className="px-2 py-1 text-xs rounded text-white font-medium min-w-[80px] text-center"
                                                                    style={{ backgroundColor: SOURCE_COLORS[source] || '#4b5563' }}
                                                                >
                                                                    {source}
                                                                </span>
                                                                <div className="flex-1 h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
                                                                    <div className="h-full bg-white/20 rounded-full" style={{ width: `${Math.round(100 / product.sources.length)}%` }} />
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>

                                                    {product.sources.length === 0 && (
                                                        <p className="text-xs text-zinc-600 italic">No AI source data available</p>
                                                    )}

                                                    <div className="mt-4 p-3 bg-[#F7B500]/5 border border-[#F7B500]/20 rounded-sm">
                                                        <p className="text-[10px] text-[#F7B500] font-medium mb-1">AI Visibility Score</p>
                                                        <p className="text-2xl font-bold text-white">
                                                            {[
                                                                product.content_attributes.in_llms_txt ? 35 : 0,
                                                                product.content_attributes.has_aeo_chunks ? 30 : 0,
                                                                product.content_attributes.description_length >= 300 ? 20 : Math.round(product.content_attributes.description_length / 15),
                                                                product.content_attributes.has_images ? 15 : 0,
                                                            ].reduce((a, b) => a + b, 0)}<span className="text-sm text-zinc-500">/100</span>
                                                        </p>
                                                        <p className="text-[10px] text-zinc-500 mt-1">Based on content signals above</p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
            )}

            {/* Why Recommended — LLM visibility analysis */}
            {activeSection === 'why' && (
                <Card
                    title="Why Products Get Recommended by AI"
                    subtitle="Based on LLM visibility checks — which prompt types trigger mentions, competitor displacement, and citation rates"
                >
                    {!whyAnalysis || whyAnalysis.products.length === 0 ? (
                        <div className="text-center py-16 text-zinc-400 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a]">
                            <ChartIcon size={48} className="mx-auto mb-4 opacity-50" />
                            <p className="font-medium">No LLM visibility check data yet</p>
                            <p className="text-sm text-zinc-500 mt-2 max-w-sm mx-auto">
                                Run product AI visibility checks from the AI Visibility tab to see which prompt types
                                trigger your products to be recommended by LLMs.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-4 mt-4">
                            {whyAnalysis.products.map((entry) => (
                                <div key={entry.product_id} className="bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm p-4">
                                    <div className="flex items-center justify-between mb-3">
                                        <p className="text-xs text-zinc-500 font-mono">Product ID #{entry.product_id}</p>
                                        <div className="flex items-center gap-4">
                                            <span className="text-xs text-zinc-500">{entry.total_checks} checks</span>
                                            <span className={`text-sm font-bold font-mono ${entry.visibility_score >= 50 ? 'text-green-400' : entry.visibility_score >= 25 ? 'text-yellow-400' : 'text-red-400'}`}>
                                                {entry.visibility_score}% visible
                                            </span>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                                        <div className="bg-[#1a1a1a] rounded-sm p-3">
                                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Visibility</p>
                                            <p className="text-lg font-bold text-[#F7B500]">{entry.visibility_score}%</p>
                                            <p className="text-[10px] text-zinc-600">of prompts</p>
                                        </div>
                                        <div className="bg-[#1a1a1a] rounded-sm p-3">
                                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Citation Rate</p>
                                            <p className={`text-lg font-bold ${entry.citation_rate >= 30 ? 'text-green-400' : 'text-zinc-400'}`}>{entry.citation_rate}%</p>
                                            <p className="text-[10px] text-zinc-600">URL cited</p>
                                        </div>
                                        <div className="bg-[#1a1a1a] rounded-sm p-3">
                                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Competitor Risk</p>
                                            <p className={`text-lg font-bold ${entry.competitor_displacement_pct >= 30 ? 'text-red-400' : 'text-zinc-400'}`}>{entry.competitor_displacement_pct}%</p>
                                            <p className="text-[10px] text-zinc-600">displaced by rival</p>
                                        </div>
                                        <div className="bg-[#1a1a1a] rounded-sm p-3">
                                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Strong Recs</p>
                                            <p className="text-lg font-bold text-blue-400">{entry.recommendation_strength.strong}</p>
                                            <p className="text-[10px] text-zinc-600">strong mentions</p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {/* Top prompt types */}
                                        <div>
                                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-bold mb-2">Prompt Types That Trigger Mentions</p>
                                            {entry.top_prompt_types.length > 0 ? (
                                                <div className="space-y-1.5">
                                                    {entry.top_prompt_types.map((pt) => (
                                                        <div key={pt.type} className="flex items-center gap-2">
                                                            <span className="text-xs text-zinc-300 w-28 truncate capitalize">{pt.type.replace(/_/g, ' ')}</span>
                                                            <div className="flex-1 h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
                                                                <div className="h-full bg-[#F7B500]" style={{ width: `${pt.mention_rate}%` }} />
                                                            </div>
                                                            <span className="text-xs text-[#F7B500] font-mono w-8 text-right">{pt.mention_rate}%</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="text-xs text-zinc-600 italic">No prompt type data</p>
                                            )}
                                        </div>

                                        {/* LLM breakdown + top competitors */}
                                        <div>
                                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-bold mb-2">LLM Mention Rate</p>
                                            {entry.llm_breakdown.length > 0 ? (
                                                <div className="space-y-1.5">
                                                    {entry.llm_breakdown.map((llm) => (
                                                        <div key={llm.llm} className="flex items-center gap-2">
                                                            <span className="text-xs text-zinc-300 w-20 truncate capitalize">{llm.llm}</span>
                                                            <div className="flex-1 h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
                                                                <div className="h-full bg-blue-500" style={{ width: `${llm.mention_rate}%` }} />
                                                            </div>
                                                            <span className="text-xs text-blue-400 font-mono w-8 text-right">{llm.mention_rate}%</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="text-xs text-zinc-600 italic">No LLM data</p>
                                            )}

                                            {entry.top_competitors.length > 0 && (
                                                <div className="mt-3">
                                                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-bold mb-2">Top Competitors Displacing</p>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {entry.top_competitors.map((c) => (
                                                            <span key={c.name} className="px-2 py-0.5 text-xs bg-red-500/10 text-red-400 rounded border border-red-500/20">
                                                                {c.name} ({c.count}×)
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
            )}

            {/* Optimization Opportunities */}
            {activeSection === 'opportunities' && (
                <Card
                    title="Optimization Opportunities"
                    subtitle="High-selling products that could benefit from LLM optimization"
                >
                    {optimizationOpportunities.length === 0 ? (
                        <div className="text-center py-16 text-zinc-400 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a]">
                            <SparklesIcon size={48} className="mx-auto mb-4 opacity-50" />
                            <p>No optimization opportunities found.</p>
                            <p className="text-sm text-zinc-500 mt-2">
                                All high-selling products are already getting LLM traffic!
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {optimizationOpportunities.map((product) => (
                                <div
                                    key={product.id}
                                    className="bg-[#0a0a0a] border border-[#F7B500]/30 rounded-sm p-4"
                                >
                                    <div className="flex items-start gap-4">
                                        <div className="flex-1">
                                            <h3 className="font-medium text-white line-clamp-1">{product.title}</h3>
                                            <div className="flex items-center gap-2 text-xs text-zinc-400 mt-1">
                                                <span className="font-mono bg-[#F7B500]/10 text-[#F7B500] px-2 py-0.5 rounded">
                                                    {product.sku || 'No SKU'}
                                                </span>
                                                <span>{product.product_type}</span>
                                            </div>

                                            {/* Issues */}
                                            <div className="flex flex-wrap gap-2 mt-3">
                                                {product.issues.map((issue) => (
                                                    <span
                                                        key={issue}
                                                        className="px-2 py-1 text-xs bg-red-500/10 text-red-400 rounded border border-red-500/20"
                                                    >
                                                        ❌ {issue}
                                                    </span>
                                                ))}
                                            </div>

                                            {/* Recommendation */}
                                            <div className="mt-3 p-3 bg-[#1a1a1a] rounded-sm border-l-2 border-[#F7B500]">
                                                <p className="text-sm text-zinc-300">
                                                    <span className="text-[#F7B500] font-medium">💡 Recommendation: </span>
                                                    {product.recommendation}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="text-right">
                                            <div className="font-mono text-green-400 font-bold">
                                                {formatCurrency(product.total_revenue)}
                                            </div>
                                            <div className="text-xs text-zinc-400">
                                                {product.total_sold} sold
                                            </div>
                                            <Badge variant="warning" className="mt-2">
                                                0 LLM Orders
                                            </Badge>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
            )}
        </div>
    );
};

// Re-export types for consumers
export type { LLMReferencedProduct, OptimizationOpportunity, SuccessPatterns, AEOProductIntelligenceProps };
