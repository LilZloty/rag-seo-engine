/**
 * AEO Article Enrichment Dashboard
 *
 * Lists every blog article with its enrichment metafield status, GSC + GA4
 * performance, detected fault codes, and a composite AEO score. Per-row
 * action opens an inline detail panel that runs the enrichment dry-run, then
 * lets you publish to Shopify metafields if the result looks good.
 *
 * Backend: GET /api/v1/aeo/articles/with-metrics + POST .../enrich
 */

'use client';

import { useEffect, useMemo, useState } from 'react';
import { aeoAPI, ArticleEnrichmentResult, ArticleMetricsRow } from '@/lib/api';

type SortKey = 'aeo_score' | 'sessions' | 'impressions' | 'position' | 'title';

export default function ArticleEnrichmentDashboard() {
  const [articles, setArticles] = useState<ArticleMetricsRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('aeo_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [onlyNeedsEnrichment, setOnlyNeedsEnrichment] = useState(false);

  const [selected, setSelected] = useState<ArticleMetricsRow | null>(null);
  const [enrichResult, setEnrichResult] = useState<ArticleEnrichmentResult | null>(null);
  const [enrichLoading, setEnrichLoading] = useState(false);
  const [enrichPublishing, setEnrichPublishing] = useState(false);
  const [enrichError, setEnrichError] = useState<string | null>(null);

  useEffect(() => {
    loadArticles();
  }, [onlyNeedsEnrichment]);

  async function loadArticles() {
    setLoading(true);
    setError(null);
    try {
      const data = await aeoAPI.listArticlesWithMetrics({
        needs_enrichment_only: onlyNeedsEnrichment,
      });
      setArticles(data.articles);
    } catch (e: any) {
      setError(e?.message || 'Falló la carga');
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = q
      ? articles.filter(
          (a) =>
            a.title.toLowerCase().includes(q) ||
            a.handle.toLowerCase().includes(q) ||
            a.tags.some((t) => t.toLowerCase().includes(q)) ||
            a.fault_codes.some((c) => c.toLowerCase().includes(q))
        )
      : articles;

    rows = [...rows].sort((a, b) => {
      let av: number | string = 0;
      let bv: number | string = 0;
      if (sortKey === 'title') {
        av = a.title.toLowerCase();
        bv = b.title.toLowerCase();
      } else if (sortKey === 'sessions') {
        av = a.ga4.sessions;
        bv = b.ga4.sessions;
      } else if (sortKey === 'impressions') {
        av = a.gsc.impressions;
        bv = b.gsc.impressions;
      } else if (sortKey === 'position') {
        av = a.gsc.position ?? 999;
        bv = b.gsc.position ?? 999;
      } else {
        av = a.aeo_score;
        bv = b.aeo_score;
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return rows;
  }, [articles, search, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'title' ? 'asc' : 'desc');
    }
  }

  async function openEnrich(article: ArticleMetricsRow) {
    setSelected(article);
    setEnrichResult(null);
    setEnrichError(null);
  }

  async function runEnrich(dryRun: boolean) {
    if (!selected) return;
    const id = typeof selected.article_id === 'number'
      ? selected.article_id
      : parseInt(String(selected.article_id), 10);
    if (isNaN(id)) {
      setEnrichError('Article ID inválido');
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
      const data = await aeoAPI.enrichArticle(id, { dry_run: dryRun });
      setEnrichResult(data);
      if (!dryRun && data.written) {
        // Refresh list to reflect new enrichment status
        loadArticles();
      }
    } catch (e: any) {
      setEnrichError(e?.message || 'Falló la generación');
    } finally {
      setEnrichLoading(false);
      setEnrichPublishing(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-100">
      <header className="border-b border-zinc-800 bg-black/40 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold tracking-tight">
                Enriquecimiento de artículos
              </h1>
              <p className="mt-0.5 text-xs text-zinc-400">
                TL;DR · FAQs · Knowledge Graph · GSC + GA4
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="text-zinc-500">
                <span className="text-[#F7B500] font-semibold">{filtered.length}</span>{' '}
                artículos
              </span>
              <button
                onClick={loadArticles}
                disabled={loading}
                className="px-3 py-1.5 border border-zinc-700 hover:border-[#F7B500] text-zinc-300 hover:text-[#F7B500] transition-colors"
              >
                {loading ? 'Cargando…' : 'Refrescar'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <input
            type="text"
            placeholder="Buscar por título, handle, tag o código de falla…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-[280px] bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm placeholder:text-zinc-600 focus:border-[#F7B500] focus:outline-none"
          />
          <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={onlyNeedsEnrichment}
              onChange={(e) => setOnlyNeedsEnrichment(e.target.checked)}
              className="accent-[#F7B500]"
            />
            Solo sin enriquecer
          </label>
        </div>

        {/* Error */}
        {error && (
          <div className="text-sm text-red-400 bg-red-950/30 border border-red-800 px-4 py-3 mb-4">
            {error}
          </div>
        )}

        {/* Table */}
        <div className="bg-zinc-900 border border-zinc-800 overflow-hidden">
          {loading && articles.length === 0 ? (
            <div className="text-center py-20 text-zinc-500 text-sm">
              Cargando artículos…
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-20 text-zinc-500 text-sm">
              No hay artículos que coincidan.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b-2 border-[#F7B500] bg-black/50 text-xs uppercase tracking-wide">
                    <SortHeader label="Artículo" active={sortKey === 'title'} dir={sortDir} onClick={() => toggleSort('title')} />
                    <SortHeader label="Score" align="right" active={sortKey === 'aeo_score'} dir={sortDir} onClick={() => toggleSort('aeo_score')} />
                    <SortHeader label="Sesiones" align="right" active={sortKey === 'sessions'} dir={sortDir} onClick={() => toggleSort('sessions')} />
                    <SortHeader label="Impresiones" align="right" active={sortKey === 'impressions'} dir={sortDir} onClick={() => toggleSort('impressions')} />
                    <SortHeader label="Posición" align="right" active={sortKey === 'position'} dir={sortDir} onClick={() => toggleSort('position')} />
                    <th className="px-4 py-3 text-zinc-500 font-semibold">Enriquecimiento</th>
                    <th className="px-4 py-3 text-zinc-500 font-semibold text-right">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  {filtered.map((a) => (
                    <tr
                      key={String(a.article_id)}
                      className={`hover:bg-[#F7B500]/5 transition-colors ${
                        selected?.article_id === a.article_id ? 'bg-[#F7B500]/10' : ''
                      }`}
                    >
                      <td className="px-4 py-3 max-w-[400px]">
                        <div className="font-medium text-zinc-100 line-clamp-2">{a.title}</div>
                        <div className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
                          <span className="font-mono">{a.handle}</span>
                          {a.fault_codes.length > 0 && (
                            <span className="text-[10px] uppercase tracking-wide text-[#F7B500]">
                              {a.fault_codes.join(' · ')}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <ScoreBadge score={a.aeo_score} />
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {a.ga4.sessions.toLocaleString('es-MX')}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {a.gsc.impressions.toLocaleString('es-MX')}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {a.gsc.position != null ? a.gsc.position.toFixed(1) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <EnrichmentStatus enrichment={a.enrichment} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => openEnrich(a)}
                          className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#F7B500] text-black text-xs font-bold hover:bg-[#ffc933] transition-colors"
                        >
                          Enriquecer →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <DetailPanel
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
      </main>
    </div>
  );
}

/* ===== Helper components ===== */

function SortHeader({
  label,
  align,
  active,
  dir,
  onClick,
}: {
  label: string;
  align?: 'left' | 'right';
  active: boolean;
  dir: 'asc' | 'desc';
  onClick: () => void;
}) {
  return (
    <th
      className={`px-4 py-3 text-zinc-500 font-semibold cursor-pointer select-none hover:text-[#F7B500] ${
        align === 'right' ? 'text-right' : ''
      } ${active ? 'text-[#F7B500]' : ''}`}
      onClick={onClick}
    >
      {label}
      {active && <span className="ml-1">{dir === 'asc' ? '↑' : '↓'}</span>}
    </th>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const tone =
    score >= 80
      ? 'bg-green-500/20 text-green-400 border-green-500/40'
      : score >= 50
      ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
      : 'bg-red-500/20 text-red-400 border-red-500/40';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-bold tabular-nums border ${tone}`}>
      {score}
    </span>
  );
}

function EnrichmentStatus({
  enrichment,
}: {
  enrichment: ArticleMetricsRow['enrichment'];
}) {
  const chips: { label: string; ok: boolean }[] = [
    { label: 'TL;DR', ok: enrichment.has_tldr },
    { label: `FAQ ×${enrichment.faqs_count}`, ok: enrichment.faqs_count >= 3 },
    { label: 'Revisado', ok: !!enrichment.last_reviewed_at },
  ];
  return (
    <div className="flex flex-wrap gap-1">
      {chips.map((c, i) => (
        <span
          key={i}
          className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 border ${
            c.ok
              ? 'border-green-500/40 text-green-400 bg-green-500/10'
              : 'border-zinc-700 text-zinc-600'
          }`}
        >
          {c.label}
        </span>
      ))}
    </div>
  );
}

function DetailPanel({
  article,
  result,
  loading,
  publishing,
  error,
  onClose,
  onDryRun,
  onPublish,
}: {
  article: ArticleMetricsRow;
  result: ArticleEnrichmentResult | null;
  loading: boolean;
  publishing: boolean;
  error: string | null;
  onClose: () => void;
  onDryRun: () => void;
  onPublish: () => void;
}) {
  const tone = (c: number) =>
    c >= 0.9
      ? 'bg-green-500/20 text-green-400 border-green-500/40'
      : c >= 0.7
      ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
      : 'bg-red-500/20 text-red-400 border-red-500/40';

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-zinc-900 border-l border-zinc-800 shadow-2xl overflow-y-auto z-50">
      <div className="sticky top-0 bg-zinc-900 border-b border-zinc-800 px-5 py-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs text-zinc-500 mb-0.5">#{article.article_id}</p>
          <h2 className="font-semibold text-zinc-100 line-clamp-2">{article.title}</h2>
        </div>
        <button
          onClick={onClose}
          className="flex-none w-8 h-8 text-zinc-500 hover:text-[#F7B500] text-xl leading-none"
          aria-label="Cerrar"
        >
          ×
        </button>
      </div>

      <div className="p-5 space-y-5">
        {/* Quick stats from existing metrics */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Stat label="AEO Score" value={article.aeo_score.toString()} />
          <Stat label="Sesiones (30d)" value={article.ga4.sessions.toLocaleString('es-MX')} />
          <Stat label="Impresiones (30d)" value={article.gsc.impressions.toLocaleString('es-MX')} />
          <Stat
            label="Posición media"
            value={article.gsc.position != null ? article.gsc.position.toFixed(1) : '—'}
          />
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          <button
            onClick={onDryRun}
            disabled={loading || publishing}
            className="flex-1 px-4 py-2 bg-zinc-100 text-black text-xs font-bold hover:bg-white disabled:opacity-50 transition-colors"
          >
            {loading ? 'Generando…' : 'Generar (Dry Run)'}
          </button>
          <button
            onClick={onPublish}
            disabled={!result || loading || publishing || result.confidence < 0.7}
            title={
              !result
                ? 'Primero corre un dry run'
                : result.confidence < 0.7
                ? 'Confidence <0.7'
                : ''
            }
            className="flex-1 px-4 py-2 bg-[#F7B500] text-black text-xs font-bold hover:bg-[#ffc933] disabled:opacity-50 transition-colors"
          >
            {publishing ? 'Publicando…' : 'Publicar a Shopify'}
          </button>
        </div>

        {error && (
          <div className="text-xs text-red-400 bg-red-950/30 border border-red-800 px-3 py-2">
            {error}
          </div>
        )}

        {/* Enrichment result */}
        {result && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-500 uppercase tracking-wide">
                Resultado
              </span>
              <span
                className={`px-2 py-0.5 text-xs font-bold border ${tone(result.confidence)}`}
              >
                Confidence {(result.confidence * 100).toFixed(0)}%
              </span>
            </div>

            {result.written && (
              <div className="text-xs bg-green-500/10 border border-green-500/40 text-green-400 px-3 py-2">
                Metafields publicados a Shopify.
              </div>
            )}
            {result.skip_reason && !result.written && (
              <div className="text-xs bg-amber-500/10 border border-amber-500/40 text-amber-400 px-3 py-2">
                No se publicó — {result.skip_reason}
              </div>
            )}

            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <Stat label="PAA" value={result.source_signals.paa_count.toString()} />
              <Stat label="Queries GSC" value={result.source_signals.gsc_query_count.toString()} />
              <Stat
                label="Códigos falla"
                value={(result.source_signals.fault_code_count ?? 0).toString()}
                detail={result.source_signals.fault_codes?.join(', ')}
              />
              <Stat label="Palabras" value={result.source_signals.article_word_count.toString()} />
            </div>

            <div className="border border-zinc-800 p-3 bg-zinc-950">
              <div className="text-[10px] uppercase tracking-wide text-zinc-500 mb-1">
                TL;DR ({result.tldr_summary.length} chars)
              </div>
              <p className="text-sm text-zinc-100 leading-relaxed">{result.tldr_summary}</p>
            </div>

            <div className="border border-zinc-800 p-3 bg-zinc-950">
              <div className="text-[10px] uppercase tracking-wide text-zinc-500 mb-2">
                FAQs ({result.faqs.length})
              </div>
              <ul className="space-y-2">
                {result.faqs.map((faq, i) => (
                  <li key={i} className="border-l-2 border-[#F7B500] pl-2">
                    <p className="font-semibold text-zinc-100 text-xs">{faq.q}</p>
                    <p className="mt-1 text-xs text-zinc-400 whitespace-pre-line line-clamp-4">
                      {faq.a}
                    </p>
                  </li>
                ))}
              </ul>
            </div>

            {result.warnings.length > 0 && (
              <div className="border border-amber-500/40 bg-amber-500/5 p-3">
                <div className="text-[10px] uppercase tracking-wide text-amber-400 mb-1">
                  Advertencias
                </div>
                <ul className="list-disc pl-4 text-xs text-amber-300 space-y-0.5">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="bg-zinc-950 border border-zinc-800 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-0.5 text-sm font-bold text-zinc-100 tabular-nums">{value}</div>
      {detail && (
        <div className="mt-0.5 text-[10px] font-mono text-zinc-500 truncate">{detail}</div>
      )}
    </div>
  );
}
