'use client';

/**
 * AEO Focused Overview — the replacement for the widget-heavy default view.
 *
 * Shows ONLY data that is (a) real and (b) actionable today. Every number
 * traces back to a verifiable source (GA4 referrer logs, Shopify order
 * history, or live DB counts). Speculative widgets (visibility correlation,
 * value/mention ratios, score cards built from small samples) are reachable
 * through the other tabs but explicitly do not belong in the first view.
 *
 * Four sections, in order of actionability:
 *   1. Hero — AI referral traffic (last 30d). Factual sessions from GA4.
 *   2. Products earning from AI (last 365d). Real orders, real revenue.
 *   3. High-revenue products missing from llms.txt. Concrete opportunity list.
 *   4. Schema deployment gap. Per-category coverage + "do this next" CTA.
 */

import React from 'react';
import { formatCurrency } from './constants';
import type {
    AITrafficReport,
    ProductIntelligenceResponse,
    SchemaMetrics,
} from '@/lib/api';

interface Props {
    aiTraffic: AITrafficReport | null;
    intelligence: ProductIntelligenceResponse | null;
    schemaMetrics: SchemaMetrics | null;
    loading: boolean;
}

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

/** Extract source tag ("chatgpt", "claude", ...) from a full referrer URL. */
function domainFromReferrer(url: string): string {
    try {
        const host = new URL(url).hostname;
        if (host.includes('chatgpt')) return 'chatgpt';
        if (host.includes('claude')) return 'claude';
        if (host.includes('perplexity')) return 'perplexity';
        if (host.includes('gemini') || host.includes('bard')) return 'gemini';
        if (host.includes('copilot')) return 'copilot';
        if (host.includes('phind')) return 'phind';
        if (host.includes('you.com')) return 'you';
        if (host.includes('example-store')) return 'internal-utm';
        return host.replace(/^www\./, '');
    } catch {
        return 'unknown';
    }
}

function groupReferrers(referrers: Record<string, number> | undefined): Array<{ source: string; sessions: number }> {
    if (!referrers) return [];
    const grouped: Record<string, number> = {};
    for (const [url, count] of Object.entries(referrers)) {
        const src = domainFromReferrer(url);
        grouped[src] = (grouped[src] || 0) + (count || 0);
    }
    return Object.entries(grouped)
        .map(([source, sessions]) => ({ source, sessions }))
        .sort((a, b) => b.sessions - a.sessions);
}

const SOURCE_COLOR: Record<string, string> = {
    chatgpt: '#10A37F',
    claude: '#CC785C',
    perplexity: '#20808D',
    gemini: '#4285F4',
    copilot: '#0078D4',
    phind: '#6366F1',
    you: '#EC4899',
    'internal-utm': '#6B7280',
};

// ────────────────────────────────────────────────────────────────────────────
// Sub-components
// ────────────────────────────────────────────────────────────────────────────

const SectionHeader: React.FC<{ title: string; subtitle?: string; badge?: string }> = ({ title, subtitle, badge }) => (
    <div className="mb-3 flex items-start justify-between gap-3">
        <div>
            <h3 className="text-sm font-semibold text-white">{title}</h3>
            {subtitle && <p className="text-xs text-zinc-500 mt-0.5">{subtitle}</p>}
        </div>
        {badge && (
            <span className="shrink-0 text-[10px] uppercase tracking-wider text-zinc-500 border border-[#3a3a3a] rounded-sm px-2 py-0.5">
                {badge}
            </span>
        )}
    </div>
);

const EmptyState: React.FC<{ message: string }> = ({ message }) => (
    <div className="bg-[#0f0f0f] border border-dashed border-[#3a3a3a] rounded-sm p-6 text-center">
        <p className="text-sm text-zinc-500">{message}</p>
    </div>
);

// ─────── 1. AI Traffic Hero ─────────
const AITrafficHero: React.FC<{ data: AITrafficReport | null }> = ({ data }) => {
    const summary = data?.summary;
    const referrers = (data?.raw_data as any)?.ai_referrals
        ? ((data?.raw_data as any).ai_referrals as Array<{ referrer: string; sessions: number }>)
            .reduce<Record<string, number>>((acc, r) => {
                acc[r.referrer] = (acc[r.referrer] || 0) + (r.sessions || 0);
                return acc;
            }, {})
        : undefined;
    const sources = groupReferrers(referrers);
    const total = summary?.ai_sessions || 0;

    return (
        <div className="bg-gradient-to-br from-[#1a1a1a] to-[#0f0f0f] border border-[#3a3a3a] rounded-sm p-6">
            <div className="flex items-start justify-between gap-6 flex-wrap">
                <div>
                    <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">AI referral sessions (last 30 days)</p>
                    <p className="text-5xl font-bold text-[#F7B500]">{total.toLocaleString()}</p>
                    <p className="text-xs text-zinc-500 mt-2">
                        From GA4 — direct evidence of customers arriving via ChatGPT, Claude, Perplexity, etc.
                        Mobile/app traffic not captured, so the real number is likely 2-3× higher.
                    </p>
                </div>

                {sources.length > 0 && (
                    <div className="flex-1 min-w-[240px] space-y-1.5">
                        {sources.slice(0, 6).map(({ source, sessions }) => {
                            const pct = total > 0 ? Math.round((sessions / total) * 100) : 0;
                            const color = SOURCE_COLOR[source] || '#F7B500';
                            return (
                                <div key={source} className="flex items-center gap-2 text-xs">
                                    <span className="w-20 text-zinc-400 capitalize">{source}</span>
                                    <div className="flex-1 h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
                                        <div className="h-full" style={{ width: `${pct}%`, backgroundColor: color }} />
                                    </div>
                                    <span className="w-14 text-right font-mono text-white">{sessions.toLocaleString()}</span>
                                    <span className="w-10 text-right text-zinc-500">{pct}%</span>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

// ─────── 2. Products earning from AI ─────────
const ProductsEarningFromAI: React.FC<{ intelligence: ProductIntelligenceResponse | null }> = ({ intelligence }) => {
    const products = intelligence?.products_from_llm || [];
    const totalRevenue = products.reduce((acc, p) => acc + (p.revenue_from_llm || 0), 0);
    const totalOrders = products.reduce((acc, p) => acc + (p.orders_from_llm || 0), 0);

    return (
        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5">
            <SectionHeader
                title={`Products earning from AI (${products.length} products)`}
                subtitle={`${totalOrders} orders, ${formatCurrency(totalRevenue)} revenue attributed to AI sources — last 365 days`}
                badge="From GA4 + Shopify"
            />

            {products.length === 0 ? (
                <EmptyState message="No AI-attributed orders yet — wait for GA4 to populate, or check if your GA4 integration is wired up." />
            ) : (
                <div className="border border-[#2a2a2a] rounded-sm overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                            <thead className="bg-[#0f0f0f] border-b border-[#2a2a2a]">
                                <tr className="text-zinc-500 text-left">
                                    <th className="px-3 py-2 font-medium">Product</th>
                                    <th className="px-3 py-2 font-medium text-right">Orders</th>
                                    <th className="px-3 py-2 font-medium text-right">Revenue</th>
                                    <th className="px-3 py-2 font-medium">Source</th>
                                    <th className="px-3 py-2 font-medium text-center">In llms.txt?</th>
                                </tr>
                            </thead>
                            <tbody>
                                {products.slice(0, 15).map((p: any) => {
                                    const inLlms = p.content_attributes?.in_llms_txt;
                                    const src = (p.sources || [])[0] || 'unknown';
                                    return (
                                        <tr key={p.shopify_id} className="border-b border-[#2a2a2a] last:border-0 hover:bg-[#0f0f0f]/60">
                                            <td className="px-3 py-2 text-white max-w-sm truncate" title={p.title}>
                                                {p.title}
                                                <div className="text-[10px] text-zinc-600 font-mono">{p.sku}</div>
                                            </td>
                                            <td className="px-3 py-2 text-right font-mono text-white">{p.orders_from_llm}</td>
                                            <td className="px-3 py-2 text-right font-mono text-[#F7B500] font-medium">
                                                {formatCurrency(p.revenue_from_llm || 0)}
                                            </td>
                                            <td className="px-3 py-2">
                                                <span
                                                    className="inline-block px-1.5 py-0.5 rounded-sm text-[10px] font-medium capitalize"
                                                    style={{
                                                        backgroundColor: (SOURCE_COLOR[src] || '#F7B500') + '20',
                                                        color: SOURCE_COLOR[src] || '#F7B500',
                                                    }}
                                                >
                                                    {src}
                                                </span>
                                            </td>
                                            <td className="px-3 py-2 text-center">
                                                {inLlms ? (
                                                    <span className="text-green-500" title="In llms.txt">✓</span>
                                                ) : (
                                                    <span className="text-yellow-500" title="Not yet in llms.txt — consider adding">—</span>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    {products.length > 15 && (
                        <div className="px-3 py-2 bg-[#0f0f0f] text-[10px] text-zinc-500 border-t border-[#2a2a2a]">
                            Showing top 15 by revenue — {products.length - 15} more products also converting from AI
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

// ─────── 3. Opportunity list ─────────
const OptimizationOpportunities: React.FC<{ intelligence: ProductIntelligenceResponse | null }> = ({ intelligence }) => {
    const opps = intelligence?.optimization_opportunities || [];
    const missingCount = opps.filter((o: any) => (o.issues || []).includes('Not in llms.txt')).length;

    return (
        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5">
            <SectionHeader
                title="High-revenue products missing from llms.txt"
                subtitle={`${missingCount} top-selling products AIs currently can't see — each one is a concrete add-to-llms.txt opportunity.`}
                badge="From Shopify"
            />

            {opps.length === 0 ? (
                <EmptyState message="No gaps — every top-seller is already in llms.txt." />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {opps.slice(0, 10).map((o: any) => {
                        const issues: string[] = o.issues || [];
                        const hasShortDesc = issues.includes('Short description');
                        return (
                            <div key={o.shopify_id} className="bg-[#0f0f0f] border border-[#2a2a2a] rounded-sm p-3">
                                <div className="flex items-start justify-between gap-2 mb-1.5">
                                    <p className="text-xs text-white leading-tight line-clamp-2" title={o.title}>{o.title}</p>
                                    <span className="shrink-0 font-mono text-[#F7B500] text-xs font-bold">
                                        {formatCurrency(o.total_revenue)}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                                    <span className="font-mono">{o.sku}</span>
                                    <span>•</span>
                                    <span>{o.total_sold} units sold</span>
                                </div>
                                <div className="flex gap-1 mt-2 flex-wrap">
                                    {issues.map((issue) => (
                                        <span
                                            key={issue}
                                            className={`text-[10px] px-1.5 py-0.5 rounded-sm ${
                                                issue === 'Not in llms.txt'
                                                    ? 'bg-yellow-900/30 text-yellow-400 border border-yellow-700/30'
                                                    : 'bg-blue-900/30 text-blue-400 border border-blue-700/30'
                                            }`}
                                        >
                                            {issue}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

// ─────── 4. Schema deployment gap ─────────
const SchemaGap: React.FC<{ metrics: SchemaMetrics | null }> = ({ metrics }) => {
    const m = metrics as any;
    if (!m) return null;

    const rows = [
        {
            label: 'FAQ schema',
            deployed: m.faq_schemas_deployed ?? 0,
            eligible: m.faq_total_eligible ?? 0,
            pct: m.faq_coverage_pct ?? 0,
            note: 'On fault-code pages — biggest Google rich-result opportunity.',
        },
        {
            label: 'HowTo schema',
            deployed: m.howto_schemas_deployed ?? 0,
            eligible: m.howto_total_eligible ?? 0,
            pct: m.howto_coverage_pct ?? 0,
            note: 'On diagnostic articles — helps AI engines cite specific repair steps.',
        },
        {
            label: 'VehiclePart schema',
            deployed: m.vehiclepart_schemas_deployed ?? 0,
            eligible: m.vehiclepart_total_eligible ?? 0,
            pct: m.vehiclepart_coverage_pct ?? 0,
            note: 'Products with a transmission_code set (schema-eligible proxy, not deployment verified).',
        },
    ];

    return (
        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5">
            <SectionHeader
                title="Schema deployment gap"
                subtitle="Where structured data is missing — filling these lifts both Google snippets and AI citation accuracy."
                badge="Live DB counts"
            />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {rows.map((r) => {
                    const pct = r.pct ?? 0;
                    const isZero = r.deployed === 0 && r.eligible > 0;
                    return (
                        <div
                            key={r.label}
                            className={`bg-[#0f0f0f] border rounded-sm p-3 ${
                                isZero ? 'border-yellow-700/40' : 'border-[#2a2a2a]'
                            }`}
                        >
                            <div className="flex items-baseline justify-between mb-1">
                                <span className="text-xs text-zinc-400">{r.label}</span>
                                <span className={`text-xs font-mono ${isZero ? 'text-yellow-400' : 'text-white'}`}>
                                    {r.deployed} / {r.eligible}
                                </span>
                            </div>
                            <div className="flex items-baseline gap-1 mb-2">
                                <span className={`text-2xl font-bold ${isZero ? 'text-yellow-400' : 'text-[#F7B500]'}`}>
                                    {pct.toFixed(1)}%
                                </span>
                                {isZero && (
                                    <span className="text-[10px] text-yellow-500/80 uppercase tracking-wider">not deployed</span>
                                )}
                            </div>
                            <div className="h-1 bg-[#2a2a2a] rounded-full overflow-hidden mb-2">
                                <div
                                    className="h-full"
                                    style={{
                                        width: `${Math.min(pct, 100)}%`,
                                        backgroundColor: isZero ? '#EAB308' : '#F7B500',
                                    }}
                                />
                            </div>
                            <p className="text-[10px] text-zinc-600 leading-relaxed">{r.note}</p>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

// ────────────────────────────────────────────────────────────────────────────
// Main
// ────────────────────────────────────────────────────────────────────────────

export const AEOFocusedOverview: React.FC<Props> = ({ aiTraffic, intelligence, schemaMetrics, loading }) => {
    if (loading) {
        return (
            <div className="space-y-4">
                {[1, 2, 3, 4].map((n) => (
                    <div key={`skel-${n}`} className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-6 animate-pulse h-32" />
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Framing note — tells the viewer what they're looking at. The rest
                of the AEO tabs are exploratory; this view is only grounded data. */}
            <div className="text-xs text-zinc-500 leading-relaxed bg-[#1a1a1a]/60 border border-[#2a2a2a] rounded-sm px-4 py-3">
                Each section below is direct evidence — AI traffic from GA4, sales from Shopify, schema counts from the live DB.
                No visibility scores, no correlation ratios, no small-sample percentages. For speculative/exploratory views,
                use the other tabs.
            </div>

            <AITrafficHero data={aiTraffic} />
            <ProductsEarningFromAI intelligence={intelligence} />
            <OptimizationOpportunities intelligence={intelligence} />
            <SchemaGap metrics={schemaMetrics} />
        </div>
    );
};
