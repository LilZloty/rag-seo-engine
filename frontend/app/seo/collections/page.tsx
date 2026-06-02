'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { optimizerAPI, CollectionOptimizer } from '../../../lib/api';

// ─── Icons ───────────────────────────────────────────────────────────────────

const SearchIcon = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
);

const ChevronDown = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
);

const ChevronUp = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
    </svg>
);

const ExternalLink = () => (
    <svg className="size-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
);

const ArrowLeft = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
);

const EditIcon = () => (
    <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
    </svg>
);

// ─── Status badge ─────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
    pending:   'bg-[#333333] text-[#888888]',
    analyzed:  'bg-blue-500/20 text-blue-400',
    ready:     'bg-[#f7b500]/20 text-[#f7b500]',
    published: 'bg-green-500/20 text-green-400',
};

const StatusBadge = ({ status }: { status: string }) => (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status] || STATUS_COLORS.pending}`}>
        {status}
    </span>
);

const CompBadge = ({ comp }: { comp?: string | null }) => {
    if (!comp) return <span className="text-[#666666]">—</span>;
    const cls = comp === 'LOW' ? 'bg-green-500/20 text-green-400' :
                comp === 'HIGH' ? 'bg-red-500/20 text-red-400' :
                'bg-[#f7b500]/20 text-[#f7b500]';
    return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>{comp}</span>;
};

// ─── Queries sub-row ──────────────────────────────────────────────────────────

interface Query { query: string; impressions: number; clicks: number; ctr: number; position: number; }

const QueryRow = ({ collectionId }: { collectionId: number }) => {
    const [queries, setQueries] = useState<Query[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        optimizerAPI.getCollectionQueries(collectionId)
            .then((data: any) => setQueries((data.queries || data).slice(0, 8)))
            .catch(() => setQueries([]))
            .finally(() => setLoading(false));
    }, [collectionId]);

    if (loading) return <div className="px-6 py-4 text-[#888888] text-sm">Loading keywords…</div>;
    if (!queries.length) return <div className="px-6 py-4 text-[#666666] text-sm">No GSC query data — run Analyze first.</div>;

    return (
        <div className="px-6 py-4 bg-[#0f0f0f]">
            <p className="text-xs text-[#888888] uppercase tracking-wider mb-3">Top Search Queries</p>
            <table className="w-full text-xs">
                <thead>
                    <tr className="text-[#666666]">
                        <th className="text-left pb-2 font-medium">Query</th>
                        <th className="text-right pb-2 font-medium text-[#4285f4]">Impressions</th>
                        <th className="text-right pb-2 font-medium text-[#4285f4]">Clicks</th>
                        <th className="text-right pb-2 font-medium text-[#4285f4]">CTR</th>
                        <th className="text-right pb-2 font-medium text-[#4285f4]">Position</th>
                    </tr>
                </thead>
                <tbody>
                    {queries.map((q, i) => (
                        <tr key={q.query || `query-${i}`} className="border-t border-[#1a1a1a]">
                            <td className="py-1.5 pr-4 text-[#cccccc] font-mono">{q.query}</td>
                            <td className="py-1.5 text-right text-white font-mono">{q.impressions.toLocaleString()}</td>
                            <td className="py-1.5 text-right text-white font-mono">{q.clicks}</td>
                            <td className="py-1.5 text-right text-[#888888] font-mono">{(q.ctr * 100).toFixed(1)}%</td>
                            <td className="py-1.5 text-right font-mono">
                                <span className={q.position <= 10 ? 'text-green-400' : q.position <= 20 ? 'text-[#f7b500]' : 'text-red-400'}>
                                    {q.position.toFixed(1)}
                                </span>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

// ─── Main page ────────────────────────────────────────────────────────────────

type SortField = 'impressions' | 'sessions' | 'revenue' | 'volume' | 'position' | 'bounce_rate';

// Hoisted out of CollectionsListContent so it's a stable component reference —
// defining it inside the parent re-created the component on every render and
// destroyed any internal state.
function SortTh({
    field,
    label,
    color = '#888888',
    sortBy,
    sortDir,
    onToggle,
}: {
    field: SortField;
    label: string;
    color?: string;
    sortBy: SortField;
    sortDir: 'desc' | 'asc';
    onToggle: (field: SortField) => void;
}) {
    return (
        <th
            className="p-3 text-right font-medium cursor-pointer select-none hover:opacity-80 transition-opacity whitespace-nowrap"
            style={{ color }}
            onClick={() => onToggle(field)}
        >
            <span className="inline-flex items-center gap-1 justify-end">
                {label}
                {sortBy === field ? (sortDir === 'desc' ? <ChevronDown /> : <ChevronUp />) : null}
            </span>
        </th>
    );
}

function CollectionsListContent() {
    const searchParams = useSearchParams();
    const highlightId = searchParams.get('id') ? Number(searchParams.get('id')) : null;

    const [collections, setCollections] = useState<CollectionOptimizer[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [sortBy, setSortBy] = useState<SortField>('impressions');
    const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const [page, setPage] = useState(0);
    const highlightRef = useRef<HTMLTableRowElement | null>(null);
    const PAGE_SIZE = 25;

    useEffect(() => {
        setLoading(true);
        optimizerAPI.getCollections({ limit: 200 })
            .then(res => setCollections(res.collections))
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    // Scroll to highlighted row
    useEffect(() => {
        if (!highlightRef.current) return;
        const t = setTimeout(
            () => highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }),
            400
        );
        return () => clearTimeout(t);
    }, [loading]);

    const filtered = collections
        .filter(c => {
            if (statusFilter !== 'all' && c.status !== statusFilter) return false;
            if (search && !c.title.toLowerCase().includes(search.toLowerCase()) && !c.category.toLowerCase().includes(search.toLowerCase())) return false;
            return true;
        })
        .sort((a, b) => {
            let av = 0, bv = 0;
            if (sortBy === 'impressions')  { av = a.impressions || 0; bv = b.impressions || 0; }
            if (sortBy === 'sessions')     { av = a.ga4_sessions || 0; bv = b.ga4_sessions || 0; }
            if (sortBy === 'revenue')      { av = a.shopify_attributed_revenue || 0; bv = b.shopify_attributed_revenue || 0; }
            if (sortBy === 'volume')       { av = a.dataforseo_volume || 0; bv = b.dataforseo_volume || 0; }
            if (sortBy === 'position')     { av = a.position > 0 ? a.position : 999; bv = b.position > 0 ? b.position : 999; }
            if (sortBy === 'bounce_rate')  { av = a.ga4_bounce_rate || 0; bv = b.ga4_bounce_rate || 0; }
            return sortDir === 'desc' ? bv - av : av - bv;
        });

    const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
    const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

    const toggleSort = (field: SortField) => {
        if (sortBy === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
        else { setSortBy(field); setSortDir('desc'); }
    };

    // Summary stats
    const withShopify = collections.filter(c => (c.shopify_attributed_revenue || 0) > 0);
    const withDFS = collections.filter(c => (c.dataforseo_volume || 0) > 0);
    const totalRevenue = collections.reduce((s, c) => s + (c.shopify_attributed_revenue || 0), 0);
    const totalSessions = collections.reduce((s, c) => s + (c.ga4_sessions || 0), 0);
    const totalImpressions = collections.reduce((s, c) => s + (c.impressions || 0), 0);

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white p-6">
            <div className="max-w-[1400px] mx-auto">

                {/* Header */}
                <div className="flex items-center gap-4 mb-6">
                    <Link href="/seo/unified-dashboard" className="flex items-center gap-1 text-[#888888] hover:text-white transition-colors text-sm">
                        <ArrowLeft />
                        Dashboard
                    </Link>
                    <span className="text-[#444444]">/</span>
                    <h1 className="text-2xl font-semibold text-white">Collections SEO</h1>
                    <span className="text-[#666666] text-sm">{collections.length} collections</span>
                    <div className="ml-auto">
                        <Link
                            href="/seo/dashboard"
                            className="flex items-center gap-2 px-4 py-2 bg-[#f7b500] hover:bg-[#f7b500]/90 text-black font-semibold rounded-lg transition-colors text-sm"
                        >
                            Manage in SEO Dashboard
                            <ExternalLink />
                        </Link>
                    </div>
                </div>

                {/* Summary cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                    <div className="bg-[#1a1a1a] border border-[#4285f4]/30 rounded-lg p-4">
                        <p className="text-[#4285f4] text-xs font-semibold uppercase tracking-wider mb-1">GSC Total</p>
                        <p className="text-white text-2xl font-bold">{totalImpressions.toLocaleString()}</p>
                        <p className="text-[#666666] text-xs mt-1">impressions across all collections</p>
                    </div>
                    <div className="bg-[#1a1a1a] border border-[#ff6d00]/30 rounded-lg p-4">
                        <p className="text-[#ff6d00] text-xs font-semibold uppercase tracking-wider mb-1">GA4 Total</p>
                        <p className="text-white text-2xl font-bold">{totalSessions.toLocaleString()}</p>
                        <p className="text-[#666666] text-xs mt-1">sessions across all collections</p>
                    </div>
                    <div className="bg-[#1a1a1a] border border-[#f7b500]/30 rounded-lg p-4">
                        <p className="text-[#f7b500] text-xs font-semibold uppercase tracking-wider mb-1">Shopify Revenue</p>
                        <p className="text-white text-2xl font-bold">${totalRevenue.toLocaleString('en-MX', { maximumFractionDigits: 0 })}</p>
                        <p className="text-[#666666] text-xs mt-1">{withShopify.length} collections attributed</p>
                    </div>
                    <div className="bg-[#1a1a1a] border border-[#10b981]/30 rounded-lg p-4">
                        <p className="text-[#10b981] text-xs font-semibold uppercase tracking-wider mb-1">DataForSEO</p>
                        <p className="text-white text-2xl font-bold">{withDFS.length}</p>
                        <p className="text-[#666666] text-xs mt-1">collections with keyword data</p>
                    </div>
                </div>

                {/* Filters */}
                <div className="flex flex-wrap items-center gap-3 mb-4">
                    <div className="flex items-center gap-2 bg-[#1a1a1a] border border-[#333333] rounded-lg px-3 py-2 flex-1 min-w-[200px] max-w-xs">
                        <SearchIcon />
                        <input
                            type="text"
                            placeholder="Search collections…"
                            value={search}
                            onChange={e => { setSearch(e.target.value); setPage(0); }}
                            className="bg-transparent text-white text-sm focus:outline-none w-full placeholder-[#555555]"
                        />
                    </div>
                    <select
                        value={statusFilter}
                        onChange={e => { setStatusFilter(e.target.value); setPage(0); }}
                        className="bg-[#1a1a1a] border border-[#333333] rounded-lg px-3 py-2 text-white text-sm focus:outline-none cursor-pointer"
                    >
                        <option value="all">All statuses</option>
                        <option value="pending">Pending</option>
                        <option value="analyzed">Analyzed</option>
                        <option value="ready">Ready</option>
                        <option value="published">Published</option>
                    </select>
                    <span className="text-[#666666] text-sm ml-auto">{filtered.length} results</span>
                </div>

                {/* Table */}
                <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg overflow-hidden">
                    {loading ? (
                        <div className="p-12 text-center text-[#888888]">Loading collections…</div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-[#333333] bg-[#252525]">
                                        <th className="py-3 px-4 text-left text-[#888888] font-medium whitespace-nowrap">Collection</th>
                                        <th className="p-3 text-left text-[#888888] font-medium whitespace-nowrap">Status</th>
                                        {/* GSC */}
                                        <SortTh field="impressions" label="Impr." color="#4285f4" sortBy={sortBy} sortDir={sortDir} onToggle={toggleSort} />
                                        <SortTh field="position"    label="Pos."  color="#4285f4" sortBy={sortBy} sortDir={sortDir} onToggle={toggleSort} />
                                        {/* GA4 */}
                                        <SortTh field="sessions"    label="Sessions"   color="#ff6d00" sortBy={sortBy} sortDir={sortDir} onToggle={toggleSort} />
                                        <SortTh field="bounce_rate" label="Bounce"      color="#ff6d00" sortBy={sortBy} sortDir={sortDir} onToggle={toggleSort} />
                                        {/* Shopify */}
                                        <SortTh field="revenue" label="Revenue MXN" color="#f7b500" sortBy={sortBy} sortDir={sortDir} onToggle={toggleSort} />
                                        <th className="p-3 text-right text-[#f7b500] font-medium whitespace-nowrap">Orders</th>
                                        <th className="p-3 text-right text-[#f7b500] font-medium whitespace-nowrap">LLM Rev.</th>
                                        {/* DataForSEO */}
                                        <SortTh field="volume" label="Vol/mo" color="#10b981" sortBy={sortBy} sortDir={sortDir} onToggle={toggleSort} />
                                        <th className="p-3 text-right text-[#10b981] font-medium whitespace-nowrap">Comp.</th>
                                        <th className="p-3 text-right text-[#10b981] font-medium whitespace-nowrap">CPC</th>
                                        {/* Keywords toggle */}
                                        <th className="py-3 px-4 text-right text-[#888888] font-medium whitespace-nowrap">Keywords</th>
                                        {/* Actions */}
                                        <th className="p-3 text-center text-[#888888] font-medium whitespace-nowrap">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {paginated.length === 0 ? (
                                        <tr>
                                            <td colSpan={14} className="py-12 text-center text-[#666666]">
                                                No collections match your filters.
                                            </td>
                                        </tr>
                                    ) : paginated.map((c) => {
                                        const isHighlight = c.id === highlightId;
                                        const isExpanded = expandedId === c.id;
                                        return (
                                            <React.Fragment key={c.id}>
                                                <tr
                                                    ref={isHighlight ? highlightRef : null}
                                                    className={`border-b border-[#333333] transition-colors ${
                                                        isHighlight ? 'bg-[#f7b500]/10 border-l-2 border-l-[#f7b500]' : 'hover:bg-[#252525]'
                                                    }`}
                                                >
                                                    {/* Identity */}
                                                    <td className="py-3 px-4">
                                                        <Link href={`/seo/collections/${c.id}`} className="block group">
                                                            <p className="text-white font-medium group-hover:text-[#f7b500] transition-colors cursor-pointer">{c.title}</p>
                                                        </Link>
                                                        <p className="text-[#666666] text-xs">{c.category}</p>
                                                        {c.dataforseo_primary_keyword && (
                                                            <p className="text-[#10b981] text-xs mt-0.5">⌕ {c.dataforseo_primary_keyword}</p>
                                                        )}
                                                    </td>
                                                    <td className="p-3"><StatusBadge status={c.status} /></td>
                                                    {/* GSC */}
                                                    <td className="p-3 text-right font-mono text-white">
                                                        {(c.impressions || 0) > 0 ? c.impressions.toLocaleString() : '—'}
                                                    </td>
                                                    <td className="p-3 text-right font-mono">
                                                        {c.position > 0 ? (
                                                            <span className={c.position <= 10 ? 'text-green-400' : c.position <= 20 ? 'text-[#f7b500]' : 'text-red-400'}>
                                                                {c.position.toFixed(1)}
                                                            </span>
                                                        ) : '—'}
                                                    </td>
                                                    {/* GA4 */}
                                                    <td className="p-3 text-right font-mono text-white">
                                                        {(c.ga4_sessions || 0) > 0 ? (c.ga4_sessions || 0).toLocaleString() : '—'}
                                                    </td>
                                                    <td className="p-3 text-right font-mono">
                                                        {(c.ga4_bounce_rate || 0) > 0 ? (
                                                            <span className={(c.ga4_bounce_rate || 0) > 0.7 ? 'text-red-400' : (c.ga4_bounce_rate || 0) < 0.5 ? 'text-green-400' : 'text-[#f7b500]'}>
                                                                {((c.ga4_bounce_rate || 0) * 100).toFixed(0)}%
                                                            </span>
                                                        ) : '—'}
                                                    </td>
                                                    {/* Shopify */}
                                                    <td className="p-3 text-right font-mono">
                                                        {(c.shopify_attributed_revenue || 0) > 0 ? (
                                                            <span className="text-[#f7b500] font-semibold">
                                                                ${(c.shopify_attributed_revenue || 0).toLocaleString('en-MX', { maximumFractionDigits: 0 })}
                                                            </span>
                                                        ) : '—'}
                                                    </td>
                                                    <td className="p-3 text-right font-mono text-white">
                                                        {(c.shopify_attributed_orders || 0) > 0 ? c.shopify_attributed_orders : '—'}
                                                    </td>
                                                    <td className="p-3 text-right font-mono">
                                                        {(c.shopify_llm_revenue || 0) > 0 ? (
                                                            <span className="text-purple-400">
                                                                ${(c.shopify_llm_revenue || 0).toLocaleString('en-MX', { maximumFractionDigits: 0 })}
                                                            </span>
                                                        ) : '—'}
                                                    </td>
                                                    {/* DataForSEO */}
                                                    <td className="p-3 text-right font-mono">
                                                        {(c.dataforseo_volume || 0) > 0 ? (
                                                            <span className="text-[#10b981]">{(c.dataforseo_volume || 0).toLocaleString()}</span>
                                                        ) : '—'}
                                                    </td>
                                                    <td className="p-3 text-right">
                                                        <CompBadge comp={c.dataforseo_competition} />
                                                    </td>
                                                    <td className="p-3 text-right font-mono text-[#888888]">
                                                        {(c.dataforseo_cpc || 0) > 0 ? `$${(c.dataforseo_cpc || 0).toFixed(2)}` : '—'}
                                                    </td>
                                                    {/* Expand toggle */}
                                                    <td className="py-3 px-4 text-right">
                                                        <button
                                                            onClick={() => setExpandedId(isExpanded ? null : c.id)}
                                                            className="text-[#888888] hover:text-white transition-colors inline-flex items-center gap-1 text-xs"
                                                        >
                                                            {isExpanded ? <><ChevronUp /> Hide</> : <><ChevronDown /> Show</>}
                                                        </button>
                                                    </td>
                                                    {/* Actions */}
                                                    <td className="p-3 text-center">
                                                        <Link
                                                            href={`/seo/collections/${c.id}`}
                                                            className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#f7b500]/20 text-[#f7b500] border border-[#f7b500]/30 rounded-lg hover:bg-[#f7b500]/30 transition-colors text-xs font-medium"
                                                        >
                                                            <EditIcon />
                                                            Edit
                                                        </Link>
                                                    </td>
                                                </tr>
                                                {isExpanded && (
                                                    <tr className="border-b border-[#333333]">
                                                        <td colSpan={14} className="p-0">
                                                            {/* SERP features + competitors */}
                                                            {(c.dataforseo_serp_features?.length || c.dataforseo_top_competitor || c.dataforseo_people_also_ask?.length) ? (
                                                                <div className="px-6 py-3 bg-[#0f0f0f] border-b border-[#1a1a1a] flex flex-wrap gap-6">
                                                                    {c.dataforseo_top_competitor && (
                                                                        <div>
                                                                            <p className="text-xs text-[#666666] mb-1">Top Competitor</p>
                                                                            <p className="text-white text-sm font-mono">{c.dataforseo_top_competitor}</p>
                                                                        </div>
                                                                    )}
                                                                    {c.dataforseo_serp_features && c.dataforseo_serp_features.length > 0 && (
                                                                        <div>
                                                                            <p className="text-xs text-[#666666] mb-1">SERP Features</p>
                                                                            <div className="flex flex-wrap gap-1">
                                                                                {c.dataforseo_serp_features.map((f, i) => (
                                                                                    <span key={typeof f === 'string' ? f : `feature-${i}`} className="text-xs px-2 py-0.5 bg-[#333333] text-[#cccccc] rounded">{f}</span>
                                                                                ))}
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                    {c.dataforseo_people_also_ask && c.dataforseo_people_also_ask.length > 0 && (
                                                                        <div className="flex-1 min-w-[280px]">
                                                                            <p className="text-xs text-[#666666] mb-1">People Also Ask</p>
                                                                            <ul className="space-y-1">
                                                                                {c.dataforseo_people_also_ask.map((paa, i) => (
                                                                                    <li key={paa.question || `paa-${i}`} className="text-xs text-[#cccccc]">• {paa.question}</li>
                                                                                ))}
                                                                            </ul>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            ) : null}
                                                            <QueryRow collectionId={c.id} />
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

                {/* Pagination */}
                {totalPages > 1 && (
                    <div className="flex items-center justify-between mt-4">
                        <span className="text-[#666666] text-sm">
                            Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
                        </span>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setPage(p => Math.max(0, p - 1))}
                                disabled={page === 0}
                                className="px-3 py-1.5 bg-[#1a1a1a] border border-[#333333] rounded-lg text-sm text-white disabled:opacity-40 hover:border-[#555555] transition-colors"
                            >
                                Previous
                            </button>
                            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i).map(pageNum => (
                                <button
                                    key={`page-${pageNum}`}
                                    onClick={() => setPage(pageNum)}
                                    className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                                        page === pageNum
                                            ? 'bg-[#f7b500] text-black font-semibold'
                                            : 'bg-[#1a1a1a] border border-[#333333] text-white hover:border-[#555555]'
                                    }`}
                                >
                                    {pageNum + 1}
                                </button>
                            ))}
                            <button
                                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                                disabled={page === totalPages - 1}
                                className="px-3 py-1.5 bg-[#1a1a1a] border border-[#333333] rounded-lg text-sm text-white disabled:opacity-40 hover:border-[#555555] transition-colors"
                            >
                                Next
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

// Wrap in Suspense because useSearchParams requires it in Next.js 13+
export default function CollectionsPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-[#0a0a0a] text-white flex items-center justify-center">
                <p className="text-[#888888]">Loading…</p>
            </div>
        }>
            <CollectionsListContent />
        </Suspense>
    );
}
