import type { ProductFilters, CollectionFilters } from '../types/dashboard';

export const DATE_RANGES = [
    { value: 7, label: 'Last 7 Days' },
    { value: 30, label: 'Last 30 Days' },
    { value: 90, label: 'Last 90 Days' },
];

export const PERIOD_COMPARISONS = [
    { value: 'none', label: 'No Comparison' },
    { value: 'week', label: 'This Week vs Last Week' },
    { value: 'month', label: 'This Month vs Last Month' },
    { value: 'quarter', label: 'This Quarter vs Last Quarter' },
];

export const SALES_VOLUME_OPTIONS = [
    { value: 'all', label: 'All Sales' },
    { value: '0', label: '0 sales' },
    { value: '1-10', label: '1-10 sales' },
    { value: '11-50', label: '11-50 sales' },
    { value: '50-100', label: '50-100 sales' },
    { value: '100+', label: '100+ sales' },
];

export const TRAFFIC_RANGE_OPTIONS = [
    { value: 'all', label: 'All Traffic' },
    { value: '0-100', label: '0-100 sessions' },
    { value: '100-500', label: '100-500 sessions' },
    { value: '500-1000', label: '500-1000 sessions' },
    { value: '1000+', label: '1000+ sessions' },
];

export const OPPORTUNITY_SCORE_OPTIONS = [
    { value: 'all', label: 'All Scores' },
    { value: 'high', label: 'High Priority' },
    { value: 'medium', label: 'Medium Priority' },
    { value: 'low', label: 'Low Priority' },
];

export const DEFAULT_PRODUCT_FILTERS: ProductFilters = {
    search: '',
    showNeedsSEO: false,
    priceMin: '',
    priceMax: '',
    salesVolume: 'all',
    revenueMin: '',
    revenueMax: '',
    dateCreatedStart: '',
    dateCreatedEnd: '',
    seoScoreMin: 0,
    seoScoreMax: 100,
    hasImages: 'all',
    category: 'all',
};

export const DEFAULT_COLLECTION_FILTERS: CollectionFilters = {
    search: '',
    trafficRange: 'all',
    conversionRateMin: 0,
    conversionRateMax: 100,
    revenueMin: '',
    revenueMax: '',
    aiTrafficOnly: false,
    opportunityScore: 'all',
    periodComparison: 'none',
};

export const DEFAULT_VISIBLE_COLUMNS = {
    product: true,
    sku: true,
    seoScore: true,
    sold: true,
    revenue: true,
    price: true,
    images: true,
    inventory: true,
    created: true,
    updated: true,
    gscImpressions: false,
    gscPosition: false,
    gscCtr: false,
    ga4Sessions: false,
    opportunityLevel: false,
};
