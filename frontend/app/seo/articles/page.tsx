/**
 * SEO Articles Dashboard — /seo/articles
 *
 * Blog-article counterpart to /seo/dashboard (products + collections).
 * Lists every article with GSC + GA4 metrics, AEO enrichment status, and a
 * composite priority_score that ranks optimization opportunity.
 *
 * Backend: GET /api/v1/seo/articles
 */

'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
    seoArticlesAPI,
    aeoAPI,
    SEOArticleRow,
    SEOArticlesResponse,
    SEOArticleQuery,
    ArticleEnrichmentResult,
} from '@/lib/api';

type SortKey = 'priority' | 'impressions' | 'sessions' | 'position' | 'aeo_score';

const STORE_URL = process.env.NEXT_PUBLIC_STORE_URL || 'https://www.example-store.com';

const DRIVER_LABELS: Record<string, string> = {
    missing_tldr: 'Write TL;DR',
    missing_faqs: 'Generate FAQs',
    no_tags: 'Add tags',
    no_fault_codes: 'Add fault codes',
};

function scoreTier(score: number) {
    if (score >= 50) return { label: 'GOLD', color: '#f7b500' };
    if (score >= 25) return { label: 'SILVER', color: '#94a3b8' };
    return { label: 'BRONZE', color: '#b45309' };
}

function effortBucket(score: number) {
    if (score <= 30) return { label: 'Low', tone: 'text-[#8be78b]', bg: 'bg-[#8be78b]/10', border: 'border-[#8be78b]/30' };
    if (score <= 60) return { label: 'Medium', tone: 'text-[#f7b500]', bg: 'bg-[#f7b500]/10', border: 'border-[#f7b500]/30' };
    return { label: 'High', tone: 'text-[#ff8a3d]', bg: 'bg-[#ff8a3d]/10', border: 'border-[#ff8a3d]/30' };
}

export default function SEOArticlesDashboard() {
    const router = useRouter();
    const [data, setData] = useState<SEOArticlesResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [sortKey, setSortKey] = useState<SortKey>('priority');
    const [search, setSearch] = useState('');
    const [needsEnrichmentOnly, setNeedsEnrichmentOnly] = useState(false);
    const [minScore, setMinScore] = useState(0);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [queriesCache, setQueriesCache] = useState<Record<string, SEOArticleQuery[] | 'loading' | 'error'>>({});

    // Enrichment drawer state — reused pattern from /aeo/enrichment
    const [selected, setSelected] = useState<SEOArticleRow | null>(null);
    const [enrichResult, setEnrichResult] = useState<ArticleEnrichmentResult | null>(null);
    const [enrichLoading, setEnrichLoading] = useState(false);
    const [enrichPublishing, setEnrichPublishing] = useState(false);
    const [enrichError, setEnrichError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await seoArticlesAPI.list({ sort: sortKey, min_score: minScore });
            setData(res);
        } catch (e: any) {
            setError(e?.message || 'Failed to load articles');
        } finally {
            setLoading(false);
        }
    }, [sortKey, minScore]);

    useEffect(() => { load(); }, [load]);

    const fetchQueries = useCallback(async (articleId: string) => {
        if (queriesCache[articleId] && queriesCache[articleId] !== 'error') return;
        setQueriesCache(prev => ({ ...prev, [articleId]: 'loading' }));
        try {
            const res = await seoArticlesAPI.topQueries(articleId);
            setQueriesCache(prev => ({ ...prev, [articleId]: res.queries }));
        } catch {
            setQueriesCache(prev => ({ ...prev, [articleId]: 'error' }));
        }
    }, [queriesCache]);

    const toggleExpanded = useCallback((articleId: string) => {
        setExpandedId(prev => {
            const next = prev === articleId ? null : articleId;
            if (next) fetchQueries(next);
            return next;
        });
    }, [fetchQueries]);

    const filtered = useMemo(() => {
        if (!data) return [];
        const q = search.trim().toLowerCase();
        let rows = q
            ? data.articles.filter(a =>
                a.title.toLowerCase().includes(q) ||
                a.handle.toLowerCase().includes(q) ||
                a.tags.some(t => t.toLowerCase().includes(q)) ||
                a.fault_codes.some(c => c.toLowerCase().includes(q))
            )
            : data.articles;
        if (needsEnrichmentOnly) {
            rows = rows.filter(a => !a.enrichment.fully_enriched);
        }
        return rows;
    }, [data, search, needsEnrichmentOnly]);

    async function runEnrich(dryRun: boolean) {
        if (!selected) return;
        const id = typeof selected.article_id === 'number'
            ? selected.article_id
            : parseInt(String(selected.article_id), 10);
        if (isNaN(id)) {
            setEnrichError('Invalid article ID');
            return;
        }
        setEnrichError(null);
        if (dryRun) {
            setEnrichLoading(true);
            setEnrichResult(null);
        } else {
            setEnrichPublishing(true);
        }
        try {
            const res = await aeoAPI.enrichArticle(id, { dry_run: dryRun });
            setEnrichResult(res);
            if (!dryRun && res.written) await load();
        } catch (e: any) {
            setEnrichError(e?.message || 'Enrichment failed');
        } finally {
            setEnrichLoading(false);
            setEnrichPublishing(false);
        }
    }

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white p-8">
            <div className="max-w-7xl mx-auto">

                {/* Header */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-6 gap-4">
                    <div>
                        <h1 className="text-3xl font-semibold text-white">SEO Articles</h1>
                        <p className="text-[#888888]">Posiciones · sesiones · CTR · enriquecimiento AEO — priorizado por impacto</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Link
                            href="/seo/dashboard"
                            className="text-xs text-[#888888] hover:text-white px-3 py-1.5 border border-[#333333] hover:border-[#f7b500]"
                        >
                            ← Productos
                        </Link>
                        <button
                            onClick={load}
                            disabled={loading}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111111] border border-[#333333] hover:border-[#f7b500] text-white text-xs disabled:opacity-50"
                        >
                            <svg className={`size-3.5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Refresh
                        </button>
                    </div>
                </div>

                {/* KPI strip */}
                {data && (
                    <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-6">
                        <Kpi label="Artículos" value={data.count.toLocaleString('es-MX')} />
                        <Kpi label="Impresiones 30d" value={data.totals.impressions_30d.toLocaleString('es-MX')} />
                        <Kpi label="Clicks 30d" value={data.totals.clicks_30d.toLocaleString('es-MX')} />
                        <Kpi label="Sesiones 30d" value={data.totals.sessions_30d.toLocaleString('es-MX')} />
                        <Kpi label="Posición media" value={data.totals.avg_position ? data.totals.avg_position.toFixed(1) : '—'} />
                        <Kpi
                            label="Clicks potenciales"
                            value={`+${Math.round(data.totals.projected_clicks_potential).toLocaleString('es-MX')}`}
                            accent
                        />
                    </div>
                )}

                {/* Optimization Queue — top 10 by priority */}
                {data && (
                    <OptimizationQueueSection articles={data.articles.slice(0, 10)} />
                )}

                {/* Toolbar */}
                <div className="flex flex-wrap items-center gap-3 mb-4 mt-6">
                    <input
                        type="text"
                        placeholder="Buscar título, handle, tag o código de falla…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="flex-1 min-w-[280px] bg-[#111111] border border-[#333333] px-3 py-2 text-sm placeholder:text-[#555555] focus:border-[#f7b500] focus:outline-none"
                    />
                    <label className="flex items-center gap-2 text-xs text-[#888888] cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={needsEnrichmentOnly}
                            onChange={(e) => setNeedsEnrichmentOnly(e.target.checked)}
                            className="accent-[#f7b500]"
                        />
                        Solo sin enriquecer
                    </label>
                    <div className="flex items-center gap-2 text-xs text-[#888888]">
                        <span>Score mín:</span>
                        <select
                            value={minScore}
                            onChange={(e) => setMinScore(Number(e.target.value))}
                            className="bg-[#111111] border border-[#333333] text-white text-xs px-2 py-1.5 focus:outline-none cursor-pointer"
                        >
                            <option value={0}>Todos</option>
                            <option value={25}>≥ 25 (Silver+)</option>
                            <option value={50}>≥ 50 (Gold)</option>
                            <option value={75}>≥ 75</option>
                        </select>
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div className="bg-[#3d1a1a] border border-[#ff8a3d]/40 p-3 mb-4 text-[#ff8a3d] text-sm">
                        {error}
                    </div>
                )}

                {/* Table */}
                <div className="bg-[#111111] border border-[#333333] overflow-hidden">
                    {loading && !data ? (
                        <div className="text-center py-20 text-[#666666] text-sm">Cargando artículos…</div>
                    ) : filtered.length === 0 ? (
                        <div className="text-center py-20 text-[#666666] text-sm">Sin resultados.</div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead>
                                    <tr className="border-b-2 border-[#f7b500] bg-black/40 text-xs uppercase tracking-wide">
                                        <SortHeader label="Artículo" active={sortKey === 'priority'} onClick={() => setSortKey('priority')} />
                                        <SortHeader label="Priority" align="right" active={sortKey === 'priority'} onClick={() => setSortKey('priority')} />
                                        <SortHeader label="Pos" align="right" active={sortKey === 'position'} onClick={() => setSortKey('position')} />
                                        <SortHeader label="Impr 30d" align="right" active={sortKey === 'impressions'} onClick={() => setSortKey('impressions')} />
                                        <SortHeader label="Clicks" align="right" active={sortKey === 'priority'} onClick={() => setSortKey('priority')} />
                                        <SortHeader label="CTR" align="right" active={sortKey === 'priority'} onClick={() => setSortKey('priority')} />
                                        <SortHeader label="Sesiones" align="right" active={sortKey === 'sessions'} onClick={() => setSortKey('sessions')} />
                                        <SortHeader label="AEO" align="right" active={sortKey === 'aeo_score'} onClick={() => setSortKey('aeo_score')} />
                                        <th className="px-3 py-3 text-[#888888] font-semibold text-right">Acción</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-[#222222]">
                                    {filtered.map((a) => {
                                        const c = a.priority_components;
                                        const tier = scoreTier(a.priority_score);
                                        const isExpanded = expandedId === String(a.article_id);
                                        const ctr = a.gsc.ctr != null ? (a.gsc.ctr * 100).toFixed(2) + '%' : '—';
                                        const queriesState = queriesCache[String(a.article_id)];

                                        return (
                                            <React.Fragment key={String(a.article_id)}>
                                                <tr className="hover:bg-[#181818] transition-colors">
                                                    <td className="px-3 py-3 max-w-[380px]">
                                                        <div className="flex items-start gap-2">
                                                            <button
                                                                onClick={() => toggleExpanded(String(a.article_id))}
                                                                className="text-[#666666] hover:text-white text-xs flex-shrink-0 mt-0.5"
                                                                title="Ver queries"
                                                            >
                                                                {isExpanded ? '▾' : '▸'}
                                                            </button>
                                                            <div className="min-w-0">
                                                                <div className="font-medium text-white truncate" title={a.title}>{a.title}</div>
                                                                <div className="mt-0.5 flex items-center gap-2 text-xs text-[#666666]">
                                                                    <span className="font-mono">{a.handle}</span>
                                                                    {a.fault_codes.length > 0 && (
                                                                        <span className="text-[10px] uppercase tracking-wide text-[#f7b500]">
                                                                            {a.fault_codes.join(' · ')}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                                <div className="mt-1 flex gap-1">
                                                                    {a.enrichment.has_tldr ? (
                                                                        <span className="text-[10px] px-1.5 py-0.5 border border-[#8be78b]/40 text-[#8be78b] bg-[#8be78b]/10">TL;DR</span>
                                                                    ) : (
                                                                        <span className="text-[10px] px-1.5 py-0.5 border border-[#444] text-[#666]">no TL;DR</span>
                                                                    )}
                                                                    <span className={`text-[10px] px-1.5 py-0.5 border ${a.enrichment.faqs_count >= 3
                                                                        ? 'border-[#8be78b]/40 text-[#8be78b] bg-[#8be78b]/10'
                                                                        : 'border-[#444] text-[#666]'
                                                                        }`}>FAQ ×{a.enrichment.faqs_count}</span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="px-3 py-3 text-right">
                                                        <div className="font-mono text-base text-white">{a.priority_score.toFixed(0)}</div>
                                                        <div className="font-mono text-[10px]" style={{ color: tier.color }}>{tier.label}</div>
                                                    </td>
                                                    <td className="px-3 py-3 text-right tabular-nums">
                                                        {a.gsc.position != null ? a.gsc.position.toFixed(1) : '—'}
                                                        {c.projected_clicks.target_position > 0 && a.gsc.position != null && (
                                                            <div className="text-[10px] text-[#888888]">→ {c.projected_clicks.target_position}</div>
                                                        )}
                                                    </td>
                                                    <td className="px-3 py-3 text-right tabular-nums">
                                                        {a.gsc.impressions.toLocaleString('es-MX')}
                                                    </td>
                                                    <td className="px-3 py-3 text-right tabular-nums">
                                                        {a.gsc.clicks.toLocaleString('es-MX')}
                                                        {c.projected_clicks.value > 0 && (
                                                            <div className="text-[10px] text-[#f7b500]">+{Math.round(c.projected_clicks.value)}</div>
                                                        )}
                                                    </td>
                                                    <td className="px-3 py-3 text-right tabular-nums">{ctr}</td>
                                                    <td className="px-3 py-3 text-right tabular-nums">
                                                        {a.ga4.sessions.toLocaleString('es-MX')}
                                                    </td>
                                                    <td className="px-3 py-3 text-right">
                                                        <AEOBadge score={a.aeo_score} />
                                                    </td>
                                                    <td className="px-3 py-3 text-right">
                                                        <div className="flex items-center gap-1 justify-end">
                                                            <a
                                                                href={`${STORE_URL}${a.url}`}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="text-[#666666] hover:text-white text-xs px-2 py-1"
                                                                title="Ver en tienda"
                                                            >
                                                                ↗
                                                            </a>
                                                            <button
                                                                onClick={() => { setSelected(a); setEnrichResult(null); setEnrichError(null); }}
                                                                className="bg-[#f7b500] hover:bg-[#ffc928] text-black text-xs font-medium px-3 py-1.5"
                                                            >
                                                                Enriquecer
                                                            </button>
                                                        </div>
                                                    </td>
                                                </tr>
                                                {isExpanded && (
                                                    <tr className="bg-[#0d0d0d]">
                                                        <td colSpan={9} className="px-3 py-4">
                                                            <ExpandedRow
                                                                article={a}
                                                                queries={queriesState}
                                                            />
                                                        </td>
                                                    </tr>
                                                )}
                                            </React.Fragment>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Enrichment drawer */}
                {selected && (
                    <EnrichmentDrawer
                        article={selected}
                        result={enrichResult}
                        loading={enrichLoading}
                        publishing={enrichPublishing}
                        error={enrichError}
                        onClose={() => setSelected(null)}
                        onDryRun={() => runEnrich(true)}
                        onPublish={() => runEnrich(false)}
                    />
                )}
            </div>
        </div>
    );
}

// ============================================================================
// Sub-components
// ============================================================================

function Kpi({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
        <div className={`bg-[#111111] border ${accent ? 'border-[#f7b500]/40' : 'border-[#222222]'} px-3 py-2.5`}>
            <div className="text-[10px] uppercase tracking-wide text-[#666666]">{label}</div>
            <div className={`mt-0.5 text-base font-semibold tabular-nums ${accent ? 'text-[#f7b500]' : 'text-white'}`}>{value}</div>
        </div>
    );
}

function AEOBadge({ score }: { score: number }) {
    const tone = score >= 80
        ? 'bg-[#8be78b]/15 text-[#8be78b] border-[#8be78b]/40'
        : score >= 50
            ? 'bg-[#f7b500]/15 text-[#f7b500] border-[#f7b500]/40'
            : 'bg-[#ff8a3d]/15 text-[#ff8a3d] border-[#ff8a3d]/40';
    return (
        <span className={`inline-flex items-center px-2 py-0.5 text-xs font-bold tabular-nums border ${tone}`}>
            {score}
        </span>
    );
}

function SortHeader({
    label,
    align = 'left',
    active,
    onClick,
}: {
    label: string;
    align?: 'left' | 'right';
    active: boolean;
    onClick: () => void;
}) {
    return (
        <th
            className={`px-3 py-3 text-[#888888] font-semibold cursor-pointer select-none hover:text-[#f7b500] ${align === 'right' ? 'text-right' : ''} ${active ? 'text-[#f7b500]' : ''}`}
            onClick={onClick}
        >
            {label} {active && <span className="ml-0.5">↓</span>}
        </th>
    );
}

function OptimizationQueueSection({ articles }: { articles: SEOArticleRow[] }) {
    const totalProjected = articles.reduce((acc, a) => acc + a.priority_components.projected_clicks.value, 0);
    return (
        <div className="bg-[#111111] border border-[#f7b500]/30 p-5 mb-2">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-lg font-semibold text-white">Optimization Queue</h3>
                    <p className="text-[#666666] text-sm">
                        Top {articles.length} artículos por priority score • +{Math.round(totalProjected).toLocaleString('es-MX')} clicks potenciales
                    </p>
                </div>
            </div>
            <div className="divide-y divide-[#222222]">
                {articles.map((a, idx) => {
                    const c = a.priority_components;
                    const tier = scoreTier(a.priority_score);
                    const effort = effortBucket(c.effort_estimate.score);
                    return (
                        <div key={String(a.article_id)} className="py-2.5 flex items-center gap-4">
                            <div className="flex-shrink-0 w-12 text-center">
                                <div className="text-[#555555] text-xs">#{idx + 1}</div>
                                <div className="font-mono text-[10px]" style={{ color: tier.color }}>{tier.label}</div>
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-white text-sm font-medium truncate" title={a.title}>{a.title}</div>
                                <div className="text-[#666666] text-xs">
                                    Pos {c.projected_clicks.current_position.toFixed(1)}{c.projected_clicks.target_position > 0 ? ` → ${c.projected_clicks.target_position}` : ''} • {a.gsc.impressions.toLocaleString('es-MX')} impr • AEO {a.aeo_score}
                                </div>
                            </div>
                            <div className="hidden md:block text-right w-24">
                                <div className="text-[#f7b500] text-sm font-semibold">+{Math.round(c.projected_clicks.value)}</div>
                                <div className="text-[#666666] text-xs">clicks</div>
                            </div>
                            <div className={`hidden md:flex flex-col items-center px-2 py-1 border ${effort.border} ${effort.bg} text-xs`}>
                                <span className={`font-medium ${effort.tone}`}>{effort.label}</span>
                            </div>
                            <div className="w-14 text-right">
                                <div className="text-white font-mono text-base">{a.priority_score.toFixed(0)}</div>
                                <div className="text-[#666666] text-xs">/ 100</div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function ExpandedRow({
    article,
    queries,
}: {
    article: SEOArticleRow;
    queries: SEOArticleQuery[] | 'loading' | 'error' | undefined;
}) {
    const c = article.priority_components;
    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 text-xs">
            {/* Score breakdown */}
            <div className="lg:col-span-1 space-y-1.5">
                <div className="text-[#888888] uppercase tracking-wide text-[10px] mb-2">Priority breakdown</div>
                <ComponentRow label="Projected clicks" value={c.projected_clicks.normalized} weight={40} note={`+${Math.round(c.projected_clicks.value)} @ pos ${c.projected_clicks.target_position}`} />
                <ComponentRow label="Enrichment gap" value={c.enrichment_gap.value} weight={20} note={`AEO ${c.enrichment_gap.aeo_score} / 100`} />
                <ComponentRow label="Engagement" value={c.engagement_quality.value} weight={15} note={`${c.engagement_quality.avg_duration_s}s avg • ${c.engagement_quality.bounce_rate != null ? `${(c.engagement_quality.bounce_rate * 100).toFixed(0)}% bounce` : 'no bounce'}`} />
                <ComponentRow label="Traffic" value={c.traffic_potential.value} weight={15} note={`${c.traffic_potential.ga4_sessions} sesiones`} />
                <ComponentRow label="Confidence" value={c.confidence.value} weight={10} note={`${c.confidence.gsc_impressions} impr / ${c.confidence.ga4_sessions} sess`} />
                <ComponentRow label="Effort (penalty)" value={c.effort_estimate.score} weight={-5} note={c.effort_estimate.drivers.length ? c.effort_estimate.drivers.map(d => DRIVER_LABELS[d] || d).join(' • ') : 'no work needed'} />
            </div>

            {/* Top queries */}
            <div className="lg:col-span-2">
                <div className="text-[#888888] uppercase tracking-wide text-[10px] mb-2">Top queries (CTR gap, 90 días)</div>
                {queries === 'loading' && <div className="text-[#666666] italic">Cargando queries…</div>}
                {queries === 'error' && <div className="text-[#ff8a3d]">No se pudieron cargar las queries.</div>}
                {Array.isArray(queries) && queries.length === 0 && (
                    <div className="text-[#555555] italic">No hay queries reportadas por GSC para este artículo.</div>
                )}
                {Array.isArray(queries) && queries.length > 0 && (
                    <div className="space-y-1">
                        {queries.slice(0, 12).map((q, i) => {
                            const gapPercent = q.ctr_gap !== null ? q.ctr_gap * 100 : null;
                            const gapColor = gapPercent !== null && gapPercent < -1 ? 'text-[#ff8a3d]' : 'text-[#888888]';
                            return (
                                <div key={`${q.query}-${i}`} className="flex items-center gap-2 py-1 border-b border-[#1a1a1a]">
                                    <span className="text-white truncate flex-1" title={q.query}>{q.query}</span>
                                    <span className="text-[#666666] w-12 text-right">pos {q.position.toFixed(1)}</span>
                                    <span className="text-[#888888] w-16 text-right">{q.impressions.toLocaleString('es-MX')} impr</span>
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
                )}
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
            <div className="text-[#555555] mb-1">w: {weight > 0 ? `+${weight}%` : `${weight}%`} • {contribution >= 0 ? '+' : ''}{contribution.toFixed(1)}</div>
            <div className="text-[#666666] truncate" title={note}>{note}</div>
        </div>
    );
}

function EnrichmentDrawer({
    article,
    result,
    loading,
    publishing,
    error,
    onClose,
    onDryRun,
    onPublish,
}: {
    article: SEOArticleRow;
    result: ArticleEnrichmentResult | null;
    loading: boolean;
    publishing: boolean;
    error: string | null;
    onClose: () => void;
    onDryRun: () => void;
    onPublish: () => void;
}) {
    const tone = (c: number) =>
        c >= 0.9 ? 'bg-[#8be78b]/15 text-[#8be78b] border-[#8be78b]/40'
            : c >= 0.7 ? 'bg-[#f7b500]/15 text-[#f7b500] border-[#f7b500]/40'
                : 'bg-[#ff8a3d]/15 text-[#ff8a3d] border-[#ff8a3d]/40';

    return (
        <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-[#111111] border-l border-[#333333] shadow-2xl overflow-y-auto z-50">
            <div className="sticky top-0 bg-[#111111] border-b border-[#333333] px-5 py-4 flex items-start justify-between gap-4">
                <div className="min-w-0">
                    <p className="text-xs text-[#666666] mb-0.5">#{article.article_id} • priority {article.priority_score.toFixed(0)}</p>
                    <h2 className="font-semibold text-white line-clamp-2">{article.title}</h2>
                </div>
                <button onClick={onClose} className="flex-none w-8 h-8 text-[#666666] hover:text-[#f7b500] text-xl leading-none">×</button>
            </div>

            <div className="p-5 space-y-5">
                <div className="grid grid-cols-2 gap-2 text-xs">
                    <Stat label="Priority Score" value={article.priority_score.toFixed(0)} />
                    <Stat label="AEO Score" value={article.aeo_score.toString()} />
                    <Stat label="Sesiones (30d)" value={article.ga4.sessions.toLocaleString('es-MX')} />
                    <Stat label="Impresiones (30d)" value={article.gsc.impressions.toLocaleString('es-MX')} />
                    <Stat label="Posición media" value={article.gsc.position != null ? article.gsc.position.toFixed(1) : '—'} />
                    <Stat label="Clicks potenciales" value={`+${Math.round(article.priority_components.projected_clicks.value)}`} />
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={onDryRun}
                        disabled={loading || publishing}
                        className="flex-1 px-4 py-2 bg-white text-black text-xs font-bold hover:bg-[#eeeeee] disabled:opacity-50"
                    >
                        {loading ? 'Generando…' : 'Generar (Dry Run)'}
                    </button>
                    <button
                        onClick={onPublish}
                        disabled={!result || loading || publishing || (result?.confidence ?? 0) < 0.7}
                        title={!result ? 'Primero corre un dry run' : (result.confidence < 0.7 ? 'Confidence < 0.7' : '')}
                        className="flex-1 px-4 py-2 bg-[#f7b500] text-black text-xs font-bold hover:bg-[#ffc928] disabled:opacity-50"
                    >
                        {publishing ? 'Publicando…' : 'Publicar a Shopify'}
                    </button>
                </div>

                {error && <div className="text-xs text-[#ff8a3d] bg-[#3d1a1a] border border-[#ff8a3d]/40 px-3 py-2">{error}</div>}

                {result && (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-[#888888] uppercase tracking-wide">Resultado</span>
                            <span className={`px-2 py-0.5 text-xs font-bold border ${tone(result.confidence)}`}>
                                Confidence {(result.confidence * 100).toFixed(0)}%
                            </span>
                        </div>

                        {result.written && (
                            <div className="text-xs bg-[#8be78b]/10 border border-[#8be78b]/40 text-[#8be78b] px-3 py-2">
                                Metafields publicados a Shopify.
                            </div>
                        )}
                        {result.skip_reason && !result.written && (
                            <div className="text-xs bg-[#f7b500]/10 border border-[#f7b500]/40 text-[#f7b500] px-3 py-2">
                                No se publicó — {result.skip_reason}
                            </div>
                        )}

                        <div className="border border-[#333333] p-3 bg-[#0a0a0a]">
                            <div className="text-[10px] uppercase tracking-wide text-[#666666] mb-1">
                                TL;DR ({result.tldr_summary.length} chars)
                            </div>
                            <p className="text-sm text-white leading-relaxed">{result.tldr_summary}</p>
                        </div>

                        <div className="border border-[#333333] p-3 bg-[#0a0a0a]">
                            <div className="text-[10px] uppercase tracking-wide text-[#666666] mb-2">
                                FAQs ({result.faqs.length})
                            </div>
                            <ul className="space-y-2">
                                {result.faqs.map((faq, i) => (
                                    <li key={i} className="border-l-2 border-[#f7b500] pl-2">
                                        <p className="font-semibold text-white text-xs">{faq.q}</p>
                                        <p className="mt-1 text-xs text-[#888888] whitespace-pre-line line-clamp-4">{faq.a}</p>
                                    </li>
                                ))}
                            </ul>
                        </div>

                        {result.warnings.length > 0 && (
                            <div className="border border-[#f7b500]/40 bg-[#f7b500]/5 p-3">
                                <div className="text-[10px] uppercase tracking-wide text-[#f7b500] mb-1">Advertencias</div>
                                <ul className="list-disc pl-4 text-xs text-[#f7b500] space-y-0.5">
                                    {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div className="bg-[#0a0a0a] border border-[#222222] px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-[#666666]">{label}</div>
            <div className="mt-0.5 text-sm font-bold text-white tabular-nums">{value}</div>
        </div>
    );
}
