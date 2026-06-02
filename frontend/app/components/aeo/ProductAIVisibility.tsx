'use client';

import React, { useState, useEffect } from 'react';
import { formatDateTime } from '@/app/lib/dates';
import { Card, Button, Badge } from '../';
import { RefreshIcon, ChipIcon, SparklesIcon } from '../ui/Icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, RadialBarChart, RadialBar } from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent, type ChartConfig } from '../ui/chart';

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// LLM Provider colors for charts
const LLM_COLORS: Record<string, string> = {
    grok: '#000000',
    chatgpt: '#10A37F',
    perplexity: '#20B2AA',
    gemini: '#4285F4',
    claude: '#D97706',
    openai: '#10A37F',
};

// Visibility level colors
const LEVEL_COLORS: Record<string, string> = {
    high: '#22c55e',
    medium: '#F7B500',
    low: '#ef4444',
};

// Types
interface VisibilityOverview {
    product_id: number;
    product_title: string;
    product_sku: string | null;
    current_score: number | null;
    current_level: string | null;
    last_checked: string | null;
    by_llm: Record<string, number> | null;
    change_7d: number | null;
    top_competitors: Array<{ name: string; mentions: number }> | null;
}

interface VisibilityTrendPoint {
    date: string;
    score: number;
    level: string;
    by_llm: Record<string, number>;
    mentions: number;
    first_positions: number;
    competitor_share: number;
}

interface VisibilityCheckResult {
    prompt: string;
    prompt_type: string;
    provider: string;
    was_mentioned: boolean;
    position: number | null;
    context: string;
    brand_mentioned: boolean;
    url_cited: boolean;
    competitors: string[];
    sentiment: string | null;
    error: string | null;
}

interface VisibilityCheckResponse {
    product_id: number;
    checks_performed: number;
    score: {
        score: number;
        level: string;
        breakdown: {
            mention_score: number;
            position_score: number;
            citation_score: number;
            competitor_score: number;
        };
        by_llm: Record<string, number>;
        stats: {
            total_checks: number;
            mentions: number;
            first_positions: number;
            url_citations: number;
            competitor_appearances: number;
        };
    };
    results: VisibilityCheckResult[];
}

// V2.0 Enhanced Types
interface RevenueOpportunity {
    current_state: {
        sessions: number;
        conversion_rate: number;
        sold_30d: number;
        revenue_30d: number;
        visibility_score: number;
    };
    opportunity: {
        target_visibility: number;
        visibility_gap: number;
        estimated_traffic_increase_pct: number;
        additional_sessions: number;
        additional_sales: number;
        additional_monthly_revenue: number;
    };
    confidence: 'high' | 'medium' | 'low';
}

interface CompetitorInsight {
    provider: string;
    prompt: string;
    prompt_type: string;
    competitors: string[];
    analysis: {
        competitor_contexts: Array<{
            competitor: string;
            quotes: string[];
            keywords: string[];
        }>;
        content_gaps: string[];
    };
    recommendation: {
        action: string;
        suggested_content?: string;
        keywords_to_add?: string[];
    };
}

interface PromptEffectiveness {
    prompt_type: string;
    total_checks: number;
    mention_rate: number;
    first_position_rate: number;
    effectiveness: 'high' | 'medium' | 'low';
}

interface V2RecommendationsResponse {
    product_id: number;
    product_title: string;
    current_visibility_score: number;
    provider_insights: Record<string, {
        mention_rate: number;
        citation_rate: number;
        first_position_rate: number;
        checks: number;
    }>;
    recommendations: Array<{
        provider: string;
        priority: string;
        issue: string;
        action: string;
        impact: string;
        content_to_add?: string;
        competitor_said?: string[];
    }>;
    competitor_insights: CompetitorInsight[];
    prompt_effectiveness: PromptEffectiveness[];
    revenue_opportunity: RevenueOpportunity;
}

interface ProductAIVisibilityProps {
    productId: number;
    onClose?: () => void;
}

// Available LLM providers for selection
const AVAILABLE_PROVIDERS = [
    { id: 'grok', name: 'Grok', color: '#000000', icon: '🤖' },
    { id: 'openai', name: 'ChatGPT', color: '#10A37F', icon: '💬' },
    { id: 'perplexity', name: 'Perplexity', color: '#20B2AA', icon: '🔍' },
];

export const ProductAIVisibility: React.FC<ProductAIVisibilityProps> = ({
    productId,
    onClose
}) => {
    const [overview, setOverview] = useState<VisibilityOverview | null>(null);
    const [trend, setTrend] = useState<VisibilityTrendPoint[]>([]);
    const [checkResult, setCheckResult] = useState<VisibilityCheckResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [checking, setChecking] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'overview' | 'trend' | 'results' | 'insights'>('overview');
    const [selectedProviders, setSelectedProviders] = useState<string[]>(['grok']);
    const [showProviderDropdown, setShowProviderDropdown] = useState(false);
    
    // V2.0 Enhanced State
    const [v2Recommendations, setV2Recommendations] = useState<V2RecommendationsResponse | null>(null);
    const [loadingV2, setLoadingV2] = useState(false);
    const [useV2Prompts, setUseV2Prompts] = useState(true);

    // Toggle provider selection
    const toggleProvider = (providerId: string) => {
        setSelectedProviders(prev =>
            prev.includes(providerId)
                ? prev.filter(p => p !== providerId)
                : [...prev, providerId]
        );
    };

    // Fetch overview data
    const fetchOverview = async () => {
        try {
            const response = await fetch(`${API_BASE}/api/v1/product-visibility/${productId}`);
            if (response.ok) {
                const data = await response.json();
                setOverview(data);
            }
        } catch (err) {
            console.error('Failed to fetch visibility overview:', err);
        }
    };

    // Fetch trend data
    const fetchTrend = async () => {
        try {
            const response = await fetch(`${API_BASE}/api/v1/product-visibility/${productId}/trend?days=30`);
            if (response.ok) {
                const data = await response.json();
                setTrend(data.trend || []);
            }
        } catch (err) {
            console.error('Failed to fetch visibility trend:', err);
        }
    };

    // V2.0: Fetch enhanced recommendations with competitor insights
    const fetchV2Recommendations = async () => {
        setLoadingV2(true);
        try {
            const response = await fetch(`${API_BASE}/api/v1/product-visibility/${productId}/recommendations-v2?days=30`);
            if (response.ok) {
                const data = await response.json();
                setV2Recommendations(data);
            }
        } catch (err) {
            console.error('Failed to fetch V2 recommendations:', err);
        } finally {
            setLoadingV2(false);
        }
    };

    // Run visibility check (V2 enhanced with real data prompts)
    const runVisibilityCheck = async (providers: string[] = selectedProviders) => {
        if (providers.length === 0) {
            setError('Select at least one LLM provider');
            return;
        }
        setChecking(true);
        setError(null);
        try {
            // Use V2 endpoint if enhanced prompts enabled
            const endpoint = useV2Prompts 
                ? `${API_BASE}/api/v1/product-visibility/${productId}/check-v2?use_v2_prompts=true`
                : `${API_BASE}/api/v1/product-visibility/${productId}/check`;
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ providers, max_prompts: useV2Prompts ? 10 : 5 })
            });
            if (response.ok) {
                const data = await response.json();
                setCheckResult(data);
                // Refresh all data after check
                await Promise.all([
                    fetchOverview(),
                    fetchTrend(),
                    fetchV2Recommendations()
                ]);
                setActiveTab('results');
            } else {
                const errorData = await response.json();
                setError(errorData.detail || 'Failed to run visibility check');
            }
        } catch (err) {
            setError('Failed to connect to API');
        } finally {
            setChecking(false);
        }
    };

    // Initial load
    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            await Promise.all([fetchOverview(), fetchTrend(), fetchV2Recommendations()]);
            setLoading(false);
        };
        loadData();
    }, [productId]);

    // Calculate radial bar data for score visualization
    const getRadialData = () => {
        if (!overview?.current_score) return [];
        return [
            {
                name: 'Score',
                value: overview.current_score,
                fill: LEVEL_COLORS[overview.current_level || 'low']
            }
        ];
    };

    // Format trend data for multi-line chart
    const formatTrendData = () => {
        return trend.map(t => ({
            date: t.date.substring(5), // MM-DD format
            score: t.score,
            ...t.by_llm
        }));
    };

    if (loading) {
        return (
            <Card className="p-6 bg-[#1a1a1a] border-[#333]">
                <div className="flex items-center justify-center py-12">
                    <div className="animate-pulse text-zinc-400">Loading visibility data…</div>
                </div>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header with product info */}
            <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                    <h2 className="text-xl font-semibold text-white">AI Visibility Score</h2>
                    <p className="text-zinc-400 text-sm mt-1">
                        {overview?.product_title || 'Product'}
                        {overview?.product_sku && <span className="ml-2 text-zinc-500">({overview.product_sku})</span>}
                    </p>
                </div>
                <div className="flex gap-2 items-center">
                    {/* V2 Enhanced Prompts Toggle */}
                    <label className="flex items-center gap-2 px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded-sm text-sm cursor-pointer hover:border-[#F7B500]/50">
                        <input
                            type="checkbox"
                            checked={useV2Prompts}
                            onChange={() => setUseV2Prompts(!useV2Prompts)}
                            className="rounded border-[#555] bg-[#0f0f0f] text-[#F7B500]"
                        />
                        <span className="text-zinc-300">V2 Prompts</span>
                        <span className="text-xs text-zinc-500">(GSC + Vehicles)</span>
                    </label>
                    
                    {/* Provider Selector Dropdown */}
                    <div className="relative">
                        <button
                            onClick={() => setShowProviderDropdown(!showProviderDropdown)}
                            className="px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded-sm text-sm text-zinc-300 hover:border-[#F7B500]/50 flex items-center gap-2"
                        >
                            <span>LLMs: {selectedProviders.length}</span>
                            <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>
                        {showProviderDropdown && (
                            <div className="absolute top-full right-0 mt-1 w-48 bg-[#1a1a1a] border border-[#333] rounded-sm shadow-lg z-10">
                                {AVAILABLE_PROVIDERS.map(provider => (
                                    <label
                                        key={provider.id}
                                        className="flex items-center gap-3 px-3 py-2 hover:bg-[#333] cursor-pointer"
                                    >
                                        <input
                                            type="checkbox"
                                            checked={selectedProviders.includes(provider.id)}
                                            onChange={() => toggleProvider(provider.id)}
                                            className="rounded border-[#555] bg-[#0f0f0f] text-[#F7B500]"
                                        />
                                        <span className="text-lg">{provider.icon}</span>
                                        <span className="text-zinc-300 text-sm">{provider.name}</span>
                                        <div
                                            className="size-2 rounded-full ml-auto"
                                            style={{ backgroundColor: provider.color }}
                                        />
                                    </label>
                                ))}
                            </div>
                        )}
                    </div>
                    <Button
                        onClick={() => runVisibilityCheck()}
                        disabled={checking || selectedProviders.length === 0}
                        className="bg-[#F7B500] text-black hover:bg-[#F7B500]/80"
                    >
                        {checking ? (
                            <span className="flex items-center gap-2">
                                <RefreshIcon className="animate-spin" size={16} />
                                Checking...
                            </span>
                        ) : (
                            <span className="flex items-center gap-2">
                                <SparklesIcon size={16} />
                                Check Visibility
                            </span>
                        )}
                    </Button>
                    {onClose && (
                        <Button onClick={onClose} variant="outline">
                            Close
                        </Button>
                    )}
                </div>
            </div>

            {error && (
                <div className="bg-red-500/10 border border-red-500/50 rounded-sm p-4 text-red-400">
                    {error}
                </div>
            )}

            {/* Tab navigation */}
            <div className="flex gap-1 bg-[#0f0f0f] p-1 rounded-sm">
                {(['overview', 'trend', 'results', 'insights'] as const).map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-4 py-2 rounded-sm text-sm font-medium transition-colors ${activeTab === tab
                            ? 'bg-[#F7B500] text-black'
                            : 'text-zinc-400 hover:text-white hover:bg-[#1a1a1a]'
                            }`}
                    >
                        {tab === 'insights' ? '🎯 Insights V2' : tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                ))}
            </div>

            {/* Overview Tab */}
            {activeTab === 'overview' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Score Card */}
                    <Card className="bg-[#1a1a1a] border-[#333] p-6">
                        <h3 className="text-sm text-zinc-400 mb-4">Visibility Score</h3>
                        <div className="flex items-center justify-center">
                            {overview?.current_score !== null ? (
                                <div className="relative">
                                    <ChartContainer config={{ value: { label: 'Score', color: LEVEL_COLORS[overview?.current_level || 'low'] } } satisfies ChartConfig} className="size-[160px]">
                                        <RadialBarChart
                                            innerRadius="70%"
                                            outerRadius="100%"
                                            data={getRadialData()}
                                            startAngle={180}
                                            endAngle={0}
                                        >
                                            <RadialBar
                                                background={{ fill: '#333' }}
                                                dataKey="value"
                                                cornerRadius={10}
                                            />
                                        </RadialBarChart>
                                    </ChartContainer>
                                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                                        <span className="text-4xl font-bold text-white">
                                            {Math.round(overview.current_score)}
                                        </span>
                                        <span
                                            className="text-sm font-medium capitalize"
                                            style={{ color: LEVEL_COLORS[overview.current_level || 'low'] }}
                                        >
                                            {overview.current_level || 'Unknown'}
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-8">
                                    <ChipIcon className="text-zinc-500 mx-auto mb-2" size={32} />
                                    <p className="text-zinc-500">No visibility data yet</p>
                                    <p className="text-zinc-600 text-sm">Run a check to get started</p>
                                </div>
                            )}
                        </div>
                        {overview?.change_7d !== null && overview?.change_7d !== undefined && (
                            <div className="text-center mt-4">
                                <span className={`text-sm ${overview.change_7d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {overview.change_7d >= 0 ? '↑' : '↓'} {Math.abs(overview.change_7d).toFixed(1)} pts vs 7 days ago
                                </span>
                            </div>
                        )}
                    </Card>

                    {/* LLM Breakdown */}
                    <Card className="bg-[#1a1a1a] border-[#333] p-6">
                        <h3 className="text-sm text-zinc-400 mb-4">Visibility by LLM</h3>
                        {overview?.by_llm && Object.keys(overview.by_llm).length > 0 ? (
                            <div className="space-y-3">
                                {Object.entries(overview.by_llm).map(([provider, score]) => (
                                    <div key={provider} className="flex items-center gap-3">
                                        <div
                                            className="size-3 rounded-full"
                                            style={{ backgroundColor: LLM_COLORS[provider] || '#666' }}
                                        />
                                        <span className="text-zinc-300 capitalize flex-1">{provider}</span>
                                        <span className="text-white font-mono">{score}%</span>
                                        <div className="w-20 h-2 bg-[#333] rounded-full overflow-hidden">
                                            <div
                                                className="h-full rounded-full"
                                                style={{
                                                    width: `${score}%`,
                                                    backgroundColor: LLM_COLORS[provider] || '#666'
                                                }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-zinc-500">
                                No LLM data available
                            </div>
                        )}
                    </Card>

                    {/* Top Competitors */}
                    <Card className="bg-[#1a1a1a] border-[#333] p-6">
                        <h3 className="text-sm text-zinc-400 mb-4">Top Competitors Mentioned</h3>
                        {overview?.top_competitors && overview.top_competitors.length > 0 ? (
                            <div className="space-y-2">
                                {overview.top_competitors.map((comp, idx) => (
                                    <div key={comp.name} className="flex items-center justify-between py-2 border-b border-[#333] last:border-0">
                                        <span className="text-zinc-300 capitalize">{comp.name}</span>
                                        <Badge variant="outline" className="text-red-400 border-red-400/50">
                                            {comp.mentions} mentions
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-zinc-500">
                                No competitor data
                            </div>
                        )}
                    </Card>
                </div>
            )}

            {/* Trend Tab */}
            {activeTab === 'trend' && (
                <Card className="bg-[#1a1a1a] border-[#333] p-6">
                    <h3 className="text-sm text-zinc-400 mb-4">Visibility Trend (30 Days)</h3>
                    {trend.length > 0 ? (
                        <ChartContainer
                            config={{
                                score:      { label: 'Overall Score', color: 'hsl(var(--chart-1))' },
                                chatgpt:    { label: 'ChatGPT',       color: 'hsl(var(--chart-4))' },
                                perplexity: { label: 'Perplexity',    color: 'hsl(var(--chart-2))' },
                                gemini:     { label: 'Gemini',        color: 'hsl(var(--chart-2))' },
                                claude:     { label: 'Claude',        color: 'hsl(var(--chart-3))' },
                                grok:       { label: 'Grok',          color: '#888888' },
                            } satisfies ChartConfig}
                            className="h-[300px] w-full"
                        >
                            <LineChart data={formatTrendData()}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                <XAxis dataKey="date" stroke="#666" tick={{ fontSize: 12 }} />
                                <YAxis stroke="#666" domain={[0, 100]} tick={{ fontSize: 12 }} />
                                <ChartTooltip content={<ChartTooltipContent />} />
                                <ChartLegend content={<ChartLegendContent />} />
                                <Line type="monotone" dataKey="score" stroke="var(--color-score)" strokeWidth={2} dot={{ strokeWidth: 0 }} name="Overall Score" />
                                {trend[0]?.by_llm && Object.keys(trend[0].by_llm).map(provider => (
                                    <Line
                                        key={provider}
                                        type="monotone"
                                        dataKey={provider}
                                        stroke={LLM_COLORS[provider] || '#666'}
                                        strokeWidth={1}
                                        strokeDasharray="5 5"
                                        dot={false}
                                        name={provider.charAt(0).toUpperCase() + provider.slice(1)}
                                    />
                                ))}
                            </LineChart>
                        </ChartContainer>
                    ) : (
                        <div className="text-center py-12 text-zinc-500">
                            No trend data available. Run visibility checks to build history.
                        </div>
                    )}
                </Card>
            )}

            {/* Results Tab */}
            {activeTab === 'results' && checkResult && (
                <div className="space-y-4">
                    {/* Summary Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        {[
                            { label: 'Total Checks', value: checkResult.score.stats.total_checks },
                            { label: 'Mentions', value: checkResult.score.stats.mentions },
                            { label: '1st Position', value: checkResult.score.stats.first_positions },
                            { label: 'URL Citations', value: checkResult.score.stats.url_citations },
                            { label: 'Competitor Apps', value: checkResult.score.stats.competitor_appearances },
                        ].map(stat => (
                            <Card key={stat.label} className="bg-[#1a1a1a] border-[#333] p-4 text-center">
                                <p className="text-2xl font-bold text-white">{stat.value}</p>
                                <p className="text-xs text-zinc-400">{stat.label}</p>
                            </Card>
                        ))}
                    </div>

                    {/* Individual Results */}
                    <Card className="bg-[#1a1a1a] border-[#333] p-6">
                        <h3 className="text-sm text-zinc-400 mb-4">Check Results</h3>
                        <div className="space-y-4">
                            {checkResult.results.map((result) => (
                                <div
                                    key={`${result.provider}-${result.prompt}`}
                                    className={`p-4 rounded-sm border ${result.was_mentioned
                                        ? 'border-green-500/30 bg-green-500/5'
                                        : 'border-[#333] bg-[#0f0f0f]'
                                        }`}
                                >
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2 mb-2">
                                                <Badge
                                                    style={{ backgroundColor: LLM_COLORS[result.provider] || '#666' }}
                                                    className="text-white text-xs"
                                                >
                                                    {result.provider}
                                                </Badge>
                                                <Badge variant="outline" className="text-zinc-400 text-xs">
                                                    {result.prompt_type}
                                                </Badge>
                                            </div>
                                            <p className="text-zinc-300 text-sm mb-2">{result.prompt}</p>
                                            <div className="flex flex-wrap gap-2">
                                                {result.was_mentioned && (
                                                    <span className="text-green-400 text-xs">✓ Mentioned</span>
                                                )}
                                                {result.position && (
                                                    <span className="text-[#F7B500] text-xs">
                                                        Position: #{result.position}
                                                    </span>
                                                )}
                                                {result.brand_mentioned && (
                                                    <span className="text-blue-400 text-xs">✓ Brand</span>
                                                )}
                                                {result.url_cited && (
                                                    <span className="text-purple-400 text-xs">✓ URL Cited</span>
                                                )}
                                                {result.competitors.length > 0 && (
                                                    <span className="text-red-400 text-xs">
                                                        Competitors: {result.competitors.join(', ')}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className={`px-3 py-1 rounded-sm text-sm font-medium ${result.was_mentioned
                                            ? 'bg-green-500/20 text-green-400'
                                            : 'bg-red-500/20 text-red-400'
                                            }`}>
                                            {result.context}
                                        </div>
                                    </div>
                                    {result.error && (
                                        <div className="mt-2 text-red-400 text-xs">
                                            Error: {result.error}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </Card>
                </div>
            )}

            {activeTab === 'results' && !checkResult && (
                <Card className="bg-[#1a1a1a] border-[#333] p-12 text-center">
                    <SparklesIcon className="text-zinc-500 mx-auto mb-4" size={48} />
                    <h3 className="text-lg text-zinc-300 mb-2">No Check Results Yet</h3>
                    <p className="text-zinc-500 mb-4">
                        Run a visibility check to see detailed results for each LLM query
                    </p>
                    <Button
                        onClick={() => runVisibilityCheck(['grok'])}
                        disabled={checking}
                        className="bg-[#F7B500] text-black hover:bg-[#F7B500]/80"
                    >
                        Run Visibility Check
                    </Button>
                </Card>
            )}

            {/* V2.0 Insights Tab */}
            {activeTab === 'insights' && (
                <div className="space-y-6">
                    {loadingV2 ? (
                        <Card className="bg-[#1a1a1a] border-[#333] p-6">
                            <div className="animate-pulse text-zinc-400 text-center">Loading V2 insights…</div>
                        </Card>
                    ) : v2Recommendations ? (
                        <>
                            {/* Revenue Opportunity Card */}
                            <Card className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 border-green-500/30 p-6">
                                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                    💰 Revenue Opportunity
                                    <Badge className={`text-xs ${
                                        v2Recommendations.revenue_opportunity?.confidence === 'high' 
                                            ? 'bg-green-500/20 text-green-400' 
                                            : v2Recommendations.revenue_opportunity?.confidence === 'medium'
                                                ? 'bg-yellow-500/20 text-yellow-400'
                                                : 'bg-zinc-500/20 text-zinc-400'
                                    }`}>
                                        {v2Recommendations.revenue_opportunity?.confidence} confidence
                                    </Badge>
                                </h3>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div className="bg-[#0f0f0f] p-4 rounded-sm">
                                        <p className="text-zinc-400 text-xs mb-1">Current Score</p>
                                        <p className="text-2xl font-bold text-white">
                                            {v2Recommendations.revenue_opportunity?.current_state?.visibility_score?.toFixed(0) || 0}
                                        </p>
                                    </div>
                                    <div className="bg-[#0f0f0f] p-4 rounded-sm">
                                        <p className="text-zinc-400 text-xs mb-1">Target Score</p>
                                        <p className="text-2xl font-bold text-[#F7B500]">
                                            {v2Recommendations.revenue_opportunity?.opportunity?.target_visibility || 70}
                                        </p>
                                    </div>
                                    <div className="bg-[#0f0f0f] p-4 rounded-sm">
                                        <p className="text-zinc-400 text-xs mb-1">Est. Additional Sales/mo</p>
                                        <p className="text-2xl font-bold text-blue-400">
                                            +{v2Recommendations.revenue_opportunity?.opportunity?.additional_sales?.toFixed(1) || 0}
                                        </p>
                                    </div>
                                    <div className="bg-[#0f0f0f] p-4 rounded-sm">
                                        <p className="text-zinc-400 text-xs mb-1">Est. Monthly Revenue</p>
                                        <p className="text-2xl font-bold text-green-400">
                                            +${v2Recommendations.revenue_opportunity?.opportunity?.additional_monthly_revenue?.toFixed(0) || 0}
                                        </p>
                                    </div>
                                </div>
                            </Card>

                            {/* Prompt Effectiveness */}
                            {v2Recommendations.prompt_effectiveness && v2Recommendations.prompt_effectiveness.length > 0 && (
                                <Card className="bg-[#1a1a1a] border-[#333] p-6">
                                    <h3 className="text-sm text-zinc-400 mb-4">📊 Prompt Effectiveness (Which Query Types Work Best)</h3>
                                    <div className="space-y-3">
                                        {v2Recommendations.prompt_effectiveness.map((pe) => (
                                            <div key={pe.prompt_type} className="flex items-center justify-between p-3 bg-[#0f0f0f] rounded-sm">
                                                <div className="flex items-center gap-3">
                                                    <Badge variant="outline" className={`text-xs ${
                                                        pe.effectiveness === 'high' ? 'border-green-500 text-green-400' :
                                                        pe.effectiveness === 'medium' ? 'border-yellow-500 text-yellow-400' :
                                                        'border-red-500 text-red-400'
                                                    }`}>
                                                        {pe.effectiveness}
                                                    </Badge>
                                                    <span className="text-zinc-300 capitalize">{pe.prompt_type.replace(/_/g, ' ')}</span>
                                                </div>
                                                <div className="flex items-center gap-4 text-sm">
                                                    <span className="text-zinc-400">{pe.total_checks} checks</span>
                                                    <span className={pe.mention_rate > 50 ? 'text-green-400' : pe.mention_rate > 20 ? 'text-yellow-400' : 'text-red-400'}>
                                                        {pe.mention_rate}% mention rate
                                                    </span>
                                                    <span className="text-blue-400">{pe.first_position_rate}% 1st pos</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </Card>
                            )}

                            {/* Competitor Insights */}
                            {v2Recommendations.competitor_insights && v2Recommendations.competitor_insights.length > 0 && (
                                <Card className="bg-[#1a1a1a] border-[#333] p-6">
                                    <h3 className="text-sm text-zinc-400 mb-4">🎯 Competitor Intelligence (Why They Beat You)</h3>
                                    <div className="space-y-4">
                                        {v2Recommendations.competitor_insights.map((ci) => (
                                            <div key={`${ci.provider}-${ci.prompt}`} className="p-4 bg-[#0f0f0f] rounded-sm border border-red-500/20">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <Badge style={{ backgroundColor: LLM_COLORS[ci.provider] || '#666' }} className="text-white text-xs">
                                                        {ci.provider}
                                                    </Badge>
                                                    <span className="text-zinc-400 text-xs">{ci.prompt_type}</span>
                                                </div>
                                                <p className="text-sm text-zinc-300 mb-2 italic">"{ci.prompt.substring(0, 100)}..."</p>
                                                <div className="flex flex-wrap gap-2 mb-3">
                                                    {ci.competitors.map(comp => (
                                                        <Badge key={comp} variant="outline" className="text-red-400 border-red-400/50 text-xs">
                                                            {comp}
                                                        </Badge>
                                                    ))}
                                                </div>
                                                {ci.analysis?.competitor_contexts?.[0]?.quotes?.[0] && (
                                                    <div className="bg-red-500/10 p-3 rounded-sm mb-3">
                                                        <p className="text-xs text-zinc-400 mb-1">What competitor said:</p>
                                                        <p className="text-sm text-red-300 italic">
                                                            "{ci.analysis.competitor_contexts[0].quotes[0].substring(0, 200)}..."
                                                        </p>
                                                    </div>
                                                )}
                                                {ci.recommendation && (
                                                    <div className="bg-green-500/10 p-3 rounded-sm">
                                                        <p className="text-xs text-zinc-400 mb-1">💡 Action to take:</p>
                                                        <p className="text-sm text-green-300">{ci.recommendation.action}</p>
                                                        {ci.recommendation.keywords_to_add && ci.recommendation.keywords_to_add.length > 0 && (
                                                            <div className="flex flex-wrap gap-1 mt-2">
                                                                {ci.recommendation.keywords_to_add.map(kw => (
                                                                    <Badge key={kw} className="bg-green-500/20 text-green-400 text-xs">
                                                                        +{kw}
                                                                    </Badge>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </Card>
                            )}

                            {/* Actionable Recommendations */}
                            {v2Recommendations.recommendations && v2Recommendations.recommendations.length > 0 && (
                                <Card className="bg-[#1a1a1a] border-[#333] p-6">
                                    <h3 className="text-sm text-zinc-400 mb-4">⚡ Priority Actions</h3>
                                    <div className="space-y-3">
                                        {v2Recommendations.recommendations.map((rec) => (
                                            <div
                                                key={`${rec.provider}-${rec.issue}`}
                                                className={`p-4 rounded-sm border ${
                                                    rec.priority === 'high' ? 'border-red-500/30 bg-red-500/5' :
                                                    rec.priority === 'medium' ? 'border-yellow-500/30 bg-yellow-500/5' :
                                                    'border-[#333] bg-[#0f0f0f]'
                                                }`}
                                            >
                                                <div className="flex items-start justify-between gap-4">
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-2 mb-2">
                                                            <Badge className={`text-xs ${
                                                                rec.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                                                                rec.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                                                'bg-zinc-500/20 text-zinc-400'
                                                            }`}>
                                                                {rec.priority}
                                                            </Badge>
                                                            <Badge style={{ backgroundColor: LLM_COLORS[rec.provider] || '#666' }} className="text-white text-xs">
                                                                {rec.provider}
                                                            </Badge>
                                                        </div>
                                                        <p className="text-zinc-300 text-sm font-medium mb-1">{rec.issue}</p>
                                                        <p className="text-zinc-400 text-sm">{rec.action}</p>
                                                        {rec.content_to_add && (
                                                            <p className="text-blue-400 text-xs mt-2">📝 {rec.content_to_add}</p>
                                                        )}
                                                    </div>
                                                    <span className="text-xs text-zinc-500 whitespace-nowrap">{rec.impact}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </Card>
                            )}
                        </>
                    ) : (
                        <Card className="bg-[#1a1a1a] border-[#333] p-12 text-center">
                            <SparklesIcon className="text-zinc-500 mx-auto mb-4" size={48} />
                            <h3 className="text-lg text-zinc-300 mb-2">No V2 Insights Yet</h3>
                            <p className="text-zinc-500 mb-4">
                                Run a visibility check to generate data-driven insights
                            </p>
                            <Button
                                onClick={() => fetchV2Recommendations()}
                                disabled={loadingV2}
                                className="bg-[#F7B500] text-black hover:bg-[#F7B500]/80"
                            >
                                Load Insights
                            </Button>
                        </Card>
                    )}
                </div>
            )}

            {/* Last checked timestamp */}
            {overview?.last_checked && (
                <p className="text-xs text-zinc-500 text-right">
                    Last checked: {formatDateTime(overview.last_checked)}
                </p>
            )}
        </div>
    );
};

export default ProductAIVisibility;
