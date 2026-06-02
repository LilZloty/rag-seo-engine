import { useState, useCallback, useEffect, useRef } from 'react';
import { optimizerAPI, productAPI, analyticsAPI, GA4Dashboard, CollectionOptimizer, Product, productsAIAPI, AITrafficReport, LLMSalesReport, taskAPI } from '../lib/api';
import type { ProductFilters, CollectionFilters, SalesPeriod } from '../lib/types/dashboard';

interface UseDashboardDataParams {
    activeTab: 'products' | 'collections';
    collectionTab: string;
    days: number;
    productFilters: ProductFilters;
    collectionFilters: CollectionFilters;
    salesPeriod: SalesPeriod;
    activeSegment: string;
    itemsPerPage: number;
    currentPage: number;
    collectionsPerPage: number;
    collectionsPage: number;
    collectionsSortBy: string;
    autoRefresh: boolean;
}

export function useDashboardData(params: UseDashboardDataParams) {
    const {
        activeTab, collectionTab, days,
        productFilters, collectionFilters, salesPeriod, activeSegment,
        itemsPerPage, currentPage, collectionsPerPage, collectionsPage,
        collectionsSortBy, autoRefresh,
    } = params;

    // Products state
    const [products, setProducts] = useState<Product[]>([]);
    const [productsTotal, setProductsTotal] = useState(0);
    const [productsLoading, setProductsLoading] = useState(true);

    // Collections state
    const [ga4Dashboard, setGa4Dashboard] = useState<GA4Dashboard | null>(null);
    const [collections, setCollections] = useState<CollectionOptimizer[]>([]);
    const [opportunities, setOpportunities] = useState<CollectionOptimizer[]>([]);
    const [collectionsLoading, setCollectionsLoading] = useState(true);

    // All collections (paginated tab)
    const [allCollections, setAllCollections] = useState<CollectionOptimizer[]>([]);
    const [allCollectionsTotal, setAllCollectionsTotal] = useState(0);
    const [allCollectionsLoading, setAllCollectionsLoading] = useState(false);

    // Analytics
    const [aiTrafficData, setAiTrafficData] = useState<AITrafficReport | null>(null);
    const [llmSalesData, setLlmSalesData] = useState<LLMSalesReport | null>(null);
    const [analyticsSummary, setAnalyticsSummary] = useState<{
        total_products: number; products_with_ga4: number; products_with_gsc: number;
        avg_performance_score: number; high_opportunity_count: number;
        medium_opportunity_count: number; low_opportunity_count: number;
    } | null>(null);

    // Operation states
    const [isLoading, setIsLoading] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [syncingShopify, setSyncingShopify] = useState(false);
    const [runningDataForSEO, setRunningDataForSEO] = useState(false);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [mounted, setMounted] = useState(false);
    const [segmentCounts, setSegmentCounts] = useState<Record<string, number>>({});
    const [queryCache, setQueryCache] = useState<Record<number, any[]>>({});

    // Multi-Agent
    const [multiAgentEnabled, setMultiAgentEnabled] = useState(false);
    const [multiAgentStatus, setMultiAgentStatus] = useState<{
        multi_agent_enabled: boolean;
        mode: string;
        agents: string[];
    } | null>(null);

    // Task polling helper — waits for a Celery task to complete
    const pollUntilDone = useCallback(async (taskId: string): Promise<unknown> => {
        const POLL_INTERVAL = 2000;
        while (true) {
            const status = await taskAPI.getStatus(taskId);
            if (status.status === 'SUCCESS') return status.result;
            if (status.status === 'FAILURE') throw new Error(String(status.result || 'Task failed'));
            await new Promise(r => setTimeout(r, POLL_INTERVAL));
        }
    }, []);

    // Check if response is a queued task and poll it
    const handleMaybeTask = useCallback(async (response: any): Promise<any> => {
        if (response?.task_id && response?.status === 'queued') {
            return pollUntilDone(response.task_id);
        }
        return response;
    }, [pollUntilDone]);

    // Inventory sync
    const syncInventoryForProducts = useCallback(async (productIds: string[], currentProducts: Product[]) => {
        try {
            const INVENTORY_TTL_MS = 60 * 60 * 1000;
            const now = Date.now();
            const staleProducts = currentProducts.filter(p => {
                if (p.inventory_quantity === undefined || p.inventory_quantity === null) return true;
                if (!p.last_inventory_sync) return true;
                const lastSync = new Date(p.last_inventory_sync).getTime();
                return (now - lastSync) > INVENTORY_TTL_MS;
            });

            if (staleProducts.length === 0) return;

            const staleIds = staleProducts.map(p => p.id);
            const result = await productAPI.syncInventory(staleIds);

            if (result.products_updated > 0) {
                const offset = (currentPage - 1) * itemsPerPage;
                const data = await productAPI.getProducts({
                    needs_seo_only: productFilters.showNeedsSEO,
                    segment: activeSegment,
                    sales_period: salesPeriod,
                    search: productFilters.search || undefined,
                    limit: itemsPerPage,
                    offset: offset
                });
                setProducts(data.products);
            }
        } catch (error) {
            console.error('[Inventory] Sync failed:', error);
        }
    }, [currentPage, itemsPerPage, productFilters.showNeedsSEO, productFilters.search, activeSegment, salesPeriod]);

    // Load products
    const loadProducts = useCallback(async (page: number = currentPage, segment: string = activeSegment, searchQuery: string = productFilters.search) => {
        setProductsLoading(true);
        setIsLoading(true);
        try {
            const offset = (page - 1) * itemsPerPage;
            const [data, counts] = await Promise.all([
                productAPI.getProducts({
                    needs_seo_only: productFilters.showNeedsSEO,
                    segment: segment,
                    sales_period: salesPeriod,
                    search: searchQuery || undefined,
                    limit: itemsPerPage,
                    offset: offset
                }),
                productAPI.getSegmentCounts()
            ]);
            setProducts(data.products);
            setProductsTotal(data.total);
            setSegmentCounts(counts);

            if (data.products.length > 0) {
                const productIds = data.products.map(p => p.id);
                syncInventoryForProducts(productIds, data.products);
            }
        } catch (error) {
            console.error('Failed to load products:', error);
        } finally {
            setProductsLoading(false);
            setIsLoading(false);
            setLastUpdated(new Date());
        }
    }, [productFilters.showNeedsSEO, productFilters.search, currentPage, itemsPerPage, activeSegment, salesPeriod, syncInventoryForProducts]);

    // Load collections
    const loadCollections = useCallback(async () => {
        setCollectionsLoading(true);
        setIsLoading(true);
        try {
            const [ga4Data, opportunitiesData, collectionsData] = await Promise.all([
                optimizerAPI.getGA4Dashboard(days),
                optimizerAPI.getHighOpportunityCollections({
                    min_sessions: 50,
                    max_conversion_rate: 2,
                    limit: 20
                }),
                optimizerAPI.getCollections({ limit: 10, sort_by: 'priority' })
            ]);
            setGa4Dashboard(ga4Data);
            setOpportunities(opportunitiesData.collections);
            setCollections(collectionsData.collections);
        } catch (err) {
            console.error('Failed to load collections:', err);
        } finally {
            setCollectionsLoading(false);
            setIsLoading(false);
            setLastUpdated(new Date());
        }
    }, [days]);

    // Load all collections (paginated)
    const loadAllCollections = useCallback(async (page: number = collectionsPage) => {
        setAllCollectionsLoading(true);
        try {
            const offset = (page - 1) * collectionsPerPage;
            const data = await optimizerAPI.getCollections({
                limit: collectionsPerPage,
                offset: offset,
                sort_by: collectionsSortBy,
                search: collectionFilters.search || undefined,
            });
            setAllCollections(data.collections);
            setAllCollectionsTotal(data.total);
        } catch (err) {
            console.error('Failed to load all collections:', err);
        } finally {
            setAllCollectionsLoading(false);
        }
    }, [collectionsPage, collectionsPerPage, collectionsSortBy, collectionFilters.search]);

    // Sync handlers
    const handleAnalyzeAll = useCallback(async () => {
        setAnalyzing(true);
        try {
            const response = await optimizerAPI.analyzeAllGA4();
            await handleMaybeTask(response);
            await loadCollections();
        } catch (err) {
            console.error('Failed to analyze GA4 data:', err);
        } finally {
            setAnalyzing(false);
        }
    }, [loadCollections, handleMaybeTask]);

    const handleSyncShopify = useCallback(async () => {
        setSyncingShopify(true);
        try {
            await optimizerAPI.syncShopifyAttribution(days);
            await loadCollections();
        } catch (err) {
            console.error('Failed to sync Shopify attribution:', err);
        } finally {
            setSyncingShopify(false);
        }
    }, [days, loadCollections]);

    const handleRunDataForSEO = useCallback(async () => {
        setRunningDataForSEO(true);
        try {
            const response = await optimizerAPI.runDataForSEOAll();
            await handleMaybeTask(response);
            await loadCollections();
        } catch (err) {
            console.error('Failed to run DataForSEO:', err);
        } finally {
            setRunningDataForSEO(false);
        }
    }, [loadCollections, handleMaybeTask]);

    const handleRunDataForSEOSingle = useCallback(async (collectionId: number) => {
        try {
            await optimizerAPI.runDataForSEOCollection(collectionId);
            await loadCollections();
        } catch (err) {
            console.error('Failed to run DataForSEO for collection:', err);
        }
    }, [loadCollections]);

    const loadCollectionQueries = useCallback(async (collectionId: number) => {
        if (queryCache[collectionId]) return;
        try {
            const data = await optimizerAPI.getCollectionQueries(collectionId);
            setQueryCache(prev => ({ ...prev, [collectionId]: data.queries || [] }));
        } catch (err) {
            console.error('Failed to load queries for collection:', err);
            setQueryCache(prev => ({ ...prev, [collectionId]: [] }));
        }
    }, [queryCache]);

    // Mount effect
    useEffect(() => {
        setMounted(true);
        setLastUpdated(new Date());
    }, []);

    // Multi-agent status
    useEffect(() => {
        const loadMultiAgentStatus = async () => {
            try {
                const status = await productsAIAPI.getMultiAgentStatus();
                setMultiAgentStatus(status);
                setMultiAgentEnabled(status.multi_agent_enabled);
            } catch (e) {
                console.log('[Multi-Agent] Status check failed, using defaults');
            }
        };
        loadMultiAgentStatus();
    }, []);

    // Load analytics data (once on mount)
    useEffect(() => {
        const loadAnalyticsData = async () => {
            try {
                const [aiTraffic, summary, llmSales] = await Promise.all([
                    analyticsAPI.getAITraffic(30),
                    productAPI.getAnalyticsSummary(),
                    analyticsAPI.getLLMSales(365),
                ]);
                setAiTrafficData(aiTraffic);
                setAnalyticsSummary(summary);
                setLlmSalesData(llmSales);
            } catch (e) {
                console.warn('[Analytics] Could not load analytics data for charts:', e);
            }
        };
        loadAnalyticsData();
    }, []);

    // Auto-refresh
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (autoRefresh && mounted) {
            interval = setInterval(() => {
                if (activeTab === 'products') {
                    loadProducts();
                } else {
                    loadCollections();
                }
            }, 30000);
        }
        return () => clearInterval(interval);
    }, [autoRefresh, activeTab, loadProducts, loadCollections, mounted]);

    // Load products on mount
    useEffect(() => {
        if (mounted) {
            loadProducts();
        }
    }, [loadProducts, mounted]);

    // Load collections when tab switches
    useEffect(() => {
        if (activeTab === 'collections' && mounted) {
            loadCollections();
        }
    }, [activeTab, loadCollections, mounted]);

    // Load all collections when sub-tab is 'all'
    useEffect(() => {
        if (activeTab === 'collections' && collectionTab === 'all') {
            loadAllCollections();
        }
    }, [activeTab, collectionTab, collectionsPage, collectionsPerPage, collectionsSortBy, collectionFilters.search]);

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => {
            if (activeTab === 'products') {
                loadProducts(1, activeSegment, productFilters.search);
            }
        }, 500);
        return () => clearTimeout(timer);
    }, [productFilters.search, activeTab, activeSegment]);

    return {
        // Data
        products, productsTotal, productsLoading,
        collections, opportunities, collectionsLoading,
        allCollections, allCollectionsTotal, allCollectionsLoading,
        ga4Dashboard,
        aiTrafficData, llmSalesData, analyticsSummary,
        segmentCounts, queryCache,
        // Operation states
        isLoading, analyzing, syncingShopify, runningDataForSEO,
        lastUpdated, mounted,
        // Multi-agent
        multiAgentEnabled, setMultiAgentEnabled,
        multiAgentStatus,
        // Actions
        loadProducts, loadCollections, loadAllCollections,
        handleAnalyzeAll, handleSyncShopify,
        handleRunDataForSEO, handleRunDataForSEOSingle,
        loadCollectionQueries,
    };
}
