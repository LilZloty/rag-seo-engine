import { useMemo } from 'react';
import type { Product, GA4Dashboard } from '../lib/api';
import type { TrafficSource } from '../lib/types/dashboard';

interface AITrafficSummary {
    total_sessions: number;
    ai_sessions: number;
    traditional_sessions: number;
    referrers?: Record<string, number>;
}

interface AITrafficReport {
    summary?: AITrafficSummary;
}

export function useDashboardChartData(
    products: Product[],
    aiTrafficData: AITrafficReport | null,
    ga4Dashboard: GA4Dashboard | null
) {
    const revenueOverviewData = useMemo(() => [
        { period: '30 days',  revenue: products.reduce((s, p) => s + (p.revenue_30d  || 0), 0), units: products.reduce((s, p) => s + (p.sold_30d  || 0), 0) },
        { period: '90 days',  revenue: products.reduce((s, p) => s + (p.revenue_90d  || 0), 0), units: products.reduce((s, p) => s + (p.sold_90d  || 0), 0) },
        { period: '1 year',   revenue: products.reduce((s, p) => s + (p.revenue_365d || 0), 0), units: products.reduce((s, p) => s + (p.sold_365d || 0), 0) },
        { period: 'All time', revenue: products.reduce((s, p) => s + (p.revenue_all_time || p.total_revenue || 0), 0), units: products.reduce((s, p) => s + (p.sold_all_time || p.total_sold || 0), 0) },
    ], [products]);

    const topOrganicData = useMemo(() => {
        return products
            .filter(p => (p.gsc_impressions || 0) > 0 || (p.ga4_sessions || 0) > 0)
            .map(p => ({
                name: p.title.length > 24 ? p.title.substring(0, 24) + '\u2026' : p.title,
                impressions: p.gsc_impressions || 0,
                sessions: p.ga4_sessions || 0,
                seoScore: p.seo_score,
            }))
            .sort((a, b) => (b.impressions || b.sessions) - (a.impressions || a.sessions))
            .slice(0, 7);
    }, [products]);

    const funnelData = useMemo(() => {
        const totalImpressions = products.reduce((s, p) => s + (p.gsc_impressions || 0), 0);
        const totalClicks = products.reduce((s, p) => s + (p.gsc_clicks || 0), 0);
        const totalSessions = products.reduce((s, p) => s + (p.ga4_sessions || 0), 0);
        const totalSold = products.reduce((s, p) => s + (p.total_sold || 0), 0);
        return [
            { name: 'GSC Impressions', value: totalImpressions || 1, fill: '#3b82f6' },
            { name: 'GSC Clicks', value: totalClicks || 0, fill: '#8b5cf6' },
            { name: 'GA4 Sessions', value: totalSessions || 0, fill: '#f7b500' },
            { name: 'Units Sold', value: totalSold || 0, fill: '#22c55e' },
        ];
    }, [products]);

    const heatmapData = useMemo(() => {
        const byType: Record<string, { seoSum: number; count: number; revenue: number }> = {};
        products.forEach(p => {
            const type = p.product_type || 'Sin tipo';
            if (!byType[type]) byType[type] = { seoSum: 0, count: 0, revenue: 0 };
            byType[type].seoSum += p.seo_score;
            byType[type].count += 1;
            byType[type].revenue += p.total_revenue || 0;
        });
        return Object.entries(byType)
            .map(([category, d]) => ({
                category: category.length > 20 ? category.substring(0, 20) + '\u2026' : category,
                performance: Math.round(d.seoSum / d.count),
                revenue: Math.round(d.revenue),
            }))
            .sort((a, b) => b.revenue - a.revenue)
            .slice(0, 6);
    }, [products]);

    const trafficSourcesData: TrafficSource[] = useMemo(() => {
        if (aiTrafficData?.summary) {
            const { total_sessions, ai_sessions, traditional_sessions } = aiTrafficData.summary;
            const referrers = aiTrafficData.summary.referrers || {};
            const items: TrafficSource[] = [
                { name: 'Organic', value: traditional_sessions || 0, color: '#22c55e' },
                { name: 'AI Referral', value: ai_sessions || 0, color: '#f7b500' },
            ];
            Object.entries(referrers).slice(0, 3).forEach(([name, count], i) => {
                const colors = ['#8b5cf6', '#3b82f6', '#666666'];
                if ((count as number) > 0) items.push({ name, value: count as number, color: colors[i] || '#555' });
            });
            return items.filter(i => i.value > 0);
        }
        const aiSessions = ga4Dashboard?.stats?.total_ai_referral_sessions || 0;
        const totalSessions = ga4Dashboard?.stats?.total_sessions || 1;
        return [
            { name: 'Organic/Other', value: Math.max(0, totalSessions - aiSessions), color: '#22c55e' },
            { name: 'AI Referral', value: aiSessions, color: '#f7b500' },
        ].filter(i => i.value > 0);
    }, [aiTrafficData, ga4Dashboard]);

    const categoryComparisonData = useMemo(() => heatmapData, [heatmapData]);

    return {
        revenueOverviewData,
        topOrganicData,
        funnelData,
        heatmapData,
        trafficSourcesData,
        categoryComparisonData,
    };
}
