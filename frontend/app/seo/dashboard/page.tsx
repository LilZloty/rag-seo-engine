'use client';

import React, { useState, useEffect, useCallback, useMemo, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Product, productAPI, productsAIAPI, taskAPI } from '../../../lib/api';
import { MultiAgentToggle } from '../../components/ui/MultiAgentToggle';
import { DataSourceFilters, DEFAULT_DATA_SOURCE_FILTERS } from '../../../components/filters/DataSourceTabs';
import { FilterGroup, DEFAULT_FILTER_GROUP } from '../../../components/filters/VisualFilterBuilder';
import { filterAndSortProducts, filterCollections, sortOpportunityCollections, computeCollectionStats, exportToCSV as exportToCSVUtil } from '../../../lib/utils/dashboardFilters';
import { useDashboardData } from '../../../hooks/useDashboardData';
import { useDashboardChartData } from '../../../hooks/useDashboardChartData';
import type { FilterPreset, ProductFilters, CollectionFilters, SortField, SalesPeriod } from '../../../lib/types/dashboard';
import { DATE_RANGES, DEFAULT_PRODUCT_FILTERS, DEFAULT_COLLECTION_FILTERS, DEFAULT_VISIBLE_COLUMNS } from '../../../lib/constants/dashboard';
import OptimizationQueue from '../../components/seo/dashboard/OptimizationQueue';
import { PackageIcon, CollectionIcon, ShoppingCartIcon, RefreshIcon, CalendarIcon } from '../../components/ui/Icons';

// Dynamic-import the heavy tab sections: each pulls in recharts (~150KB).
// `ssr: false` keeps the chart code out of the server bundle; the inactive
// tab's chunk only loads when the user actually switches to it.
const ChartLoader = () => (
    <div className="flex items-center justify-center py-20 text-[#666666] text-sm">
        <div className="size-4 border-2 border-[#f7b500] border-t-transparent animate-spin rounded-full mr-3" />
        Cargando…
    </div>
);
const ProductsSection = dynamic(() => import('../../components/seo/dashboard/ProductsSection'), {
    ssr: false,
    loading: ChartLoader,
});
const CollectionsSection = dynamic(() => import('../../components/seo/dashboard/CollectionsSection'), {
    ssr: false,
    loading: ChartLoader,
});

function SEODashboardContent() {
    const router = useRouter();
    const searchParams = useSearchParams();

    // ============================================
    // UI STATE
    // ============================================

    const [activeTab, setActiveTab] = useState<'products' | 'collections'>('products');
    const [isSyncing, setIsSyncing] = useState(false);
    const [days, setDays] = useState(30);
    const [autoRefresh, setAutoRefresh] = useState(false);
    const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(50);
    const [collectionTab, setCollectionTab] = useState<'all' | 'overview' | 'analytics' | 'opportunities' | 'keywords' | 'intelligence'>('overview');
    const [collectionsPage, setCollectionsPage] = useState(1);
    const [collectionsPerPage, setCollectionsPerPage] = useState(25);
    const [collectionsSortBy, setCollectionsSortBy] = useState<'impressions' | 'sessions' | 'revenue' | 'volume' | 'priority'>('impressions');
    const [collectionsSortDir, setCollectionsSortDir] = useState<'desc' | 'asc'>('desc');
    const [collectionSortBy, setCollectionSortBy] = useState('impressions');
    const [productFilters, setProductFilters] = useState<ProductFilters>(DEFAULT_PRODUCT_FILTERS);
    const [collectionFilters, setCollectionFilters] = useState<CollectionFilters>(DEFAULT_COLLECTION_FILTERS);
    const [visibleColumns, setVisibleColumns] = useState(DEFAULT_VISIBLE_COLUMNS);
    const [filterPresets, setFilterPresets] = useState<FilterPreset[]>([]);
    const [showSavePresetModal, setShowSavePresetModal] = useState(false);
    const [presetName, setPresetName] = useState('');
    const [activeSegment, setActiveSegment] = useState<string>('all');
    const [dataSourceFilters, setDataSourceFilters] = useState<DataSourceFilters>(DEFAULT_DATA_SOURCE_FILTERS);
    const [visualFilters, setVisualFilters] = useState<FilterGroup>(DEFAULT_FILTER_GROUP);
    const [isFilterBuilderOpen, setIsFilterBuilderOpen] = useState(false);
    const [sortField, setSortField] = useState<'title' | 'seo_score' | 'total_sold' | 'total_revenue' | 'ga4_sessions' | 'gsc_impressions' | 'gsc_position' | 'gsc_ctr' | 'performance_score' | 'created_at' | 'updated_at' | 'inventory_quantity'>('created_at');
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
    const [salesPeriod, setSalesPeriod] = useState<'30d' | '90d' | '365d' | 'all_time'>('90d');

    // Poll a Celery task until done (if response is a queued task)
    const awaitTask = useCallback(async (response: any): Promise<any> => {
        if (response?.task_id && response?.status === 'queued') {
            while (true) {
                const status = await taskAPI.getStatus(response.task_id);
                if (status.status === 'SUCCESS') return status.result;
                if (status.status === 'FAILURE') throw new Error(String(status.result || 'Task failed'));
                await new Promise(r => setTimeout(r, 2000));
            }
        }
        return response;
    }, []);

    // ============================================
    // DATA HOOKS
    // ============================================

    const {
        products, productsTotal, productsLoading,
        collections, opportunities, collectionsLoading,
        allCollections, allCollectionsTotal, allCollectionsLoading,
        ga4Dashboard,
        aiTrafficData, llmSalesData, analyticsSummary,
        segmentCounts, queryCache,
        isLoading, analyzing, syncingShopify, runningDataForSEO,
        lastUpdated, mounted,
        multiAgentEnabled, setMultiAgentEnabled, multiAgentStatus,
        loadProducts, loadCollections, loadAllCollections,
        handleAnalyzeAll, handleSyncShopify,
        handleRunDataForSEO, handleRunDataForSEOSingle,
        loadCollectionQueries,
    } = useDashboardData({
        activeTab, collectionTab, days,
        productFilters, collectionFilters, salesPeriod, activeSegment,
        itemsPerPage, currentPage, collectionsPerPage, collectionsPage,
        collectionsSortBy, autoRefresh,
    });

    const {
        revenueOverviewData, topOrganicData, funnelData,
        heatmapData, trafficSourcesData, categoryComparisonData,
    } = useDashboardChartData(products, aiTrafficData, ga4Dashboard);

    // Sorting handler
    const handleSort = (field: typeof sortField) => {
        if (sortField === field) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortDirection('desc');
        }
    };

    const getSortIcon = (field: typeof sortField) => {
        if (sortField !== field) {
            return <span className="text-[#555555] ml-1">↕</span>;
        }
        return sortDirection === 'asc'
            ? <span className="text-[#f7b500] ml-1">↑</span>
            : <span className="text-[#f7b500] ml-1">↓</span>;
    };

    // Check for tab query parameter on mount
    useEffect(() => {
        const tabParam = searchParams.get('tab');
        if (tabParam === 'collections') {
            setActiveTab('collections');
            setCollectionTab('all');
        }
    }, [searchParams]);

    // ============================================
    // FILTERING LOGIC
    // ============================================

    const filteredProducts = useMemo(() =>
        filterAndSortProducts(products, activeSegment, visualFilters, dataSourceFilters, sortField, sortDirection),
        [products, activeSegment, dataSourceFilters, visualFilters, sortField, sortDirection]
    );

    const filteredCollections = useMemo(() =>
        filterCollections(opportunities, collectionFilters),
        [opportunities, collectionFilters]
    );

    const sortedOpportunityCollections = useMemo(() =>
        sortOpportunityCollections(filteredCollections, collectionSortBy),
        [filteredCollections, collectionSortBy]
    );

    const collectionStats = useMemo(() =>
        computeCollectionStats(collections),
        [collections]
    );

    // ============================================
    // EXPORT & REPORTING
    // ============================================

    const exportToCSV = () => exportToCSVUtil(activeTab, filteredProducts, filteredCollections);

    const generatePDFReport = () => {
        alert('PDF Report generation would be implemented with a library like jsPDF or react-pdf');
    };

    const shareFilteredView = () => {
        const params = new URLSearchParams();
        params.set('tab', activeTab);
        if (activeTab === 'products') {
            Object.entries(productFilters).forEach(([key, value]) => {
                if (value !== '' && value !== 'all' && value !== false && value !== 0 && value !== 100) {
                    params.set(`pf_${key}`, String(value));
                }
            });
        } else {
            Object.entries(collectionFilters).forEach(([key, value]) => {
                if (value !== '' && value !== 'all' && value !== false && value !== 0 && value !== 100) {
                    params.set(`cf_${key}`, String(value));
                }
            });
        }
        const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`;
        navigator.clipboard.writeText(url);
        alert('Shareable URL copied to clipboard!');
    };

    // ============================================
    // FILTER PRESETS
    // ============================================

    const saveFilterPreset = () => {
        if (!presetName.trim()) return;
        const newPreset: FilterPreset = {
            id: Date.now().toString(),
            name: presetName,
            filters: activeTab === 'products' ? { ...productFilters } : { ...collectionFilters },
            tab: activeTab,
        };
        setFilterPresets(prev => [...prev, newPreset]);
        setPresetName('');
        setShowSavePresetModal(false);
    };

    const loadFilterPreset = (preset: FilterPreset) => {
        setActiveTab(preset.tab);
        if (preset.tab === 'products') {
            setProductFilters(preset.filters as ProductFilters);
        } else {
            setCollectionFilters(preset.filters as CollectionFilters);
        }
    };

    const deleteFilterPreset = (id: string) => {
        setFilterPresets(filterPresets.filter(p => p.id !== id));
    };

    // ============================================
    // BULK ACTIONS
    // ============================================

    const toggleProductSelection = (id: string) => {
        const newSelected = new Set(selectedProducts);
        if (newSelected.has(id)) {
            newSelected.delete(id);
        } else {
            newSelected.add(id);
        }
        setSelectedProducts(newSelected);
    };

    const selectAllFiltered = () => {
        setSelectedProducts(new Set(filteredProducts.map(p => p.id)));
    };

    const selectAllNeedingSEO = () => {
        const needingSEO = filteredProducts.filter(p => p.seo_score < 70);
        setSelectedProducts(new Set(needingSEO.map(p => p.id)));
    };

    const selectTop10ByRevenue = () => {
        const top10 = [...filteredProducts].sort((a, b) => (b.total_revenue || 0) - (a.total_revenue || 0)).slice(0, 10);
        setSelectedProducts(new Set(top10.map(p => p.id)));
    };

    const clearSelection = () => {
        setSelectedProducts(new Set());
    };

    const bulkGenerateSEO = () => {
        alert(`Generating SEO for ${selectedProducts.size} selected products...`);
    };

    const bulkUpdateStatus = () => {
        alert(`Updating status for ${selectedProducts.size} selected products...`);
    };

    // ============================================
    // COMPUTED VALUES
    // ============================================

    const needsSEOCount = products.filter(p => p.seo_score < 70).length;
    const avgSEOScore = products.length > 0
        ? Math.round(products.reduce((acc, p) => acc + p.seo_score, 0) / products.length)
        : 0;

    // Chart data preparation
    const topConvertersChartData = ga4Dashboard?.top_converters?.slice(0, 10).map(c => ({
        name: c.title.length > 20 ? c.title.substring(0, 20) + '...' : c.title,
        sessions: c.sessions,
        conversions: c.conversions,
        rate: parseFloat(c.conversion_rate)
    })) || [];

    const conversionDistributionData = [
        { name: '0-1%', value: ga4Dashboard?.top_converters?.filter(c => parseFloat(c.conversion_rate) < 1).length || 0, color: '#666666' },
        { name: '1-5%', value: ga4Dashboard?.top_converters?.filter(c => parseFloat(c.conversion_rate) >= 1 && parseFloat(c.conversion_rate) < 5).length || 0, color: '#f7b500' },
        { name: '5-10%', value: ga4Dashboard?.top_converters?.filter(c => parseFloat(c.conversion_rate) >= 5 && parseFloat(c.conversion_rate) < 10).length || 0, color: '#888888' },
        { name: '10%+', value: ga4Dashboard?.top_converters?.filter(c => parseFloat(c.conversion_rate) >= 10).length || 0, color: '#555555' },
    ];

    const scatterData = ga4Dashboard?.top_converters?.map(c => ({
        x: c.sessions,
        y: parseFloat(c.conversion_rate),
        z: c.conversions,
        name: c.title
    })) || [];

    // ============================================
    // RENDER
    // ============================================

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white p-8">
            <div className="max-w-7xl mx-auto">
                {/* Header - Cleaned Up */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-6 gap-4">
                    <div>
                        <h1 className="text-3xl font-semibold text-white">SEO Dashboard</h1>
                        <p className="text-[#888888]">Manage and optimize your products and collections</p>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                        {/* Multi-Agent Toggle - Subtle */}
                        <div className="flex items-center gap-2 mr-2">
                            <MultiAgentToggle
                                enabled={multiAgentEnabled}
                                onChange={setMultiAgentEnabled}
                                variant="compact"
                            />
                            {multiAgentEnabled && (
                                <span className="text-[10px] text-[#f7b500] font-medium">4A</span>
                            )}
                        </div>

                        {/* Last Updated */}
                        <span className="text-[#666666] text-xs">
                            {mounted && lastUpdated ? lastUpdated.toLocaleTimeString() : 'Loading...'}
                        </span>

                        {/* Auto-refresh */}
                        <label className="flex items-center gap-1.5 cursor-pointer text-xs">
                            <input
                                type="checkbox"
                                checked={autoRefresh}
                                onChange={(e) => setAutoRefresh(e.target.checked)}
                                className="size-3 accent-[#f7b500]"
                            />
                            <span className="text-[#888888]">Auto</span>
                        </label>

                        {/* Refresh */}
                        <button
                            onClick={() => activeTab === 'products' ? loadProducts(currentPage) : loadCollections()}
                            disabled={isLoading}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111111] border border-[#333333] hover:border-[#f7b500] text-white text-xs transition-colors disabled:opacity-50"
                        >
                            <svg className={`size-3.5 ${isLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Refresh
                        </button>
                    </div>
                </div>

                {/* Sync Actions Bar - Products Tab */}
                {activeTab === 'products' && (
                    <div className="flex items-center gap-2 mb-6 flex-wrap">
                        <button
                            onClick={async () => {
                                try {
                                    setIsSyncing(true);
                                    const response = await productAPI.syncShopify() as any;
                                    const result = await awaitTask(response);
                                    const r = result || response;
                                    alert(`Shopify sync complete!\n${r.new_products || 0} new products\n${r.updated_products || 0} updated\n${r.total_in_database || '?'} total in DB`);
                                    await loadProducts(1);
                                    setCurrentPage(1);
                                } catch (error) {
                                    console.error('Sync failed:', error);
                                    alert(`Shopify sync failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
                                } finally { setIsSyncing(false); }
                            }}
                            disabled={productsLoading || isSyncing}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111111] border border-[#333333] hover:border-[#f7b500] text-[#f7b500] text-xs transition-colors disabled:opacity-50"
                        >
                            {isSyncing ? '⏳ Syncing...' : '🛒 Shopify Sync'}
                        </button>
                        <button
                            onClick={async () => {
                                try {
                                    setIsSyncing(true);
                                    const response = await productAPI.syncAnalytics();
                                    await awaitTask(response);
                                    await loadProducts(currentPage);
                                } catch (error) {
                                    console.error('Analytics sync failed:', error);
                                } finally { setIsSyncing(false); }
                            }}
                            disabled={productsLoading || isSyncing}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111111] border border-[#333333] hover:border-[#f7b500] text-[#f7b500] text-xs transition-colors disabled:opacity-50"
                        >
                            📊 Analytics
                        </button>
                        <button
                            onClick={async () => {
                                try {
                                    setIsSyncing(true);
                                    const response = await productAPI.syncSales();
                                    const result = await awaitTask(response);
                                    alert(`Sales sync complete! Updated ${result?.products_updated || 0} products.`);
                                    await loadProducts(currentPage);
                                } catch (error) {
                                    console.error('Sales sync failed:', error);
                                } finally { setIsSyncing(false); }
                            }}
                            disabled={productsLoading || isSyncing}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111111] border border-[#333333] hover:border-[#f7b500] text-[#f7b500] text-xs transition-colors disabled:opacity-50"
                        >
                            💰 Sales
                        </button>
                        {multiAgentEnabled && (
                            <button
                                onClick={async () => {
                                    if (products.length === 0) return;
                                    try {
                                        setIsSyncing(true);
                                        const topProducts = products.slice(0, 5);
                                        for (const p of topProducts) {
                                            await productsAIAPI.quickScan(p.id);
                                        }
                                        alert(`AI Scan complete for ${topProducts.length} products.`);
                                    } catch (e) {
                                        console.error('[AI Scan] Failed:', e);
                                    } finally {
                                        setIsSyncing(false);
                                    }
                                }}
                                disabled={productsLoading || isSyncing || products.length === 0}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111111] border border-[#333333] hover:border-[#f7b500] text-[#f7b500] text-xs transition-colors disabled:opacity-50"
                            >
                                🤖 AI Scan
                            </button>
                        )}
                        <div className="flex-1" />
                        <button onClick={exportToCSV} className="text-xs text-[#888888] hover:text-white px-2 py-1">CSV</button>
                        <button onClick={shareFilteredView} className="text-xs text-[#888888] hover:text-white px-2 py-1">Share</button>
                    </div>
                )}

                {/* Collections Tab Actions */}
                {activeTab === 'collections' && (
                    <div className="flex flex-wrap items-center gap-2 mb-6">
                        <CalendarIcon />
                        <select
                            value={days}
                            onChange={(e) => setDays(Number(e.target.value))}
                            className="bg-[#111111] border border-[#333333] text-white text-xs px-2 py-1.5 focus:outline-none cursor-pointer"
                        >
                            {DATE_RANGES.map(range => (
                                <option key={range.value} value={range.value} className="bg-[#111111]">
                                    {range.label}
                                </option>
                            ))}
                        </select>
                        <button
                            onClick={handleSyncShopify}
                            disabled={syncingShopify}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#252525] border border-[#333333] hover:border-[#f7b500]/50 text-[#888888] hover:text-white text-xs transition-all disabled:opacity-50"
                        >
                            {syncingShopify ? (
                                <><div className="size-3 border border-current border-t-transparent animate-spin rounded-full"></div>Syncing Shopify…</>
                            ) : (
                                <><ShoppingCartIcon />Sync Shopify</>
                            )}
                        </button>
                        <button
                            onClick={handleRunDataForSEO}
                            disabled={runningDataForSEO}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#252525] border border-[#333333] hover:border-[#10b981]/50 text-[#888888] hover:text-white text-xs transition-all disabled:opacity-50"
                        >
                            {runningDataForSEO ? (
                                <><div className="size-3 border border-current border-t-transparent animate-spin rounded-full"></div>Running DataForSEO…</>
                            ) : (
                                <><RefreshIcon />Run DataForSEO</>
                            )}
                        </button>
                    </div>
                )}

                {/* Main Tabs - Products / Collections */}
                <div className="flex gap-1 bg-[#111111] border border-[#333333] p-1 mb-8">
                    <button
                        onClick={() => setActiveTab('products')}
                        className={`flex items-center gap-2 px-6 py-3 transition-all ${activeTab === 'products'
                            ? 'bg-[#f7b500] text-black font-medium'
                            : 'text-[#888888] hover:text-white'
                            }`}
                    >
                        <PackageIcon />
                        Products
                        <span className="ml-2 px-2 py-0.5 bg-black/20 text-xs">
                            {needsSEOCount} need SEO
                        </span>
                    </button>

                    <button
                        onClick={() => setActiveTab('collections')}
                        className={`flex items-center gap-2 px-6 py-3 transition-all ${activeTab === 'collections'
                            ? 'bg-[#f7b500] text-black font-medium'
                            : 'text-[#888888] hover:text-white'
                            }`}
                    >
                        <CollectionIcon />
                        Collections
                        <span className="ml-2 px-2 py-0.5 bg-black/20 text-xs">
                            {opportunities.length} opportunities
                        </span>
                    </button>
                </div>

                {/* OPTIMIZATION QUEUE — replaces heuristic Smart Recommendations.
                    Reads from /api/v1/seo-intelligence/optimization-queue, which
                    serves nightly-computed priority scores. */}
                <OptimizationQueue limit={20} />

                {/* PRODUCTS TAB */}
                {activeTab === 'products' && (
                    <ProductsSection
                        products={products}
                        productsTotal={productsTotal}
                        filteredProducts={filteredProducts}
                        productsLoading={productsLoading}
                        mounted={mounted}
                        segmentCounts={segmentCounts}
                        activeSegment={activeSegment}
                        onSegmentChange={(segmentId) => {
                            setActiveSegment(segmentId);
                            setCurrentPage(1);
                            loadProducts(1, segmentId);
                        }}
                        dataSourceFilters={dataSourceFilters}
                        onDataSourceFilterChange={(key, value) => setDataSourceFilters(prev => ({ ...prev, [key]: value }))}
                        onClearDataSourceFilters={() => setDataSourceFilters(DEFAULT_DATA_SOURCE_FILTERS)}
                        visualFilters={visualFilters}
                        onVisualFiltersChange={setVisualFilters}
                        isFilterBuilderOpen={isFilterBuilderOpen}
                        onToggleFilterBuilder={() => setIsFilterBuilderOpen(!isFilterBuilderOpen)}
                        productFilters={productFilters}
                        onProductFiltersChange={setProductFilters}
                        salesPeriod={salesPeriod}
                        onSalesPeriodChange={setSalesPeriod}
                        visibleColumns={visibleColumns}
                        onVisibleColumnsChange={setVisibleColumns}
                        selectedProducts={selectedProducts}
                        onToggleProductSelection={toggleProductSelection}
                        onSelectAllFiltered={selectAllFiltered}
                        onSelectAllNeedingSEO={selectAllNeedingSEO}
                        onSelectTop10ByRevenue={selectTop10ByRevenue}
                        onClearSelection={clearSelection}
                        onBulkGenerateSEO={bulkGenerateSEO}
                        onBulkUpdateStatus={bulkUpdateStatus}
                        sortField={sortField}
                        sortDirection={sortDirection}
                        onSort={handleSort}
                        getSortIcon={getSortIcon}
                        currentPage={currentPage}
                        onPageChange={setCurrentPage}
                        itemsPerPage={itemsPerPage}
                        onItemsPerPageChange={setItemsPerPage}
                        onLoadProducts={loadProducts}
                        needsSEOCount={needsSEOCount}
                        avgSEOScore={avgSEOScore}
                        revenueOverviewData={revenueOverviewData}
                        topOrganicData={topOrganicData}
                    />
                )}

                {/* COLLECTIONS TAB */}
                {activeTab === 'collections' && (
                    <CollectionsSection
                        collections={collections}
                        opportunities={opportunities}
                        filteredCollections={filteredCollections}
                        sortedOpportunityCollections={sortedOpportunityCollections}
                        collectionStats={collectionStats}
                        allCollections={allCollections}
                        allCollectionsTotal={allCollectionsTotal}
                        allCollectionsLoading={allCollectionsLoading}
                        ga4Dashboard={ga4Dashboard}
                        collectionsLoading={collectionsLoading}
                        analyzing={analyzing}
                        collectionTab={collectionTab}
                        onCollectionTabChange={setCollectionTab}
                        collectionFilters={collectionFilters}
                        onCollectionFiltersChange={setCollectionFilters}
                        collectionSortBy={collectionSortBy}
                        onCollectionSortByChange={setCollectionSortBy}
                        collectionsSortBy={collectionsSortBy}
                        onCollectionsSortByChange={setCollectionsSortBy}
                        collectionsSortDir={collectionsSortDir}
                        onCollectionsSortDirChange={setCollectionsSortDir}
                        collectionsPage={collectionsPage}
                        onCollectionsPageChange={setCollectionsPage}
                        collectionsPerPage={collectionsPerPage}
                        queryCache={queryCache}
                        onLoadCollectionQueries={loadCollectionQueries}
                        onToggleQueryExpand={(id) => {}}
                        onAnalyzeAll={handleAnalyzeAll}
                        onRunDataForSEOSingle={handleRunDataForSEOSingle}
                        funnelData={funnelData}
                        heatmapData={heatmapData}
                        categoryComparisonData={categoryComparisonData}
                        trafficSourcesData={trafficSourcesData}
                        aiTrafficData={aiTrafficData}
                        showSavePresetModal={showSavePresetModal}
                        onShowSavePresetModal={setShowSavePresetModal}
                        presetName={presetName}
                        onPresetNameChange={setPresetName}
                        onSaveFilterPreset={saveFilterPreset}
                    />
                )}
            </div>

        </div>
    );
}

// Wrap with Suspense for useSearchParams
export default function SEODashboardPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-black flex items-center justify-center">
                <div className="flex items-center gap-3">
                    <div className="size-6 border-2 border-[#f7b500] border-t-transparent animate-spin"></div>
                    <span className="text-white">Loading dashboard…</span>
                </div>
            </div>
        }>
            <SEODashboardContent />
        </Suspense>
    );
}
