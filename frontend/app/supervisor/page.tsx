/**
 * Supervisor News Feed — phase 1 of the supervisor agent.
 *
 * Reads from /api/v1/supervisor/news and shows summarized SEO/AEO/GEO news
 * items grouped by tag. The reasoning loop (phase 3+) will land later;
 * for now this is the substrate Theo can already use to stay current.
 */
'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

interface NewsItem {
    id: number;
    source: string;
    title: string;
    url: string;
    summary_bullets: string[];
    tag: string | null;
    relevance: 'high' | 'medium' | 'low' | 'skip' | null;
    published_at: string | null;
    fetched_at: string | null;
}

interface NewsFeed {
    items: NewsItem[];
    total: number;
    page: number;
    page_size: number;
    by_tag: Record<string, number>;
}

interface SupervisorHealth {
    status: string;
    sources_count: number;
    news_items_count: number;
    summarized_count: number;
    last_ingest_at: string | null;
    last_run_status: string | null;
    summarizer_provider: string;
    summarizer_configured: boolean;
}

const TAG_COLORS: Record<string, string> = {
    algo: 'danger',
    aeo: 'brand',
    geo: 'info',
    tooling: 'default',
    policy: 'warning',
    market: 'success',
    other: 'outline',
};

const TAG_LABELS: Record<string, string> = {
    algo: 'Algoritmo',
    aeo: 'AEO',
    geo: 'GEO',
    tooling: 'Plataformas',
    policy: 'Políticas',
    market: 'Mercado MX',
    other: 'Otro',
};

const RELEVANCE_LABELS: Record<string, string> = {
    high: 'Alta',
    medium: 'Media',
    low: 'Baja',
    skip: 'Descartar',
};

function formatDate(iso: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
}

function timeSince(iso: string | null): string {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const hours = Math.floor(diff / 3_600_000);
    if (hours < 1) return 'hace minutos';
    if (hours < 24) return `hace ${hours}h`;
    const days = Math.floor(hours / 24);
    return `hace ${days}d`;
}

export default function SupervisorNewsPage() {
    const [feed, setFeed] = useState<NewsFeed | null>(null);
    const [health, setHealth] = useState<SupervisorHealth | null>(null);
    const [tag, setTag] = useState<string | null>(null);
    const [includeSkipped, setIncludeSkipped] = useState(false);
    const [days, setDays] = useState(14);
    const [loading, setLoading] = useState(false);
    const [ingesting, setIngesting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadFeed = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            params.set('days', String(days));
            params.set('page_size', '100');
            if (tag) params.set('tag', tag);
            const r = await fetch(`${API_BASE}/supervisor/news?${params}`);
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const data = (await r.json()) as NewsFeed;
            setFeed(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setLoading(false);
        }
    }, [tag, days]);

    const loadHealth = useCallback(async () => {
        try {
            const r = await fetch(`${API_BASE}/supervisor/health`);
            if (r.ok) setHealth((await r.json()) as SupervisorHealth);
        } catch {
            // health is best-effort
        }
    }, []);

    useEffect(() => {
        loadFeed();
        loadHealth();
    }, [loadFeed, loadHealth]);

    const triggerIngest = async () => {
        setIngesting(true);
        setError(null);
        try {
            const r = await fetch(`${API_BASE}/supervisor/news/ingest?summarize=true`, { method: 'POST' });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            await r.json();
            await loadFeed();
            await loadHealth();
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setIngesting(false);
        }
    };

    const visibleItems = useMemo(() => {
        if (!feed) return [];
        return includeSkipped
            ? feed.items
            : feed.items.filter((i) => i.relevance !== 'skip');
    }, [feed, includeSkipped]);

    const tagCounts = feed?.by_tag ?? {};
    const totalSignal = Object.values(tagCounts).reduce((a, b) => a + b, 0);

    return (
        <div className="min-h-screen bg-v07-bg text-white">
            {/* Header */}
            <div className="border-b border-[#1f1f1f] bg-v07-header">
                <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between flex-wrap gap-3">
                    <div>
                        <div className="text-v07-text-muted text-xs tracking-widest uppercase mb-1">
                            <Link href="/" className="hover:text-v07-yellow transition-colors">Inicio</Link>
                            <span className="mx-2">/</span>
                            Supervisor
                        </div>
                        <h1 className="text-2xl font-display tracking-wide">Supervisor — Noticias SEO/AEO/GEO</h1>
                        <p className="text-v07-text-muted text-sm mt-1">
                            Resumen automático de cambios en algoritmos, plataformas y mercado.
                            Última actualización: {timeSince(health?.last_ingest_at ?? null)}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button onClick={triggerIngest} disabled={ingesting} variant="primary">
                            {ingesting ? 'Ingiriendo…' : 'Refrescar ahora'}
                        </Button>
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto p-6 space-y-6">
                {/* Health strip */}
                {health && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <HealthStat label="Fuentes" value={health.sources_count} />
                        <HealthStat label="Items totales" value={health.news_items_count} />
                        <HealthStat
                            label="Resumidos"
                            value={`${health.summarized_count} / ${health.news_items_count}`}
                        />
                        <HealthStat
                            label="Estado"
                            value={health.status}
                            tone={health.status === 'ok' ? 'good' : 'warn'}
                        />
                    </div>
                )}

                {error && (
                    <Card className="border-red-500/30">
                        <div className="text-red-400 text-sm">Error: {error}</div>
                    </Card>
                )}

                {/* Filter row */}
                <Card>
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="text-v07-text-muted text-xs uppercase tracking-widest mr-2">Filtrar:</span>
                        <FilterChip label={`Todas (${totalSignal})`} active={tag === null} onClick={() => setTag(null)} />
                        {Object.entries(tagCounts).map(([t, c]) => (
                            <FilterChip
                                key={t}
                                label={`${TAG_LABELS[t] ?? t} (${c})`}
                                active={tag === t}
                                onClick={() => setTag(tag === t ? null : t)}
                            />
                        ))}
                        <div className="ml-auto flex items-center gap-3 text-xs">
                            <label className="flex items-center gap-2 text-v07-text-muted cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={includeSkipped}
                                    onChange={(e) => setIncludeSkipped(e.target.checked)}
                                    className="accent-v07-yellow"
                                />
                                Incluir descartados
                            </label>
                            <select
                                value={days}
                                onChange={(e) => setDays(Number(e.target.value))}
                                className="bg-v07-card border border-[#3a3a3a] text-white text-xs px-2 py-1 rounded-sm"
                            >
                                <option value={3}>3 días</option>
                                <option value={7}>7 días</option>
                                <option value={14}>14 días</option>
                                <option value={30}>30 días</option>
                            </select>
                        </div>
                    </div>
                </Card>

                {/* Feed */}
                {loading && !feed ? (
                    <div className="text-v07-text-muted py-12 text-center">Cargando…</div>
                ) : visibleItems.length === 0 ? (
                    <Card>
                        <div className="text-center py-10">
                            <div className="text-v07-text-muted text-sm">
                                Aún no hay noticias en este rango.
                            </div>
                            <div className="text-v07-text-subtle text-xs mt-2">
                                Si nunca corriste la ingesta, presiona <span className="text-v07-yellow">Refrescar ahora</span>.
                            </div>
                        </div>
                    </Card>
                ) : (
                    <div className="space-y-3">
                        {visibleItems.map((item) => (
                            <NewsCard key={item.id} item={item} />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────
// Subcomponents
// ─────────────────────────────────────────────

function HealthStat({
    label,
    value,
    tone = 'neutral',
}: {
    label: string;
    value: string | number;
    tone?: 'good' | 'warn' | 'neutral';
}) {
    const toneClass =
        tone === 'good'
            ? 'text-green-400'
            : tone === 'warn'
              ? 'text-yellow-400'
              : 'text-white';
    return (
        <div className="bg-v07-card border border-[#1f1f1f] px-4 py-3 rounded-sm">
            <div className="text-v07-text-subtle text-[10px] uppercase tracking-widest">{label}</div>
            <div className={`text-lg font-display mt-1 ${toneClass}`}>{value}</div>
        </div>
    );
}

function FilterChip({
    label,
    active,
    onClick,
}: {
    label: string;
    active: boolean;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className={`text-xs px-3 py-1 rounded-sm border transition-colors ${
                active
                    ? 'bg-v07-yellow text-black border-v07-yellow'
                    : 'bg-v07-card text-v07-text-muted border-[#3a3a3a] hover:border-v07-yellow hover:text-white'
            }`}
        >
            {label}
        </button>
    );
}

function NewsCard({ item }: { item: NewsItem }) {
    const tagVariant = (TAG_COLORS[item.tag ?? 'other'] ?? 'default') as
        | 'default'
        | 'success'
        | 'warning'
        | 'danger'
        | 'info'
        | 'brand'
        | 'outline';
    const isLowSignal = item.relevance === 'skip' || item.relevance === 'low';

    return (
        <Card className={isLowSignal ? 'opacity-60' : ''}>
            <div className="flex items-start gap-4 flex-col md:flex-row">
                <div className="flex-shrink-0 w-full md:w-44 text-xs">
                    <div className="text-v07-text-muted">{item.source}</div>
                    <div className="text-v07-text-subtle">{formatDate(item.published_at)}</div>
                    <div className="mt-2 flex flex-wrap gap-1">
                        {item.tag && (
                            <Badge variant={tagVariant}>{TAG_LABELS[item.tag] ?? item.tag}</Badge>
                        )}
                        {item.relevance && (
                            <Badge
                                variant={
                                    item.relevance === 'high'
                                        ? 'brand'
                                        : item.relevance === 'medium'
                                          ? 'info'
                                          : 'default'
                                }
                            >
                                {RELEVANCE_LABELS[item.relevance] ?? item.relevance}
                            </Badge>
                        )}
                    </div>
                </div>
                <div className="flex-1 min-w-0">
                    <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-white font-medium hover:text-v07-yellow transition-colors block"
                    >
                        {item.title}
                    </a>
                    {item.summary_bullets && item.summary_bullets.length > 0 ? (
                        <ul className="mt-2 space-y-1 text-sm text-v07-text-muted">
                            {item.summary_bullets.map((b, i) => (
                                <li key={typeof b === 'string' ? b : `bullet-${i}`} className="flex gap-2">
                                    <span className="text-v07-yellow flex-shrink-0">·</span>
                                    <span>{b}</span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="mt-2 text-xs text-v07-text-subtle italic">
                            Aún no resumido (próxima corrida lo tomará).
                        </div>
                    )}
                </div>
            </div>
        </Card>
    );
}
