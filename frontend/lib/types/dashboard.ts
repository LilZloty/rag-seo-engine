import { DataSourceFilters } from '../../components/filters/DataSourceTabs';

export interface FilterPreset {
    id: string;
    name: string;
    filters: ProductFilters | CollectionFilters;
    tab: 'products' | 'collections';
}

export interface ProductFilters {
    search: string;
    showNeedsSEO: boolean;
    priceMin: number | '';
    priceMax: number | '';
    salesVolume: 'all' | '0' | '1-10' | '11-50' | '50-100' | '100+';
    revenueMin: number | '';
    revenueMax: number | '';
    dateCreatedStart: string;
    dateCreatedEnd: string;
    seoScoreMin: number;
    seoScoreMax: number;
    hasImages: 'all' | 'yes' | 'no';
    category: string;
}

export interface CollectionFilters {
    search: string;
    trafficRange: 'all' | '0-100' | '100-500' | '500-1000' | '1000+';
    conversionRateMin: number;
    conversionRateMax: number;
    revenueMin: number | '';
    revenueMax: number | '';
    aiTrafficOnly: boolean;
    opportunityScore: 'all' | 'high' | 'medium' | 'low';
    periodComparison: 'none' | 'week' | 'month' | 'quarter';
}

export interface TrendData {
    date: string;
    revenue: number;
    traffic: number;
    conversions: number;
    seoScore: number;
}

export interface Recommendation {
    id: string;
    type: 'product' | 'collection' | 'seo' | 'inventory' | 'opportunity';
    title: string;
    message: string;
    priority: 'high' | 'medium' | 'low' | 'critical';
    estimatedImpact: number;
    action: string;
    actionType: 'optimize' | 'review' | 'promote' | 'fix' | 'analyze' | 'dismiss';
    entityId?: string;
    entityType?: 'product' | 'collection';
    dismissed?: boolean;
    dismissedAt?: Date;
    createdAt: Date;
    metric?: {
        label: string;
        value: string;
        trend?: 'up' | 'down' | 'neutral';
    };
}

export interface TrafficSource {
    name: string;
    value: number;
    color: string;
}

export interface StatCardProps {
    title: string;
    value: string | number;
    subtitle?: string;
    trend?: { value: number; isPositive: boolean };
    icon: React.ReactNode;
    color: string;
}

export type SortField = 'title' | 'seo_score' | 'total_sold' | 'total_revenue' | 'ga4_sessions' | 'gsc_impressions' | 'gsc_position' | 'gsc_ctr' | 'performance_score' | 'created_at' | 'updated_at' | 'inventory_quantity';

export type SortDirection = 'asc' | 'desc';

export type CollectionsSortBy = 'impressions' | 'sessions' | 'revenue' | 'volume' | 'priority';

export type SalesPeriod = '30d' | '90d' | '365d' | 'all_time';
