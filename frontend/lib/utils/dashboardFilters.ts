import { Product, CollectionOptimizer } from '../api';
import { applySmartSegmentFilter } from '../../components/filters/SmartSegments';
import { applyVisualFilters, FilterGroup } from '../../components/filters/VisualFilterBuilder';
import { DataSourceFilters } from '../../components/filters/DataSourceTabs';
import type { CollectionFilters, SortField, SortDirection } from '../types/dashboard';

export function filterAndSortProducts(
    products: Product[],
    activeSegment: string,
    visualFilters: FilterGroup,
    dataSourceFilters: DataSourceFilters,
    sortField: SortField,
    sortDirection: SortDirection
): Product[] {
    // 1. Smart Segment
    let result = applySmartSegmentFilter([...products], activeSegment);

    // 2. Visual Filter Builder
    result = applyVisualFilters(result, visualFilters);

    // 3. Data Source filters
    result = result.filter(p => {
        const productPrice = parseFloat(p.price || '0') || 0;
        if (dataSourceFilters.priceMin !== '' && productPrice < Number(dataSourceFilters.priceMin)) return false;
        if (dataSourceFilters.priceMax !== '' && productPrice > Number(dataSourceFilters.priceMax)) return false;

        if (dataSourceFilters.salesVolume !== 'all') {
            const sold = p.total_sold || 0;
            switch (dataSourceFilters.salesVolume) {
                case '0': if (sold !== 0) return false; break;
                case '1-10': if (sold < 1 || sold > 10) return false; break;
                case '11-50': if (sold < 11 || sold > 50) return false; break;
                case '50-100': if (sold < 50 || sold > 100) return false; break;
                case '100+': if (sold < 100) return false; break;
            }
        }

        if (dataSourceFilters.revenueMin !== '' && (p.total_revenue || 0) < Number(dataSourceFilters.revenueMin)) return false;
        if (dataSourceFilters.vendor && !p.vendor?.toLowerCase().includes(dataSourceFilters.vendor.toLowerCase())) return false;
        if (dataSourceFilters.productType && !p.product_type?.toLowerCase().includes(dataSourceFilters.productType.toLowerCase())) return false;

        if (dataSourceFilters.sessionsMin !== '' && (p.ga4_sessions || 0) < Number(dataSourceFilters.sessionsMin)) return false;
        if (dataSourceFilters.sessionsMax !== '' && (p.ga4_sessions || 0) > Number(dataSourceFilters.sessionsMax)) return false;
        if (dataSourceFilters.engagementMin !== '' && (p.ga4_engagement_time || 0) < Number(dataSourceFilters.engagementMin)) return false;
        if (dataSourceFilters.bounceRateMax !== '' && (p.ga4_bounce_rate || 0) > Number(dataSourceFilters.bounceRateMax)) return false;

        if (dataSourceFilters.performanceScore !== 'all') {
            const score = p.performance_score || 0;
            switch (dataSourceFilters.performanceScore) {
                case '0-25': if (score > 25) return false; break;
                case '26-50': if (score < 26 || score > 50) return false; break;
                case '51-75': if (score < 51 || score > 75) return false; break;
                case '76-100': if (score < 76) return false; break;
            }
        }

        if (dataSourceFilters.impressionsMin !== '' && (p.gsc_impressions || 0) < Number(dataSourceFilters.impressionsMin)) return false;
        if (dataSourceFilters.clicksMin !== '' && (p.gsc_clicks || 0) < Number(dataSourceFilters.clicksMin)) return false;
        if (dataSourceFilters.ctrMin !== '' && (p.gsc_ctr || 0) < Number(dataSourceFilters.ctrMin)) return false;
        if (dataSourceFilters.positionMax !== '' && (p.gsc_position || 0) > Number(dataSourceFilters.positionMax)) return false;

        return true;
    });

    // 4. Sort
    result.sort((a, b) => {
        let aValue: number | string = 0;
        let bValue: number | string = 0;

        switch (sortField) {
            case 'title': aValue = a.title || ''; bValue = b.title || ''; break;
            case 'seo_score': aValue = a.seo_score || 0; bValue = b.seo_score || 0; break;
            case 'total_sold': aValue = a.total_sold || 0; bValue = b.total_sold || 0; break;
            case 'total_revenue': aValue = a.total_revenue || 0; bValue = b.total_revenue || 0; break;
            case 'ga4_sessions': aValue = a.ga4_sessions || 0; bValue = b.ga4_sessions || 0; break;
            case 'gsc_impressions': aValue = a.gsc_impressions || 0; bValue = b.gsc_impressions || 0; break;
            case 'gsc_position': aValue = a.gsc_position || 999; bValue = b.gsc_position || 999; break;
            case 'gsc_ctr': aValue = a.gsc_ctr || 0; bValue = b.gsc_ctr || 0; break;
            case 'performance_score': aValue = a.performance_score || 0; bValue = b.performance_score || 0; break;
            case 'created_at':
                aValue = a.created_at ? new Date(a.created_at).getTime() : 0;
                bValue = b.created_at ? new Date(b.created_at).getTime() : 0;
                break;
            case 'updated_at':
                aValue = a.updated_at ? new Date(a.updated_at).getTime() : 0;
                bValue = b.updated_at ? new Date(b.updated_at).getTime() : 0;
                break;
            case 'inventory_quantity':
                aValue = a.inventory_quantity ?? -1;
                bValue = b.inventory_quantity ?? -1;
                break;
        }

        if (typeof aValue === 'string' && typeof bValue === 'string') {
            return sortDirection === 'asc'
                ? aValue.localeCompare(bValue)
                : bValue.localeCompare(aValue);
        }

        return sortDirection === 'asc'
            ? (aValue as number) - (bValue as number)
            : (bValue as number) - (aValue as number);
    });

    return result;
}

export function filterCollections(
    opportunities: CollectionOptimizer[],
    filters: CollectionFilters
): CollectionOptimizer[] {
    return opportunities.filter(c => {
        if (filters.search && !c.title.toLowerCase().includes(filters.search.toLowerCase())) return false;

        if (filters.trafficRange !== 'all') {
            const sessions = c.ga4_sessions || 0;
            switch (filters.trafficRange) {
                case '0-100': if (sessions < 0 || sessions > 100) return false; break;
                case '100-500': if (sessions < 100 || sessions > 500) return false; break;
                case '500-1000': if (sessions < 500 || sessions > 1000) return false; break;
                case '1000+': if (sessions < 1000) return false; break;
            }
        }

        const convRate = c.ga4_conversion_rate || 0;
        if (convRate < filters.conversionRateMin || convRate > filters.conversionRateMax) return false;
        if (filters.aiTrafficOnly && !(c.ga4_ai_referral_sessions && c.ga4_ai_referral_sessions > 0)) return false;

        return true;
    });
}

export function sortOpportunityCollections(
    collections: CollectionOptimizer[],
    sortBy: string
): CollectionOptimizer[] {
    const sorted = [...collections];
    switch (sortBy) {
        case 'impressions': sorted.sort((a, b) => (b.impressions || 0) - (a.impressions || 0)); break;
        case 'position': sorted.sort((a, b) => (a.position || 999) - (b.position || 999)); break;
        case 'sessions': sorted.sort((a, b) => (b.ga4_sessions || 0) - (a.ga4_sessions || 0)); break;
        case 'bounce_rate': sorted.sort((a, b) => (b.ga4_bounce_rate || 0) - (a.ga4_bounce_rate || 0)); break;
        case 'revenue': sorted.sort((a, b) => (b.shopify_attributed_revenue || 0) - (a.shopify_attributed_revenue || 0)); break;
        case 'volume': sorted.sort((a, b) => (b.dataforseo_volume || 0) - (a.dataforseo_volume || 0)); break;
        default: sorted.sort((a, b) => (b.impressions || 0) - (a.impressions || 0));
    }
    return sorted;
}

export function computeCollectionStats(collections: CollectionOptimizer[]) {
    const withGSC = collections.filter(c => c.impressions > 0);
    const withGA4 = collections.filter(c => (c.ga4_sessions || 0) > 0);
    const withDFS = collections.filter(c => (c.dataforseo_volume || 0) > 0);
    const withBounce = collections.filter(c => (c.ga4_bounce_rate || 0) > 0);
    const withShopify = collections.filter(c => (c.last_shopify_sync));
    return {
        avgImpressions: withGSC.length > 0 ? Math.round(withGSC.reduce((s, c) => s + c.impressions, 0) / withGSC.length) : 0,
        avgPosition: withGSC.length > 0 ? (withGSC.reduce((s, c) => s + (c.position || 0), 0) / withGSC.length) : 0,
        totalSessions: collections.reduce((s, c) => s + (c.ga4_sessions || 0), 0),
        avgBounceRate: withBounce.length > 0 ? (withBounce.reduce((s, c) => s + (c.ga4_bounce_rate || 0), 0) / withBounce.length) : 0,
        collectionsWithGA4: withGA4.length,
        totalShopifyRevenue: collections.reduce((s, c) => s + (c.shopify_attributed_revenue || 0), 0),
        totalShopifyOrders: collections.reduce((s, c) => s + (c.shopify_attributed_orders || 0), 0),
        lastShopifySync: withShopify.length > 0 ? withShopify[0].last_shopify_sync : null,
        avgDFSVolume: withDFS.length > 0 ? Math.round(withDFS.reduce((s, c) => s + (c.dataforseo_volume || 0), 0) / withDFS.length) : 0,
        collectionsWithDFS: withDFS.length,
    };
}

export function exportToCSV(
    activeTab: 'products' | 'collections',
    filteredProducts: any[],
    filteredCollections: any[]
) {
    const data = activeTab === 'products' ? filteredProducts : filteredCollections;
    const headers = activeTab === 'products'
        ? ['ID', 'Title', 'SKU', 'SEO Score', 'Price', 'Sold', 'Revenue']
        : ['ID', 'Title', 'Sessions', 'Conversions', 'Conversion Rate'];

    const csvContent = [
        headers.join(','),
        ...data.map((item: any) => activeTab === 'products'
            ? [item.id, `"${item.title}"`, item.sku || '', item.seo_score, item.price || 0, item.total_sold || 0, item.total_revenue || 0].join(',')
            : [item.id, `"${item.title}"`, item.ga4_sessions || 0, item.ga4_conversions || 0, item.ga4_conversion_rate || 0].join(',')
        )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeTab}-export-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
}
