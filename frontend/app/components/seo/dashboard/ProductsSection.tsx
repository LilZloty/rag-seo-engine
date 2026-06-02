'use client';

import React from 'react';
import Link from 'next/link';
import { formatDate } from '@/app/lib/dates';
import { Product } from '../../../../lib/api';
import type { ProductFilters, SortField, SalesPeriod } from '../../../../lib/types/dashboard';
import type { DataSourceFilters } from '../../../../components/filters/DataSourceTabs';
import type { FilterGroup } from '../../../../components/filters/VisualFilterBuilder';
import SmartSegments from '../../../../components/filters/SmartSegments';
import DataSourceTabs, { DEFAULT_DATA_SOURCE_FILTERS } from '../../../../components/filters/DataSourceTabs';
import VisualFilterBuilder from '../../../../components/filters/VisualFilterBuilder';
import { revenueTrendConfig, sessionTrendConfig } from '../../../../lib/chartConfigs';
import StatCard from './StatCard';
import {
    PackageIcon, TrendingUpIcon,
    SearchIcon, WarningIcon as AlertIcon,
    SettingsIcon, LightningIcon,
    CheckIcon, ColumnsIcon
} from '../../ui/Icons';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Cell,
} from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '../../ui/chart';

// ============================================
// VISIBLE COLUMNS TYPE
// ============================================

export interface VisibleColumns {
    product: boolean;
    sku: boolean;
    seoScore: boolean;
    sold: boolean;
    revenue: boolean;
    price: boolean;
    images: boolean;
    inventory: boolean;
    created: boolean;
    updated: boolean;
    gscImpressions: boolean;
    gscPosition: boolean;
    gscCtr: boolean;
    ga4Sessions: boolean;
    opportunityLevel: boolean;
}

// ============================================
// PROPS INTERFACE
// ============================================

export interface ProductsSectionProps {
    // Data
    products: Product[];
    productsTotal: number;
    filteredProducts: Product[];
    productsLoading: boolean;
    mounted: boolean;

    // Segments
    segmentCounts: Record<string, number>;
    activeSegment: string;
    onSegmentChange: (segmentId: string) => void;

    // Data Source Filters
    dataSourceFilters: DataSourceFilters;
    onDataSourceFilterChange: (key: string, value: any) => void;
    onClearDataSourceFilters: () => void;

    // Visual Filters
    visualFilters: FilterGroup;
    onVisualFiltersChange: (filters: FilterGroup) => void;
    isFilterBuilderOpen: boolean;
    onToggleFilterBuilder: () => void;

    // Product Filters
    productFilters: ProductFilters;
    onProductFiltersChange: (filters: ProductFilters) => void;

    // Sales Period
    salesPeriod: SalesPeriod;
    onSalesPeriodChange: (period: SalesPeriod) => void;

    // Visible Columns
    visibleColumns: VisibleColumns;
    onVisibleColumnsChange: (columns: VisibleColumns) => void;

    // Selection
    selectedProducts: Set<string>;
    onToggleProductSelection: (id: string) => void;
    onSelectAllFiltered: () => void;
    onSelectAllNeedingSEO: () => void;
    onSelectTop10ByRevenue: () => void;
    onClearSelection: () => void;

    // Bulk Actions
    onBulkGenerateSEO: () => void;
    onBulkUpdateStatus: () => void;

    // Sorting
    sortField: SortField;
    sortDirection: 'asc' | 'desc';
    onSort: (field: SortField) => void;
    getSortIcon: (field: SortField) => React.ReactNode;

    // Pagination
    currentPage: number;
    onPageChange: (page: number) => void;
    itemsPerPage: number;
    onItemsPerPageChange: (perPage: number) => void;
    onLoadProducts: (page?: number, segment?: string) => void;

    // Computed values
    needsSEOCount: number;
    avgSEOScore: number;

    // Chart data
    revenueOverviewData: Array<{ period: string; revenue: number; units: number }>;
    topOrganicData: Array<{ name: string; impressions: number; sessions: number; seoScore: number }>;
}

// ============================================
// COMPONENT
// ============================================

const ProductsSection: React.FC<ProductsSectionProps> = ({
    products,
    productsTotal,
    filteredProducts,
    productsLoading,
    mounted,
    segmentCounts,
    activeSegment,
    onSegmentChange,
    dataSourceFilters,
    onDataSourceFilterChange,
    onClearDataSourceFilters,
    visualFilters,
    onVisualFiltersChange,
    isFilterBuilderOpen,
    onToggleFilterBuilder,
    productFilters,
    onProductFiltersChange,
    salesPeriod,
    onSalesPeriodChange,
    visibleColumns,
    onVisibleColumnsChange,
    selectedProducts,
    onToggleProductSelection,
    onSelectAllFiltered,
    onSelectAllNeedingSEO,
    onSelectTop10ByRevenue,
    onClearSelection,
    onBulkGenerateSEO,
    onBulkUpdateStatus,
    sortField,
    sortDirection,
    onSort,
    getSortIcon,
    currentPage,
    onPageChange,
    itemsPerPage,
    onItemsPerPageChange,
    onLoadProducts,
    needsSEOCount,
    avgSEOScore,
    revenueOverviewData,
    topOrganicData,
}) => {
    return (
        <>
            {/* Products Stats with Trends */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <StatCard
                    title="Total Products"
                    value={productsTotal}
                    subtitle="In database"
                    trend={{ value: 12, isPositive: true }}
                    icon={<PackageIcon />}
                    color="bg-[#333333] text-[#888888]"
                />
                <StatCard
                    title="Need SEO"
                    value={needsSEOCount}
                    subtitle="SEO score < 70"
                    trend={{ value: 5, isPositive: false }}
                    icon={<AlertIcon />}
                    color="bg-[#333333] text-[#666666]"
                />
                <StatCard
                    title="Avg SEO Score"
                    value={avgSEOScore}
                    subtitle="Out of 100"
                    trend={{ value: 8, isPositive: true }}
                    icon={<TrendingUpIcon />}
                    color="bg-[#f7b500]/20 text-[#f7b500]"
                />
                <StatCard
                    title="Optimized"
                    value={productsTotal - needsSEOCount}
                    subtitle="SEO score >= 70"
                    trend={{ value: 15, isPositive: true }}
                    icon={<SearchIcon />}
                    color="bg-[#f7b500]/20 text-[#f7b500]"
                />
            </div>

            {/* SEO Revenue & Traffic Overview — always populated from loaded products */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

                {/* Revenue by time window */}
                <div className="bg-[#111111] border border-[#333333] p-6">
                    <div className="flex items-center justify-between mb-1">
                        <h3 className="text-base font-semibold text-white tracking-tight">Revenue Overview</h3>
                        <span className="text-xs text-[#555555]">{products.length} products loaded</span>
                    </div>
                    <p className="text-xs text-[#555555] mb-4">Cumulative revenue across time windows</p>
                    <ChartContainer config={revenueTrendConfig} className="h-56 w-full">
                        <BarChart data={revenueOverviewData} barCategoryGap="30%">
                            <defs>
                                <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.95} />
                                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0.55} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" vertical={false} />
                            <XAxis
                                dataKey="period"
                                stroke="transparent"
                                tick={{ fill: '#666666', fontSize: 11 }}
                                axisLine={false}
                                tickLine={false}
                            />
                            <YAxis
                                stroke="transparent"
                                tick={{ fill: '#555555', fontSize: 10 }}
                                axisLine={false}
                                tickLine={false}
                                tickFormatter={(v) => v >= 1000 ? `$${(v / 1000).toFixed(0)}K` : `$${v}`}
                                width={42}
                            />
                            <ChartTooltip
                                content={<ChartTooltipContent formatter={(val, name) =>
                                    name === 'revenue'
                                        ? [`$${Number(val).toLocaleString()}`, 'Revenue']
                                        : [Number(val).toLocaleString(), 'Units sold']
                                } />}
                            />
                            <Bar dataKey="revenue" fill="url(#revenueGrad)" radius={[4, 4, 0, 0]} maxBarSize={52} />
                            <Bar dataKey="units" fill="#1d3557" radius={[4, 4, 0, 0]} maxBarSize={52} />
                        </BarChart>
                    </ChartContainer>
                    {revenueOverviewData[0]?.revenue === 0 && (
                        <p className="text-center text-xs text-[#444444] mt-2">No revenue data synced yet — run a Shopify sync</p>
                    )}
                </div>

                {/* Top products by organic search visibility */}
                <div className="bg-[#111111] border border-[#333333] p-6">
                    <div className="flex items-center justify-between mb-1">
                        <h3 className="text-base font-semibold text-white tracking-tight">Organic Visibility</h3>
                        <span className="text-xs text-[#555555]">top products · GSC impressions</span>
                    </div>
                    <p className="text-xs text-[#555555] mb-4">Search impressions vs GA4 sessions per product</p>
                    {topOrganicData.length > 0 ? (
                        <ChartContainer config={sessionTrendConfig} className="h-56 w-full">
                            <BarChart data={topOrganicData} layout="vertical" margin={{ right: 8 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" horizontal={false} />
                                <XAxis
                                    type="number"
                                    stroke="transparent"
                                    tick={{ fill: '#555555', fontSize: 10 }}
                                    axisLine={false}
                                    tickLine={false}
                                    tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : String(v)}
                                />
                                <YAxis
                                    type="category"
                                    dataKey="name"
                                    width={96}
                                    stroke="transparent"
                                    tick={{ fill: '#888888', fontSize: 10 }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <ChartTooltip content={<ChartTooltipContent />} />
                                <Bar dataKey="impressions" fill="#f7b500" radius={[0, 4, 4, 0]} maxBarSize={14}>
                                    {topOrganicData.map((entry) => (
                                        <Cell
                                            key={entry.name || entry.id}
                                            fill={entry.seoScore >= 70 ? '#22c55e' : entry.seoScore >= 50 ? '#f7b500' : '#ef4444'}
                                            fillOpacity={0.85}
                                        />
                                    ))}
                                </Bar>
                                <Bar dataKey="sessions" fill="#3b82f6" radius={[0, 4, 4, 0]} maxBarSize={14} fillOpacity={0.6} />
                            </BarChart>
                        </ChartContainer>
                    ) : (
                        <div className="h-56 flex flex-col items-center justify-center gap-2">
                            <span className="text-[#444444] text-sm">No GSC or GA4 data on loaded products</span>
                            <span className="text-[#333333] text-xs">Sync Google Search Console to populate</span>
                        </div>
                    )}
                    <div className="flex items-center gap-4 mt-3 pt-3 border-t border-[#1e1e1e]">
                        <span className="flex items-center gap-1.5 text-xs text-[#555555]"><span className="size-2 rounded-sm bg-[#22c55e] inline-block" />SEO ≥ 70</span>
                        <span className="flex items-center gap-1.5 text-xs text-[#555555]"><span className="size-2 rounded-sm bg-[#f7b500] inline-block" />SEO 50–69</span>
                        <span className="flex items-center gap-1.5 text-xs text-[#555555]"><span className="size-2 rounded-sm bg-[#ef4444] inline-block" />SEO &lt; 50</span>
                        <span className="flex items-center gap-1.5 text-xs text-[#555555]"><span className="size-2 rounded-sm bg-[#3b82f6] opacity-60 inline-block" />Sessions</span>
                    </div>
                </div>
            </div>

            {/* ========== NEW UNIFIED FILTER SYSTEM ========== */}

            {/* Smart Segments - Quick one-click filters */}
            <SmartSegments
                products={products}
                totalProducts={productsTotal}
                serverCounts={segmentCounts}
                activeSegment={activeSegment}
                onSegmentChange={onSegmentChange}
            />

            {/* Data Source Tabs - Grouped filters by source */}
            <div className="mb-6">
                <DataSourceTabs
                    filters={dataSourceFilters}
                    onFilterChange={onDataSourceFilterChange}
                    onClearAll={onClearDataSourceFilters}
                    activeFiltersCount={Object.entries(dataSourceFilters).filter(([k, v]) => {
                        if (typeof v === 'string' && (v === 'all' || v === '')) return false;
                        if (v === '' || v === 0) return false;
                        return true;
                    }).length}
                />
            </div>

            {/* Visual Filter Builder - Power user custom conditions */}
            <div className="mb-6">
                <VisualFilterBuilder
                    filterGroup={visualFilters}
                    onFilterChange={onVisualFiltersChange}
                    isOpen={isFilterBuilderOpen}
                    onToggle={onToggleFilterBuilder}
                />
            </div>

            {/* Search Bar with Sales Period Selector */}
            <div className="bg-[#111111] border border-[#333333] p-4 mb-6">
                <div className="flex items-center gap-4">
                    <div className="flex-1 relative">
                        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[#666666]">
                            <SearchIcon />
                        </div>
                        <input
                            type="text"
                            placeholder="Search products by title or SKU..."
                            value={productFilters.search}
                            onChange={(e) => onProductFiltersChange({ ...productFilters, search: e.target.value })}
                            className="w-full bg-[#252525] border border-[#333333] pl-10 pr-4 py-2 text-white placeholder-[#666666] focus:outline-none focus:border-[#f7b500] text-sm"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-[#888888] text-sm">Sales Period:</span>
                        <select
                            value={salesPeriod}
                            onChange={(e) => onSalesPeriodChange(e.target.value as SalesPeriod)}
                            className="bg-[#252525] border border-[#333333] px-3 py-2 text-white text-sm focus:outline-none focus:border-[#f7b500]"
                        >
                            <option value="30d">Last 30 Days</option>
                            <option value="90d">Last 90 Days</option>
                            <option value="365d">Last Year</option>
                            <option value="all_time">All Time</option>
                        </select>
                    </div>
                    {productFilters.search && (
                        <button
                            onClick={() => onProductFiltersChange({ ...productFilters, search: '' })}
                            className="px-3 py-2 text-[#888888] hover:text-white text-sm"
                        >
                            Clear
                        </button>
                    )}
                </div>
            </div>

            {/* Quick Actions Bar */}
            {selectedProducts.size > 0 && (
                <div className="bg-[#f7b500]/10 border border-[#f7b500]/30 p-4 mb-6 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <span className="text-white font-medium">{selectedProducts.size} selected</span>
                        <button
                            onClick={onClearSelection}
                            className="text-[#888888] hover:text-white text-sm"
                        >
                            Clear
                        </button>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={onBulkGenerateSEO}
                            className="flex items-center gap-2 px-4 py-2 bg-[#f7b500] hover:bg-[#f7b500]/90 text-black font-medium transition-colors"
                        >
                            <LightningIcon />
                            Bulk Generate SEO
                        </button>
                        <button
                            onClick={onBulkUpdateStatus}
                            className="flex items-center gap-2 px-4 py-2 bg-[#333333] hover:bg-[#444444] text-white transition-colors"
                        >
                            <SettingsIcon />
                            Update Status
                        </button>
                    </div>
                </div>
            )}

            {/* Smart Selection Buttons */}
            <div className="flex flex-wrap items-center gap-2 mb-6">
                <span className="text-[#888888] text-sm mr-2">Smart Select:</span>
                <button
                    onClick={onSelectAllFiltered}
                    className="px-3 py-1.5 bg-[#252525] hover:bg-[#333333] text-white text-sm transition-colors"
                >
                    All Filtered ({filteredProducts.length})
                </button>
                <button
                    onClick={onSelectAllNeedingSEO}
                    className="px-3 py-1.5 bg-[#252525] hover:bg-[#333333] text-white text-sm transition-colors"
                >
                    All Needing SEO
                </button>
                <button
                    onClick={onSelectTop10ByRevenue}
                    className="px-3 py-1.5 bg-[#252525] hover:bg-[#333333] text-white text-sm transition-colors"
                >
                    Top 10 by Revenue
                </button>

                <div className="flex-1"></div>

                {/* Column Visibility Toggle */}
                <div className="relative group">
                    <button className="flex items-center gap-2 px-3 py-1.5 bg-[#252525] hover:bg-[#333333] text-white text-sm transition-colors">
                        <ColumnsIcon />
                        Columns
                    </button>
                    <div className="absolute right-0 top-full mt-2 w-52 bg-[#111111] border border-[#333333] p-2 shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                        {Object.entries(visibleColumns).map(([key, visible]) => {
                            const labels: Record<string, string> = {
                                product: 'Product', sku: 'SKU', seoScore: 'SEO Score',
                                sold: 'Units Sold', revenue: 'Revenue', price: 'Price',
                                images: 'Images', inventory: 'Stock', created: 'Created',
                                updated: 'Updated',
                                gscImpressions: '📈 GSC Impressions', gscPosition: '📍 GSC Position',
                                gscCtr: '🖱 GSC CTR', ga4Sessions: '👥 GA4 Sessions',
                                opportunityLevel: '⭐ Opportunity',
                            };
                            return (
                                <label key={key} className="flex items-center gap-2 p-2 hover:bg-[#252525] rounded cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={visible}
                                        onChange={(e) => onVisibleColumnsChange({ ...visibleColumns, [key]: e.target.checked })}
                                        className="size-4 rounded border-[#333333] bg-[#111111] text-[#f7b500]"
                                    />
                                    <span className="text-sm text-[#cccccc]">{labels[key] || key}</span>
                                </label>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* Products Table */}
            <div id="products-table" className="bg-[#111111] border border-[#333333] overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-[#333333] bg-[#252525]">
                                <th className="py-3 px-4 text-left">
                                    <input
                                        type="checkbox"
                                        checked={selectedProducts.size === filteredProducts.length && filteredProducts.length > 0}
                                        onChange={(e) => e.target.checked ? onSelectAllFiltered() : onClearSelection()}
                                        className="size-4 rounded border-[#333333] bg-[#111111] text-[#f7b500]"
                                    />
                                </th>
                                {visibleColumns.product && (
                                    <th
                                        className="py-3 px-4 text-left text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('title')}
                                    >
                                        Product {getSortIcon('title')}
                                    </th>
                                )}
                                {visibleColumns.sku && (
                                    <th className="py-3 px-4 text-left text-[#888888] text-sm font-medium">SKU</th>
                                )}
                                {visibleColumns.seoScore && (
                                    <th
                                        className="py-3 px-4 text-right text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('seo_score')}
                                    >
                                        SEO Score {getSortIcon('seo_score')}
                                    </th>
                                )}
                                {visibleColumns.sold && (
                                    <th
                                        className="py-3 px-4 text-right text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('total_sold')}
                                    >
                                        Sold ({salesPeriod === '30d' ? '30d' : salesPeriod === '90d' ? '90d' : salesPeriod === '365d' ? '1y' : 'all'}) {getSortIcon('total_sold')}
                                    </th>
                                )}
                                {visibleColumns.revenue && (
                                    <th
                                        className="py-3 px-4 text-right text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('total_revenue')}
                                    >
                                        Revenue ({salesPeriod === '30d' ? '30d' : salesPeriod === '90d' ? '90d' : salesPeriod === '365d' ? '1y' : 'all'}) {getSortIcon('total_revenue')}
                                    </th>
                                )}
                                {visibleColumns.price && (
                                    <th className="py-3 px-4 text-right text-[#888888] text-sm font-medium">Price</th>
                                )}
                                {visibleColumns.images && (
                                    <th className="py-3 px-4 text-center text-[#888888] text-sm font-medium">Images</th>
                                )}
                                {visibleColumns.inventory && (
                                    <th
                                        className="py-3 px-4 text-center text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('inventory_quantity')}
                                    >
                                        Stock {getSortIcon('inventory_quantity')}
                                    </th>
                                )}
                                {visibleColumns.created && (
                                    <th
                                        className="py-3 px-4 text-left text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('created_at')}
                                        title="When product was first added to Shopify"
                                    >
                                        Added to Shopify {getSortIcon('created_at')}
                                    </th>
                                )}
                                {visibleColumns.updated && (
                                    <th
                                        className="py-3 px-4 text-left text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('updated_at')}
                                    >
                                        Updated {getSortIcon('updated_at')}
                                    </th>
                                )}
                                {visibleColumns.gscImpressions && (
                                    <th
                                        className="py-3 px-4 text-right text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('gsc_impressions')}
                                        title="Google Search Console — total monthly impressions"
                                    >
                                        Impressions {getSortIcon('gsc_impressions')}
                                    </th>
                                )}
                                {visibleColumns.gscPosition && (
                                    <th
                                        className="py-3 px-4 text-right text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('gsc_position')}
                                        title="Average Google search position (lower = better)"
                                    >
                                        Pos. {getSortIcon('gsc_position')}
                                    </th>
                                )}
                                {visibleColumns.gscCtr && (
                                    <th
                                        className="py-3 px-4 text-right text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('gsc_ctr')}
                                        title="Click-through rate from Google Search"
                                    >
                                        CTR {getSortIcon('gsc_ctr')}
                                    </th>
                                )}
                                {visibleColumns.ga4Sessions && (
                                    <th
                                        className="py-3 px-4 text-right text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('ga4_sessions')}
                                        title="Google Analytics 4 — sessions in last 30 days"
                                    >
                                        Sessions {getSortIcon('ga4_sessions')}
                                    </th>
                                )}
                                {visibleColumns.opportunityLevel && (
                                    <th
                                        className="py-3 px-4 text-center text-[#888888] text-sm font-medium cursor-pointer hover:text-white transition-colors"
                                        onClick={() => onSort('performance_score')}
                                        title="AI-calculated opportunity level based on traffic, conversion and SEO"
                                    >
                                        Opp. {getSortIcon('performance_score')}
                                    </th>
                                )}
                                <th className="py-3 px-4 text-center text-[#888888] text-sm font-medium">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {productsLoading ? (
                                <tr>
                                    <td colSpan={12} className="py-8 text-center text-[#666666]">
                                        <div className="flex items-center justify-center gap-2">
                                            <div className="size-5 border-2 border-[#f7b500] border-t-transparent animate-spin"></div>
                                            Loading products...
                                        </div>
                                    </td>
                                </tr>
                            ) : filteredProducts.length === 0 ? (
                                <tr>
                                    <td colSpan={12} className="py-8 text-center text-[#666666]">No products found matching your filters</td>
                                </tr>
                            ) : (
                                filteredProducts.map((product) => (
                                    <tr key={product.id} className="border-b border-[#333333] hover:bg-[#252525] transition-colors">
                                        <td className="p-4">
                                            <input
                                                type="checkbox"
                                                checked={selectedProducts.has(product.id)}
                                                onChange={() => onToggleProductSelection(product.id)}
                                                className="size-4 rounded border-[#333333] bg-[#111111] text-[#f7b500]"
                                            />
                                        </td>
                                        {visibleColumns.product && (
                                            <td className="p-4">
                                                <div className="flex items-center gap-3">
                                                    {product.image_url && (
                                                        <img
                                                            src={product.image_url}
                                                            alt={product.title}
                                                            className="size-10 rounded object-cover"
                                                        />
                                                    )}
                                                    <Link
                                                        href={`/generate/${product.id}`}
                                                        className="text-white hover:text-[#f7b500] transition-colors cursor-pointer"
                                                    >
                                                        {product.title}
                                                    </Link>
                                                </div>
                                            </td>
                                        )}
                                        {visibleColumns.sku && <td className="p-4 text-[#888888]">{product.sku || '-'}</td>}
                                        {visibleColumns.seoScore && (
                                            <td className="p-4 text-right">
                                                <span className={`font-mono font-bold ${product.seo_score >= 70 ? 'text-[#f7b500]' :
                                                    product.seo_score >= 50 ? 'text-[#888888]' : 'text-[#666666]'
                                                    }`}>
                                                    {product.seo_score}
                                                </span>
                                            </td>
                                        )}
                                        {visibleColumns.sold && <td className="p-4 text-right text-white font-mono">{product.total_sold}</td>}
                                        {visibleColumns.revenue && (
                                            <td className="p-4 text-right text-[#f7b500] font-mono">
                                                ${product.total_revenue?.toLocaleString() || 0}
                                            </td>
                                        )}
                                        {visibleColumns.images && (
                                            <td className="p-4 text-center">
                                                {product.image_url ? (
                                                    <span className="text-[#f7b500]"><CheckIcon /></span>
                                                ) : (
                                                    <span className="text-[#666666]">×</span>
                                                )}
                                            </td>
                                        )}
                                        {visibleColumns.inventory && (
                                            <td className="p-4 text-center">
                                                {product.inventory_quantity !== undefined && product.inventory_quantity !== null ? (
                                                    <span className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium ${product.inventory_quantity === 0 ? 'bg-[#333333] text-[#666666]' :
                                                            product.inventory_quantity <= 5 ? 'bg-[#f7b500]/20 text-[#f7b500]' :
                                                                'bg-[#333333] text-[#888888]'
                                                        }`}>
                                                        {product.inventory_quantity === 0 ? (
                                                            <>
                                                                <svg className="size-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                                </svg>
                                                                Out of Stock
                                                            </>
                                                        ) : product.inventory_quantity <= 5 ? (
                                                            <>
                                                                <svg className="size-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                                                </svg>
                                                                Low ({product.inventory_quantity})
                                                            </>
                                                        ) : (
                                                            <>
                                                                <svg className="size-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                                </svg>
                                                                In Stock ({product.inventory_quantity})
                                                            </>
                                                        )}
                                                    </span>
                                                ) : (
                                                    <span className="text-[#666666]">-</span>
                                                )}
                                            </td>
                                        )}
                                        {visibleColumns.created && (
                                            <td className="p-4 text-[#888888] text-sm" title={product.shopify_created_at ? "From Shopify" : "From database"}>
                                                {mounted && (product.shopify_created_at || product.created_at)
                                                    ? formatDate(product.shopify_created_at || product.created_at)
                                                    : '-'}
                                            </td>
                                        )}
                                        {visibleColumns.updated && (
                                            <td className="p-4 text-[#888888] text-sm" title={product.shopify_updated_at ? "From Shopify" : "From database"}>
                                                {mounted && (product.shopify_updated_at || product.updated_at)
                                                    ? formatDate(product.shopify_updated_at || product.updated_at)
                                                    : '-'}
                                            </td>
                                        )}
                                        {visibleColumns.gscImpressions && (
                                            <td className="p-4 text-right font-mono text-sm">
                                                {(product.gsc_impressions || 0) > 0 ? (
                                                    <span className="text-[#888888]">
                                                        {(product.gsc_impressions! >= 1000)
                                                            ? `${(product.gsc_impressions! / 1000).toFixed(1)}K`
                                                            : product.gsc_impressions}
                                                    </span>
                                                ) : <span className="text-[#444444]">—</span>}
                                            </td>
                                        )}
                                        {visibleColumns.gscPosition && (
                                            <td className="p-4 text-right font-mono text-sm">
                                                {(product.gsc_position || 0) > 0 ? (
                                                    <span className={
                                                        product.gsc_position! <= 3 ? 'text-[#22c55e] font-bold' :
                                                        product.gsc_position! <= 10 ? 'text-[#f7b500]' :
                                                        product.gsc_position! <= 20 ? 'text-[#888888]' :
                                                        'text-[#555555]'
                                                    } title={`Avg position: ${product.gsc_position?.toFixed(1)}`}>
                                                        {product.gsc_position!.toFixed(1)}
                                                        {product.gsc_position! <= 3 && <span className="ml-1 text-xs">🏆</span>}
                                                        {product.gsc_position! > 3 && product.gsc_position! <= 10 && <span className="ml-1 text-[#f7b500] text-xs">↑</span>}
                                                        {product.gsc_position! > 10 && product.gsc_position! <= 20 && <span className="ml-1 text-[#666666] text-xs">→</span>}
                                                        {product.gsc_position! > 20 && <span className="ml-1 text-[#555555] text-xs">↓</span>}
                                                    </span>
                                                ) : <span className="text-[#444444]">—</span>}
                                            </td>
                                        )}
                                        {visibleColumns.gscCtr && (
                                            <td className="p-4 text-right font-mono text-sm">
                                                {(product.gsc_ctr || 0) > 0 ? (
                                                    <span className={
                                                        product.gsc_ctr! >= 0.05 ? 'text-[#22c55e]' :
                                                        product.gsc_ctr! >= 0.02 ? 'text-[#f7b500]' :
                                                        'text-[#888888]'
                                                    }>
                                                        {(product.gsc_ctr! * 100).toFixed(1)}%
                                                    </span>
                                                ) : <span className="text-[#444444]">—</span>}
                                            </td>
                                        )}
                                        {visibleColumns.ga4Sessions && (
                                            <td className="p-4 text-right font-mono text-sm">
                                                {(product.ga4_sessions || 0) > 0 ? (
                                                    <span className="text-[#888888]">
                                                        {product.ga4_sessions!.toLocaleString()}
                                                    </span>
                                                ) : <span className="text-[#444444]">—</span>}
                                            </td>
                                        )}
                                        {visibleColumns.opportunityLevel && (
                                            <td className="p-4 text-center">
                                                {product.opportunity_level ? (
                                                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded-sm ${
                                                        product.opportunity_level === 'high'
                                                            ? 'bg-[#f7b500]/20 text-[#f7b500] border border-[#f7b500]/30'
                                                            : product.opportunity_level === 'medium'
                                                            ? 'bg-[#888888]/20 text-[#888888] border border-[#888888]/30'
                                                            : 'bg-[#333333] text-[#555555] border border-[#444444]'
                                                    }`}>
                                                        {product.opportunity_level === 'high' ? '⬆ High' :
                                                         product.opportunity_level === 'medium' ? '→ Mid' : '↓ Low'}
                                                    </span>
                                                ) : <span className="text-[#444444]">—</span>}
                                            </td>
                                        )}
                                        <td className="p-4 text-center">
                                            <Link
                                                href={`/generate/${product.id}`}
                                                className="inline-flex items-center gap-1 px-3 py-1 bg-[#f7b500]/10 hover:bg-[#f7b500]/20 text-[#f7b500] rounded text-sm transition-colors"
                                            >
                                                Optimize
                                            </Link>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination Controls */}
                <div className="p-4 border-t border-[#333333] bg-[#111111] flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <span className="text-sm text-[#888888]">
                            Showing {((currentPage - 1) * itemsPerPage) + 1} - {Math.min(currentPage * itemsPerPage, productsTotal)} of {productsTotal} products
                        </span>
                        <select
                            value={itemsPerPage}
                            onChange={(e) => {
                                onItemsPerPageChange(Number(e.target.value));
                                onPageChange(1);
                                onLoadProducts(1);
                            }}
                            className="bg-[#252525] border border-[#333333] rounded px-2 py-1 text-sm text-white"
                        >
                            <option value={25}>25 per page</option>
                            <option value={50}>50 per page</option>
                            <option value={100}>100 per page</option>
                        </select>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => {
                                const newPage = Math.max(1, currentPage - 1);
                                onPageChange(newPage);
                                onLoadProducts(newPage);
                            }}
                            disabled={currentPage === 1}
                            className="px-3 py-1 bg-[#252525] border border-[#333333] rounded text-sm text-white
                                disabled:opacity-50 disabled:cursor-not-allowed hover:border-[#f7b500] transition-colors"
                        >
                            ← Prev
                        </button>

                        {/* Page numbers */}
                        {(() => {
                            const totalPages = Math.ceil(productsTotal / itemsPerPage);
                            const pages = [];
                            const maxVisible = 5;
                            let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
                            let end = Math.min(totalPages, start + maxVisible - 1);
                            if (end - start < maxVisible - 1) {
                                start = Math.max(1, end - maxVisible + 1);
                            }

                            for (let pageNum = start; pageNum <= end; pageNum++) {
                                pages.push(
                                    <button
                                        key={`page-${pageNum}`}
                                        onClick={() => {
                                            onPageChange(pageNum);
                                            onLoadProducts(pageNum);
                                        }}
                                        className={`px-3 py-1 rounded text-sm transition-colors ${pageNum === currentPage
                                            ? 'bg-[#f7b500] text-black font-medium'
                                            : 'bg-[#252525] border border-[#333333] text-white hover:border-[#f7b500]'
                                            }`}
                                    >
                                        {pageNum}
                                    </button>
                                );
                            }
                            return pages;
                        })()}

                        <button
                            onClick={() => {
                                const totalPages = Math.ceil(productsTotal / itemsPerPage);
                                const newPage = Math.min(totalPages, currentPage + 1);
                                onPageChange(newPage);
                                onLoadProducts(newPage);
                            }}
                            disabled={currentPage >= Math.ceil(productsTotal / itemsPerPage)}
                            className="px-3 py-1 bg-[#252525] border border-[#333333] rounded text-sm text-white
                                disabled:opacity-50 disabled:cursor-not-allowed hover:border-[#f7b500] transition-colors"
                        >
                            Next →
                        </button>
                    </div>
                </div>

                {/* Link to full products page */}
                <div className="p-4 border-t border-[#333333] bg-[#252525]">
                    <Link
                        href="/dashboard"
                        className="flex items-center justify-center gap-2 text-[#f7b500] hover:text-[#f7b500]/80 transition-colors"
                    >
                        <span>View Full Products Page</span>
                        <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                    </Link>
                    <p className="text-center text-[#666666] text-xs mt-1">
                        Access advanced filters, bulk actions, and more
                    </p>
                </div>
            </div>
        </>
    );
};

export default ProductsSection;
