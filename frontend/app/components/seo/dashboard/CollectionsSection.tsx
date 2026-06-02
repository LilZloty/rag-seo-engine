'use client';

import React, { useMemo, useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { CollectionOptimizer, GA4Dashboard, collectionsAIAPI, CollectionOpportunity } from '../../../../lib/api';
import type { FilterPreset, CollectionFilters } from '../../../../lib/types/dashboard';
import { PERIOD_COMPARISONS, TRAFFIC_RANGE_OPTIONS, OPPORTUNITY_SCORE_OPTIONS } from '../../../../lib/constants/dashboard';
import {
    funnelConfig, topCollectionsConfig, conversionDistConfig,
    seoScoreConfig, trafficSourcesConfig, revenueByTypeConfig, scatterConfig
} from '../../../../lib/chartConfigs';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
    PieChart, Pie, Cell,
    ScatterChart, Scatter, ZAxis,
    FunnelChart, Funnel,
} from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '../../ui/chart';
import { RefreshIcon, FilterIcon } from '../../ui/Icons';

export interface CollectionStats {
    avgImpressions: number;
    avgPosition: number;
    totalSessions: number;
    avgBounceRate: number;
    collectionsWithGA4: number;
    totalShopifyRevenue: number;
    totalShopifyOrders: number;
    lastShopifySync: string | null;
    avgDFSVolume: number;
    collectionsWithDFS: number;
}

export interface CollectionsSectionProps {
    collections: CollectionOptimizer[];
    opportunities: CollectionOptimizer[];
    filteredCollections: CollectionOptimizer[];
    sortedOpportunityCollections: CollectionOptimizer[];
    collectionStats: CollectionStats;
    allCollections: CollectionOptimizer[];
    allCollectionsTotal: number;
    allCollectionsLoading: boolean;
    ga4Dashboard: GA4Dashboard | null;
    collectionsLoading: boolean;
    analyzing: boolean;
    collectionTab: 'all' | 'overview' | 'analytics' | 'opportunities' | 'keywords' | 'intelligence';
    onCollectionTabChange: (tab: 'all' | 'overview' | 'analytics' | 'opportunities' | 'keywords' | 'intelligence') => void;
    collectionFilters: CollectionFilters;
    onCollectionFiltersChange: (filters: CollectionFilters) => void;
    collectionSortBy: string;
    onCollectionSortByChange: (sortBy: string) => void;
    collectionsSortBy: 'impressions' | 'sessions' | 'revenue' | 'volume' | 'priority';
    onCollectionsSortByChange: (sortBy: 'impressions' | 'sessions' | 'revenue' | 'volume' | 'priority') => void;
    collectionsSortDir: 'desc' | 'asc';
    onCollectionsSortDirChange: (dir: 'desc' | 'asc') => void;
    collectionsPage: number;
    onCollectionsPageChange: (page: number | ((prev: number) => number)) => void;
    collectionsPerPage: number;
    queryCache: Record<string | number, any>;
    onLoadCollectionQueries: (collectionId: number) => void;
    onToggleQueryExpand: (collectionId: number) => void;
    onAnalyzeAll: () => void;
    onRunDataForSEOSingle: (collectionId: number) => void;
    funnelData: any[];
    heatmapData: any[];
    categoryComparisonData: any[];
    trafficSourcesData: any[];
    aiTrafficData: any;
    showSavePresetModal: boolean;
    onShowSavePresetModal: (show: boolean) => void;
    presetName: string;
    onPresetNameChange: (name: string) => void;
    onSaveFilterPreset: () => void;
}

const CollectionsSection: React.FC<CollectionsSectionProps> = ({
    collections,
    opportunities,
    filteredCollections,
    sortedOpportunityCollections,
    collectionStats,
    allCollections,
    allCollectionsTotal,
    allCollectionsLoading,
    ga4Dashboard,
    collectionsLoading,
    analyzing,
    collectionTab,
    onCollectionTabChange,
    collectionFilters,
    onCollectionFiltersChange,
    collectionSortBy,
    onCollectionSortByChange,
    collectionsSortBy,
    onCollectionsSortByChange,
    collectionsSortDir,
    onCollectionsSortDirChange,
    collectionsPage,
    onCollectionsPageChange,
    collectionsPerPage,
    queryCache,
    onLoadCollectionQueries,
    onToggleQueryExpand,
    onAnalyzeAll,
    onRunDataForSEOSingle,
    funnelData,
    heatmapData,
    categoryComparisonData,
    trafficSourcesData,
    aiTrafficData,
    showSavePresetModal,
    onShowSavePresetModal,
    presetName,
    onPresetNameChange,
    onSaveFilterPreset,
}) => {
    const router = useRouter();

    // Computed chart data derived from props
    const topConvertersChartData = useMemo(() =>
        ga4Dashboard?.top_converters?.slice(0, 10).map(c => ({
            name: c.title.length > 20 ? c.title.substring(0, 20) + '...' : c.title,
            sessions: c.sessions,
            conversions: c.conversions,
            rate: parseFloat(c.conversion_rate)
        })) || [],
        [ga4Dashboard]
    );

    const conversionDistributionData = useMemo(() => [
        { name: '0-1%', value: ga4Dashboard?.top_converters?.filter(c => parseFloat(c.conversion_rate) < 1).length || 0, color: '#666666' },
        { name: '1-5%', value: ga4Dashboard?.top_converters?.filter(c => parseFloat(c.conversion_rate) >= 1 && parseFloat(c.conversion_rate) < 5).length || 0, color: '#f7b500' },
        { name: '5-10%', value: ga4Dashboard?.top_converters?.filter(c => parseFloat(c.conversion_rate) >= 5 && parseFloat(c.conversion_rate) < 10).length || 0, color: '#888888' },
        { name: '10%+', value: ga4Dashboard?.top_converters?.filter(c => parseFloat(c.conversion_rate) >= 10).length || 0, color: '#555555' },
    ], [ga4Dashboard]);

    const scatterData = useMemo(() =>
        ga4Dashboard?.top_converters?.map(c => ({
            x: c.sessions,
            y: parseFloat(c.conversion_rate),
            z: c.conversions,
            name: c.title
        })) || [],
        [ga4Dashboard]
    );

    return (
        <>
            {/* Data Source Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                {/* GSC */}
                <div className="bg-[#111111] border border-[#333333] p-6 hover:border-[#4285f4]/40 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">Search Console</span>
                        <div className="size-2 rounded-full bg-[#4285f4]"></div>
                    </div>
                    <p className="text-2xl font-bold text-white font-mono">
                        {collectionStats.avgImpressions > 0 ? collectionStats.avgImpressions.toLocaleString() : '—'}
                    </p>
                    <p className="text-[#888888] text-xs mb-3">avg impressions / collection</p>
                    <div className="pt-3 border-t border-[#333333]">
                        <p className="text-[#4285f4] font-mono text-sm">
                            {collectionStats.avgPosition > 0 ? `pos ${collectionStats.avgPosition.toFixed(1)} avg` : '—'}
                        </p>
                        <p className="text-[#555555] text-xs">30-day average</p>
                    </div>
                </div>

                {/* GA4 */}
                <div className="bg-[#111111] border border-[#333333] p-6 hover:border-[#ff6d00]/40 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">Google Analytics</span>
                        <div className="size-2 rounded-full bg-[#ff6d00]"></div>
                    </div>
                    <p className="text-2xl font-bold text-white font-mono">
                        {collectionStats.totalSessions.toLocaleString()}
                    </p>
                    <p className="text-[#888888] text-xs mb-3">total sessions</p>
                    <div className="pt-3 border-t border-[#333333]">
                        <p className="text-[#ff6d00] font-mono text-sm">
                            {collectionStats.avgBounceRate > 0 ? `${collectionStats.avgBounceRate.toFixed(1)}% avg bounce` : '—'}
                        </p>
                        <p className="text-[#555555] text-xs">{collectionStats.collectionsWithGA4} collections tracked</p>
                    </div>
                </div>

                {/* Shopify */}
                <div className="bg-[#111111] border border-[#f7b500]/30 p-6 hover:border-[#f7b500]/60 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">Shopify</span>
                        <div className="size-2 rounded-full bg-[#f7b500]"></div>
                    </div>
                    <p className="text-2xl font-bold text-[#f7b500] font-mono">
                        {collectionStats.totalShopifyRevenue > 0
                            ? `$${collectionStats.totalShopifyRevenue.toLocaleString('es-MX', { maximumFractionDigits: 0 })}`
                            : '—'}
                    </p>
                    <p className="text-[#888888] text-xs mb-3">attributed revenue MXN</p>
                    <div className="pt-3 border-t border-[#333333]">
                        <p className="text-[#f7b500] font-mono text-sm">
                            {collectionStats.totalShopifyOrders > 0 ? `${collectionStats.totalShopifyOrders} orders` : '—'}
                        </p>
                        <p className="text-[#555555] text-xs">
                            {collectionStats.lastShopifySync ? 'synced' : 'not synced yet'}
                        </p>
                    </div>
                </div>

                {/* DataForSEO */}
                <div className="bg-[#111111] border border-[#333333] p-6 hover:border-[#10b981]/40 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">DataForSEO</span>
                        <div className="size-2 rounded-full bg-[#10b981]"></div>
                    </div>
                    <p className="text-2xl font-bold text-white font-mono">
                        {collectionStats.avgDFSVolume > 0 ? collectionStats.avgDFSVolume.toLocaleString() : '—'}
                    </p>
                    <p className="text-[#888888] text-xs mb-3">avg monthly search vol</p>
                    <div className="pt-3 border-t border-[#333333]">
                        <p className="text-[#10b981] font-mono text-sm">
                            {collectionStats.collectionsWithDFS} analyzed
                        </p>
                        <p className="text-[#555555] text-xs">Mexico · Spanish</p>
                    </div>
                </div>
            </div>

            {/* Period Comparison Selector */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <select
                        value={collectionFilters.periodComparison}
                        onChange={(e) => onCollectionFiltersChange({ ...collectionFilters, periodComparison: e.target.value as any })}
                        className="bg-[#111111] border border-[#333333] px-4 py-2 text-white focus:outline-none focus:border-[#f7b500]"
                    >
                        {PERIOD_COMPARISONS.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>

                    {collectionFilters.periodComparison !== 'none' && (
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                className="size-4 rounded border-[#333333] bg-[#111111] text-[#f7b500]"
                            />
                            <span className="text-[#cccccc] text-sm">Show Before/After SEO</span>
                        </label>
                    )}
                </div>
            </div>

            {/* Collections Advanced Filters */}
            <div className="bg-[#111111] border border-[#333333] p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <FilterIcon />
                        <h3 className="text-lg font-semibold text-white">Collection Filters</h3>
                    </div>
                    <button
                        onClick={() => onCollectionFiltersChange({
                            search: '',
                            trafficRange: 'all',
                            conversionRateMin: 0,
                            conversionRateMax: 100,
                            revenueMin: '',
                            revenueMax: '',
                            aiTrafficOnly: false,
                            opportunityScore: 'all',
                            periodComparison: 'none',
                        })}
                        className="px-3 py-2 text-[#888888] hover:text-white text-sm"
                    >
                        Reset
                    </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Search */}
                    <label className="block">
                        <span className="text-[#888888] text-sm mb-1 block">Search</span>
                        <input
                            type="text"
                            placeholder="Search collections..."
                            value={collectionFilters.search}
                            onChange={(e) => onCollectionFiltersChange({ ...collectionFilters, search: e.target.value })}
                            className="w-full bg-[#252525] border border-[#333333] px-3 py-2 text-white placeholder-[#666666] focus:outline-none focus:border-[#f7b500] text-sm"
                        />
                    </label>

                    {/* Traffic Range */}
                    <label className="block">
                        <span className="text-[#888888] text-sm mb-1 block">Traffic Range</span>
                        <select
                            value={collectionFilters.trafficRange}
                            onChange={(e) => onCollectionFiltersChange({ ...collectionFilters, trafficRange: e.target.value as any })}
                            className="w-full bg-[#252525] border border-[#333333] px-3 py-2 text-white focus:outline-none focus:border-[#f7b500] text-sm"
                        >
                            {TRAFFIC_RANGE_OPTIONS.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    </label>

                    {/* Conversion Rate Range */}
                    <div>
                        <label className="text-[#888888] text-sm mb-1 block">
                            Conv. Rate: {collectionFilters.conversionRateMin}% - {collectionFilters.conversionRateMax}%
                        </label>
                        <div className="flex items-center gap-2">
                            <input
                                type="range"
                                min="0"
                                max="100"
                                value={collectionFilters.conversionRateMin}
                                onChange={(e) => onCollectionFiltersChange({ ...collectionFilters, conversionRateMin: Number(e.target.value) })}
                                className="flex-1 accent-[#f7b500]"
                            />
                            <input
                                type="range"
                                min="0"
                                max="100"
                                value={collectionFilters.conversionRateMax}
                                onChange={(e) => onCollectionFiltersChange({ ...collectionFilters, conversionRateMax: Number(e.target.value) })}
                                className="flex-1 accent-[#f7b500]"
                            />
                        </div>
                    </div>

                    {/* Opportunity Score */}
                    <label className="block">
                        <span className="text-[#888888] text-sm mb-1 block">Opportunity Score</span>
                        <select
                            value={collectionFilters.opportunityScore}
                            onChange={(e) => onCollectionFiltersChange({ ...collectionFilters, opportunityScore: e.target.value as any })}
                            className="w-full bg-[#252525] border border-[#333333] px-3 py-2 text-white focus:outline-none focus:border-[#f7b500] text-sm"
                        >
                            {OPPORTUNITY_SCORE_OPTIONS.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    </label>

                    {/* AI Traffic Only */}
                    <div className="flex items-end">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={collectionFilters.aiTrafficOnly}
                                onChange={(e) => onCollectionFiltersChange({ ...collectionFilters, aiTrafficOnly: e.target.checked })}
                                className="size-4 rounded border-[#333333] bg-[#111111] text-[#f7b500] focus:ring-[#f7b500]"
                            />
                            <span className="text-[#cccccc] text-sm">AI Traffic Only</span>
                        </label>
                    </div>
                </div>
            </div>

            {/* Collections Sub-Tabs */}
            <div className="flex gap-1 bg-[#252525] p-1 mb-6">
                {[
                    { id: 'all', label: 'All Collections' },
                    { id: 'intelligence', label: 'Intelligence' },
                    { id: 'overview', label: 'Overview' },
                    { id: 'analytics', label: 'Analytics & Charts' },
                    { id: 'opportunities', label: 'Opportunities' },
                    { id: 'keywords', label: 'Keywords' },
                ].map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => onCollectionTabChange(tab.id as any)}
                        className={`flex items-center gap-2 px-4 py-2 transition-all ${collectionTab === tab.id
                            ? 'bg-[#f7b500] text-black font-medium'
                            : 'text-[#888888] hover:text-white'
                            }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* All Collections */}
            {collectionTab === 'all' && (
                <div className="bg-[#111111] border border-[#333333] overflow-hidden">
                    <div className="p-4 border-b border-[#333333] flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-white">All Collections</h3>
                        <span className="text-[#666666] text-sm">{allCollectionsTotal} total</span>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-[#333333] bg-[#252525]">
                                    <th className="py-3 px-4 text-left text-[#888888] font-medium">Collection</th>
                                    <th className="p-3 text-left text-[#888888] font-medium">Status</th>
                                    <th className="p-3 text-right text-[#4285f4] font-medium cursor-pointer" onClick={() => { onCollectionsSortByChange('impressions'); onCollectionsSortDirChange(collectionsSortDir === 'desc' ? 'asc' : 'desc'); }}>Impr.</th>
                                    <th className="p-3 text-right text-[#4285f4] font-medium">Pos.</th>
                                    <th className="p-3 text-right text-[#ff6d00] font-medium cursor-pointer" onClick={() => { onCollectionsSortByChange('sessions'); onCollectionsSortDirChange(collectionsSortDir === 'desc' ? 'asc' : 'desc'); }}>Sessions</th>
                                    <th className="p-3 text-right text-[#f7b500] font-medium cursor-pointer" onClick={() => { onCollectionsSortByChange('revenue'); onCollectionsSortDirChange(collectionsSortDir === 'desc' ? 'asc' : 'desc'); }}>Revenue</th>
                                    <th className="p-3 text-right text-[#10b981] font-medium cursor-pointer" onClick={() => { onCollectionsSortByChange('volume'); onCollectionsSortDirChange(collectionsSortDir === 'desc' ? 'asc' : 'desc'); }}>Vol/mo</th>
                                    <th className="p-3 text-center text-[#888888] font-medium">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {allCollectionsLoading ? (
                                    <tr>
                                        <td colSpan={8} className="py-8 text-center text-[#666666]">
                                            <div className="flex items-center justify-center gap-2">
                                                <div className="size-5 border-2 border-[#f7b500] border-t-transparent animate-spin"></div>
                                                Loading collections...
                                            </div>
                                        </td>
                                    </tr>
                                ) : allCollections.length === 0 ? (
                                    <tr>
                                        <td colSpan={8} className="py-8 text-center text-[#666666]">No collections found</td>
                                    </tr>
                                ) : (
                                    allCollections.map((c) => (
                                        <tr key={c.id} className="border-b border-[#333333] hover:bg-[#252525] transition-colors">
                                            <td className="py-3 px-4">
                                                <button
                                                    type="button"
                                                    className="text-white font-medium hover:text-[#f7b500] cursor-pointer transition-colors text-left bg-transparent border-0 p-0"
                                                    onClick={() => router.push(`/seo/collections/${c.id}`)}
                                                >{c.title}</button>
                                                <p className="text-[#666666] text-xs">{c.category}</p>
                                                {c.dataforseo_primary_keyword && (
                                                    <p className="text-[#10b981] text-xs mt-0.5">⌕ {c.dataforseo_primary_keyword}</p>
                                                )}
                                            </td>
                                            <td className="p-3">
                                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                                    c.status === 'published' ? 'bg-green-500/20 text-green-400' :
                                                    c.status === 'ready' ? 'bg-[#f7b500]/20 text-[#f7b500]' :
                                                    c.status === 'analyzed' ? 'bg-blue-500/20 text-blue-400' :
                                                    'bg-[#333333] text-[#888888]'
                                                }`}>{c.status}</span>
                                            </td>
                                            <td className="p-3 text-right font-mono text-white">{(c.impressions || 0) > 0 ? c.impressions.toLocaleString() : '—'}</td>
                                            <td className="p-3 text-right font-mono">
                                                {c.position > 0 ? (
                                                    <span className={c.position <= 10 ? 'text-green-400' : c.position <= 20 ? 'text-[#f7b500]' : 'text-red-400'}>
                                                        {c.position.toFixed(1)}
                                                    </span>
                                                ) : '—'}
                                            </td>
                                            <td className="p-3 text-right font-mono text-white">{(c.ga4_sessions || 0) > 0 ? c.ga4_sessions!.toLocaleString() : '—'}</td>
                                            <td className="p-3 text-right font-mono">
                                                {(c.shopify_attributed_revenue || 0) > 0 ? (
                                                    <span className="text-[#f7b500]">${(c.shopify_attributed_revenue || 0).toLocaleString('en-MX', { maximumFractionDigits: 0 })}</span>
                                                ) : '—'}
                                            </td>
                                            <td className="p-3 text-right font-mono">
                                                {(c.dataforseo_volume || 0) > 0 ? (
                                                    <span className="text-[#10b981]">{(c.dataforseo_volume || 0).toLocaleString()}</span>
                                                ) : '—'}
                                            </td>
                                            <td className="p-3 text-center">
                                                <button
                                                    onClick={() => router.push(`/seo/collections/${c.id}`)}
                                                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#f7b500]/20 text-[#f7b500] border border-[#f7b500]/30 rounded hover:bg-[#f7b500]/30 transition-colors text-xs font-medium"
                                                >
                                                    <svg className="size-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                                    </svg>
                                                    Edit
                                                </button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                    {/* Pagination */}
                    {allCollectionsTotal > collectionsPerPage && (
                        <div className="flex items-center justify-between p-4 border-t border-[#333333]">
                            <span className="text-[#666666] text-sm">
                                Showing {((collectionsPage - 1) * collectionsPerPage) + 1}–{Math.min(collectionsPage * collectionsPerPage, allCollectionsTotal)} of {allCollectionsTotal}
                            </span>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => onCollectionsPageChange((p: number) => Math.max(1, p - 1))}
                                    disabled={collectionsPage === 1}
                                    className="px-3 py-1.5 bg-[#252525] border border-[#333333] text-white text-sm disabled:opacity-40 hover:border-[#555555] transition-colors"
                                >
                                    Previous
                                </button>
                                {Array.from({ length: Math.min(5, Math.ceil(allCollectionsTotal / collectionsPerPage)) }, (_, i) => i + 1).map(page => (
                                    <button
                                        key={page}
                                        onClick={() => onCollectionsPageChange(page)}
                                        className={`px-3 py-1.5 text-sm transition-colors ${collectionsPage === page ? 'bg-[#f7b500] text-black font-medium' : 'bg-[#252525] border border-[#333333] text-white hover:border-[#555555]'}`}
                                    >
                                        {page}
                                    </button>
                                ))}
                                <button
                                    onClick={() => onCollectionsPageChange((p: number) => Math.min(Math.ceil(allCollectionsTotal / collectionsPerPage), p + 1))}
                                    disabled={collectionsPage >= Math.ceil(allCollectionsTotal / collectionsPerPage)}
                                    className="px-3 py-1.5 bg-[#252525] border border-[#333333] text-white text-sm disabled:opacity-40 hover:border-[#555555] transition-colors"
                                >
                                    Next
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Collections Overview */}
            {collectionTab === 'overview' && (
                <div className="bg-[#111111] border border-[#333333] overflow-hidden">
                    <div className="p-6 border-b border-[#333333]">
                        <h3 className="text-lg font-semibold text-white">Top Converting Collections</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-[#333333] bg-[#252525]">
                                    <th className="py-3 px-4 text-left text-[#888888] text-sm font-medium">Rank</th>
                                    <th className="py-3 px-4 text-left text-[#888888] text-sm font-medium">Collection</th>
                                    <th className="py-3 px-4 text-right text-[#888888] text-sm font-medium">Sessions</th>
                                    <th className="py-3 px-4 text-right text-[#888888] text-sm font-medium">Conversions</th>
                                    <th className="py-3 px-4 text-right text-[#888888] text-sm font-medium">Conv. Rate</th>
                                    <th className="py-3 px-4 text-right text-[#888888] text-sm font-medium">Revenue</th>
                                </tr>
                            </thead>
                            <tbody>
                                {collectionsLoading ? (
                                    <tr>
                                        <td colSpan={6} className="py-8 text-center text-[#666666]">
                                            <div className="flex items-center justify-center gap-2">
                                                <div className="size-5 border-2 border-[#f7b500] border-t-transparent animate-spin"></div>
                                                Loading collections...
                                            </div>
                                        </td>
                                    </tr>
                                ) : (
                                    ga4Dashboard?.top_converters?.slice(0, 10).map((collection, index) => {
                                        const rate = parseFloat(collection.conversion_rate);
                                        let rateColor = 'text-[#666666]';
                                        if (rate >= 10) rateColor = 'text-[#f7b500]';
                                        else if (rate >= 5) rateColor = 'text-[#f7b500]';
                                        else if (rate >= 2) rateColor = 'text-[#888888]';

                                        return (
                                            <tr key={collection.id} className="border-b border-[#333333] hover:bg-[#111111] transition-colors">
                                                <td className="p-4">
                                                    <span className="text-[#666666] font-mono">#{index + 1}</span>
                                                </td>
                                                <td className="p-4">
                                                    <button
                                                        type="button"
                                                        className="text-white font-medium hover:text-[#f7b500] cursor-pointer transition-colors text-left bg-transparent border-0 p-0"
                                                        onClick={() => router.push(`/seo/collections/${collection.id}`)}
                                                    >
                                                        {collection.title}
                                                    </button>
                                                </td>
                                                <td className="p-4 text-right text-white font-mono">{collection.sessions.toLocaleString()}</td>
                                                <td className="p-4 text-right text-white font-mono">{collection.conversions}</td>
                                                <td className="p-4 text-right">
                                                    <span className={`font-mono font-bold ${rateColor}`}>{collection.conversion_rate}%</span>
                                                </td>
                                                <td className="p-4 text-right text-[#f7b500] font-mono">
                                                    ${(collection.conversions * 150).toLocaleString()}
                                                </td>
                                            </tr>
                                        );
                                    })
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Collections Analytics */}
            {collectionTab === 'analytics' && (
                <div className="space-y-6">
                    {/* Funnel Chart */}
                    <div className="bg-[#111111] border border-[#333333] p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold text-white">SEO Conversion Funnel</h3>
                            <span className="text-xs text-[#555555]">real data — loaded products</span>
                        </div>
                        <ChartContainer config={funnelConfig} className="h-80 w-full">
                            <FunnelChart>
                                <ChartTooltip content={<ChartTooltipContent />} />
                                <Funnel
                                    dataKey="value"
                                    data={funnelData}
                                    isAnimationActive
                                    label={(entry: any) => `${entry.name}: ${entry.value.toLocaleString()}`}
                                >
                                    {funnelData.map((entry) => (
                                        <Cell key={entry.name || entry.fill} fill={entry.fill} />
                                    ))}
                                </Funnel>
                            </FunnelChart>
                        </ChartContainer>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="bg-[#111111] border border-[#333333] p-6">
                            <h3 className="text-lg font-semibold text-white mb-4">Top Collections by Sessions</h3>
                            <ChartContainer config={topCollectionsConfig} className="h-80 w-full">
                                <BarChart data={topConvertersChartData} layout="vertical">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#333333" />
                                    <XAxis type="number" stroke="#666666" />
                                    <YAxis dataKey="name" type="category" width={150} stroke="#888888" fontSize={11} />
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                    <Bar dataKey="sessions" fill="#3b82f6" name="Sessions" />
                                    <Bar dataKey="conversions" fill="#22c55e" name="Conversions" />
                                </BarChart>
                            </ChartContainer>
                        </div>

                        <div className="bg-[#111111] border border-[#333333] p-6">
                            <h3 className="text-lg font-semibold text-white mb-4">Conversion Rate Distribution</h3>
                            <ChartContainer config={conversionDistConfig} className="h-80 w-full">
                                <PieChart>
                                    <Pie
                                        data={conversionDistributionData}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={60}
                                        outerRadius={100}
                                        paddingAngle={5}
                                        dataKey="value"
                                        label={({ name, value }) => `${name}: ${value}`}
                                    >
                                        {conversionDistributionData.map((entry) => (
                                            <Cell key={entry.name || entry.color} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                </PieChart>
                            </ChartContainer>
                        </div>
                    </div>

                    {/* Category Comparison & Traffic Sources */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="bg-[#111111] border border-[#333333] p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-lg font-semibold text-white">Avg SEO Score by Product Type</h3>
                                <span className="text-xs text-[#555555]">real data — loaded products</span>
                            </div>
                            <ChartContainer config={seoScoreConfig} className="h-80 w-full">
                                <BarChart data={categoryComparisonData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#333333" />
                                    <XAxis dataKey="category" stroke="#666666" fontSize={10} />
                                    <YAxis stroke="#666666" domain={[0, 100]} />
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                    <Bar dataKey="performance" fill="#f7b500" name="Avg SEO Score" />
                                </BarChart>
                            </ChartContainer>
                        </div>

                        <div className="bg-[#111111] border border-[#333333] p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-lg font-semibold text-white">Traffic Sources</h3>
                                <span className="text-xs text-[#555555]">{aiTrafficData ? 'real GA4 data' : 'from GA4 dashboard'}</span>
                            </div>
                            {trafficSourcesData.length > 0 ? (
                                <ChartContainer config={trafficSourcesConfig} className="h-80 w-full">
                                    <PieChart>
                                        <Pie
                                            data={trafficSourcesData}
                                            cx="50%"
                                            cy="50%"
                                            outerRadius={100}
                                            dataKey="value"
                                            label={({ name, value }) => `${name}: ${value.toLocaleString()}`}
                                        >
                                            {trafficSourcesData.map((entry) => (
                                                <Cell key={entry.name || entry.color} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                    </PieChart>
                                </ChartContainer>
                            ) : (
                                <div className="flex items-center justify-center h-80 text-[#555555] text-sm">
                                    No traffic data available — sync GA4 first
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Heatmap — real avg SEO score per product type */}
                    <div className="bg-[#111111] border border-[#333333] p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold text-white">Revenue by Product Type</h3>
                            <span className="text-xs text-[#555555]">real data — loaded products</span>
                        </div>
                        <ChartContainer config={revenueByTypeConfig} className="h-80 w-full">
                            <BarChart data={heatmapData} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" stroke="#333333" />
                                <XAxis type="number" stroke="#666666" tickFormatter={(v) => v >= 1000 ? `$${(v/1000).toFixed(0)}K` : `$${v}`} />
                                <YAxis dataKey="category" type="category" width={140} stroke="#888888" fontSize={11} />
                                <ChartTooltip content={<ChartTooltipContent />} />
                                <Bar dataKey="revenue" name="Revenue ($)" radius={[0, 4, 4, 0]}>
                                    {heatmapData.map((entry) => (
                                        <Cell
                                            key={entry.category || entry.name}
                                            fill={entry.performance >= 80 ? '#22c55e' : entry.performance >= 60 ? '#f7b500' : '#888888'}
                                        />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ChartContainer>
                    </div>

                    <div className="bg-[#111111] border border-[#333333] p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">Sessions vs Conversion Rate</h3>
                        <ChartContainer config={scatterConfig} className="h-80 w-full">
                            <ScatterChart>
                                <CartesianGrid strokeDasharray="3 3" stroke="#333333" />
                                <XAxis type="number" dataKey="x" name="Sessions" stroke="#666666" />
                                <YAxis type="number" dataKey="y" name="Conversion Rate %" stroke="#666666" />
                                <ZAxis type="number" dataKey="z" range={[50, 400]} />
                                <ChartTooltip content={<ChartTooltipContent />} />
                                <Scatter data={scatterData} fill="#f7b500" fillOpacity={0.6} />
                            </ScatterChart>
                        </ChartContainer>
                    </div>
                </div>
            )}

            {/* Collections Opportunities */}
            {collectionTab === 'opportunities' && (
                <>
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h3 className="text-lg font-semibold text-white">Collections Performance</h3>
                            <p className="text-[#888888] text-sm">All 4 data sources — click column headers to sort</p>
                        </div>
                        <button
                            onClick={onAnalyzeAll}
                            disabled={analyzing}
                            className="flex items-center gap-2 px-4 py-2 bg-[#f7b500] hover:bg-[#f7b500]/90 text-black font-medium transition-colors disabled:opacity-50"
                        >
                            {analyzing ? (
                                <><div className="size-4 border-2 border-black border-t-transparent animate-spin"></div>Analyzing…</>
                            ) : (
                                <><RefreshIcon />Analyze All</>
                            )}
                        </button>
                    </div>

                    <div className="bg-[#111111] border border-[#333333] overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                                <thead>
                                    <tr className="border-b border-[#333333] bg-[#252525]">
                                        <th className="py-3 px-4 text-left text-[#888888] font-medium min-w-[160px]">Collection</th>
                                        {/* GSC */}
                                        <th className="p-3 text-right text-[#4285f4] font-medium cursor-pointer hover:text-white whitespace-nowrap" onClick={() => onCollectionSortByChange('impressions')}>Impress. {collectionSortBy === 'impressions' ? '↓' : ''}</th>
                                        <th className="p-3 text-right text-[#4285f4] font-medium cursor-pointer hover:text-white" onClick={() => onCollectionSortByChange('position')}>Pos. {collectionSortBy === 'position' ? '↑' : ''}</th>
                                        <th className="p-3 text-right text-[#4285f4] font-medium whitespace-nowrap">CTR</th>
                                        {/* GA4 */}
                                        <th className="p-3 text-right text-[#ff6d00] font-medium cursor-pointer hover:text-white" onClick={() => onCollectionSortByChange('sessions')}>Sessions {collectionSortBy === 'sessions' ? '↓' : ''}</th>
                                        <th className="p-3 text-right text-[#ff6d00] font-medium cursor-pointer hover:text-white" onClick={() => onCollectionSortByChange('bounce_rate')}>Bounce {collectionSortBy === 'bounce_rate' ? '↓' : ''}</th>
                                        <th className="p-3 text-right text-[#ff6d00] font-medium whitespace-nowrap">Conv.</th>
                                        {/* Shopify */}
                                        <th className="p-3 text-right text-[#f7b500] font-medium cursor-pointer hover:text-white whitespace-nowrap" onClick={() => onCollectionSortByChange('revenue')}>Revenue {collectionSortBy === 'revenue' ? '↓' : ''}</th>
                                        <th className="p-3 text-right text-[#f7b500] font-medium">Orders</th>
                                        <th className="p-3 text-right text-[#f7b500] font-medium whitespace-nowrap">LLM Rev.</th>
                                        {/* DataForSEO */}
                                        <th className="p-3 text-right text-[#10b981] font-medium cursor-pointer hover:text-white" onClick={() => onCollectionSortByChange('volume')}>Vol/mo {collectionSortBy === 'volume' ? '↓' : ''}</th>
                                        <th className="p-3 text-right text-[#10b981] font-medium">Comp.</th>
                                        <th className="p-3 text-right text-[#10b981] font-medium">CPC</th>
                                        <th className="p-3 text-center text-[#888888] font-medium">DFS</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sortedOpportunityCollections.map((c) => (
                                        <tr key={c.id} className="border-b border-[#1a1a1a] hover:bg-[#1a1a1a] transition-colors">
                                            <td className="py-3 px-4">
                                                <p className="text-white font-medium line-clamp-1">{c.title}</p>
                                                <p className="text-[#555555] text-[10px]">{c.category}</p>
                                            </td>
                                            {/* GSC */}
                                            <td className="p-3 text-right text-white font-mono">{c.impressions > 0 ? `${(c.impressions / 1000).toFixed(1)}k` : <span className="text-[#444]">—</span>}</td>
                                            <td className="p-3 text-right font-mono">
                                                <span className={c.position > 0 && c.position <= 3 ? 'text-[#f7b500]' : c.position <= 10 ? 'text-white' : 'text-[#666]'}>
                                                    {c.position > 0 ? `#${c.position.toFixed(1)}` : <span className="text-[#444]">—</span>}
                                                </span>
                                            </td>
                                            <td className="p-3 text-right text-[#888] font-mono">{c.ctr > 0 ? `${(c.ctr * 100).toFixed(2)}%` : <span className="text-[#444]">—</span>}</td>
                                            {/* GA4 */}
                                            <td className="p-3 text-right text-white font-mono">{(c.ga4_sessions || 0) > 0 ? (c.ga4_sessions || 0).toLocaleString() : <span className="text-[#444]">—</span>}</td>
                                            <td className="p-3 text-right font-mono">
                                                {(c.ga4_bounce_rate || 0) > 0 ? (
                                                    <span className={(c.ga4_bounce_rate || 0) > 70 ? 'text-red-400' : (c.ga4_bounce_rate || 0) > 50 ? 'text-[#888]' : 'text-[#10b981]'}>
                                                        {(c.ga4_bounce_rate || 0).toFixed(1)}%
                                                    </span>
                                                ) : <span className="text-[#444]">—</span>}
                                            </td>
                                            <td className="p-3 text-right font-mono">
                                                {(c.ga4_conversion_rate || 0) > 0 ? (
                                                    <span className={(c.ga4_conversion_rate || 0) >= 2 ? 'text-[#f7b500]' : (c.ga4_conversion_rate || 0) >= 0.5 ? 'text-[#888]' : 'text-[#666]'}>
                                                        {(c.ga4_conversion_rate || 0).toFixed(2)}%
                                                    </span>
                                                ) : <span className="text-[#444]">—</span>}
                                            </td>
                                            {/* Shopify */}
                                            <td className="p-3 text-right font-mono">
                                                {(c.shopify_attributed_revenue || 0) > 0
                                                    ? <span className="text-[#f7b500]">${(c.shopify_attributed_revenue || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 })}</span>
                                                    : <span className="text-[#444]">—</span>}
                                            </td>
                                            <td className="p-3 text-right text-[#888] font-mono">{(c.shopify_attributed_orders || 0) > 0 ? c.shopify_attributed_orders : <span className="text-[#444]">—</span>}</td>
                                            <td className="p-3 text-right font-mono">
                                                {(c.shopify_llm_revenue || 0) > 0
                                                    ? <span className="text-[#f7b500]">${(c.shopify_llm_revenue || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 })}</span>
                                                    : <span className="text-[#444]">—</span>}
                                            </td>
                                            {/* DataForSEO */}
                                            <td className="p-3 text-right text-white font-mono">{(c.dataforseo_volume || 0) > 0 ? (c.dataforseo_volume || 0).toLocaleString() : <span className="text-[#444]">—</span>}</td>
                                            <td className="p-3 text-right font-mono">
                                                {c.dataforseo_competition ? (
                                                    <span className={c.dataforseo_competition === 'HIGH' ? 'text-red-400' : c.dataforseo_competition === 'MEDIUM' ? 'text-[#f7b500]' : 'text-[#10b981]'}>
                                                        {c.dataforseo_competition}
                                                    </span>
                                                ) : <span className="text-[#444]">—</span>}
                                            </td>
                                            <td className="p-3 text-right text-[#888] font-mono">{(c.dataforseo_cpc || 0) > 0 ? `$${(c.dataforseo_cpc || 0).toFixed(2)}` : <span className="text-[#444]">—</span>}</td>
                                            <td className="p-3 text-center">
                                                <button
                                                    onClick={() => onRunDataForSEOSingle(c.id)}
                                                    className="px-2 py-0.5 text-[#10b981] border border-[#10b981]/30 hover:bg-[#10b981]/10 transition-colors text-[10px]"
                                                    title="Run DataForSEO for this collection"
                                                >
                                                    Run
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {sortedOpportunityCollections.length === 0 && (
                            <div className="text-center py-12 text-[#666666]">
                                No collections match your current filters
                            </div>
                        )}
                    </div>

                    <div className="mt-4 p-4 border border-[#333333] bg-[#252525]">
                        <Link href="/seo/collections/list" className="flex items-center justify-center gap-2 text-[#f7b500] hover:text-[#f7b500]/80 transition-colors">
                            <span>View Full Collections Page</span>
                            <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                        </Link>
                        <p className="text-center text-[#666666] text-xs mt-1">Access status filters, sorting, pagination, and bulk actions</p>
                    </div>
                </>
            )}

            {/* Intelligence Tab */}
            {collectionTab === 'intelligence' && (
                <IntelligenceTab collections={allCollections} />
            )}

            {/* Keywords Tab */}
            {collectionTab === 'keywords' && (
                <div className="space-y-4">
                    <div className="bg-[#111111] border border-[#333333] overflow-hidden">
                        <div className="p-5 border-b border-[#333333] flex items-center justify-between">
                            <div>
                                <h3 className="text-base font-semibold text-white">GSC Query Breakdown by Collection</h3>
                                <p className="text-[#666666] text-xs mt-0.5">Click a row to expand its search queries</p>
                            </div>
                            <span className="text-[#555555] text-xs">{collections.filter(c => c.impressions > 0).length} collections with GSC data</span>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                                <thead>
                                    <tr className="border-b border-[#333333] bg-[#252525]">
                                        <th className="py-3 px-4 text-left text-[#888888] w-6"></th>
                                        <th className="py-3 px-4 text-left text-[#888888] font-medium">Collection</th>
                                        <th className="p-3 text-right text-[#4285f4] font-medium">Impressions</th>
                                        <th className="p-3 text-right text-[#4285f4] font-medium">Position</th>
                                        <th className="p-3 text-right text-[#10b981] font-medium">DFS Vol.</th>
                                        <th className="p-3 text-right text-[#10b981] font-medium">Top Competitor</th>
                                        <th className="p-3 text-left text-[#10b981] font-medium">SERP Features</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {collections
                                        .filter(c => c.impressions > 0 || (c.dataforseo_volume || 0) > 0)
                                        .sort((a, b) => b.impressions - a.impressions)
                                        .map((c) => (
                                        <>
                                            <tr
                                                key={c.id}
                                                className="border-b border-[#1a1a1a] hover:bg-[#1a1a1a] cursor-pointer transition-colors"
                                                onClick={() => {
                                                    onLoadCollectionQueries(c.id);
                                                    onToggleQueryExpand(c.id);
                                                }}
                                            >
                                                <td className="py-3 px-4 text-[#555555]">{queryCache[`expanded_${c.id}`] ? '▼' : '▶'}</td>
                                                <td className="py-3 px-4">
                                                    <p className="text-white font-medium">{c.title}</p>
                                                    <p className="text-[#555555] text-[10px]">{c.category}</p>
                                                </td>
                                                <td className="p-3 text-right text-white font-mono">{c.impressions > 0 ? `${(c.impressions / 1000).toFixed(1)}k` : '—'}</td>
                                                <td className="p-3 text-right font-mono">
                                                    <span className={c.position > 0 && c.position <= 3 ? 'text-[#f7b500]' : c.position <= 10 ? 'text-white' : 'text-[#666]'}>
                                                        {c.position > 0 ? `#${c.position.toFixed(1)}` : '—'}
                                                    </span>
                                                </td>
                                                <td className="p-3 text-right text-white font-mono">{(c.dataforseo_volume || 0) > 0 ? (c.dataforseo_volume || 0).toLocaleString() : <span className="text-[#444]">—</span>}</td>
                                                <td className="p-3 text-right text-[#888] font-mono truncate max-w-[120px]">{c.dataforseo_top_competitor || <span className="text-[#444]">—</span>}</td>
                                                <td className="p-3">
                                                    <div className="flex flex-wrap gap-1">
                                                        {(c.dataforseo_serp_features || []).slice(0, 3).map((f: string) => (
                                                            <span key={f} className="px-1.5 py-0.5 bg-[#252525] text-[#10b981] text-[10px] rounded">{f}</span>
                                                        ))}
                                                    </div>
                                                </td>
                                            </tr>
                                            {queryCache[`expanded_${c.id}`] && (
                                                <tr key={`queries_${c.id}`} className="border-b border-[#1a1a1a] bg-[#0a0a0a]">
                                                    <td colSpan={7} className="px-4 py-3">
                                                        {!queryCache[c.id] ? (
                                                            <p className="text-[#555555] text-xs py-2">Loading queries…</p>
                                                        ) : queryCache[c.id].length === 0 ? (
                                                            <p className="text-[#555555] text-xs py-2">No queries found — run Analyze first.</p>
                                                        ) : (
                                                            <table className="w-full text-xs">
                                                                <thead>
                                                                    <tr className="text-[#555555]">
                                                                        <th className="text-left pb-2 pr-4">Query</th>
                                                                        <th className="text-right pb-2 px-3">Clicks</th>
                                                                        <th className="text-right pb-2 px-3">Impress.</th>
                                                                        <th className="text-right pb-2 px-3">CTR</th>
                                                                        <th className="text-right pb-2 px-3">Pos.</th>
                                                                        <th className="text-left pb-2 px-3">Intent</th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {queryCache[c.id].slice(0, 10).map((q: any, i: number) => (
                                                                        <tr key={q.query || `query-${i}`} className="border-t border-[#1a1a1a]">
                                                                            <td className="py-1.5 pr-4 text-[#888]">{q.query}</td>
                                                                            <td className="py-1.5 px-3 text-right text-white font-mono">{q.clicks}</td>
                                                                            <td className="py-1.5 px-3 text-right text-[#666] font-mono">{q.impressions}</td>
                                                                            <td className="py-1.5 px-3 text-right text-[#666] font-mono">{(q.ctr * 100).toFixed(1)}%</td>
                                                                            <td className="py-1.5 px-3 text-right font-mono">
                                                                                <span className={q.position <= 3 ? 'text-[#f7b500]' : q.position <= 10 ? 'text-white' : 'text-[#555]'}>
                                                                                    #{q.position?.toFixed(1)}
                                                                                </span>
                                                                            </td>
                                                                            <td className="py-1.5 px-3 text-[#555]">{q.intent || '—'}</td>
                                                                        </tr>
                                                                    ))}
                                                                </tbody>
                                                            </table>
                                                        )}
                                                    </td>
                                                </tr>
                                            )}
                                        </>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* Save Filter Preset Modal */}
            {showSavePresetModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-[#111111] border border-[#333333] p-6 w-96">
                        <h3 className="text-lg font-semibold text-white mb-4">Save Filter Preset</h3>
                        <input
                            type="text"
                            placeholder="Preset name..."
                            value={presetName}
                            onChange={(e) => onPresetNameChange(e.target.value)}
                            className="w-full bg-[#252525] border border-[#333333] px-4 py-2 text-white placeholder-[#666666] focus:outline-none focus:border-[#f7b500] mb-4"
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => onShowSavePresetModal(false)}
                                className="px-4 py-2 text-[#888888] hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={onSaveFilterPreset}
                                disabled={!presetName.trim()}
                                className="px-4 py-2 bg-[#f7b500] hover:bg-[#f7b500]/90 text-black font-medium transition-colors disabled:opacity-50"
                            >
                                Save
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

// ============================================================================
// Intelligence Tab Component
// ============================================================================

function IntelligenceTab({ collections }: { collections: CollectionOptimizer[] }) {
    const router = useRouter();
    const [health, setHealth] = useState<any>(null);
    const [opportunities, setOpportunities] = useState<CollectionOpportunity[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [syncing, setSyncing] = useState(false);

    const loadData = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const [healthRes, oppRes] = await Promise.all([
                collectionsAIAPI.getHealthOverview(),
                collectionsAIAPI.discoverOpportunities(15),
            ]);
            setHealth(healthRes.data);
            setOpportunities(oppRes.data);
        } catch (err: any) {
            setError(err.message || 'Failed to load intelligence data');
        } finally {
            setLoading(false);
        }
    }, []);

    const syncAllCollections = useCallback(async () => {
        if (collections.length === 0) return;
        try {
            setSyncing(true);
            const ids = collections.slice(0, 20).map(c => c.id);
            await collectionsAIAPI.syncAllBatch(ids);
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Sync failed');
        } finally {
            setSyncing(false);
        }
    }, [collections, loadData]);

    useEffect(() => {
        loadData();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <div className="flex items-center gap-3">
                    <div className="size-5 border-2 border-[#f7b500] border-t-transparent rounded-full animate-spin" />
                    <span className="text-[#888888]">Loading collection intelligence…</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
                {error}
                <button onClick={loadData} className="ml-3 underline text-red-300">Retry</button>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Health Score + Summary */}
            {health && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                        {/* Health Score */}
                        <div className="bg-[#111111] border border-[#333333] p-5">
                            <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">Health Score</span>
                            <p className={`text-4xl font-bold font-mono mt-2 ${
                                (health.health_score?.score || 0) >= 70 ? 'text-green-400' :
                                (health.health_score?.score || 0) >= 40 ? 'text-[#f7b500]' :
                                'text-red-400'
                            }`}>
                                {health.health_score?.score || 0}
                            </p>
                            <p className="text-[#555555] text-xs mt-1">{health.total_collections} collections</p>
                        </div>
                        {/* Content Coverage */}
                        <div className="bg-[#111111] border border-[#333333] p-5">
                            <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">Content</span>
                            <p className="text-2xl font-bold font-mono mt-2 text-white">
                                {health.content_coverage?.content_rate || 0}%
                            </p>
                            <p className="text-[#555555] text-xs mt-1">
                                {health.content_coverage?.with_content || 0} / {health.total_collections} have content
                            </p>
                        </div>
                        {/* Cannibalization Alerts */}
                        <div className="bg-[#111111] border border-[#333333] p-5">
                            <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">Cannibal Alerts</span>
                            <p className={`text-2xl font-bold font-mono mt-2 ${
                                (health.cannibalization?.open_alerts || 0) > 0 ? 'text-red-400' : 'text-green-400'
                            }`}>
                                {health.cannibalization?.open_alerts || 0}
                            </p>
                            <p className="text-[#555555] text-xs mt-1">open conflicts</p>
                        </div>
                        {/* Revenue at Risk */}
                        <div className="bg-[#111111] border border-[#333333] p-5">
                            <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">Revenue at Risk</span>
                            <p className="text-2xl font-bold font-mono mt-2 text-[#f7b500]">
                                ${(health.opportunities?.revenue_at_risk || 0).toLocaleString('en-MX', { maximumFractionDigits: 0 })}
                            </p>
                            <p className="text-[#555555] text-xs mt-1">
                                {health.opportunities?.unoptimized_count || 0} unoptimized
                            </p>
                        </div>
                        {/* AI Visibility */}
                        <div className="bg-[#111111] border border-[#333333] p-5">
                            <span className="text-[#888888] text-xs font-medium uppercase tracking-wider">AI Traffic</span>
                            <p className="text-2xl font-bold font-mono mt-2 text-purple-400">
                                {(health.ai_visibility?.total_ai_sessions || 0).toLocaleString()}
                            </p>
                            <p className="text-[#555555] text-xs mt-1">
                                {health.ai_visibility?.collections_with_ai_traffic || 0} collections with AI traffic
                            </p>
                        </div>
                    </div>

                    {/* Health Score Breakdown */}
                    {health.health_score?.breakdown && (
                        <div className="bg-[#111111] border border-[#333333] p-5">
                            <h3 className="text-sm font-semibold text-white mb-4">Health Score Breakdown</h3>
                            <div className="space-y-3">
                                {Object.entries(health.health_score.breakdown as Record<string, number>).map(([key, value]) => (
                                    <div key={key} className="flex items-center gap-3">
                                        <span className="text-[#888888] text-xs w-40 capitalize">{key.replace(/_/g, ' ')}</span>
                                        <div className="flex-1 bg-[#252525] h-2 rounded-full overflow-hidden">
                                            <div
                                                className="h-full rounded-full transition-all"
                                                style={{
                                                    width: `${Math.min(100, (value / 25) * 100)}%`,
                                                    backgroundColor: value > 15 ? '#22c55e' : value > 8 ? '#f7b500' : '#ef4444'
                                                }}
                                            />
                                        </div>
                                        <span className="text-white text-xs font-mono w-12 text-right">{value.toFixed(1)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Status Breakdown */}
                    {health.status_breakdown && (
                        <div className="bg-[#111111] border border-[#333333] p-5">
                            <h3 className="text-sm font-semibold text-white mb-3">Optimization Status</h3>
                            <div className="flex gap-3 flex-wrap">
                                {Object.entries(health.status_breakdown as Record<string, number>).map(([status, count]) => {
                                    const colors: Record<string, string> = {
                                        pending: 'bg-[#333333] text-[#888888]',
                                        analyzing: 'bg-blue-500/20 text-blue-400',
                                        analyzed: 'bg-blue-500/20 text-blue-400',
                                        generating: 'bg-[#f7b500]/20 text-[#f7b500]',
                                        ready: 'bg-[#f7b500]/20 text-[#f7b500]',
                                        published: 'bg-green-500/20 text-green-400',
                                        tracking: 'bg-purple-500/20 text-purple-400',
                                    };
                                    return (
                                        <div key={status} className={`px-3 py-2 rounded text-sm font-medium ${colors[status] || colors.pending}`}>
                                            {status}: <span className="font-mono">{count}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* Safe Opportunities — All 4 Data Sources */}
            <div className="bg-[#111111] border border-[#333333] overflow-hidden">
                <div className="p-5 border-b border-[#333333] flex items-center justify-between">
                    <div>
                        <h3 className="text-base font-semibold text-white">Safe Optimization Opportunities</h3>
                        <p className="text-[#666666] text-xs mt-0.5">
                            Ranked by revenue potential. All 4 data sources: GSC, GA4, Shopify, DataForSEO
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={syncAllCollections}
                            disabled={syncing}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#f7b500]/20 text-[#f7b500] border border-[#f7b500]/30 rounded hover:bg-[#f7b500]/30 transition-colors text-xs font-medium disabled:opacity-50"
                        >
                            {syncing ? (
                                <>
                                    <div className="size-3 border-2 border-[#f7b500] border-t-transparent rounded-full animate-spin" />
                                    Syncing all sources...
                                </>
                            ) : (
                                <>
                                    <RefreshIcon />
                                    Sync All Data Sources
                                </>
                            )}
                        </button>
                        <button
                            onClick={loadData}
                            className="text-xs text-[#888888] hover:text-white transition-colors px-2 py-1"
                        >
                            Refresh
                        </button>
                    </div>
                </div>
                {opportunities.length === 0 ? (
                    <div className="p-8 text-center text-[#666666] text-sm">
                        No opportunities found. Try syncing data sources first.
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                            <thead>
                                <tr className="border-b border-[#333333] bg-[#252525]">
                                    <th className="py-3 px-4 text-left text-[#888888] font-medium">Collection</th>
                                    <th className="py-3 px-2 text-center text-[#888888] font-medium">Risk</th>
                                    {/* GSC */}
                                    <th className="py-3 px-2 text-right text-[#4285f4] font-medium" title="Search Console">Impr.</th>
                                    <th className="py-3 px-2 text-right text-[#4285f4] font-medium">Pos.</th>
                                    {/* GA4 */}
                                    <th className="py-3 px-2 text-right text-[#ff6d00] font-medium" title="Google Analytics">Sessions</th>
                                    <th className="py-3 px-2 text-right text-[#ff6d00] font-medium">Conv.</th>
                                    <th className="py-3 px-2 text-right text-[#ff6d00] font-medium">Bounce</th>
                                    {/* Shopify */}
                                    <th className="py-3 px-2 text-right text-[#f7b500] font-medium" title="Shopify Attribution">Revenue</th>
                                    <th className="py-3 px-2 text-right text-[#f7b500] font-medium">Orders</th>
                                    {/* DataForSEO */}
                                    <th className="py-3 px-2 text-right text-[#10b981] font-medium" title="DataForSEO">Vol/mo</th>
                                    {/* Intelligence */}
                                    <th className="py-3 px-2 text-center text-green-400 font-medium">Safe</th>
                                    <th className="py-3 px-2 text-right text-[#f7b500] font-medium">Score</th>
                                    <th className="py-3 px-2 text-center text-[#888888] font-medium"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {opportunities.map((opp) => {
                                    // Data freshness indicator — green if synced within 7 days
                                    const sources = [opp.last_gsc_sync, opp.last_ga4_sync, opp.last_shopify_sync, opp.last_dataforseo_sync];
                                    const syncedCount = sources.filter(Boolean).length;

                                    return (
                                        <tr key={opp.collection_id} className="border-b border-[#333333] hover:bg-[#252525] transition-colors">
                                            <td className="py-3 px-4">
                                                <button
                                                    type="button"
                                                    className="text-white font-medium hover:text-[#f7b500] cursor-pointer transition-colors text-left bg-transparent border-0 p-0"
                                                    onClick={() => router.push(`/seo/collections/${opp.collection_id}`)}
                                                >
                                                    {opp.collection_title}
                                                </button>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    <span className="text-[#555555] text-[10px]">{opp.category}</span>
                                                    {/* Data freshness dots */}
                                                    <div className="flex gap-0.5" title={`${syncedCount}/4 sources synced`}>
                                                        <span className={`size-1 rounded-full ${opp.last_gsc_sync ? 'bg-[#4285f4]' : 'bg-[#333]'}`} title="GSC" />
                                                        <span className={`size-1 rounded-full ${opp.last_ga4_sync ? 'bg-[#ff6d00]' : 'bg-[#333]'}`} title="GA4" />
                                                        <span className={`size-1 rounded-full ${opp.last_shopify_sync ? 'bg-[#f7b500]' : 'bg-[#333]'}`} title="Shopify" />
                                                        <span className={`size-1 rounded-full ${opp.last_dataforseo_sync ? 'bg-[#10b981]' : 'bg-[#333]'}`} title="DataForSEO" />
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="py-3 px-2 text-center">
                                                <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium ${
                                                    opp.cannibalization_status === 'safe' ? 'bg-green-500/20 text-green-400' :
                                                    opp.cannibalization_status === 'warning' ? 'bg-[#f7b500]/20 text-[#f7b500]' :
                                                    'bg-red-500/20 text-red-400'
                                                }`}>
                                                    <span className={`size-1 rounded-full ${
                                                        opp.cannibalization_status === 'safe' ? 'bg-green-400' :
                                                        opp.cannibalization_status === 'warning' ? 'bg-[#f7b500]' :
                                                        'bg-red-400'
                                                    }`} />
                                                    {opp.risk_score}%
                                                </span>
                                            </td>
                                            {/* GSC */}
                                            <td className="py-3 px-2 text-right font-mono text-white">
                                                {opp.impressions > 0 ? (opp.impressions > 999 ? `${(opp.impressions / 1000).toFixed(1)}k` : opp.impressions) : <span className="text-[#333]">—</span>}
                                            </td>
                                            <td className="py-3 px-2 text-right font-mono">
                                                {opp.position > 0 ? (
                                                    <span className={opp.position <= 10 ? 'text-green-400' : opp.position <= 20 ? 'text-[#f7b500]' : 'text-[#666]'}>
                                                        #{opp.position.toFixed(0)}
                                                    </span>
                                                ) : <span className="text-[#333]">—</span>}
                                            </td>
                                            {/* GA4 */}
                                            <td className="py-3 px-2 text-right font-mono text-white">
                                                {opp.ga4_sessions > 0 ? opp.ga4_sessions.toLocaleString() : <span className="text-[#333]">—</span>}
                                            </td>
                                            <td className="py-3 px-2 text-right font-mono">
                                                {opp.ga4_conversions > 0 ? (
                                                    <span className="text-green-400">{opp.ga4_conversions}</span>
                                                ) : <span className="text-[#333]">—</span>}
                                            </td>
                                            <td className="py-3 px-2 text-right font-mono">
                                                {opp.ga4_bounce_rate > 0 ? (
                                                    <span className={opp.ga4_bounce_rate > 70 ? 'text-red-400' : opp.ga4_bounce_rate > 50 ? 'text-[#f7b500]' : 'text-green-400'}>
                                                        {opp.ga4_bounce_rate.toFixed(0)}%
                                                    </span>
                                                ) : <span className="text-[#333]">—</span>}
                                            </td>
                                            {/* Shopify */}
                                            <td className="py-3 px-2 text-right font-mono">
                                                {opp.shopify_revenue > 0 ? (
                                                    <span className="text-[#f7b500]">${opp.shopify_revenue.toLocaleString('en-MX', { maximumFractionDigits: 0 })}</span>
                                                ) : <span className="text-[#333]">—</span>}
                                            </td>
                                            <td className="py-3 px-2 text-right font-mono text-white">
                                                {opp.shopify_orders > 0 ? opp.shopify_orders : <span className="text-[#333]">—</span>}
                                            </td>
                                            {/* DataForSEO */}
                                            <td className="py-3 px-2 text-right font-mono text-[#10b981]">
                                                {opp.dataforseo_volume > 0 ? opp.dataforseo_volume.toLocaleString() : <span className="text-[#333]">—</span>}
                                            </td>
                                            {/* Intelligence */}
                                            <td className="py-3 px-2 text-center font-mono text-green-400 text-[10px]">
                                                {opp.safe_keywords}/{opp.safe_keywords + opp.blocked_keywords}
                                            </td>
                                            <td className="py-3 px-2 text-right">
                                                <span className="text-[#f7b500] font-mono font-bold">{opp.opportunity_score}</span>
                                            </td>
                                            <td className="py-3 px-2 text-center">
                                                <button
                                                    onClick={() => router.push(`/seo/collections/${opp.collection_id}`)}
                                                    className="px-2 py-1 bg-[#f7b500]/20 text-[#f7b500] border border-[#f7b500]/30 rounded hover:bg-[#f7b500]/30 transition-colors text-[10px] font-medium"
                                                >
                                                    Optimize
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* High Volume No Content */}
            {health?.opportunities?.high_volume_no_content?.length > 0 && (
                <div className="bg-[#111111] border border-[#333333] p-5">
                    <h3 className="text-sm font-semibold text-white mb-3">
                        High Volume, No Content
                        <span className="text-[#666666] font-normal ml-2">
                            ({health.opportunities.high_volume_no_content.length} collections)
                        </span>
                    </h3>
                    <div className="space-y-2">
                        {health.opportunities.high_volume_no_content.map((c: any) => (
                            <div
                                key={c.id}
                                role="button"
                                tabIndex={0}
                                aria-label={`Open collection ${c.title}`}
                                className="flex items-center justify-between py-2 px-3 bg-[#252525] rounded hover:bg-[#333333] cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
                                onClick={() => router.push(`/seo/collections/${c.id}`)}
                                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); router.push(`/seo/collections/${c.id}`); } }}
                            >
                                <span className="text-white text-sm">{c.title}</span>
                                <div className="flex items-center gap-4 text-xs">
                                    <span className="text-[#10b981] font-mono">{c.volume.toLocaleString()} vol/mo</span>
                                    <span className="text-[#4285f4] font-mono">{c.impressions.toLocaleString()} impr</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

export default CollectionsSection;
