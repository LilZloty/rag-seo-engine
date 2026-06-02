"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card } from "@/app/components/ui/Card";
import { Button } from "@/app/components/ui/Button";
import { Badge } from "@/app/components/ui/Badge";
import { formatDateTime } from "@/app/lib/dates";
import { Tabs } from "@/app/components/ui/Tabs";
import {
  ArrowLeftIcon,
  CheckIcon,
  ChartIcon,
  ClockIcon,
  DatabaseIcon,
  FireIcon,
  SearchIcon,
  SparklesIcon,
  SyncIcon,
  WarningIcon,
} from "@/app/components/ui/Icons";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

interface MatchedProduct {
  id: string;
  shopify_id: string;
  title: string;
  handle: string | null;
  vendor: string | null;
  transmission_code: string | null;
  product_type: string | null;
}

interface InternalDetails {
  title: string | null;
  description: string | null;
  oem: string[] | null;
  makers: string[] | null;
  transmissions: { name: string; otherCodes: string[] | null; year: string }[] | null;
  vehicules: unknown;
}

interface SucursalItem {
  sku: string;
  quantity: number;
  matched: boolean;
  product: MatchedProduct | null;
  internal_details: InternalDetails | null;
  feed_metadata: Record<string, unknown>;
}

interface SucursalBlock {
  name: string;
  host: string;
  ok: boolean;
  error: string | null;
  fetched_at: string;
  duration_ms: number;
  items: SucursalItem[];
  total_units: number;
  item_count: number;
  matched_count: number;
  unmatched_count: number;
}

interface UnmatchedAggregateRow {
  sku: string;
  total_quantity: number;
  by_sucursal: Record<string, number>;
  internal_details: InternalDetails | null;
}

interface Opportunity {
  sku: string;
  type: "publish_candidate" | "seo_blind_spot" | "conversion_gap";
  score: number;
  title: string;
  in_store_qty: number;
  cross_sucursal_count: number;
  reasons: string[];
  action: string;
  internal_details: InternalDetails | null;
  shopify_product: Record<string, unknown> | null;
  signals: Record<string, unknown>;
}

interface TransmissionGap {
  transmission_code: string;
  in_store_skus: number;
  shopify_products: number;
  coverage: number;
  total_in_store_qty: number;
  gsc_impressions: number;
  gap_score: number;
  query_impressions?: number;
  query_clicks?: number;
  top_queries?: string[];
}

interface UnmetDemandEntry {
  type: "transmission" | "maker";
  code: string;
  impressions: number;
  clicks: number;
  top_queries: string[];
  shopify_products: number;
  in_store_qty: number;
  gap: boolean;
}

interface SearchDemand {
  total_queries_analyzed: number;
  by_transmission: Record<string, { impressions: number; clicks: number; top_queries: string[] }>;
  by_maker: Record<string, { impressions: number; clicks: number; top_queries: string[] }>;
  unmet_demand: UnmetDemandEntry[];
}

interface Snapshot {
  fetched_at: string;
  duration_ms: number;
  error: string | null;
  sucursales: SucursalBlock[];
  unmatched_aggregate: UnmatchedAggregateRow[];
  opportunities: Opportunity[];
  transmission_gaps: TransmissionGap[];
  search_demand: SearchDemand | null;
  summary: {
    total_units: number;
    matched_skus: number;
    unmatched_skus: number;
    sucursales_ok: number;
    sucursales_failed: number;
    details_resolved: number;
    details_total_skus: number;
    opportunities_count: number;
    opportunities_by_type: Record<string, number>;
    transmission_gaps_count: number;
    search_demand_queries: number;
    unmet_demand_count: number;
  };
}

interface SucursalConfigured {
  name: string;
  host: string;
}

interface ApiResponse {
  fetched_at: string | null;
  snapshot: Snapshot | null;
  message: string | null;
  sucursales_configured: SucursalConfigured[];
}

const INITIAL_TOP_N = 10;

function numberFmt(n: number): string {
  return new Intl.NumberFormat("es-MX").format(n);
}

export default function SucursalesDashboardPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState("sucursales");
  const [oppFilter, setOppFilter] = useState<string>("all");

  const loadSnapshot = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sucursales/top-products`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: ApiResponse = await res.json();
      setData(json);
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Failed to load snapshot");
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setRefreshError(null);
    try {
      const res = await fetch(`${API_BASE}/sucursales/refresh`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: ApiResponse = await res.json();
      setData(json);
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadSnapshot();
  }, [loadSnapshot]);

  const snapshot = data?.snapshot ?? null;

  const sucursalesList = useMemo(() => {
    if (snapshot) return snapshot.sucursales;
    return (data?.sucursales_configured ?? []).map((s) => ({
      name: s.name,
      host: s.host,
      ok: false,
      error: null,
      fetched_at: "",
      duration_ms: 0,
      items: [],
      total_units: 0,
      item_count: 0,
      matched_count: 0,
      unmatched_count: 0,
    })) as SucursalBlock[];
  }, [snapshot, data?.sucursales_configured]);

  return (
    <div className="min-h-screen bg-black text-white p-4 md:p-6">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Breadcrumb */}
        <Link
          href="/intelligence"
          className="inline-flex items-center gap-1.5 text-sm text-zinc-400 hover:text-[#F7B500] transition-colors"
        >
          <ArrowLeftIcon size={14} /> Intelligence
        </Link>

        {/* Header */}
        <Card>
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="size-10 rounded-sm bg-[#F7B500]/10 border border-[#F7B500]/30 flex items-center justify-center">
                <DatabaseIcon size={20} className="text-[#F7B500]" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Sucursales — In-Store Sales</h1>
                <p className="text-sm text-zinc-400">
                  TopProducts feed from m107 · m207 · m407 · m507 ·{" "}
                  <span className="text-zinc-500">rolling 90-day units sold</span>
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs text-zinc-500">Last fetched</p>
                <p className="text-sm flex items-center gap-1.5">
                  <ClockIcon size={14} className="text-zinc-400" />
                  {data?.fetched_at ? formatDateTime(data.fetched_at) : "Never"}
                </p>
              </div>
              <Button
                variant="primary"
                size="md"
                loading={refreshing}
                onClick={refresh}
                icon={<SyncIcon size={16} />}
              >
                {refreshing ? "Fetching…" : "Refresh"}
              </Button>
            </div>
          </div>

          {/* Configuration warning */}
          {snapshot?.error && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-sm flex items-start gap-2">
              <WarningIcon size={16} className="text-red-400 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-400">Configuration error</p>
                <p className="text-xs text-zinc-300 mt-0.5">{snapshot.error}</p>
              </div>
            </div>
          )}

          {/* Fetch error */}
          {refreshError && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-sm flex items-start gap-2">
              <WarningIcon size={16} className="text-red-400 mt-0.5 shrink-0" />
              <p className="text-sm text-red-400">{refreshError}</p>
            </div>
          )}

          {/* Empty state */}
          {!loading && !snapshot && !refreshError && data?.message && (
            <div className="mt-4 p-4 bg-[#2a2a2a] border border-[#3a3a3a] rounded-sm">
              <p className="text-sm text-zinc-300">{data.message}</p>
            </div>
          )}

          {/* Summary stats */}
          {snapshot && !snapshot.error && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <StatCell label="Total units (90d)" value={numberFmt(snapshot.summary.total_units)} accent />
              <StatCell label="Matched SKUs" value={numberFmt(snapshot.summary.matched_skus)} variant="success" />
              <StatCell label="Unmatched SKUs" value={numberFmt(snapshot.summary.unmatched_skus)} variant="warning" />
              <StatCell label="Sucursales OK" value={`${snapshot.summary.sucursales_ok} / 4`} variant={snapshot.summary.sucursales_failed === 0 ? "success" : "danger"} />
              <StatCell label="Details enriched" value={`${numberFmt(snapshot.summary.details_resolved)} / ${numberFmt(snapshot.summary.details_total_skus)}`} />
              <StatCell label="Fetch duration" value={`${(snapshot.duration_ms / 1000).toFixed(1)}s`} />
            </div>
          )}
        </Card>

        {/* Tabs */}
        {snapshot && !snapshot.error && (
          <Tabs
            tabs={[
              { id: "sucursales", label: "Sucursales" },
              { id: "opportunities", label: `Opportunities (${snapshot.opportunities?.length || 0})` },
              { id: "transmissions", label: `Transmission Gaps (${snapshot.transmission_gaps?.length || 0})` },
              { id: "search-demand", label: `Search Demand (${snapshot.summary?.unmet_demand_count || 0})` },
            ]}
            activeTab={activeTab}
            onChange={setActiveTab}
          />
        )}

        {/* Tab: Sucursales */}
        {activeTab === "sucursales" && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {sucursalesList.map((sucursal) => (
                <SucursalCard
                  key={sucursal.name}
                  sucursal={sucursal}
                  expanded={!!expanded[sucursal.name]}
                  onToggleExpand={() =>
                    setExpanded((prev) => ({ ...prev, [sucursal.name]: !prev[sucursal.name] }))
                  }
                />
              ))}
            </div>
            {snapshot && snapshot.unmatched_aggregate.length > 0 && (
              <UnmatchedAggregateCard rows={snapshot.unmatched_aggregate} />
            )}
          </>
        )}

        {/* Tab: Opportunities */}
        {activeTab === "opportunities" && snapshot?.opportunities && (
          <OpportunitiesTab
            opportunities={snapshot.opportunities}
            filter={oppFilter}
            onFilterChange={setOppFilter}
          />
        )}

        {/* Tab: Transmission Gaps */}
        {activeTab === "transmissions" && snapshot?.transmission_gaps && (
          <TransmissionGapsTab gaps={snapshot.transmission_gaps} />
        )}

        {/* Tab: Search Demand */}
        {activeTab === "search-demand" && snapshot?.search_demand && (
          <SearchDemandTab demand={snapshot.search_demand} />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Subcomponents
// ============================================================================

function StatCell({
  label,
  value,
  accent,
  variant,
}: {
  label: string;
  value: string;
  accent?: boolean;
  variant?: "success" | "warning" | "danger";
}) {
  const valueColor =
    variant === "success"
      ? "text-green-400"
      : variant === "warning"
      ? "text-yellow-400"
      : variant === "danger"
      ? "text-red-400"
      : accent
      ? "text-[#F7B500]"
      : "text-white";
  return (
    <div className="p-3 bg-[#2a2a2a] rounded-sm border border-[#3a3a3a]">
      <p className="text-xs text-zinc-500 uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 ${valueColor}`}>{value}</p>
    </div>
  );
}

function SucursalCard({
  sucursal,
  expanded,
  onToggleExpand,
}: {
  sucursal: SucursalBlock;
  expanded: boolean;
  onToggleExpand: () => void;
}) {
  const visibleItems = expanded ? sucursal.items : sucursal.items.slice(0, INITIAL_TOP_N);
  const hasMore = sucursal.items.length > INITIAL_TOP_N;
  const hasData = sucursal.items.length > 0;

  return (
    <Card>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">{sucursal.name}</h2>
            {sucursal.ok ? (
              <Badge variant="success">
                <CheckIcon size={10} className="mr-1" /> OK
              </Badge>
            ) : hasData || sucursal.error ? (
              <Badge variant="danger">
                <WarningIcon size={10} className="mr-1" /> Failed
              </Badge>
            ) : (
              <Badge variant="default">Not fetched</Badge>
            )}
          </div>
          <p className="text-xs text-zinc-500 mt-0.5 font-mono">{sucursal.host}</p>
        </div>
        {sucursal.duration_ms > 0 && (
          <span className="text-xs text-zinc-500">{sucursal.duration_ms} ms</span>
        )}
      </div>

      {sucursal.error && (
        <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded-sm">
          <p className="text-xs text-red-400">{sucursal.error}</p>
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 mb-3">
        <MiniStat label="Units" value={numberFmt(sucursal.total_units)} />
        <MiniStat label="Items" value={numberFmt(sucursal.item_count)} />
        <MiniStat
          label="Match rate"
          value={
            sucursal.item_count > 0
              ? `${Math.round((sucursal.matched_count / sucursal.item_count) * 100)}%`
              : "—"
          }
        />
      </div>

      {hasData ? (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-zinc-500 border-b border-[#3a3a3a]">
                  <th className="text-left py-1.5 pr-2 font-medium">SKU</th>
                  <th className="text-left py-1.5 pr-2 font-medium">Product</th>
                  <th className="text-right py-1.5 pl-2 font-medium">Qty</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item) => (
                  <tr key={item.sku} className="border-b border-[#2a2a2a] hover:bg-[#2a2a2a]/30">
                    <td className="py-1.5 pr-2 font-mono text-xs">{item.sku}</td>
                    <td className="py-1.5 pr-2">
                      {item.matched && item.product ? (
                        <div>
                          <p className="text-xs leading-tight">{item.product.title}</p>
                          {item.product.vendor && (
                            <p className="text-[10px] text-zinc-500 mt-0.5">{item.product.vendor}</p>
                          )}
                        </div>
                      ) : item.internal_details?.title ? (
                        <div>
                          <div className="flex items-center gap-1.5">
                            <Badge variant="warning">unmatched</Badge>
                          </div>
                          <p className="text-xs leading-tight mt-0.5 text-zinc-300">{item.internal_details.title}</p>
                          {item.internal_details.description && (
                            <p className="text-[10px] text-zinc-500 mt-0.5 line-clamp-1">{item.internal_details.description}</p>
                          )}
                          {item.internal_details.makers && item.internal_details.makers.length > 0 && (
                            <p className="text-[10px] text-zinc-500 mt-0.5">
                              {item.internal_details.makers.slice(0, 4).join(" · ")}
                              {item.internal_details.makers.length > 4 && ` +${item.internal_details.makers.length - 4}`}
                            </p>
                          )}
                        </div>
                      ) : (
                        <Badge variant="warning">unmatched</Badge>
                      )}
                    </td>
                    <td className="py-1.5 pl-2 text-right font-mono">{numberFmt(item.quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <button
              onClick={onToggleExpand}
              className="mt-2 w-full text-xs text-zinc-400 hover:text-[#F7B500] py-1.5 transition-colors"
            >
              {expanded
                ? `Show top ${INITIAL_TOP_N}`
                : `Show all ${sucursal.items.length} items`}
            </button>
          )}
        </>
      ) : !sucursal.error ? (
        <p className="text-sm text-zinc-500 italic">No items yet — click Refresh.</p>
      ) : null}
    </Card>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2 bg-[#2a2a2a] rounded-sm">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wide">{label}</p>
      <p className="text-sm font-semibold mt-0.5">{value}</p>
    </div>
  );
}

function UnmatchedAggregateCard({ rows }: { rows: UnmatchedAggregateRow[] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? rows : rows.slice(0, 15);
  const hasMore = rows.length > 15;
  const sucursalNames = useMemo(() => {
    const set = new Set<string>();
    rows.forEach((r) => Object.keys(r.by_sucursal).forEach((n) => set.add(n)));
    return Array.from(set);
  }, [rows]);

  return (
    <Card
      title="Unmatched SKUs"
      subtitle="SKUs in sucursal sales feeds with no matching product on Shopify — candidates to publish or codes to ignore."
      icon={<ChartIcon size={20} className="text-yellow-400" />}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-zinc-500 border-b border-[#3a3a3a]">
              <th className="text-left py-1.5 pr-2 font-medium">SKU</th>
              <th className="text-left py-1.5 pr-2 font-medium">Product (internal)</th>
              <th className="text-right py-1.5 px-2 font-medium">Total qty</th>
              {sucursalNames.map((name) => (
                <th key={name} className="text-right py-1.5 px-2 font-medium">{name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.sku} className="border-b border-[#2a2a2a] hover:bg-[#2a2a2a]/30">
                <td className="py-1.5 pr-2 font-mono text-xs whitespace-nowrap">{row.sku}</td>
                <td className="py-1.5 pr-2 max-w-[300px]">
                  {row.internal_details?.title ? (
                    <div>
                      <p className="text-xs leading-tight text-zinc-300 truncate">{row.internal_details.title}</p>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {row.internal_details.oem && row.internal_details.oem.slice(0, 3).map((code) => (
                          <span key={code} className="text-[10px] text-zinc-500 bg-[#2a2a2a] px-1 rounded">OEM {code}</span>
                        ))}
                        {row.internal_details.transmissions && row.internal_details.transmissions.slice(0, 2).map((t) => (
                          <span key={t.name} className="text-[10px] text-[#F7B500]/70 bg-[#F7B500]/10 px-1 rounded">{t.name}</span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <span className="text-[10px] text-zinc-600 italic">no details</span>
                  )}
                </td>
                <td className="py-1.5 px-2 text-right font-mono">{numberFmt(row.total_quantity)}</td>
                {sucursalNames.map((name) => (
                  <td key={name} className="py-1.5 px-2 text-right font-mono text-zinc-400">
                    {row.by_sucursal[name] ? numberFmt(row.by_sucursal[name]) : "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 w-full text-xs text-zinc-400 hover:text-[#F7B500] py-1.5 transition-colors"
        >
          {expanded ? "Show top 15" : `Show all ${rows.length} unmatched SKUs`}
        </button>
      )}
    </Card>
  );
}

// ============================================================================
// Opportunities Tab
// ============================================================================

const TYPE_CONFIG: Record<string, { label: string; color: string; badgeVariant: "brand" | "warning" | "info" }> = {
  publish_candidate: { label: "Publish", color: "text-[#F7B500]", badgeVariant: "brand" },
  seo_blind_spot: { label: "SEO", color: "text-yellow-400", badgeVariant: "warning" },
  conversion_gap: { label: "CRO", color: "text-blue-400", badgeVariant: "info" },
};

function OpportunitiesTab({
  opportunities,
  filter,
  onFilterChange,
}: {
  opportunities: Opportunity[];
  filter: string;
  onFilterChange: (f: string) => void;
}) {
  const filtered = useMemo(() => {
    if (filter === "all") return opportunities;
    return opportunities.filter((o) => o.type === filter);
  }, [opportunities, filter]);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    opportunities.forEach((o) => { counts[o.type] = (counts[o.type] || 0) + 1; });
    return counts;
  }, [opportunities]);

  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? filtered : filtered.slice(0, 25);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterButton active={filter === "all"} onClick={() => onFilterChange("all")}>
          All ({opportunities.length})
        </FilterButton>
        {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
          <FilterButton key={key} active={filter === key} onClick={() => onFilterChange(key)}>
            {cfg.label} ({typeCounts[key] || 0})
          </FilterButton>
        ))}
      </div>

      {/* Opportunity cards */}
      <div className="space-y-3">
        {visible.map((opp) => (
          <OpportunityRow key={opp.sku + opp.type} opp={opp} />
        ))}
      </div>

      {filtered.length > 25 && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="w-full text-xs text-zinc-400 hover:text-[#F7B500] py-2 transition-colors"
        >
          {showAll ? "Show top 25" : `Show all ${filtered.length} opportunities`}
        </button>
      )}

      {filtered.length === 0 && (
        <Card>
          <p className="text-sm text-zinc-500 text-center py-6">No opportunities found for this filter.</p>
        </Card>
      )}
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium rounded-sm transition-colors ${
        active
          ? "bg-[#F7B500]/20 text-[#F7B500] border border-[#F7B500]/30"
          : "bg-[#2a2a2a] text-zinc-400 border border-[#3a3a3a] hover:text-white hover:border-[#4a4a4a]"
      }`}
    >
      {children}
    </button>
  );
}

function OpportunityRow({ opp }: { opp: Opportunity }) {
  const cfg = TYPE_CONFIG[opp.type] || TYPE_CONFIG.publish_candidate;
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="hover:border-[#F7B500]/30 transition-colors">
      <div className="flex items-start gap-4">
        {/* Score */}
        <div className="flex flex-col items-center shrink-0">
          <div
            className={`size-12 rounded-sm flex items-center justify-center text-lg font-bold ${
              opp.score >= 70
                ? "bg-green-500/10 text-green-400 border border-green-500/30"
                : opp.score >= 40
                ? "bg-yellow-500/10 text-yellow-400 border border-yellow-500/30"
                : "bg-zinc-500/10 text-zinc-400 border border-zinc-500/30"
            }`}
          >
            {opp.score}
          </div>
          <span className="text-[10px] text-zinc-500 mt-1">score</span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={cfg.badgeVariant}>{cfg.label}</Badge>
            <span className="font-mono text-xs text-zinc-400">{opp.sku}</span>
            <span className="text-xs text-zinc-500">
              {numberFmt(opp.in_store_qty)} units · {opp.cross_sucursal_count} sucursal{opp.cross_sucursal_count > 1 ? "es" : ""}
            </span>
          </div>

          <p className="text-sm font-medium mt-1 truncate">{opp.title}</p>
          {opp.internal_details?.description && (
            <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{opp.internal_details.description}</p>
          )}

          {/* Reasons */}
          <div className="mt-2 space-y-1">
            {(expanded ? opp.reasons : opp.reasons.slice(0, 2)).map((reason, i) => (
              <p key={i} className="text-xs text-zinc-400 flex items-start gap-1.5">
                <SparklesIcon size={12} className="text-[#F7B500] mt-0.5 shrink-0" />
                {reason}
              </p>
            ))}
            {opp.reasons.length > 2 && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-[10px] text-zinc-500 hover:text-[#F7B500] transition-colors"
              >
                {expanded ? "less" : `+${opp.reasons.length - 2} more`}
              </button>
            )}
          </div>

          {/* Action */}
          <div className="mt-2 flex items-center gap-2">
            <span className={`text-xs font-medium ${cfg.color}`}>
              {opp.action}
            </span>
            {opp.shopify_product && (opp.shopify_product as Record<string, unknown>).handle && (
              <span className="text-[10px] text-zinc-500">
                shopify: /{String((opp.shopify_product as Record<string, unknown>).handle)}
              </span>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

// ============================================================================
// Transmission Gaps Tab
// ============================================================================

interface TransmissionDrillDown {
  transmission_code: string;
  matched_count: number;
  unmatched_count: number;
  matched: { sku: string; title: string; total_in_store_qty: number; shopify_product: Record<string, unknown> | null; internal_details: InternalDetails | null }[];
  unmatched: { sku: string; title: string; total_in_store_qty: number; internal_details: InternalDetails | null }[];
}

function TransmissionGapsTab({ gaps }: { gaps: TransmissionGap[] }) {
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [drillDown, setDrillDown] = useState<TransmissionDrillDown | null>(null);
  const [drillLoading, setDrillLoading] = useState(false);

  const handleToggle = async (code: string) => {
    if (expandedCode === code) {
      setExpandedCode(null);
      setDrillDown(null);
      return;
    }
    setExpandedCode(code);
    setDrillLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sucursales/transmission/${encodeURIComponent(code)}/products`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setDrillDown(json);
    } catch {
      setDrillDown(null);
    } finally {
      setDrillLoading(false);
    }
  };

  return (
    <Card
      title="Transmission Coverage Gaps"
      subtitle="Transmissions with high in-store demand but low product coverage on Shopify. Click a transmission to see its products."
      icon={<FireIcon size={20} className="text-[#F7B500]" />}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-zinc-500 border-b border-[#3a3a3a]">
              <th className="text-left py-2 pr-3 font-medium">Transmission</th>
              <th className="text-right py-2 px-3 font-medium">In-store SKUs</th>
              <th className="text-right py-2 px-3 font-medium">On Shopify</th>
              <th className="text-right py-2 px-3 font-medium">Coverage</th>
              <th className="text-right py-2 px-3 font-medium">Store units (90d)</th>
              <th className="text-right py-2 px-3 font-medium">GSC (products)</th>
              <th className="text-right py-2 px-3 font-medium">GSC (queries)</th>
              <th className="text-right py-2 pl-3 font-medium">Gap score</th>
            </tr>
          </thead>
          <tbody>
            {gaps.map((gap) => (
              <TransmissionGapRow
                key={gap.transmission_code}
                gap={gap}
                expanded={expandedCode === gap.transmission_code}
                drillDown={expandedCode === gap.transmission_code ? drillDown : null}
                loading={expandedCode === gap.transmission_code && drillLoading}
                onToggle={() => handleToggle(gap.transmission_code)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function TransmissionGapRow({
  gap,
  expanded,
  drillDown,
  loading,
  onToggle,
}: {
  gap: TransmissionGap;
  expanded: boolean;
  drillDown: TransmissionDrillDown | null;
  loading: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className={`border-b border-[#2a2a2a] cursor-pointer transition-colors ${
          expanded ? "bg-[#2a2a2a]/50" : "hover:bg-[#2a2a2a]/30"
        }`}
        onClick={onToggle}
      >
        <td className="py-2 pr-3">
          <span className="font-mono text-sm font-medium text-[#F7B500] hover:underline">
            {gap.transmission_code}
          </span>
        </td>
        <td className="py-2 px-3 text-right font-mono">{gap.in_store_skus}</td>
        <td className="py-2 px-3 text-right font-mono">{gap.shopify_products}</td>
        <td className="py-2 px-3 text-right">
          <span className={gap.coverage < 0.3 ? "text-red-400" : gap.coverage < 0.6 ? "text-yellow-400" : "text-zinc-300"}>
            {(gap.coverage * 100).toFixed(0)}%
          </span>
        </td>
        <td className="py-2 px-3 text-right font-mono">{numberFmt(gap.total_in_store_qty)}</td>
        <td className="py-2 px-3 text-right font-mono">
          {gap.gsc_impressions > 0 ? numberFmt(gap.gsc_impressions) : <span className="text-zinc-600">—</span>}
        </td>
        <td className="py-2 px-3 text-right font-mono" title={gap.top_queries?.join(", ") || ""}>
          {(gap.query_impressions ?? 0) > 0 ? (
            <span className="text-[#F7B500]">{numberFmt(gap.query_impressions!)}</span>
          ) : (
            <span className="text-zinc-600">—</span>
          )}
        </td>
        <td className="py-2 pl-3 text-right">
          <span className={`font-bold ${
            gap.gap_score >= 70 ? "text-green-400" : gap.gap_score >= 40 ? "text-yellow-400" : "text-zinc-400"
          }`}>
            {gap.gap_score}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={8} className="p-0">
            <div className="bg-[#1a1a1a] border-y border-[#F7B500]/20 px-4 py-3">
              {loading ? (
                <p className="text-xs text-zinc-500 py-2">Loading products...</p>
              ) : drillDown ? (
                <div className="space-y-3">
                  {drillDown.unmatched.length > 0 && (
                    <div>
                      <p className="text-xs text-yellow-400 font-medium mb-1.5">
                        Not on Shopify ({drillDown.unmatched_count})
                      </p>
                      <div className="space-y-1">
                        {drillDown.unmatched.slice(0, 15).map((p) => (
                          <div key={p.sku} className="flex items-center gap-3 text-xs py-1 border-b border-[#2a2a2a]">
                            <span className="font-mono text-zinc-400 w-20 shrink-0">{p.sku}</span>
                            <span className="flex-1 text-zinc-300 truncate">{p.title}</span>
                            <span className="font-mono text-zinc-400 shrink-0">{numberFmt(p.total_in_store_qty)} units</span>
                          </div>
                        ))}
                        {drillDown.unmatched.length > 15 && (
                          <p className="text-[10px] text-zinc-500 pt-1">+{drillDown.unmatched.length - 15} more</p>
                        )}
                      </div>
                    </div>
                  )}
                  {drillDown.matched.length > 0 && (
                    <div>
                      <p className="text-xs text-green-400 font-medium mb-1.5">
                        On Shopify ({drillDown.matched_count})
                      </p>
                      <div className="space-y-1">
                        {drillDown.matched.slice(0, 10).map((p) => (
                          <div key={p.sku} className="flex items-center gap-3 text-xs py-1 border-b border-[#2a2a2a]">
                            <span className="font-mono text-zinc-400 w-20 shrink-0">{p.sku}</span>
                            <span className="flex-1 text-zinc-300 truncate">{p.title}</span>
                            <span className="font-mono text-zinc-400 shrink-0">{numberFmt(p.total_in_store_qty)} units</span>
                          </div>
                        ))}
                        {drillDown.matched.length > 10 && (
                          <p className="text-[10px] text-zinc-500 pt-1">+{drillDown.matched.length - 10} more</p>
                        )}
                      </div>
                    </div>
                  )}
                  {drillDown.matched.length === 0 && drillDown.unmatched.length === 0 && (
                    <p className="text-xs text-zinc-500 italic">No products found for this transmission code.</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-zinc-500 italic">Failed to load products.</p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ============================================================================
// Search Demand Tab
// ============================================================================

function SearchDemandTab({ demand }: { demand: SearchDemand }) {
  const [filter, setFilter] = useState<string>("all");

  const filtered = useMemo(() => {
    if (filter === "all") return demand.unmet_demand;
    return demand.unmet_demand.filter((e) => e.type === filter);
  }, [demand.unmet_demand, filter]);

  const typeCounts = useMemo(() => {
    const counts = { transmission: 0, maker: 0 };
    demand.unmet_demand.forEach((e) => { counts[e.type] = (counts[e.type] || 0) + 1; });
    return counts;
  }, [demand.unmet_demand]);

  return (
    <div className="space-y-4">
      <Card
        title="Search Demand Signals"
        subtitle={`${demand.total_queries_analyzed} GSC queries analyzed (90d). Showing search terms that match transmission codes and brands from your in-store sales.`}
        icon={<SearchIcon size={20} className="text-[#F7B500]" />}
      >
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <FilterButton active={filter === "all"} onClick={() => setFilter("all")}>
            All ({demand.unmet_demand.length})
          </FilterButton>
          <FilterButton active={filter === "transmission"} onClick={() => setFilter("transmission")}>
            Transmissions ({typeCounts.transmission})
          </FilterButton>
          <FilterButton active={filter === "maker"} onClick={() => setFilter("maker")}>
            Brands ({typeCounts.maker})
          </FilterButton>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-500 border-b border-[#3a3a3a]">
                <th className="text-left py-2 pr-3 font-medium">Type</th>
                <th className="text-left py-2 pr-3 font-medium">Code / Brand</th>
                <th className="text-right py-2 px-3 font-medium">Impressions</th>
                <th className="text-right py-2 px-3 font-medium">Clicks</th>
                <th className="text-right py-2 px-3 font-medium">On Shopify</th>
                <th className="text-right py-2 px-3 font-medium">In-store units</th>
                <th className="text-left py-2 pl-3 font-medium">Top queries</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((entry) => (
                <tr key={`${entry.type}-${entry.code}`} className="border-b border-[#2a2a2a] hover:bg-[#2a2a2a]/30">
                  <td className="py-2 pr-3">
                    <Badge variant={entry.type === "transmission" ? "brand" : "info"}>
                      {entry.type === "transmission" ? "Trans" : "Brand"}
                    </Badge>
                  </td>
                  <td className="py-2 pr-3">
                    <span className={`font-mono text-sm font-medium ${entry.gap ? "text-yellow-400" : "text-zinc-300"}`}>
                      {entry.code}
                    </span>
                    {entry.gap && <span className="ml-1.5 text-[10px] text-red-400">no products</span>}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-[#F7B500]">{numberFmt(entry.impressions)}</td>
                  <td className="py-2 px-3 text-right font-mono">{numberFmt(entry.clicks)}</td>
                  <td className="py-2 px-3 text-right font-mono">
                    {entry.shopify_products > 0 ? (
                      entry.shopify_products
                    ) : (
                      <span className="text-red-400">0</span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-right font-mono">
                    {entry.in_store_qty > 0 ? numberFmt(entry.in_store_qty) : <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="py-2 pl-3 max-w-[250px]">
                    <div className="flex flex-wrap gap-1">
                      {entry.top_queries.slice(0, 3).map((q, i) => (
                        <span key={i} className="text-[10px] text-zinc-500 bg-[#2a2a2a] px-1.5 py-0.5 rounded truncate max-w-[120px]">
                          {q}
                        </span>
                      ))}
                      {entry.top_queries.length > 3 && (
                        <span className="text-[10px] text-zinc-600">+{entry.top_queries.length - 3}</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <p className="text-sm text-zinc-500 text-center py-6">
            {demand.total_queries_analyzed === 0
              ? "No GSC data available — check Google Search Console credentials."
              : "No unmet demand signals found for this filter."}
          </p>
        )}
      </Card>
    </div>
  );
}
