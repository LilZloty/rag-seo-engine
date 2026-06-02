import type { ChartConfig } from '../app/components/ui/chart';

export const revenueTrendConfig: ChartConfig = {
    revenue: { label: 'Revenue ($)', color: '#22c55e' },
    units:   { label: 'Units sold',  color: '#3b82f6' },
};

export const sessionTrendConfig: ChartConfig = {
    impressions: { label: 'Impressions', color: '#f7b500' },
    sessions:    { label: 'Sessions',    color: '#3b82f6' },
};

export const funnelConfig: ChartConfig = {
    value: { label: 'Count', color: '#3b82f6' },
};

export const topCollectionsConfig: ChartConfig = {
    sessions:    { label: 'Sessions',    color: '#3b82f6' },
    conversions: { label: 'Conversions', color: '#22c55e' },
};

export const conversionDistConfig: ChartConfig = {
    value: { label: 'Conversions', color: '#8b5cf6' },
};

export const seoScoreConfig: ChartConfig = {
    performance: { label: 'Avg SEO Score', color: '#f7b500' },
};

export const trafficSourcesConfig: ChartConfig = {
    value: { label: 'Sessions', color: '#3b82f6' },
};

export const revenueByTypeConfig: ChartConfig = {
    revenue: { label: 'Revenue ($)', color: '#22c55e' },
};

export const scatterConfig: ChartConfig = {
    x: { label: 'Sessions',       color: '#f7b500' },
    y: { label: 'Conv. Rate (%)', color: '#f7b500' },
};
