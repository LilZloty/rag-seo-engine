'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { LightningIcon, RefreshIcon } from '../../ui/Icons';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

interface PriorityComponents {
    score: number;
    projected_clicks: {
        value: number;
        normalized: number;
        current_position: number;
        target_position: number;
        impressions: number;
    };
    revenue_potential: {
        value: number;
        normalized: number;
        used_rps: boolean;
        rps: number | null;
    };
    trend_urgency: {
        value: number;
        current_position?: number;
        position_30d_ago?: number;
        delta?: number;
        has_baseline: boolean;
    };
    fixability: {
        value: number;
        has_images: boolean;
        in_stock: boolean;
        convertible: boolean;
        has_baseline_content: boolean;
    };
    confidence: {
        value: number;
        gsc_impressions: number;
        ga4_sessions: number;
        gsc_above_threshold: boolean;
        ga4_above_threshold: boolean;
    };
    effort_estimate: {
        score: number;
        drivers: string[];
    };
}

interface QueueItem {
    id: string;
    shopify_id: string;
    title: string;
    sku: string | null;
    handle: string;
    priority_score: number;
    priority_components: PriorityComponents | null;
    priority_computed_at: string | null;
    gsc_impressions: number;
    gsc_position: number;
    ga4_sessions: number;
    revenue_90d: number;
    seo_score: number;
    image_count: number;
    inventory_status: string | null;
}

interface UnderperformingQuery {
    query: string;
    position: number;
    impressions: number;
    clicks: number;
    ctr: number;
    expected_ctr: number | null;
    ctr_gap: number | null;
    is_underperforming: boolean;
    potential_extra_clicks: number;
    position_change_30d: number | null;
    last_seen: string | null;
}

interface PositionTrendPoint {
    date: string;
    position: number;
    impressions: number;
    clicks: number;
}

interface CannibalizationWarning {
    query: string;
    this_page_position: number;
    this_page_impressions: number;
    competing_pages_count: number;
    competing_pages: Array<{
        page_url: string;
        position: number;
        impressions: number;
        page_type: string | null;
    }>;
    date: string | null;
}

interface ProductInsights {
    product_id: string;
    page_url: string | null;
    top_underperforming_queries: UnderperformingQuery[];
    position_trend_30d: PositionTrendPoint[];
    cannibalization: CannibalizationWarning[];
}

type InsightsState = ProductInsights | 'loading' | 'error';

interface OptimizationQueueProps {
    limit?: number;
}

const EFFORT_LABELS = ['Low', 'Medium', 'High'];
const DRIVER_LABELS: Record<string, string> = {
    missing_images: 'Add images',
    missing_description: 'Write description',
    low_seo_score: 'Rewrite SEO content',
};

function effortBucket(score: number) {
    if (score <= 30) return { label: 'Low', mins: '~15-30 min', tone: 'text-[#8be78b]', bg: 'bg-[#8be78b]/10', border: 'border-[#8be78b]/30' };
    if (score <= 60) return { label: 'Medium', mins: '~1-2 hr', tone: 'text-[#f7b500]', bg: 'bg-[#f7b500]/10', border: 'border-[#f7b500]/30' };
    return { label: 'High', mins: 'Half day+', tone: 'text-[#ff8a3d]', bg: 'bg-[#ff8a3d]/10', border: 'border-[#ff8a3d]/30' };
}

function scoreTier(score: number) {
    if (score >= 50) return { label: 'GOLD', color: '#f7b500' };
    if (score >= 25) return { label: 'SILVER', color: '#94a3b8' };
    return { label: 'BRONZE', color: '#b45309' };
}

export default function OptimizationQueue({ limit = 20 }: OptimizationQueueProps) {
    const router = useRouter();
    const [items, setItems] = useState<QueueItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [recomputing, setRecomputing] = useState(false);
    const [computedAt, setComputedAt] = useState<string | null>(null);
    // Locale formatting differs between Node ICU and the browser, so format
    // the label client-side only — keeps SSR/CSR HTML identical for hydration.
    const [computedAtLabel, setComputedAtLabel] = useState<string | null>(null);
    useEffect(() => {
        if (!computedAt) { setComputedAtLabel(null); return; }
        setComputedAtLabel(
            new Date(computedAt).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' })
        );
    }, [computedAt]);
    const [insightsCache, setInsightsCache] = useState<Record<string, InsightsState>>({});

    // sessionStorage cache survives card collapse/re-expand and tab navigation
    // within the same browser session. Previously each expand fired a network
    // call even if the card had been opened seconds ago. 5-min TTL matches the
    // backend's products endpoint cache (api.ts DEFAULT_CACHE_TTL).
    const INSIGHTS_SS_TTL_MS = 5 * 60 * 1000;
    const ssKeyFor = (productId: string) => `oq:insights:${productId}`;

    const fetchInsights = useCallback(async (productId: string) => {
        if (insightsCache[productId] && insightsCache[productId] !== 'error') return;

        // Check sessionStorage before hitting the API
        try {
            const raw = typeof window !== 'undefined' ? window.sessionStorage.getItem(ssKeyFor(productId)) : null;
            if (raw) {
                const { data, expiry } = JSON.parse(raw) as { data: ProductInsights; expiry: number };
                if (Date.now() < expiry) {
                    setInsightsCache(prev => ({ ...prev, [productId]: data }));
                    return;
                }
            }
        } catch { /* corrupted entry — fall through to fetch */ }

        setInsightsCache(prev => ({ ...prev, [productId]: 'loading' }));
        try {
            const res = await fetch(`${API_BASE}/seo-intelligence/products/${productId}/insights`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: ProductInsights = await res.json();
            setInsightsCache(prev => ({ ...prev, [productId]: data }));
            try {
                if (typeof window !== 'undefined') {
                    window.sessionStorage.setItem(ssKeyFor(productId), JSON.stringify({
                        data,
                        expiry: Date.now() + INSIGHTS_SS_TTL_MS,
                    }));
                }
            } catch { /* quota / private mode — ignore */ }
        } catch {
            setInsightsCache(prev => ({ ...prev, [productId]: 'error' }));
        }
    }, [insightsCache]);

    const toggleExpanded = useCallback((productId: string) => {
        setExpandedId(prev => {
            const next = prev === productId ? null : productId;
            if (next) fetchInsights(next);
            return next;
        });
    }, [fetchInsights]);

    const fetchQueue = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/seo-intelligence/optimization-queue?limit=${limit}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const products: QueueItem[] = data.products || [];
            setItems(products);
            setComputedAt(products[0]?.priority_computed_at || null);
        } catch (e: any) {
            setError(e.message || 'Failed to load optimization queue');
        } finally {
            setLoading(false);
        }
    }, [limit]);

    const recompute = useCallback(async () => {
        setRecomputing(true);
        try {
            await fetch(`${API_BASE}/seo-intelligence/optimization-queue/recompute`, { method: 'POST' });
            await fetchQueue();
        } finally {
            setRecomputing(false);
        }
    }, [fetchQueue]);

    useEffect(() => { fetchQueue(); }, [fetchQueue]);

    const totalProjectedClicks = items.reduce((acc, it) => acc + (it.priority_components?.projected_clicks.value || 0), 0);
    const totalRevenue = items.reduce((acc, it) => acc + (it.priority_components?.revenue_potential.value || 0), 0);

    return (
        <div className="bg-[#111111] border border-[#f7b500]/30 p-6 mb-8">
            {/* Header */}
            <div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-[#f7b500]/20">
                        <LightningIcon />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-white">Optimization Queue</h3>
                        <p className="text-[#666666] text-sm">
                            {loading ? 'Loading…' : (
                                <>
                                    Top {items.length} priorities •{' '}
                                    +{Math.round(totalProjectedClicks).toLocaleString()} projected clicks •{' '}
                                    ~${Math.round(totalRevenue).toLocaleString()} MXN potential
                                </>
                            )}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {computedAtLabel && (
                        <span className="text-[#555555] text-xs">
                            Computed {computedAtLabel}
                        </span>
                    )}
                    <button
                        onClick={recompute}
                        disabled={recomputing}
                        className="flex items-center gap-1 text-[#888888] hover:text-white text-xs px-3 py-1 hover:bg-[#222222] transition-colors disabled:opacity-50"
                        title="Force recompute (normally nightly)"
                    >
                        <RefreshIcon />
                        {recomputing ? 'Recomputing…' : 'Recompute'}
                    </button>
                </div>
            </div>

            {/* Error state */}
            {error && (
                <div className="bg-[#3d1a1a] border border-[#ff8a3d]/40 p-3 mb-4 text-[#ff8a3d] text-sm">
                    {error}. Try Recompute, or check the backend logs.
                </div>
            )}

            {/* Empty state */}
            {!loading && !error && items.length === 0 && (
                <div className="text-center py-8 text-[#666666] text-sm">
                    No products scored yet. Click <span className="text-white">Recompute</span> to derive priorities.
                </div>
            )}

            {/* Queue rows */}
            <div className="divide-y divide-[#222222]">
                {items.map((item, idx) => {
                    const c = item.priority_components;
                    if (!c) return null;
                    const tier = scoreTier(item.priority_score);
                    const effort = effortBucket(c.effort_estimate.score);
                    const isExpanded = expandedId === item.id;
                    const hasTrend = c.trend_urgency.value > 0 && c.trend_urgency.delta;
                    const currentPos = c.projected_clicks.current_position;
                    const targetPos = c.projected_clicks.target_position;

                    return (
                        <div key={item.id} className="py-3 hover:bg-[#181818] transition-colors">
                            <div className="flex items-center gap-4">
                                {/* Rank + tier */}
                                <div className="flex-shrink-0 w-14 text-center">
                                    <div className="text-[#555555] text-xs">#{idx + 1}</div>
                                    <div className="font-mono text-xs" style={{ color: tier.color }}>{tier.label}</div>
                                </div>

                                {/* Title + SKU */}
                                <div className="flex-1 min-w-0">
                                    <div className="text-white text-sm font-medium truncate" title={item.title}>
                                        {item.title}
                                    </div>
                                    <div className="text-[#666666] text-xs">
                                        {item.sku ? `SKU: ${item.sku} • ` : ''}
                                        Pos {currentPos.toFixed(1)} → {targetPos} • {c.projected_clicks.impressions.toLocaleString()} impr
                                    </div>
                                </div>

                                {/* Projected clicks */}
                                <div className="hidden md:block text-right w-28">
                                    <div className="text-[#f7b500] text-sm font-semibold">+{Math.round(c.projected_clicks.value).toLocaleString()}</div>
                                    <div className="text-[#666666] text-xs">clicks</div>
                                </div>

                                {/* Revenue */}
                                <div className="hidden lg:block text-right w-28">
                                    <div className="text-white text-sm">${Math.round(c.revenue_potential.value).toLocaleString()}</div>
                                    <div className="text-[#666666] text-xs">{c.revenue_potential.used_rps ? 'real RPS' : 'estimated'}</div>
                                </div>

                                {/* Effort */}
                                <div className={`hidden md:flex flex-col items-center px-2 py-1 border ${effort.border} ${effort.bg} text-xs`}>
                                    <span className={`font-medium ${effort.tone}`}>{effort.label}</span>
                                    <span className="text-[#666666]">{effort.mins}</span>
                                </div>

                                {/* Trend warning */}
                                {hasTrend && (
                                    <div className="hidden lg:flex items-center gap-1 text-[#ff8a3d] text-xs" title={`Lost ${c.trend_urgency.delta?.toFixed(1)} positions in 30d`}>
                                        <span>↓</span>
                                        <span>{c.trend_urgency.delta?.toFixed(1)}</span>
                                    </div>
                                )}

                                {/* Score */}
                                <div className="w-14 text-right">
                                    <div className="text-white font-mono text-base">{item.priority_score.toFixed(0)}</div>
                                    <div className="text-[#666666] text-xs">/ 100</div>
                                </div>

                                {/* Actions */}
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={() => toggleExpanded(item.id)}
                                        className="text-[#666666] hover:text-white text-xs px-2 py-1 hover:bg-[#222222]"
                                        title="Toggle breakdown + insights"
                                    >
                                        {isExpanded ? '▾' : '▸'}
                                    </button>
                                    <button
                                        onClick={() => router.push(`/generate/${item.id}`)}
                                        className="bg-[#f7b500] hover:bg-[#ffc928] text-black text-xs font-medium px-3 py-1.5 transition-colors"
                                    >
                                        Start →
                                    </button>
                                </div>
                            </div>

                            {/* Expanded breakdown + insights */}
                            {isExpanded && (
                                <div className="mt-3 pl-[72px] pr-4 space-y-4">
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                                        <ComponentRow label="Projected clicks" value={c.projected_clicks.normalized} weight={35} note={`+${Math.round(c.projected_clicks.value)} clicks`} />
                                        <ComponentRow label="Revenue potential" value={c.revenue_potential.normalized} weight={20} note={`~$${Math.round(c.revenue_potential.value)} MXN`} />
                                        <ComponentRow label="Trend urgency" value={c.trend_urgency.value} weight={15} note={hasTrend ? `Lost ${c.trend_urgency.delta?.toFixed(1)} pos in 30d` : 'Stable / improving'} />
                                        <ComponentRow label="Fixability" value={c.fixability.value} weight={15} note={`${[c.fixability.has_images && 'images', c.fixability.in_stock && 'stock', c.fixability.convertible && 'demand', c.fixability.has_baseline_content && 'content'].filter(Boolean).join(' • ') || 'no flags'}`} />
                                        <ComponentRow label="Confidence" value={c.confidence.value} weight={10} note={`${c.confidence.gsc_impressions.toLocaleString()} impr / ${c.confidence.ga4_sessions} sess`} />
                                        <ComponentRow label="Effort (penalty)" value={c.effort_estimate.score} weight={-5} note={c.effort_estimate.drivers.length ? c.effort_estimate.drivers.map(d => DRIVER_LABELS[d] || d).join(' • ') : 'no work needed'} />
                                    </div>
                                    <InsightsPanel state={insightsCache[item.id]} />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function ComponentRow({ label, value, weight, note }: { label: string; value: number; weight: number; note: string }) {
    const contribution = (value * weight) / 100;
    return (
        <div className="bg-[#0a0a0a]/50 border border-[#222222] p-2">
            <div className="flex items-baseline justify-between mb-1">
                <span className="text-[#888888]">{label}</span>
                <span className="text-white font-mono">{value.toFixed(0)}</span>
            </div>
            <div className="text-[#555555] mb-1">w: {weight > 0 ? `+${weight}%` : `${weight}%`} • contributes {contribution >= 0 ? '+' : ''}{contribution.toFixed(1)}</div>
            <div className="text-[#666666] truncate" title={note}>{note}</div>
        </div>
    );
}

function PositionSparkline({ data, width = 200, height = 40 }: { data: PositionTrendPoint[]; width?: number; height?: number }) {
    const valid = data.filter(d => d.position > 0);
    if (valid.length < 2) {
        return <div className="text-[#555555] text-xs italic">Not enough data for trend</div>;
    }
    const positions = valid.map(d => d.position);
    const minPos = Math.min(...positions);
    const maxPos = Math.max(...positions);
    const range = maxPos - minPos || 1;

    const points = valid.map((d, i) => {
        const x = (i / (valid.length - 1)) * width;
        // Lower position = better → render higher (smaller y). Invert so a
        // downward line on screen = the rank getting worse.
        const y = ((d.position - minPos) / range) * height;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const first = valid[0].position;
    const last = valid[valid.length - 1].position;
    const delta = last - first;
    const trendColor = delta > 1 ? '#ff8a3d' : delta < -1 ? '#8be78b' : '#f7b500';

    return (
        <div className="flex items-center gap-3">
            <svg width={width} height={height} className="overflow-visible">
                <polyline points={points} fill="none" stroke={trendColor} strokeWidth={1.5} />
            </svg>
            <div className="text-xs">
                <div className="text-[#888888]">Pos {first.toFixed(1)} → {last.toFixed(1)}</div>
                <div style={{ color: trendColor }}>
                    {delta > 0 ? '↓' : delta < 0 ? '↑' : '—'} {Math.abs(delta).toFixed(1)} in {valid.length}d
                </div>
            </div>
        </div>
    );
}

function InsightsPanel({ state }: { state: InsightsState | undefined }) {
    if (state === undefined) {
        return null;
    }
    if (state === 'loading') {
        return <div className="text-[#666666] text-xs">Loading insights…</div>;
    }
    if (state === 'error') {
        return <div className="text-[#ff8a3d] text-xs">Could not load insights for this product.</div>;
    }

    const hasQueries = state.top_underperforming_queries.length > 0;
    const hasTrend = state.position_trend_30d.length > 0;
    const hasCanniba = state.cannibalization.length > 0;

    if (!hasQueries && !hasTrend && !hasCanniba) {
        return (
            <div className="text-[#666666] text-xs italic border-t border-[#222222] pt-3">
                No query / trend / cannibalization data yet — this product may be too new or below GSC's reporting threshold.
            </div>
        );
    }

    return (
        <div className="border-t border-[#222222] pt-3 grid grid-cols-1 lg:grid-cols-3 gap-4 text-xs">
            {/* Top underperforming queries */}
            <div className="lg:col-span-2">
                <div className="text-[#888888] mb-2 uppercase tracking-wide text-[10px]">Top queries (CTR gap)</div>
                {hasQueries ? (
                    <div className="space-y-1">
                        {state.top_underperforming_queries.map((q, i) => {
                            const gapPercent = q.ctr_gap !== null ? (q.ctr_gap * 100) : null;
                            const gapColor = gapPercent !== null && gapPercent < -1 ? 'text-[#ff8a3d]' : 'text-[#888888]';
                            return (
                                <div key={`${q.query}-${i}`} className="flex items-center gap-2 py-1 border-b border-[#1a1a1a]">
                                    <span className="text-white truncate flex-1" title={q.query}>{q.query}</span>
                                    <span className="text-[#666666] w-12 text-right">pos {q.position.toFixed(1)}</span>
                                    <span className="text-[#888888] w-16 text-right">{q.impressions.toLocaleString()} impr</span>
                                    <span className={`${gapColor} w-20 text-right font-mono`}>
                                        {gapPercent !== null ? `${gapPercent >= 0 ? '+' : ''}${gapPercent.toFixed(1)}%` : '—'}
                                    </span>
                                    {q.potential_extra_clicks > 0 && (
                                        <span className="text-[#f7b500] w-14 text-right">+{q.potential_extra_clicks} clk</span>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="text-[#555555] italic">No query data yet.</div>
                )}
            </div>

            {/* Position trend sparkline */}
            <div>
                <div className="text-[#888888] mb-2 uppercase tracking-wide text-[10px]">Position trend (last 30d)</div>
                {hasTrend ? <PositionSparkline data={state.position_trend_30d} /> : <div className="text-[#555555] italic">No snapshots yet.</div>}
            </div>

            {/* Cannibalization */}
            {hasCanniba && (
                <div className="lg:col-span-3">
                    <div className="text-[#ff8a3d] mb-2 uppercase tracking-wide text-[10px]">
                        ⚠ Cannibalization — {state.cannibalization.length} {state.cannibalization.length === 1 ? 'query' : 'queries'} where another Example Store page is competing
                    </div>
                    <div className="space-y-2">
                        {state.cannibalization.map((c, i) => (
                            <div key={`${c.query}-${i}`} className="bg-[#1a0e08] border border-[#ff8a3d]/30 p-2">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-white">{c.query}</span>
                                    <span className="text-[#888888]">{c.competing_pages_count} pages • pos {c.this_page_position.toFixed(1)} ({c.this_page_impressions} impr)</span>
                                </div>
                                <div className="space-y-0.5">
                                    {c.competing_pages.map((p, j) => (
                                        <div key={j} className="text-[#888888] truncate" title={p.page_url}>
                                            <span className="text-[#666666]">→</span> {p.page_url.replace('https://www.example-store.com', '')} <span className="text-[#555555]">(pos {p.position.toFixed(1)}{p.page_type ? `, ${p.page_type}` : ''})</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
