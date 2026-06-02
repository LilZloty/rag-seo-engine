'use client';

import { useEffect, useState, useMemo } from 'react';
import { Card } from '@/app/components/ui/Card';
import { Button } from '@/app/components/ui/Button';
import { Badge } from '@/app/components/ui/Badge';
import { DownloadIcon, SearchIcon, TrendingUpIcon, RefreshIcon, ChartIcon } from '@/app/components/ui/Icons';
import { creativeIntelligenceAPI } from '@/lib/api';

interface TopProduct {
  title: string;
  handle: string;
  sold_all_time: number;
  sold_30d: number;
  revenue_all_time: number;
  gsc_impressions: number;
  gsc_clicks: number;
  gsc_ctr: number;
  gsc_position: number;
  ga4_sessions: number;
  transmission_code: string | null;
  product_type: string | null;
  price: string | null;
  inventory_quantity: number | null;
  inventory_status: string | null;
}

interface TransmissionEntry {
  code: string;
  units_sold: number;
}

interface BrandData {
  vehicle_brand: string;
  creative_score: number;
  total_units_all_time: number;
  total_revenue_all_time: number;
  units_30d: number;
  revenue_30d: number;
  units_90d: number;
  revenue_90d: number;
  units_365d: number;
  revenue_365d: number;
  search_impressions: number;
  search_clicks: number;
  search_ctr: number;
  ga4_sessions: number;
  ga4_revenue: number;
  product_count: number;
  top_transmissions: TransmissionEntry[];
  top_product_types: { type: string; units_sold: number }[];
  top_products: TopProduct[];
}

interface SearchQuery {
  query: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

interface Suggestion {
  brand: string;
  type: string;
  priority: string;
  headline_idea: string;
  reason: string;
  ad_angle: string;
  target_audience: string;
  top_products_for_creative: string[];
}

interface CreativeReport {
  generated_at: string;
  total_products_analyzed: number;
  brands_found: number;
  brand_ranking: BrandData[];
  vehicle_search_queries: Record<string, SearchQuery[]>;
  creative_suggestions: Suggestion[];
  unassigned_products: { title: string; sold_all_time: number; transmission_code: string | null }[];
}

const BRAND_COLORS: Record<string, string> = {
  'GM / Chevrolet': '#2563eb',
  'Ford': '#3b82f6',
  'Chrysler / Dodge / Jeep': '#8b5cf6',
  'VW / Audi': '#06b6d4',
  'Nissan': '#ef4444',
  'Toyota': '#22c55e',
  'Honda': '#f97316',
  'BMW / Mercedes': '#6366f1',
  'Hyundai / Kia': '#ec4899',
  'Mitsubishi': '#14b8a6',
  'Subaru': '#a855f7',
  'Mazda': '#f59e0b',
};

function formatNumber(n: number): string {
  return n.toLocaleString('es-MX');
}

function formatCurrency(n: number): string {
  return '$' + n.toLocaleString('es-MX', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default function CreativeIntelligencePage() {
  const [report, setReport] = useState<CreativeReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedBrand, setExpandedBrand] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'brands' | 'suggestions' | 'queries'>('brands');
  const [searchFilter, setSearchFilter] = useState('');

  const loadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await creativeIntelligenceAPI.getReport();
      setReport(data);
    } catch (err: any) {
      setError(err.message || 'Error loading creative intelligence data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadReport(); }, []);

  const filteredBrands = useMemo(() => {
    if (!report) return [];
    if (!searchFilter) return report.brand_ranking;
    const q = searchFilter.toLowerCase();
    return report.brand_ranking.filter(b =>
      b.vehicle_brand.toLowerCase().includes(q) ||
      b.top_transmissions.some(t => t.code.toLowerCase().includes(q))
    );
  }, [report, searchFilter]);

  const handleExportCSV = async () => {
    try {
      const csv = await creativeIntelligenceAPI.exportCSV();
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'creative_intelligence.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <div className="size-8 border-2 border-[#F7B500] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-zinc-400">Analizando datos de ventas, busqueda y trafico…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] p-6">
        <Card>
          <p className="text-red-400">{error}</p>
          <Button variant="secondary" onClick={loadReport} className="mt-4">Reintentar</Button>
        </Card>
      </div>
    );
  }

  if (!report) return null;

  // Totals
  const totalUnits = report.brand_ranking.reduce((s, b) => s + b.total_units_all_time, 0);
  const totalRevenue = report.brand_ranking.reduce((s, b) => s + b.total_revenue_all_time, 0);
  const totalImpressions = report.brand_ranking.reduce((s, b) => s + b.search_impressions, 0);

  return (
    <div className="min-h-screen bg-[#0a0a0a] p-4 sm:p-6 lg:p-10">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-white">Creative Intelligence</h1>
          <p className="text-zinc-400 mt-1">
            Datos cruzados de Shopify + Search Console + GA4 para crear ads por marca de vehiculo
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={loadReport} icon={<RefreshIcon size={14} />}>
            Actualizar
          </Button>
          <Button variant="primary" size="sm" onClick={handleExportCSV} icon={<DownloadIcon size={14} />}>
            Exportar CSV
          </Button>
        </div>
      </div>

      {/* KPI Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">Productos Analizados</p>
          <p className="text-2xl font-bold text-white mt-1">{formatNumber(report.total_products_analyzed)}</p>
        </div>
        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">Marcas Detectadas</p>
          <p className="text-2xl font-bold text-white mt-1">{report.brands_found}</p>
        </div>
        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">Unidades Vendidas Total</p>
          <p className="text-2xl font-bold text-[#F7B500] mt-1">{formatNumber(totalUnits)}</p>
        </div>
        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">Impresiones Google</p>
          <p className="text-2xl font-bold text-white mt-1">{formatNumber(totalImpressions)}</p>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex items-center gap-2 mb-6 border-b border-[#3a3a3a] pb-3">
        {[
          { key: 'brands' as const, label: 'Ranking por Marca' },
          { key: 'suggestions' as const, label: `Sugerencias Creativas (${report.creative_suggestions.length})` },
          { key: 'queries' as const, label: 'Queries por Marca' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveView(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-sm transition-colors ${
              activeView === tab.key
                ? 'bg-[#F7B500]/20 text-[#F7B500]'
                : 'text-zinc-400 hover:text-white hover:bg-[#3a3a3a]'
            }`}
          >
            {tab.label}
          </button>
        ))}
        <div className="flex-1" />
        <div className="relative">
          <SearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Buscar marca o transmision..."
            value={searchFilter}
            onChange={e => setSearchFilter(e.target.value)}
            className="pl-9 pr-4 py-2 text-sm bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm text-white placeholder-zinc-500 focus:border-[#F7B500] focus:outline-none w-64"
          />
        </div>
      </div>

      {/* Brand Ranking View */}
      {activeView === 'brands' && (
        <div className="space-y-4">
          {filteredBrands.map((brand, idx) => {
            const isExpanded = expandedBrand === brand.vehicle_brand;
            const barColor = BRAND_COLORS[brand.vehicle_brand] || '#6b7280';
            const maxUnits = report.brand_ranking[0]?.total_units_all_time || 1;
            const barWidth = Math.max((brand.total_units_all_time / maxUnits) * 100, 2);

            return (
              <div
                key={brand.vehicle_brand}
                className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm overflow-hidden"
              >
                {/* Brand Summary Row */}
                <button
                  onClick={() => setExpandedBrand(isExpanded ? null : brand.vehicle_brand)}
                  className="w-full text-left p-4 hover:bg-[#222] transition-colors"
                >
                  <div className="flex items-center gap-4">
                    {/* Rank */}
                    <div className="size-8 flex items-center justify-center bg-[#3a3a3a] rounded-sm text-sm font-bold text-white flex-shrink-0">
                      {idx + 1}
                    </div>

                    {/* Brand Name + Score */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="text-white font-semibold text-lg">{brand.vehicle_brand}</span>
                        <Badge variant={brand.creative_score >= 70 ? 'success' : brand.creative_score >= 40 ? 'warning' : 'default'}>
                          Score: {brand.creative_score}
                        </Badge>
                        <span className="text-zinc-500 text-sm">{brand.product_count} productos</span>
                      </div>
                      {/* Volume Bar */}
                      <div className="mt-2 h-2 bg-[#3a3a3a] rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all" style={{ width: `${barWidth}%`, backgroundColor: barColor }} />
                      </div>
                    </div>

                    {/* Key Metrics */}
                    <div className="hidden sm:flex items-center gap-6 flex-shrink-0">
                      <div className="text-right">
                        <p className="text-xs text-zinc-500">Ventas Total</p>
                        <p className="text-white font-semibold">{formatNumber(brand.total_units_all_time)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-zinc-500">Revenue</p>
                        <p className="text-white font-semibold">{formatCurrency(brand.total_revenue_all_time)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-zinc-500">Impresiones</p>
                        <p className="text-white font-semibold">{formatNumber(brand.search_impressions)}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-zinc-500">30d</p>
                        <p className="text-[#F7B500] font-semibold">{formatNumber(brand.units_30d)} uds</p>
                      </div>
                    </div>

                    {/* Expand Arrow */}
                    <svg className={`size-5 text-zinc-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {/* Expanded Detail */}
                {isExpanded && (
                  <div className="border-t border-[#3a3a3a] p-4">
                    {/* Metrics Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
                      {[
                        { label: 'Ventas 30d', value: formatNumber(brand.units_30d), sub: formatCurrency(brand.revenue_30d) },
                        { label: 'Ventas 90d', value: formatNumber(brand.units_90d), sub: formatCurrency(brand.revenue_90d) },
                        { label: 'Ventas 365d', value: formatNumber(brand.units_365d), sub: formatCurrency(brand.revenue_365d) },
                        { label: 'Ventas All-Time', value: formatNumber(brand.total_units_all_time), sub: formatCurrency(brand.total_revenue_all_time) },
                        { label: 'Impresiones GSC', value: formatNumber(brand.search_impressions), sub: `${brand.search_ctr}% CTR` },
                        { label: 'Sesiones GA4', value: formatNumber(brand.ga4_sessions), sub: formatCurrency(brand.ga4_revenue) + ' rev' },
                      ].map(m => (
                        <div key={m.label} className="bg-[#0a0a0a] border border-[#2a2a2a] rounded-sm p-3">
                          <p className="text-xs text-zinc-500">{m.label}</p>
                          <p className="text-white font-semibold">{m.value}</p>
                          <p className="text-xs text-zinc-400">{m.sub}</p>
                        </div>
                      ))}
                    </div>

                    {/* Transmissions + Types */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
                      <div>
                        <h4 className="text-sm font-medium text-zinc-400 mb-2">Transmisiones Principales</h4>
                        <div className="flex flex-wrap gap-2">
                          {brand.top_transmissions.map(t => (
                            <Badge key={t.code} variant="brand">
                              {t.code} ({formatNumber(t.units_sold)} uds)
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-zinc-400 mb-2">Tipos de Producto</h4>
                        <div className="flex flex-wrap gap-2">
                          {brand.top_product_types.map(t => (
                            <Badge key={t.type} variant="outline">
                              {t.type} ({formatNumber(t.units_sold)})
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Top Products Table */}
                    <h4 className="text-sm font-medium text-zinc-400 mb-2">Top Productos</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs text-zinc-500 uppercase border-b border-[#3a3a3a]">
                            <th className="pb-2 pr-4">Producto</th>
                            <th className="pb-2 pr-4 text-right">Vendidos</th>
                            <th className="pb-2 pr-4 text-right">30d</th>
                            <th className="pb-2 pr-4 text-right">Revenue</th>
                            <th className="pb-2 pr-4 text-right">Impresiones</th>
                            <th className="pb-2 pr-4 text-right">Clicks</th>
                            <th className="pb-2 pr-4 text-right">CTR</th>
                            <th className="pb-2 pr-4 text-right">Pos.</th>
                            <th className="pb-2 pr-4">Transmision</th>
                          </tr>
                        </thead>
                        <tbody>
                          {brand.top_products.map((p, i) => (
                            <tr key={p.title || `product-${i}`} className="border-b border-[#2a2a2a] hover:bg-[#222]">
                              <td className="py-2 pr-4 text-white max-w-xs truncate" title={p.title}>{p.title}</td>
                              <td className="py-2 pr-4 text-right text-[#F7B500] font-medium">{formatNumber(p.sold_all_time)}</td>
                              <td className="py-2 pr-4 text-right text-zinc-300">{formatNumber(p.sold_30d)}</td>
                              <td className="py-2 pr-4 text-right text-zinc-300">{formatCurrency(p.revenue_all_time)}</td>
                              <td className="py-2 pr-4 text-right text-zinc-400">{formatNumber(p.gsc_impressions)}</td>
                              <td className="py-2 pr-4 text-right text-zinc-400">{formatNumber(p.gsc_clicks)}</td>
                              <td className="py-2 pr-4 text-right text-zinc-400">{(p.gsc_ctr * 100).toFixed(1)}%</td>
                              <td className="py-2 pr-4 text-right text-zinc-400">{p.gsc_position > 0 ? p.gsc_position.toFixed(1) : '-'}</td>
                              <td className="py-2 pr-4 text-zinc-500">{p.transmission_code || '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Search Queries for this brand */}
                    {report.vehicle_search_queries[brand.vehicle_brand] && (
                      <div className="mt-6">
                        <h4 className="text-sm font-medium text-zinc-400 mb-2">Queries de Busqueda (Google)</h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                          {report.vehicle_search_queries[brand.vehicle_brand].slice(0, 12).map((q, i) => (
                            <div key={q.query || `q-${i}`} className="flex items-center justify-between bg-[#0a0a0a] border border-[#2a2a2a] rounded-sm px-3 py-2">
                              <span className="text-zinc-300 text-sm truncate mr-2">{q.query}</span>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                <span className="text-xs text-zinc-500">{formatNumber(q.impressions)} imp</span>
                                <span className="text-xs text-[#F7B500]">{q.clicks} clicks</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Creative Suggestions View */}
      {activeView === 'suggestions' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {report.creative_suggestions.map((suggestion, idx) => (
            <Card key={`${suggestion.brand}-${suggestion.headline_idea || idx}`}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={suggestion.priority === 'alta' ? 'danger' : 'warning'}>
                      {suggestion.priority.toUpperCase()}
                    </Badge>
                    <Badge variant="brand">{suggestion.brand}</Badge>
                    <Badge variant="outline">{suggestion.ad_angle}</Badge>
                  </div>
                </div>
              </div>

              <h3 className="text-white font-semibold text-lg mb-2">
                &ldquo;{suggestion.headline_idea}&rdquo;
              </h3>

              <p className="text-zinc-400 text-sm mb-3">{suggestion.reason}</p>

              <div className="mb-3">
                <p className="text-xs text-zinc-500 uppercase mb-1">Audiencia Target</p>
                <p className="text-zinc-300 text-sm">{suggestion.target_audience}</p>
              </div>

              <div>
                <p className="text-xs text-zinc-500 uppercase mb-1">Productos para el Creativo</p>
                <div className="space-y-1">
                  {suggestion.top_products_for_creative.map((p) => (
                    <p key={p} className="text-sm text-zinc-300 pl-3 border-l-2 border-[#F7B500]/30">{p}</p>
                  ))}
                </div>
              </div>
            </Card>
          ))}

          {report.creative_suggestions.length === 0 && (
            <div className="col-span-2 text-center py-12 text-zinc-500">
              No hay suficientes datos para generar sugerencias. Sincroniza primero los datos de Shopify y Google.
            </div>
          )}
        </div>
      )}

      {/* Search Queries View */}
      {activeView === 'queries' && (
        <div className="space-y-6">
          {Object.entries(report.vehicle_search_queries)
            .filter(([brand]) => !searchFilter || brand.toLowerCase().includes(searchFilter.toLowerCase()))
            .map(([brand, queries]) => (
              <Card key={brand} title={brand} subtitle={`${queries.length} queries detectadas`}>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-zinc-500 uppercase border-b border-[#3a3a3a]">
                        <th className="pb-2 pr-4">Query</th>
                        <th className="pb-2 pr-4 text-right">Impresiones</th>
                        <th className="pb-2 pr-4 text-right">Clicks</th>
                        <th className="pb-2 pr-4 text-right">CTR</th>
                        <th className="pb-2 pr-4 text-right">Posicion</th>
                      </tr>
                    </thead>
                    <tbody>
                      {queries.map((q, i) => (
                        <tr key={q.query || `query-${i}`} className="border-b border-[#2a2a2a]">
                          <td className="py-2 pr-4 text-white">{q.query}</td>
                          <td className="py-2 pr-4 text-right text-zinc-300">{formatNumber(q.impressions)}</td>
                          <td className="py-2 pr-4 text-right text-[#F7B500]">{q.clicks}</td>
                          <td className="py-2 pr-4 text-right text-zinc-400">{q.ctr}%</td>
                          <td className="py-2 pr-4 text-right text-zinc-400">{q.position}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            ))}

          {Object.keys(report.vehicle_search_queries).length === 0 && (
            <div className="text-center py-12 text-zinc-500">
              No se encontraron queries de busqueda por marca. Verifica la conexion con Search Console.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
