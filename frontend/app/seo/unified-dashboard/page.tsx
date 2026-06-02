'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { optimizerAPI, UnifiedDashboard, UnifiedRecommendation, CollectionOptimizer } from '../../../lib/api';
import {
    PieChart,
    Pie,
    Cell,
    RadarChart,
    PolarGrid,
    PolarAngleAxis,
    PolarRadiusAxis,
    Radar,
} from 'recharts';
import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    type ChartConfig,
} from '../../components/ui/chart';

// Icons
const SearchIcon = () => (
    <svg className="size-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
);

const MessageIcon = () => (
    <svg className="size-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
    </svg>
);

const RobotIcon = () => (
    <svg className="size-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
);

const TrendingUpIcon = () => (
    <svg className="size-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
);

const AlertIcon = () => (
    <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
);

const RefreshIcon = () => (
    <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
);

const ArrowRightIcon = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
);

const CalendarIcon = () => (
    <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
);

const PackageIcon = () => (
    <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
    </svg>
);

const CollectionIcon = () => (
    <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
);

// Stat Card Component
interface StatCardProps {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: React.ReactNode;
    color: string;
    trend?: number;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, subtitle, icon, color }) => (
    <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-6">
        <div className="flex items-start justify-between">
            <div>
                <p className="text-[#888888] text-sm mb-1">{title}</p>
                <p className="text-3xl font-bold text-white">{value}</p>
                {subtitle && <p className="text-[#666666] text-xs mt-1">{subtitle}</p>}
            </div>
            <div className={`p-3 rounded-lg ${color}`}>
                {icon}
            </div>
        </div>
    </div>
);

// Health Score Component
interface HealthScoreProps {
    label: string;
    score: number;
    maxScore?: number;
    color?: string;
}

const HealthScore: React.FC<HealthScoreProps> = ({ label, score, maxScore = 100, color = '#f7b500' }) => {
    const percentage = Math.min((score / maxScore) * 100, 100);
    let statusColor = 'text-red-400';
    if (percentage >= 80) statusColor = 'text-green-400';
    else if (percentage >= 60) statusColor = 'text-[#f7b500]';
    else if (percentage >= 40) statusColor = 'text-blue-400';

    return (
        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
                <span className="text-[#cccccc] text-sm">{label}</span>
                <span className={`text-lg font-bold ${statusColor}`}>{Math.round(percentage)}%</span>
            </div>
            <div className="w-full bg-[#333333] rounded-full h-2">
                <div 
                    className="h-2 rounded-full transition-all duration-500"
                    style={{ width: `${percentage}%`, backgroundColor: color }}
                />
            </div>
        </div>
    );
};

// Recommendation Card
const RecommendationCard: React.FC<{ recommendation: UnifiedRecommendation }> = ({ recommendation }) => {
    const priorityColors = {
        high: 'bg-red-500/20 text-red-400 border-red-500/30',
        medium: 'bg-[#f7b500]/20 text-[#f7b500] border-[#f7b500]/30',
        low: 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    };

    const categoryColors = {
        SEO: 'text-green-400',
        AEO: 'text-blue-400',
        GEO: 'text-purple-400'
    };

    return (
        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-4 hover:border-[#f7b500]/30 transition-colors">
            <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg ${priorityColors[recommendation.priority]}`}>
                    <AlertIcon />
                </div>
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs font-medium ${categoryColors[recommendation.category]}`}>
                            {recommendation.category}
                        </span>
                        <span className="text-[#666666]">•</span>
                        <span className="text-xs text-[#888888] capitalize">{recommendation.priority} Priority</span>
                    </div>
                    <h4 className="text-white font-medium mb-1">{recommendation.title}</h4>
                    <p className="text-[#888888] text-sm">{recommendation.action}</p>
                </div>
            </div>
        </div>
    );
};

const radarConfig: ChartConfig = {
    A: { label: 'Score', color: 'hsl(var(--chart-1))' },
};

const pieConfig: ChartConfig = {
    optimized: { label: 'Optimized', color: 'hsl(var(--chart-4))' },
    needsSeo:  { label: 'Needs SEO', color: '#ef4444' },
};

const DATE_RANGES = [
    { value: 7, label: 'Last 7 Days' },
    { value: 30, label: 'Last 30 Days' },
    { value: 90, label: 'Last 90 Days' },
];

export default function UnifiedDashboardPage() {
    const [dashboard, setDashboard] = useState<UnifiedDashboard | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [days, setDays] = useState(30);
    const [activeTab, setActiveTab] = useState<'overview' | 'products' | 'collections' | 'opportunities'>('overview');
    const [enrichedCollections, setEnrichedCollections] = useState<CollectionOptimizer[]>([]);
    const [loadingCollections, setLoadingCollections] = useState(false);

    const loadDashboard = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await optimizerAPI.getUnifiedDashboard(days);
            setDashboard(data);
        } catch (err) {
            setError('Failed to load unified dashboard data');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadDashboard();
    }, [days]);

    useEffect(() => {
        if (activeTab === 'collections' && enrichedCollections.length === 0) {
            setLoadingCollections(true);
            optimizerAPI.getCollections({ sort_by: 'sessions', limit: 20 })
                .then(res => setEnrichedCollections(res.collections))
                .catch(console.error)
                .finally(() => setLoadingCollections(false));
        }
    }, [activeTab]);

    if (loading) {
        return (
            <div className="min-h-screen bg-[#0a0a0a] text-white p-8">
                <div className="max-w-7xl mx-auto">
                    <div className="animate-pulse">
                        <div className="h-8 bg-[#333333] rounded w-1/4 mb-8"></div>
                        <div className="grid grid-cols-3 gap-6 mb-8">
                            {[1, 2, 3].map(n => (
                                <div key={`skel-${n}`} className="h-40 bg-[#1a1a1a] rounded-lg"></div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-[#0a0a0a] text-white p-8">
                <div className="max-w-7xl mx-auto">
                    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
                        <p className="text-red-400 mb-4">{error}</p>
                        <button 
                            onClick={loadDashboard}
                            className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    const overview = dashboard?.overview;
    const performance = dashboard?.performance;
    const opportunities = dashboard?.opportunities;
    const recommendations = dashboard?.recommendations || [];

    // Prepare chart data
    const seoHealthData = [
        { subject: 'Products Optimized', A: overview?.seo_health.products.optimized || 0, fullMark: overview?.seo_health.products.total || 100 },
        { subject: 'Collections Analyzed', A: overview?.seo_health.collections.analyzed || 0, fullMark: overview?.seo_health.collections.total || 100 },
        { subject: 'Collections with GA4', A: overview?.seo_health.collections.with_ga4 || 0, fullMark: overview?.seo_health.collections.total || 100 },
        { subject: 'Avg SEO Score', A: overview?.seo_health.products.avg_score || 0, fullMark: 100 },
    ];

    const productStatusData = [
        { name: 'Optimized', value: overview?.seo_health.products.optimized || 0, color: '#22c55e' },
        { name: 'Needs SEO', value: overview?.seo_health.products.needing_seo || 0, color: '#ef4444' },
    ];

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white p-8">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-8 gap-4">
                    <div>
                        <h1 className="text-3xl font-semibold text-white mb-2">Unified SEO Dashboard</h1>
                        <p className="text-[#888888]">SEO, AEO & GEO insights for products and collections</p>
                    </div>
                    
                    <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2 bg-[#1a1a1a] border border-[#333333] rounded-lg px-3 py-2">
                            <CalendarIcon />
                            <select 
                                value={days} 
                                onChange={(e) => setDays(Number(e.target.value))}
                                className="bg-transparent text-white text-sm focus:outline-none cursor-pointer"
                            >
                                {DATE_RANGES.map(range => (
                                    <option key={range.value} value={range.value} className="bg-[#1a1a1a]">
                                        {range.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <button
                            onClick={loadDashboard}
                            className="flex items-center gap-2 px-4 py-2 bg-[#333333] hover:bg-[#444444] text-white rounded-lg transition-colors"
                        >
                            <RefreshIcon />
                            Refresh
                        </button>
                    </div>
                </div>

                {/* Health Score Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <StatCard
                        title="SEO Health"
                        value={`${Math.round((overview?.seo_health.products.avg_score || 0))}%`}
                        subtitle={`${overview?.seo_health.products.optimized}/${overview?.seo_health.products.total} products optimized`}
                        icon={<SearchIcon />}
                        color="bg-green-500/20 text-green-400"
                    />
                    
                    <StatCard
                        title="AEO Health"
                        value={`${Math.round(overview?.aeo_health.coverage_percentage || 0)}%`}
                        subtitle={`${overview?.aeo_health.faq_schema_coverage} collections with FAQ`}
                        icon={<MessageIcon />}
                        color="bg-blue-500/20 text-blue-400"
                    />
                    
                    <StatCard
                        title="GEO Health"
                        value={overview?.geo_health.collections_with_ai_traffic || 0}
                        subtitle={`${overview?.geo_health.ai_referral_sessions} AI referral sessions`}
                        icon={<RobotIcon />}
                        color="bg-purple-500/20 text-purple-400"
                    />
                </div>

                {/* Tab Navigation */}
                <div className="flex gap-1 bg-[#1a1a1a] border border-[#333333] rounded-lg p-1 mb-8">
                    {[
                        { id: 'overview', label: 'Overview', icon: TrendingUpIcon },
                        { id: 'products', label: 'Products SEO', icon: PackageIcon },
                        { id: 'collections', label: 'Collections SEO', icon: CollectionIcon },
                        { id: 'opportunities', label: 'Opportunities', icon: AlertIcon },
                    ].map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id as any)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-md transition-all ${
                                activeTab === tab.id 
                                    ? 'bg-[#f7b500] text-black font-medium' 
                                    : 'text-[#888888] hover:text-white'
                            }`}
                        >
                            <tab.icon />
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* OVERVIEW TAB */}
                {activeTab === 'overview' && (
                    <>
                        {/* Performance Metrics */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                            <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-6">
                                <h3 className="text-lg font-semibold text-white mb-4">SEO Performance Radar</h3>
                                <ChartContainer config={radarConfig} className="h-80 w-full">
                                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={seoHealthData}>
                                        <PolarGrid stroke="#333333" />
                                        <PolarAngleAxis dataKey="subject" tick={{ fill: '#888888', fontSize: 12 }} />
                                        <PolarRadiusAxis angle={30} domain={[0, 'auto']} tick={{ fill: '#666666', fontSize: 10 }} />
                                        <Radar
                                            name="Current"
                                            dataKey="A"
                                            stroke="var(--color-A)"
                                            fill="var(--color-A)"
                                            fillOpacity={0.3}
                                        />
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                    </RadarChart>
                                </ChartContainer>
                            </div>

                            <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-6">
                                <h3 className="text-lg font-semibold text-white mb-4">Product SEO Status</h3>
                                <ChartContainer config={pieConfig} className="h-80 w-full">
                                    <PieChart>
                                        <Pie
                                            data={productStatusData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={60}
                                            outerRadius={100}
                                            paddingAngle={5}
                                            dataKey="value"
                                            label={({ name, value }) => `${name}: ${value}`}
                                        >
                                            {productStatusData.map((entry) => (
                                                <Cell key={entry.name || entry.color} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                    </PieChart>
                                </ChartContainer>
                            </div>
                        </div>

                        {/* Recommendations */}
                        {recommendations.length > 0 && (
                            <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-6">
                                <h3 className="text-lg font-semibold text-white mb-4">Recommendations</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {recommendations.map((rec, index) => (
                                        <RecommendationCard key={rec.title || `rec-${index}`} recommendation={rec} />
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* PRODUCTS TAB */}
                {activeTab === 'products' && (
                    <>
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                            <HealthScore
                                label="Products Optimized"
                                score={overview?.seo_health.products.optimized || 0}
                                maxScore={overview?.seo_health.products.total || 100}
                                color="#22c55e"
                            />
                            <HealthScore
                                label="Average SEO Score"
                                score={overview?.seo_health.products.avg_score || 0}
                                maxScore={100}
                                color="#f7b500"
                            />
                        </div>

                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg overflow-hidden">
                            <div className="p-6 border-b border-[#333333]">
                                <h3 className="text-lg font-semibold text-white">Top Performing Products</h3>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b border-[#333333] bg-[#252525]">
                                            <th className="py-3 px-4 text-left text-[#888888] text-sm font-medium">Product</th>
                                            <th className="py-3 px-4 text-left text-[#888888] text-sm font-medium">SKU</th>
                                            <th className="py-3 px-4 text-right text-[#888888] text-sm font-medium">SEO Score</th>
                                            <th className="py-3 px-4 text-right text-[#888888] text-sm font-medium">Sold</th>
                                            <th className="py-3 px-4 text-right text-[#888888] text-sm font-medium">Revenue</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {performance?.top_products.map((product) => (
                                            <tr key={product.id} className="border-b border-[#333333] hover:bg-[#252525] transition-colors">
                                                <td className="p-4">
                                                    <Link 
                                                        href={`/dashboard?product=${product.id}`}
                                                        className="text-white hover:text-[#f7b500] transition-colors"
                                                    >
                                                        {product.title}
                                                    </Link>
                                                </td>
                                                <td className="p-4 text-[#888888]">{product.sku || '-'}</td>
                                                <td className="p-4 text-right">
                                                    <span className={`font-mono ${
                                                        product.seo_score >= 70 ? 'text-green-400' : 
                                                        product.seo_score >= 50 ? 'text-[#f7b500]' : 'text-red-400'
                                                    }`}>
                                                        {product.seo_score}
                                                    </span>
                                                </td>
                                                <td className="p-4 text-right text-white font-mono">{product.total_sold}</td>
                                                <td className="p-4 text-right text-green-400 font-mono">
                                                    ${product.total_revenue.toLocaleString()}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                )}

                {/* COLLECTIONS TAB */}
                {activeTab === 'collections' && (
                    <>
                        {/* Health scores — 4 cards: GSC/GA4/Shopify/analyzed */}
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                            <HealthScore
                                label="Collections Analyzed"
                                score={overview?.seo_health.collections.analyzed || 0}
                                maxScore={overview?.seo_health.collections.total || 100}
                                color="#3b82f6"
                            />
                            <HealthScore
                                label="Collections Optimized"
                                score={overview?.seo_health.collections.optimized || 0}
                                maxScore={overview?.seo_health.collections.total || 100}
                                color="#22c55e"
                            />
                            <HealthScore
                                label="Collections with GA4"
                                score={overview?.seo_health.collections.with_ga4 || 0}
                                maxScore={overview?.seo_health.collections.total || 100}
                                color="#f7b500"
                            />
                            <HealthScore
                                label="With Shopify Revenue"
                                score={enrichedCollections.filter(c => (c.shopify_attributed_revenue || 0) > 0).length}
                                maxScore={overview?.seo_health.collections.total || 100}
                                color="#10b981"
                            />
                        </div>

                        {/* 4-source summary mini cards */}
                        {enrichedCollections.length > 0 && (
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                                <div className="bg-[#1a1a1a] border border-[#4285f4]/30 rounded-lg p-4">
                                    <p className="text-[#4285f4] text-xs font-semibold uppercase tracking-wider mb-1">GSC</p>
                                    <p className="text-white text-xl font-bold">
                                        {Math.round(enrichedCollections.reduce((s, c) => s + (c.impressions || 0), 0) / Math.max(enrichedCollections.length, 1)).toLocaleString()}
                                    </p>
                                    <p className="text-[#666666] text-xs">avg impressions/collection</p>
                                    <p className="text-[#4285f4] text-sm mt-1">
                                        pos {(enrichedCollections.filter(c => c.position > 0).reduce((s, c) => s + c.position, 0) / Math.max(enrichedCollections.filter(c => c.position > 0).length, 1)).toFixed(1)}
                                    </p>
                                </div>
                                <div className="bg-[#1a1a1a] border border-[#ff6d00]/30 rounded-lg p-4">
                                    <p className="text-[#ff6d00] text-xs font-semibold uppercase tracking-wider mb-1">GA4</p>
                                    <p className="text-white text-xl font-bold">
                                        {enrichedCollections.reduce((s, c) => s + (c.ga4_sessions || 0), 0).toLocaleString()}
                                    </p>
                                    <p className="text-[#666666] text-xs">total sessions</p>
                                    <p className="text-[#ff6d00] text-sm mt-1">
                                        {enrichedCollections.filter(c => (c.ga4_bounce_rate || 0) > 0).length > 0
                                            ? `${(enrichedCollections.filter(c => (c.ga4_bounce_rate || 0) > 0).reduce((s, c) => s + (c.ga4_bounce_rate || 0), 0) / enrichedCollections.filter(c => (c.ga4_bounce_rate || 0) > 0).length * 100).toFixed(0)}% avg bounce`
                                            : 'bounce: —'}
                                    </p>
                                </div>
                                <div className="bg-[#1a1a1a] border border-[#f7b500]/30 rounded-lg p-4">
                                    <p className="text-[#f7b500] text-xs font-semibold uppercase tracking-wider mb-1">Shopify</p>
                                    <p className="text-white text-xl font-bold">
                                        ${enrichedCollections.reduce((s, c) => s + (c.shopify_attributed_revenue || 0), 0).toLocaleString('en-MX', { maximumFractionDigits: 0 })}
                                    </p>
                                    <p className="text-[#666666] text-xs">attributed revenue MXN</p>
                                    <p className="text-[#f7b500] text-sm mt-1">
                                        {enrichedCollections.reduce((s, c) => s + (c.shopify_attributed_orders || 0), 0)} orders
                                    </p>
                                </div>
                                <div className="bg-[#1a1a1a] border border-[#10b981]/30 rounded-lg p-4">
                                    <p className="text-[#10b981] text-xs font-semibold uppercase tracking-wider mb-1">DataForSEO</p>
                                    <p className="text-white text-xl font-bold">
                                        {enrichedCollections.filter(c => (c.dataforseo_volume || 0) > 0).length > 0
                                            ? Math.round(enrichedCollections.filter(c => (c.dataforseo_volume || 0) > 0).reduce((s, c) => s + (c.dataforseo_volume || 0), 0) / enrichedCollections.filter(c => (c.dataforseo_volume || 0) > 0).length).toLocaleString()
                                            : '—'}
                                    </p>
                                    <p className="text-[#666666] text-xs">avg monthly vol.</p>
                                    <p className="text-[#10b981] text-sm mt-1">
                                        {enrichedCollections.filter(c => (c.dataforseo_volume || 0) > 0).length} analyzed
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Multi-source table */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg overflow-hidden">
                            <div className="p-4 border-b border-[#333333] flex items-center justify-between">
                                <h3 className="text-lg font-semibold text-white">Collections — All Data Sources</h3>
                                <Link
                                    href="/seo/dashboard"
                                    className="flex items-center gap-1 text-[#f7b500] hover:text-[#f7b500]/80 transition-colors text-sm"
                                >
                                    Full Management
                                    <ArrowRightIcon />
                                </Link>
                            </div>
                            {loadingCollections ? (
                                <div className="p-8 text-center text-[#888888]">Loading collections…</div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="border-b border-[#333333] bg-[#252525]">
                                                <th className="py-3 px-4 text-left text-[#888888] font-medium">Collection</th>
                                                {/* GSC */}
                                                <th className="p-3 text-right text-[#4285f4] font-medium">Impr.</th>
                                                <th className="p-3 text-right text-[#4285f4] font-medium">Pos.</th>
                                                {/* GA4 */}
                                                <th className="p-3 text-right text-[#ff6d00] font-medium">Sessions</th>
                                                <th className="p-3 text-right text-[#ff6d00] font-medium">Bounce</th>
                                                {/* Shopify */}
                                                <th className="p-3 text-right text-[#f7b500] font-medium">Revenue</th>
                                                <th className="p-3 text-right text-[#f7b500] font-medium">Orders</th>
                                                {/* DataForSEO */}
                                                <th className="p-3 text-right text-[#10b981] font-medium">Vol/mo</th>
                                                <th className="p-3 text-right text-[#10b981] font-medium">Comp.</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {enrichedCollections.length > 0 ? enrichedCollections.map((c) => (
                                                <tr key={c.id} className="border-b border-[#333333] hover:bg-[#252525] transition-colors">
                                                    <td className="py-3 px-4">
                                                        <Link
                                                            href={`/seo/collections?id=${c.id}`}
                                                            className="text-white hover:text-[#f7b500] transition-colors font-medium"
                                                        >
                                                            {c.title}
                                                        </Link>
                                                        <p className="text-[#666666] text-xs">{c.category}</p>
                                                    </td>
                                                    {/* GSC */}
                                                    <td className="p-3 text-right text-white font-mono">
                                                        {(c.impressions || 0) > 0 ? (c.impressions).toLocaleString() : '—'}
                                                    </td>
                                                    <td className="p-3 text-right font-mono">
                                                        <span className={c.position > 0 && c.position <= 10 ? 'text-green-400' : c.position > 10 ? 'text-[#f7b500]' : 'text-[#666666]'}>
                                                            {c.position > 0 ? c.position.toFixed(1) : '—'}
                                                        </span>
                                                    </td>
                                                    {/* GA4 */}
                                                    <td className="p-3 text-right text-white font-mono">
                                                        {(c.ga4_sessions || 0) > 0 ? (c.ga4_sessions || 0).toLocaleString() : '—'}
                                                    </td>
                                                    <td className="p-3 text-right font-mono">
                                                        {(c.ga4_bounce_rate || 0) > 0 ? (
                                                            <span className={(c.ga4_bounce_rate || 0) > 0.7 ? 'text-red-400' : (c.ga4_bounce_rate || 0) < 0.5 ? 'text-green-400' : 'text-[#f7b500]'}>
                                                                {((c.ga4_bounce_rate || 0) * 100).toFixed(0)}%
                                                            </span>
                                                        ) : '—'}
                                                    </td>
                                                    {/* Shopify */}
                                                    <td className="p-3 text-right font-mono">
                                                        {(c.shopify_attributed_revenue || 0) > 0 ? (
                                                            <span className="text-[#f7b500]">${(c.shopify_attributed_revenue || 0).toLocaleString('en-MX', { maximumFractionDigits: 0 })}</span>
                                                        ) : '—'}
                                                    </td>
                                                    <td className="p-3 text-right text-white font-mono">
                                                        {(c.shopify_attributed_orders || 0) > 0 ? c.shopify_attributed_orders : '—'}
                                                    </td>
                                                    {/* DataForSEO */}
                                                    <td className="p-3 text-right font-mono">
                                                        {(c.dataforseo_volume || 0) > 0 ? (
                                                            <span className="text-[#10b981]">{(c.dataforseo_volume || 0).toLocaleString()}</span>
                                                        ) : '—'}
                                                    </td>
                                                    <td className="p-3 text-right">
                                                        {c.dataforseo_competition ? (
                                                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                                                                c.dataforseo_competition === 'LOW' ? 'bg-green-500/20 text-green-400' :
                                                                c.dataforseo_competition === 'HIGH' ? 'bg-red-500/20 text-red-400' :
                                                                'bg-[#f7b500]/20 text-[#f7b500]'
                                                            }`}>
                                                                {c.dataforseo_competition}
                                                            </span>
                                                        ) : '—'}
                                                    </td>
                                                </tr>
                                            )) : (
                                                <tr>
                                                    <td colSpan={9} className="py-8 text-center text-[#666666]">
                                                        No collection data. Run Analyze in the{' '}
                                                        <Link href="/seo/dashboard" className="text-[#f7b500] hover:underline">SEO dashboard</Link>.
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* OPPORTUNITIES TAB */}
                {activeTab === 'opportunities' && (
                    <>
                        {/* Products Needing SEO */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-6 mb-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-lg font-semibold text-white">High-Value Products Needing SEO</h3>
                                <Link 
                                    href="/dashboard"
                                    className="flex items-center gap-1 text-[#f7b500] hover:text-[#f7b500]/80 transition-colors text-sm"
                                >
                                    View All Products
                                    <ArrowRightIcon />
                                </Link>
                            </div>
                            
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b border-[#333333]">
                                            <th className="py-2 px-4 text-left text-[#888888] text-sm">Product</th>
                                            <th className="py-2 px-4 text-right text-[#888888] text-sm">SEO Score</th>
                                            <th className="py-2 px-4 text-right text-[#888888] text-sm">Sold</th>
                                            <th className="py-2 px-4 text-right text-[#888888] text-sm">Revenue</th>
                                            <th className="py-2 px-4 text-center text-[#888888] text-sm">Impact</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {opportunities?.high_value_products_needing_seo.map((product) => (
                                            <tr key={product.id} className="border-b border-[#333333]/50">
                                                <td className="py-3 px-4">
                                                    <Link 
                                                        href={`/dashboard?product=${product.id}`}
                                                        className="text-white hover:text-[#f7b500] transition-colors"
                                                    >
                                                        {product.title}
                                                    </Link>
                                                </td>
                                                <td className="py-3 px-4 text-right">
                                                    <span className="text-red-400 font-mono">{product.seo_score}</span>
                                                </td>
                                                <td className="py-3 px-4 text-right text-white font-mono">{product.total_sold}</td>
                                                <td className="py-3 px-4 text-right text-green-400 font-mono">
                                                    ${product.total_revenue.toLocaleString()}
                                                </td>
                                                <td className="py-3 px-4 text-center">
                                                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-red-500/20 text-red-400">
                                                        {product.potential_impact}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Collections with Low Conversion */}
                        <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-lg font-semibold text-white">High-Traffic Collections with Low Conversion</h3>
                                <Link 
                                    href="/seo/ga4-dashboard"
                                    className="flex items-center gap-1 text-[#f7b500] hover:text-[#f7b500]/80 transition-colors text-sm"
                                >
                                    View GA4 Dashboard
                                    <ArrowRightIcon />
                                </Link>
                            </div>
                            
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {opportunities?.high_traffic_low_conversion_collections.map((collection) => (
                                    <div key={collection.id} className="bg-[#252525] rounded-lg p-4">
                                        <Link 
                                            href={`/seo/collections?id=${collection.id}`}
                                            className="text-white hover:text-[#f7b500] transition-colors font-medium block mb-2"
                                        >
                                            {collection.title}
                                        </Link>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span className="text-[#888888]">Sessions</span>
                                            <span className="text-white font-mono">{collection.sessions}</span>
                                        </div>
                                        <div className="flex justify-between text-sm mb-2">
                                            <span className="text-[#888888]">Conv. Rate</span>
                                            <span className="text-red-400 font-mono">{collection.conversion_rate}%</span>
                                        </div>
                                        <div className="pt-2 border-t border-[#333333]">
                                            <p className="text-xs text-[#666666] mb-1">Potential Revenue Increase</p>
                                            <p className="text-lg font-bold text-green-400">
                                                ${collection.potential_revenue_increase.toLocaleString()}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
