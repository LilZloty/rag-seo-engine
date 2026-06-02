"use client";

import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { formatDate, formatDateTime } from "@/app/lib/dates";
import { Card } from "@/app/components/ui/Card";
import { Button } from "@/app/components/ui/Button";
import { Badge } from "@/app/components/ui/Badge";
import { ProgressBar } from "@/app/components/ui/ProgressBar";
import { Tabs } from "@/app/components/ui/Tabs";
import {
  SyncIcon,
  WarningIcon,
  CheckIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  DatabaseIcon,
  ShoppingCartIcon,
  FireIcon,
  ArrowRightIcon,
  ChartIcon,
  ClockIcon,
  SearchIcon,
  BellIcon,
  UploadIcon,
  InfoIcon,
  DownloadIcon,
} from "@/app/components/ui/Icons";

// ===================== TYPES =====================
interface CompanionProduct {
  product_id: string;
  title: string;
  count: number;
}

interface InventoryProduct {
  id: string;
  shopify_id: string;
  title: string;
  sku: string | null;
  handle: string | null;
  product_type: string | null;
  price: string | null;
  inventory_quantity: number | null;
  inventory_by_location: Record<string, number> | null;
  inventory_status: string | null;
  inventory_velocity: number | null;
  days_of_supply: number | null;
  demand_score: number;
  stock_health: string | null;
  dead_stock_tier: "slow" | "stale" | "dead" | "obsolete" | null;
  last_sold_at: string | null;
  days_since_last_sale: number | null;
  low_stock_threshold: number | null;
  sold_30d: number;
  revenue_30d: number;
  sold_90d: number;
  revenue_90d: number;
  sold_365d: number;
  revenue_365d: number;
  anchor_score: number;
  ga4_sessions: number;
  gsc_impressions: number;
  active_subscribers: number;
  last_stockout_date: string | null;
  stockout_frequency_90d: number;
  urgency_score: number;
  revenue_lost_est: number;
  suggested_reorder_qty: number;
  capital_tied_up?: number;
  top_companions?: CompanionProduct[] | null;
  last_inventory_sync: string | null;
}

interface DashboardData {
  total_products: number;
  in_stock: number;
  out_of_stock: number;
  low_stock: number;
  not_synced: number;
  dead_stock: number;
  dead_stock_tiers: {
    slow: number;
    stale: number;
    dead: number;
    obsolete: number;
  };
  in_stock_rate: number;
  active_alerts: number;
  recent_restocks_7d: number;
  avg_days_of_supply: number;
  last_sync: string | null;
}

interface HealthData {
  score: number;
  label: string;
  breakdown: Record<string, { value: number; score: number; label: string }>;
  total_products_tracked: number;
}

interface InventoryAlert {
  id: string;
  type: string;
  product_id: string;
  message: string;
  severity: string;
  status: string;
  triggered_at: string | null;
}

interface ActionCenterData {
  restock_now: InventoryProduct[];
  order_soon: InventoryProduct[];
  slow_movers: InventoryProduct[];
  star_products: InventoryProduct[];
  counts: {
    restock_now: number;
    order_soon: number;
    slow_movers: number;
    star_products: number;
  };
}

interface RevenueAtRisk {
  total_revenue_lost: number;
  products_affected: number;
}

interface WaitlistProduct extends InventoryProduct {
  potential_revenue: number;
}

interface WaitlistSummary {
  total_products_with_subscribers: number;
  total_subscribers: number;
  oos_with_subscribers: number;
  in_stock_with_subscribers: number;
  potential_revenue: number;
}

// ===================== HELPERS =====================
const getScoreColor = (score: number) => {
  if (score >= 80) return "text-green-400";
  if (score >= 60) return "text-yellow-400";
  if (score >= 40) return "text-orange-400";
  return "text-red-400";
};

const getStatusBadge = (status: string | null) => {
  switch (status) {
    case "in_stock": return <Badge variant="success">In Stock</Badge>;
    case "out_of_stock": return <Badge variant="danger">Out of Stock</Badge>;
    case "low_stock": return <Badge variant="warning">Low Stock</Badge>;
    default: return <Badge variant="default">Not Synced</Badge>;
  }
};

const getHealthBadge = (health: string | null) => {
  switch (health) {
    case "healthy": return <Badge variant="success">Healthy</Badge>;
    case "warning": return <Badge variant="warning">Warning</Badge>;
    case "critical": return <Badge variant="danger">Critical</Badge>;
    case "dead": return <Badge variant="default">Dead Stock</Badge>;
    default: return null;
  }
};

const getTierBadge = (tier: string | null) => {
  switch (tier) {
    case "slow":
      return <span className="px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-yellow-500/15 text-yellow-400 border border-yellow-500/30" title="Has 30d sales but velocity < 0.05/day (~1.5 units/month)">Slow</span>;
    case "stale":
      return <span className="px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-orange-500/15 text-orange-400 border border-orange-500/30" title="No sales in 30 days, but had sales in 31–90 days">Stale</span>;
    case "dead":
      return <span className="px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-red-500/15 text-red-400 border border-red-500/30" title="No sales in 90 days, but had sales in 91–365 days">Dead</span>;
    case "obsolete":
      return <span className="px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-zinc-500/20 text-zinc-300 border border-zinc-500/40" title="Zero sales in 365 days — zombie inventory">Obsolete</span>;
    default:
      return null;
  }
};

const formatDaysSinceSale = (days: number | null): string => {
  if (days == null) return "—";
  if (days === 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
};

const getUrgencyDot = (urgencyScore: number) => {
  if (urgencyScore === -1) return <span className="inline-block size-2.5 rounded-full bg-zinc-500" title="Dead Stock" />;
  if (urgencyScore >= 70) return <span className="inline-block size-2.5 rounded-full bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]" title={`Urgent: ${urgencyScore}`} />;
  if (urgencyScore >= 40) return <span className="inline-block size-2.5 rounded-full bg-yellow-500 shadow-[0_0_6px_rgba(234,179,8,0.3)]" title={`Attention: ${urgencyScore}`} />;
  return <span className="inline-block size-2.5 rounded-full bg-green-500" title={`Healthy: ${urgencyScore}`} />;
};

const getSeverityColor = (severity: string) => {
  switch (severity) {
    case "critical": return "border-red-500/30 bg-red-500/10";
    case "warning": return "border-yellow-500/30 bg-yellow-500/10";
    case "info": return "border-blue-500/30 bg-blue-500/10";
    default: return "border-[#3a3a3a] bg-[#1a1a1a]";
  }
};

const formatCurrency = (value: number) => {
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}k`;
  return `$${value.toFixed(0)}`;
};

// Column header tooltips
const COLUMN_TOOLTIPS: Record<string, string> = {
  velocity: "Units sold per day, averaged over the last 30 days. Higher = faster-selling product.",
  supply: "Days until this product runs out at the current sales pace. Qty ÷ Velocity.",
  demand: "0–100 score: Velocity (25%) + Revenue (20%) + Sales trend (20%) + GA4 traffic (15%) + GSC impressions (10%) + GSC clicks (10%). Bonus: waitlist subscribers up to +20, anchor score up to +15.",
  qty: "Total inventory across all locations. Click a product's qty to see the per-sucursal breakdown.",
  sold_30d: "Total units sold in the last 30 days from Shopify order data.",
  sold_90d: "Total units sold in the last 90 days from Shopify order data.",
  anchor: "0–100: How much this product drives multi-product purchases. High anchor = when this goes OOS, you lose entire carts, not just this sale.",
};

// ===================== VISUAL PROGRESS BARS =====================
function SupplyBar({ days }: { days: number | null }) {
  if (!days || days >= 999) return <span className="text-zinc-500 text-xs">--</span>;
  const clamped = Math.min(days, 60);
  const pct = (clamped / 60) * 100;
  const color = days <= 3 ? "bg-red-500" : days <= 7 ? "bg-red-400" : days <= 14 ? "bg-yellow-500" : days <= 30 ? "bg-yellow-400" : "bg-green-500";
  const textColor = days <= 7 ? "text-red-400" : days <= 14 ? "text-yellow-400" : "text-green-400";
  return (
    <div className="flex items-center gap-1.5 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-[#2a2a2a] overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-bold tabular-nums ${textColor}`}>{Math.round(days)}d</span>
    </div>
  );
}

function DemandBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-1.5 min-w-[70px]">
      <div className="flex-1 h-1.5 bg-[#2a2a2a] overflow-hidden">
        <div className="h-full bg-[#F7B500] transition-all" style={{ width: `${score}%` }} />
      </div>
      <span className={`text-xs font-bold tabular-nums ${score > 50 ? "text-[#F7B500]" : "text-zinc-400"}`}>{score}</span>
    </div>
  );
}

function AnchorBar({ score }: { score: number }) {
  if (!score) return <span className="text-zinc-600 text-xs">--</span>;
  return (
    <div className="flex items-center gap-1.5 min-w-[60px]">
      <div className="flex-1 h-1.5 bg-[#2a2a2a] overflow-hidden">
        <div className="h-full bg-purple-500 transition-all" style={{ width: `${score}%` }} />
      </div>
      <span className={`text-xs font-bold tabular-nums ${score >= 50 ? "text-purple-400" : "text-purple-400/60"}`}>{score}</span>
    </div>
  );
}

// ===================== OOS DURATION INDICATOR =====================
function OosDuration({ lastStockoutDate }: { lastStockoutDate: string | null }) {
  if (!lastStockoutDate) return null;
  const daysOos = Math.floor((Date.now() - new Date(lastStockoutDate).getTime()) / 86400000);
  if (daysOos <= 0) return null;
  const color = daysOos > 14 ? "text-red-400" : daysOos > 7 ? "text-orange-400" : "text-yellow-400";
  const bgColor = daysOos > 14 ? "bg-red-500/10 border-red-500/20" : daysOos > 7 ? "bg-orange-500/10 border-orange-500/20" : "bg-yellow-500/10 border-yellow-500/20";
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium border ${bgColor} ${color}`}>
      {daysOos}d OOS
    </span>
  );
}

// ===================== SMART SLOW MOVER SUGGESTION =====================
function getSlowMoverSuggestion(p: InventoryProduct): { label: string; variant: "warning" | "danger" | "info" | "success" | "default"; reason: string } {
  const capital = p.capital_tied_up ?? ((p.inventory_quantity ?? 0) * parseFloat(p.price || "0"));
  const sessions = p.ga4_sessions || 0;
  const impressions = p.gsc_impressions || 0;
  const subs = p.active_subscribers || 0;
  const sold90 = p.sold_90d || 0;

  // Has subscribers waiting — don't liquidate, restock
  if (subs > 0) return { label: "Restock Priority", variant: "success", reason: `${subs} subscribers waiting` };
  // Is a companion of strong products — keep for cart value
  if ((p.anchor_score || 0) > 30) return { label: "Keep (Anchor)", variant: "info", reason: "Drives multi-product carts" };
  // Has traffic but no sales — pricing or listing issue
  if (sessions > 20 && sold90 === 0) return { label: "Fix Listing", variant: "warning", reason: `${sessions} sessions, 0 sales` };
  // Has GSC impressions but no sessions — SEO opportunity
  if (impressions > 100 && sessions < 5) return { label: "SEO Opportunity", variant: "info", reason: `${impressions} impressions, low CTR` };
  // Had some sales in 90d — discount to move remaining
  if (sold90 > 0 && sessions > 10) return { label: "Discount", variant: "warning", reason: `${sold90} sold in 90d, has traffic` };
  // High capital tied, no movement — liquidate
  if (capital > 500) return { label: "Liquidate", variant: "danger", reason: `${formatCurrency(capital)} capital trapped` };
  // Low capital, no movement — bundle or review
  if (capital > 100) return { label: "Bundle", variant: "warning", reason: "Low demand, consider bundling" };
  return { label: "Review", variant: "default", reason: "No clear signal" };
}

// ===================== COMPANION ROW COMPONENT =====================
function CompanionRow({ companions }: { companions: CompanionProduct[] | null | undefined }) {
  if (!companions || companions.length === 0) return null;
  return (
    <tr>
      <td colSpan={12} className="px-4 py-0">
        <div className="py-2.5 pl-8 border-t border-dashed border-[#2a2a2a]">
          <p className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1.5">Frequently bought together</p>
          <div className="flex flex-wrap gap-2">
            {companions.slice(0, 5).map((c, i) => (
              <span key={c.product_id || `companion-${i}`} className="inline-flex items-center gap-1.5 px-2 py-1 bg-[#1a1a1a] border border-[#2a2a2a] text-xs">
                <span className="text-zinc-300 truncate max-w-[200px]">{c.title || c.product_id}</span>
                <span className="text-purple-400 font-bold">{c.count}x</span>
              </span>
            ))}
          </div>
        </div>
      </td>
    </tr>
  );
}

interface InventorySnapshotItem {
  date: string;
  quantity: number;
  status: string | null;
  type: string;
}

// ===================== TOOLTIP COMPONENT =====================
function ColumnTooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const handleEnter = () => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setPos({ top: rect.top - 8, left: rect.left + rect.width / 2 });
    }
    setShow(true);
  };

  return (
    <span
      ref={ref}
      className="inline-flex ml-1 cursor-help"
      onMouseEnter={handleEnter}
      onMouseLeave={() => setShow(false)}
    >
      <InfoIcon size={12} className="text-zinc-500 hover:text-zinc-300 transition-colors" />
      {show && (
        <span
          className="fixed z-[9999] -translate-x-1/2 -translate-y-full px-3 py-2 text-xs text-zinc-200 bg-[#1a1a1a] border border-[#333] shadow-lg w-56 normal-case tracking-normal font-normal leading-relaxed whitespace-normal"
          style={{ top: pos.top, left: pos.left }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

// ===================== LOCATION POPOVER =====================
function LocationPopover({ locations, total }: { locations: Record<string, number> | null; total: number | null }) {
  const [show, setShow] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  if (!locations || Object.keys(locations).length === 0) {
    return <span>{total ?? "—"}</span>;
  }

  const entries = Object.entries(locations).sort((a, b) => b[1] - a[1]);

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setShow(!show)}
        className="underline decoration-dotted underline-offset-2 decoration-zinc-500 hover:decoration-[#F7B500] cursor-pointer transition-colors"
      >
        {total ?? "—"}
      </button>
      {show && (
        <>
          <div
            className="fixed inset-0 z-40"
            role="presentation"
            onClick={() => setShow(false)}
            onKeyDown={(e) => { if (e.key === 'Escape') setShow(false); }}
          />
          <div className="absolute z-50 right-0 top-full mt-1 bg-[#1a1a1a] border border-[#333] shadow-lg min-w-[200px]">
            <div className="px-3 py-2 border-b border-[#2a2a2a]">
              <p className="text-xs font-semibold text-zinc-300">Inventory by Location</p>
            </div>
            <div className="p-2 space-y-1">
              {entries.map(([name, qty]) => (
                <div key={name} className="flex items-center justify-between px-2 py-1.5 text-xs hover:bg-[#222] rounded">
                  <span className="text-zinc-300 truncate mr-3">{name}</span>
                  <span className={`font-bold shrink-0 ${qty === 0 ? "text-red-400" : qty <= 5 ? "text-yellow-400" : "text-white"}`}>
                    {qty}
                  </span>
                </div>
              ))}
            </div>
            <div className="px-3 py-2 border-t border-[#2a2a2a] flex justify-between text-xs">
              <span className="text-zinc-400">Total</span>
              <span className="font-bold text-white">{total}</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ===================== HISTORY POPOVER =====================
function HistoryPopover({ productId, productTitle, apiBase }: { productId: string; productTitle: string; apiBase: string }) {
  const [show, setShow] = useState(false);
  const [snapshots, setSnapshots] = useState<InventorySnapshotItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  const fetchHistory = useCallback(async () => {
    if (fetched) { setShow(true); return; }
    setLoading(true);
    setShow(true);
    try {
      const res = await fetch(`${apiBase}/inventory/snapshots/${productId}?days=90`);
      if (res.ok) {
        const data = await res.json();
        setSnapshots(data.snapshots || []);
      }
    } catch (e) {
      console.error("Failed to fetch snapshots:", e);
    } finally {
      setLoading(false);
      setFetched(true);
    }
  }, [productId, apiBase, fetched]);

  return (
    <div className="relative inline-block">
      <button
        onClick={fetchHistory}
        className="text-zinc-500 hover:text-[#F7B500] transition-colors"
        title="View inventory history"
      >
        <ClockIcon size={14} />
      </button>
      {show && (
        <>
          <div
            className="fixed inset-0 z-40"
            role="presentation"
            onClick={() => setShow(false)}
            onKeyDown={(e) => { if (e.key === 'Escape') setShow(false); }}
          />
          <div className="absolute z-50 right-0 top-full mt-1 bg-[#1a1a1a] border border-[#333] shadow-lg w-[320px]">
            <div className="px-3 py-2 border-b border-[#2a2a2a]">
              <p className="text-xs font-semibold text-zinc-300 truncate">{productTitle}</p>
              <p className="text-[10px] text-zinc-500">Last 90 days</p>
            </div>
            {loading ? (
              <div className="p-4 text-center text-xs text-zinc-500">Loading…</div>
            ) : snapshots.length === 0 ? (
              <div className="p-4 text-center text-xs text-zinc-500">No snapshot data yet. Run a daily snapshot first.</div>
            ) : (
              <div className="max-h-[280px] overflow-y-auto">
                {/* Mini chart: simple bar visualization */}
                <div className="px-3 py-2 border-b border-[#2a2a2a]">
                  <div className="flex items-end gap-[2px] h-12">
                    {snapshots.slice(-30).map((s, i) => {
                      const maxQty = Math.max(...snapshots.slice(-30).map(x => x.quantity), 1);
                      const height = Math.max((s.quantity / maxQty) * 100, 2);
                      return (
                        <div
                          key={s.date || `snap-${i}`}
                          className={`flex-1 rounded-t transition-colors ${
                            s.quantity === 0 ? "bg-red-500" : s.status === "low_stock" ? "bg-yellow-500" : "bg-green-500"
                          }`}
                          style={{ height: `${height}%` }}
                          title={`${formatDate(s.date)}: ${s.quantity} units`}
                        />
                      );
                    })}
                  </div>
                </div>
                {/* Table of snapshots */}
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[#888] uppercase text-[10px] border-b border-[#2a2a2a]">
                      <th className="px-3 py-1.5 text-left">Date</th>
                      <th className="px-3 py-1.5 text-right">Qty</th>
                      <th className="px-3 py-1.5 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...snapshots].reverse().slice(0, 20).map((s) => (
                      <tr key={`${s.date}-${s.type}-${s.quantity}`} className="border-b border-[#1a1a1a] hover:bg-[#222]">
                        <td className="px-3 py-1.5 text-zinc-400">
                          {formatDate(s.date)}
                        </td>
                        <td className={`px-3 py-1.5 text-right font-bold ${s.quantity === 0 ? "text-red-400" : "text-white"}`}>
                          {s.quantity}
                        </td>
                        <td className="px-3 py-1.5 text-right">
                          {getStatusBadge(s.status)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {snapshots.length > 20 && (
                  <p className="px-3 py-2 text-[10px] text-zinc-500 text-center">
                    Showing 20 of {snapshots.length} snapshots
                  </p>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ===================== MAIN COMPONENT =====================
export default function InventoryDashboard() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [alerts, setAlerts] = useState<InventoryAlert[]>([]);
  const [actionCenter, setActionCenter] = useState<ActionCenterData | null>(null);
  const [revenueAtRisk, setRevenueAtRisk] = useState<RevenueAtRisk | null>(null);
  const [waitlistProducts, setWaitlistProducts] = useState<WaitlistProduct[]>([]);
  const [waitlistSummary, setWaitlistSummary] = useState<WaitlistSummary | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [activeTab, setActiveTab] = useState("products");
  const [productFilter, setProductFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("urgency");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalProducts, setTotalProducts] = useState(0);
  const [salesPeriod, setSalesPeriod] = useState<"30d" | "90d">("30d");
  const [exporting, setExporting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [statusCounts, setStatusCounts] = useState({ all: 0, in_stock: 0, out_of_stock: 0, low_stock: 0, dead_stock: 0, slow: 0, stale: 0, dead: 0, obsolete: 0 });
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const [waitlistSort, setWaitlistSort] = useState("subscribers");
  const [syncingCoPurchase, setSyncingCoPurchase] = useState(false);
  const [fastestMovers, setFastestMovers] = useState<{ id: string; title: string; sku: string | null; inventory_quantity: number | null; inventory_velocity: number | null; days_of_supply: number | null; demand_score: number }[]>([]);
  const [stockoutRisk, setStockoutRisk] = useState<{ today: number; "3_days": number; "7_days": number; "14_days": number; currently_oos: number } | null>(null);
  const itemsPerPage = 50;
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

  // ===================== DATA FETCHING =====================
  // Fetch products with server-side pagination
  const fetchProducts = useCallback(async (page: number, filter: string, sort: string, search: string) => {
    setLoadingProducts(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(itemsPerPage),
        sort_by: sort,
      });
      if (filter !== "all") params.set("status", filter);
      if (search.trim()) params.set("search", search.trim());

      const res = await fetch(`${API_BASE}/inventory/products?${params}`);
      if (res.ok) {
        const data = await res.json();
        setProducts(data.products);
        setTotalPages(data.pagination.total_pages);
        setTotalProducts(data.pagination.total);
        setStatusCounts(data.counts);
      }
    } catch (e) {
      console.error("Error fetching products:", e);
    } finally {
      setLoadingProducts(false);
    }
  }, [API_BASE]);

  // Fetch everything except products (dashboard stats, alerts, etc.)
  const fetchDashboardData = async (wlSort?: string) => {
    const sort = wlSort ?? waitlistSort;
    try {
      const [dashRes, healthRes, alertRes, actionRes, riskRes, waitlistRes, waitlistSumRes, moversRes, riskTimeRes] = await Promise.all([
        fetch(`${API_BASE}/inventory/dashboard`),
        fetch(`${API_BASE}/inventory/health-score`),
        fetch(`${API_BASE}/inventory/alerts`),
        fetch(`${API_BASE}/inventory/action-center`),
        fetch(`${API_BASE}/inventory/revenue-at-risk`),
        fetch(`${API_BASE}/inventory/waitlist?sort_by=${sort}`),
        fetch(`${API_BASE}/inventory/waitlist/summary`),
        fetch(`${API_BASE}/inventory/analytics/fastest-movers`),
        fetch(`${API_BASE}/inventory/analytics/stockout-risk`),
      ]);

      if (dashRes.ok) setDashboard(await dashRes.json());
      if (healthRes.ok) setHealth(await healthRes.json());
      if (alertRes.ok) setAlerts(await alertRes.json());
      if (actionRes.ok) setActionCenter(await actionRes.json());
      if (riskRes.ok) setRevenueAtRisk(await riskRes.json());
      if (waitlistRes.ok) setWaitlistProducts(await waitlistRes.json());
      if (waitlistSumRes.ok) setWaitlistSummary(await waitlistSumRes.json());
      if (moversRes.ok) setFastestMovers(await moversRes.json());
      if (riskTimeRes.ok) setStockoutRisk(await riskTimeRes.json());
    } catch (e) {
      console.error("Error fetching dashboard data:", e);
    }
  };

  const fetchAll = async () => {
    setLoading(true);
    await Promise.all([
      fetchDashboardData(),
      fetchProducts(1, productFilter, sortBy, searchQuery),
    ]);
    setLoading(false);
  };

  const triggerSync = async (forceFull: boolean = false) => {
    setSyncing(true);
    try {
      const url = forceFull
        ? `${API_BASE}/inventory/sync?force_full=true`
        : `${API_BASE}/inventory/sync`;
      const res = await fetch(url, { method: "POST" });
      if (res.ok) {
        const stats = await res.json();
        await fetchAll();

        // Build sync summary
        const parts: string[] = [`Synced ${stats.products_synced} products.`];
        if (stats.qty_changed > 0) {
          parts.push(`${stats.qty_changed} quantities changed.`);
        } else {
          parts.push("No inventory changes detected.");
        }

        // New: incremental order sync stats
        const orders = stats.orders;
        if (orders && !orders.error) {
          const mode = orders.force_full ? "FULL backfill" : (orders.sync_window_start ? "incremental" : "first backfill");
          parts.push(`\n\nOrder sync (${mode}):`);
          parts.push(`• ${orders.line_items_upserted} line items, ${orders.orders_processed} orders`);
          parts.push(`• ${orders.products_affected} products updated`);
          parts.push(`• took ${orders.duration_seconds}s`);
        } else if (orders?.error) {
          parts.push(`\n\nOrder sync error: ${orders.error}`);
        }

        if (stats.restock_events?.length > 0) {
          parts.push(`\n${stats.restock_events.length} restocked.`);
        }
        if (stats.waitlist_cleared_count > 0) {
          const cleared = stats.waitlist_cleared as { title: string; subscribers_cleared: number }[];
          const names = cleared.map((c: { title: string; subscribers_cleared: number }) => `${c.title} (${c.subscribers_cleared} subs)`).join("\n• ");
          parts.push(`\n\nWaitlist cleaned (back in stock):\n• ${names}`);
        }
        if (stats.out_of_stock > 0) {
          parts.push(`\n${stats.out_of_stock} out of stock.`);
        }
        alert(parts.join(" "));
      }
    } catch (e) {
      console.error("Sync failed:", e);
    } finally {
      setSyncing(false);
    }
  };

  const acknowledgeAlert = async (alertId: string) => {
    try {
      await fetch(`${API_BASE}/inventory/alerts/${alertId}/ack`, { method: "POST" });
      setAlerts(prev => prev.filter(a => a.id !== alertId));
    } catch (e) {
      console.error("Failed to acknowledge alert:", e);
    }
  };

  const exportExcel = async (view: "products" | "action_center") => {
    setExporting(true);
    try {
      let res: Response;
      if (view === "products" && selectedIds.size > 0) {
        // Export only selected products via POST
        res = await fetch(`${API_BASE}/inventory/export/excel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_ids: Array.from(selectedIds) }),
        });
      } else {
        const statusParam = productFilter !== "all" && view === "products" ? `&status=${productFilter}` : "";
        res = await fetch(`${API_BASE}/inventory/export/excel?view=${view}${statusParam}`);
      }
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const disposition = res.headers.get("Content-Disposition");
        const filename = disposition?.match(/filename="(.+)"/)?.[1] || `Inventario_${view}.xlsx`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      }
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  };

  const syncCoPurchases = async () => {
    setSyncingCoPurchase(true);
    try {
      const res = await fetch(`${API_BASE}/inventory/sync-co-purchases`, { method: "POST" });
      if (res.ok) {
        const result = await res.json();
        await fetchAll();
        alert(`Co-purchase analysis complete. ${result.products_updated || 0} products updated with anchor scores.`);
      }
    } catch (e) {
      console.error("Co-purchase sync failed:", e);
    } finally {
      setSyncingCoPurchase(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (products.length > 0 && products.every(p => selectedIds.has(p.id))) {
      setSelectedIds(prev => {
        const next = new Set(prev);
        products.forEach(p => next.delete(p.id));
        return next;
      });
    } else {
      setSelectedIds(prev => {
        const next = new Set(prev);
        products.forEach(p => next.add(p.id));
        return next;
      });
    }
  };

  const toggleRowExpand = (id: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const copySKUs = (items: InventoryProduct[], sectionName: string) => {
    const skus = items.filter(p => p.sku).map(p => p.sku).join("\n");
    navigator.clipboard.writeText(skus);
    setCopiedSection(sectionName);
    setTimeout(() => setCopiedSection(null), 2000);
  };

  useEffect(() => { fetchAll(); }, []);

  // Fetch products when filter/sort/page/search changes (server-side)
  useEffect(() => {
    if (!loading) {
      fetchProducts(currentPage, productFilter, sortBy, searchQuery);
    }
  }, [currentPage, productFilter, sortBy]);

  // Debounced search — wait 400ms after user stops typing
  useEffect(() => {
    if (loading) return;
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      setCurrentPage(1);
      fetchProducts(1, productFilter, sortBy, searchQuery);
    }, 400);
    return () => { if (searchTimerRef.current) clearTimeout(searchTimerRef.current); };
  }, [searchQuery]);

  // Reset page when filter or sort changes
  useEffect(() => { setCurrentPage(1); }, [productFilter, sortBy]);

  const actionCenterBadge = actionCenter
    ? actionCenter.counts.restock_now + actionCenter.counts.order_soon
    : 0;

  const waitlistBadge = waitlistSummary ? waitlistSummary.total_subscribers : 0;

  const tabs = [
    { id: "products", label: `Products (${statusCounts.all})` },
    { id: "action", label: `Action Center${actionCenterBadge > 0 ? ` (${actionCenterBadge})` : ""}` },
    { id: "waitlist", label: `Waitlist${waitlistBadge > 0 ? ` (${waitlistBadge})` : ""}` },
    { id: "analytics", label: "Analytics" },
  ];

  // ==================== LOADING STATE ====================
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-semibold">Inventory Intelligence</h1>
          <Button variant="secondary" loading>Loading…</Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(n => (
            <Card key={`skel-${n}`} className="animate-pulse">
              <div className="h-4 bg-[#3a3a3a] rounded w-3/4 mb-4" />
              <div className="h-8 bg-[#3a3a3a] rounded w-1/2" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // ==================== EMPTY STATE ====================
  if (!dashboard || dashboard.total_products === 0) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-semibold">Inventory Intelligence</h1>
            <p className="text-zinc-400">Stock tracking, demand analysis & restock priorities</p>
          </div>
        </div>
        <Card accent className="text-center py-12">
          <DatabaseIcon size={64} className="text-[#F7B500] mx-auto mb-6" />
          <h2 className="text-2xl font-semibold mb-4">Sync Your Inventory</h2>
          <p className="text-zinc-400 mb-2 max-w-lg mx-auto">
            Connect to Shopify and pull your latest inventory data to start tracking stock levels, velocity, and demand.
          </p>
          <Button onClick={triggerSync} loading={syncing} icon={<SyncIcon size={20} />} size="lg">
            {syncing ? "Syncing from Shopify..." : "Sync Inventory Now"}
          </Button>
          {syncing && <p className="text-zinc-400 text-sm mt-4">This may take 15-30 seconds…</p>}
        </Card>
      </div>
    );
  }

  // ==================== MAIN DASHBOARD ====================
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Inventory Intelligence</h1>
          <p className="text-zinc-400">
            {dashboard.total_products} products tracked
            {dashboard.last_sync && (
              <span className="ml-2 text-zinc-500">
                · Last sync: {formatDateTime(dashboard.last_sync)}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={fetchAll} icon={<SyncIcon size={16} />}>
            Refresh
          </Button>
          <Button onClick={() => triggerSync(false)} loading={syncing} icon={<SyncIcon size={16} />}>
            {syncing ? "Syncing..." : "Sync Shopify"}
          </Button>
          <button
            onClick={() => {
              if (confirm("Force a FULL 365-day re-sync? This re-fetches all orders and takes ~2 minutes. Use only if you suspect data drift.")) {
                triggerSync(true);
              }
            }}
            disabled={syncing}
            className="text-[10px] text-zinc-600 hover:text-yellow-400 px-2 py-1 disabled:opacity-30"
            title="Re-fetch all 365 days of orders (escape hatch — incremental sync is normally enough)"
          >
            force full
          </button>
        </div>
      </div>

      {/* Quick Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <Card>
          <p className="text-xs text-zinc-400">Total</p>
          <p className="text-xl font-bold">{dashboard.total_products}</p>
        </Card>
        <Card>
          <p className="text-xs text-zinc-400">In Stock</p>
          <p className="text-xl font-bold text-green-400">{dashboard.in_stock}</p>
          <ProgressBar value={dashboard.in_stock_rate} size="sm" className="mt-1" />
        </Card>
        <Card>
          <p className="text-xs text-zinc-400">Out of Stock</p>
          <p className="text-xl font-bold text-red-400">{dashboard.out_of_stock}</p>
        </Card>
        <Card>
          <p className="text-xs text-zinc-400">Low Stock</p>
          <p className="text-xl font-bold text-yellow-400">{dashboard.low_stock}</p>
        </Card>
        <Card>
          <div title="Has stock but no sales in 90 days. Tier breakdown: slow / stale / dead / obsolete.">
            <p className="text-xs text-zinc-400">Dead Stock (90d)</p>
            <p className="text-xl font-bold text-zinc-500">{dashboard.dead_stock}</p>
            {dashboard.dead_stock_tiers && (
              <div className="mt-1 flex gap-1.5 text-[9px] text-zinc-500">
                <span title="Slow: low velocity, still selling"><span className="text-yellow-400">{dashboard.dead_stock_tiers.slow}</span> slow</span>
                <span title="Stale: 30d=0 but 90d>0"><span className="text-orange-400">{dashboard.dead_stock_tiers.stale}</span> stale</span>
                <span title="Dead: 90d=0 but 365d>0"><span className="text-red-400">{dashboard.dead_stock_tiers.dead}</span> dead</span>
                <span title="Obsolete: 365d=0"><span className="text-zinc-300">{dashboard.dead_stock_tiers.obsolete}</span> obs</span>
              </div>
            )}
          </div>
        </Card>
        {revenueAtRisk && revenueAtRisk.total_revenue_lost > 0 ? (
          <Card className="border border-red-500/20">
            <p className="text-xs text-zinc-400">Revenue at Risk</p>
            <p className="text-xl font-bold text-red-400">{formatCurrency(revenueAtRisk.total_revenue_lost)}</p>
            <p className="text-[10px] text-zinc-500">{revenueAtRisk.products_affected} products</p>
          </Card>
        ) : (
          <Card>
            <p className="text-xs text-zinc-400">Avg Supply</p>
            <p className="text-xl font-bold">{Math.round(dashboard.avg_days_of_supply)}d</p>
          </Card>
        )}
        {health && (
          <Card className="border border-[#F7B500]/20">
            <p className="text-xs text-zinc-400">Health Score</p>
            <p className={`text-xl font-bold ${getScoreColor(health.score)}`}>{health.score}/100</p>
          </Card>
        )}
      </div>

      {/* Tabs */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* ==================== PRODUCTS TAB ==================== */}
      {activeTab === "products" && (
        <div className="space-y-4">
          {/* Search + Filters + Sort */}
          <div className="space-y-3">
            <div className="relative">
              <SearchIcon size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                placeholder="Search by product name, SKU, product type, handle, or Shopify ID..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-[#111] border border-[#2a2a2a] text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-[#F7B500]/50 transition-colors"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white text-sm"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="flex flex-col gap-2">
                {/* Primary stock status pills */}
                <div className="flex gap-1 flex-wrap">
                  {[
                    { id: "all", label: "All", count: statusCounts.all },
                    { id: "in_stock", label: "In Stock", count: statusCounts.in_stock },
                    { id: "out_of_stock", label: "Out of Stock", count: statusCounts.out_of_stock },
                    { id: "low_stock", label: "Low Stock", count: statusCounts.low_stock },
                    { id: "dead_stock", label: "Dead Stock", count: statusCounts.dead_stock },
                  ].map(f => (
                    <button
                      key={f.id}
                      onClick={() => setProductFilter(f.id)}
                      className={`px-3 py-1.5 text-xs font-medium transition-all ${
                        productFilter === f.id
                          ? "bg-[#F7B500] text-black"
                          : "bg-[#111] border border-[#333] text-zinc-400 hover:text-white hover:border-[#F7B500]/50"
                      }`}
                    >
                      {f.label}
                      <span className={`ml-1.5 px-1.5 py-0.5 text-[10px] ${
                        productFilter === f.id ? "bg-black/20" : "bg-[#2a2a2a]"
                      }`}>
                        {f.count}
                      </span>
                    </button>
                  ))}
                </div>

                {/* Granular dead stock tier pills */}
                <div className="flex gap-1 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-zinc-600 self-center mr-1">Tier:</span>
                  {[
                    { id: "slow", label: "Slow", count: statusCounts.slow, color: "yellow", tooltip: "Has 30d sales but velocity < 0.05/day" },
                    { id: "stale", label: "Stale", count: statusCounts.stale, color: "orange", tooltip: "No sales in 30d, but had sales in 31–90d" },
                    { id: "dead", label: "Dead (90d)", count: statusCounts.dead, color: "red", tooltip: "No sales in 90d, but had sales in 91–365d" },
                    { id: "obsolete", label: "Obsolete (365d)", count: statusCounts.obsolete, color: "gray", tooltip: "Zero sales in 365d — zombie inventory" },
                  ].map(f => {
                    const isActive = productFilter === f.id;
                    return (
                      <button
                        key={f.id}
                        onClick={() => setProductFilter(f.id)}
                        title={f.tooltip}
                        className={`px-2.5 py-1 text-[11px] font-medium transition-all ${
                          isActive
                            ? "bg-[#F7B500] text-black"
                            : "bg-[#0c0c0c] border border-[#2a2a2a] text-zinc-500 hover:text-white hover:border-[#F7B500]/50"
                        }`}
                      >
                        {f.label}
                        <span className={`ml-1.5 px-1 py-0.5 text-[9px] ${
                          isActive ? "bg-black/20" : "bg-[#1a1a1a]"
                        }`}>
                          {f.count}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-500">
                  {totalProducts} result{totalProducts !== 1 ? "s" : ""}
                </span>

                {/* 30d/90d period toggle */}
                <div className="flex bg-[#111] border border-[#333]">
                  {(["30d", "90d"] as const).map(period => (
                    <button
                      key={period}
                      onClick={() => setSalesPeriod(period)}
                      className={`px-2.5 py-1 text-xs font-medium transition-all ${
                        salesPeriod === period
                          ? "bg-[#F7B500] text-black"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      {period}
                    </button>
                  ))}
                </div>

                <select
                  value={sortBy}
                  onChange={e => setSortBy(e.target.value)}
                  className="bg-[#111] border border-[#333] text-xs text-zinc-300 px-2 py-1.5 focus:outline-none focus:border-[#F7B500]/50"
                >
                  <option value="urgency">Sort: Most Urgent</option>
                  <option value="title">Sort: Name A→Z</option>
                  <option value="sku">Sort: SKU A→Z</option>
                  <option value="qty_desc">Sort: Qty High→Low</option>
                  <option value="qty_asc">Sort: Qty Low→High</option>
                  <option value="price_desc">Sort: Price High→Low</option>
                  <option value="price_asc">Sort: Price Low→High</option>
                  <option value="velocity">Sort: Fastest Velocity</option>
                  <option value="demand">Sort: Highest Demand</option>
                  <option value="supply">Sort: Lowest Supply</option>
                </select>

                <button
                  onClick={() => exportExcel("products")}
                  disabled={exporting}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111] border border-[#333] text-xs text-zinc-300 hover:text-white hover:border-[#F7B500]/50 transition-colors disabled:opacity-40"
                  title={selectedIds.size > 0 ? `Export ${selectedIds.size} selected` : "Export all products"}
                >
                  <DownloadIcon size={14} />
                  {exporting ? "Exporting..." : selectedIds.size > 0 ? `Excel (${selectedIds.size})` : "Excel"}
                </button>
              </div>
            </div>
          </div>

          {/* Selection bar */}
          {selectedIds.size > 0 && (
            <div className="flex items-center justify-between px-4 py-2 bg-[#F7B500]/10 border border-[#F7B500]/30">
              <span className="text-xs text-[#F7B500] font-medium">
                {selectedIds.size} product{selectedIds.size !== 1 ? "s" : ""} selected
              </span>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-xs text-zinc-400 hover:text-white"
              >
                Clear selection
              </button>
            </div>
          )}

          {/* Product Table with Urgency Dots */}
          <div className={`bg-[#111] border border-[#222] overflow-x-auto relative ${loadingProducts ? "opacity-60" : ""} transition-opacity`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[#888] text-xs uppercase tracking-wider border-b border-[#2a2a2a]">
                  <th className="px-2 py-3 w-8 text-center">
                    <input
                      type="checkbox"
                      checked={products.length > 0 && products.every(p => selectedIds.has(p.id))}
                      onChange={toggleSelectAll}
                      className="size-3.5 accent-[#F7B500] cursor-pointer"
                    />
                  </th>
                  <th className="p-3 w-8"></th>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">SKU</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3 text-right">Price</th>
                  <th className="px-4 py-3 text-right"><span className="inline-flex items-center">Qty<ColumnTooltip text={COLUMN_TOOLTIPS.qty} /></span></th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right"><span className="inline-flex items-center">Velocity<ColumnTooltip text={COLUMN_TOOLTIPS.velocity} /></span></th>
                  <th className="px-4 py-3 text-right"><span className="inline-flex items-center">Supply<ColumnTooltip text={COLUMN_TOOLTIPS.supply} /></span></th>
                  <th className="px-4 py-3 text-right"><span className="inline-flex items-center">Demand<ColumnTooltip text={COLUMN_TOOLTIPS.demand} /></span></th>
                  <th className="px-4 py-3 text-right"><span className="inline-flex items-center">Anchor<ColumnTooltip text={COLUMN_TOOLTIPS.anchor} /></span></th>
                  <th className="px-4 py-3 text-right">
                    <span className="inline-flex items-center">
                      {salesPeriod === "30d" ? "Sold 30d" : "Sold 90d"}
                      <ColumnTooltip text={salesPeriod === "30d" ? COLUMN_TOOLTIPS.sold_30d : COLUMN_TOOLTIPS.sold_90d} />
                    </span>
                  </th>
                  <th className="px-4 py-3 text-right">
                    {salesPeriod === "30d" ? "Rev 30d" : "Rev 90d"}
                  </th>
                  <th className="p-3 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {products.map(p => (
                  <tr key={p.id} className={`border-b border-[#1a1a1a] hover:bg-[#151515] transition-colors ${
                    selectedIds.has(p.id) ? "bg-[#F7B500]/[0.05]" :
                    p.urgency_score >= 70 ? "bg-red-500/[0.03]" :
                    p.urgency_score >= 40 ? "bg-yellow-500/[0.02]" : ""
                  }`}>
                    <td className="px-2 py-3 text-center">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(p.id)}
                        onChange={() => toggleSelect(p.id)}
                        className="size-3.5 accent-[#F7B500] cursor-pointer"
                      />
                    </td>
                    <td className="p-3 text-center">
                      {getUrgencyDot(p.urgency_score)}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-white truncate max-w-[280px]">{p.title}</p>
                    </td>
                    <td className="px-4 py-3 text-zinc-400 font-mono text-xs whitespace-nowrap">
                      {p.sku || "—"}
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs whitespace-nowrap">
                      {p.product_type || "—"}
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-300 whitespace-nowrap">
                      {p.price ? `$${parseFloat(p.price).toFixed(2)}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-right font-bold whitespace-nowrap">
                      <span className={
                        (p.inventory_quantity ?? 0) === 0 ? "text-red-400" :
                        (p.inventory_quantity ?? 0) <= (p.low_stock_threshold ?? 5) ? "text-yellow-400" :
                        "text-white"
                      }>
                        <LocationPopover locations={p.inventory_by_location} total={p.inventory_quantity} />
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        {getStatusBadge(p.inventory_status)}
                        {getTierBadge(p.dead_stock_tier)}
                      </div>
                      {p.days_since_last_sale != null && (
                        <div className="text-[9px] text-zinc-600 mt-0.5" title={p.last_sold_at ? `Last sold: ${formatDate(p.last_sold_at)}` : ""}>
                          last sold {formatDaysSinceSale(p.days_since_last_sale)}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {p.inventory_velocity ? (
                        <span className="text-green-400">{p.inventory_velocity.toFixed(2)}/d</span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {p.days_of_supply && p.days_of_supply < 999 ? (
                        <span className={p.days_of_supply <= 7 ? "text-red-400 font-bold" : ""}>
                          {Math.round(p.days_of_supply)}d
                        </span>
                      ) : p.days_of_supply === 999 ? "∞" : "—"}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <span className={`font-bold ${
                        p.demand_score > 50 ? "text-[#F7B500]" :
                        p.demand_score > 20 ? "text-zinc-300" :
                        "text-zinc-500"
                      }`}>
                        {p.demand_score}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {(p.anchor_score || 0) > 0 ? (
                        <span className={`font-bold ${
                          p.anchor_score >= 50 ? "text-purple-400" :
                          p.anchor_score >= 25 ? "text-zinc-300" :
                          "text-zinc-500"
                        }`}>
                          {p.anchor_score}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap text-zinc-400">
                      {(() => {
                        const sold = salesPeriod === "30d" ? p.sold_30d : p.sold_90d;
                        return sold > 0 ? sold : "—";
                      })()}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap text-zinc-400">
                      {(() => {
                        const rev = salesPeriod === "30d" ? p.revenue_30d : p.revenue_90d;
                        return rev > 0 ? formatCurrency(rev) : "—";
                      })()}
                    </td>
                    <td className="p-3 text-center">
                      <HistoryPopover productId={p.id} productTitle={p.title} apiBase={API_BASE} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {totalProducts === 0 && (
              <p className="text-center text-zinc-400 py-12">
                {searchQuery ? `No products matching "${searchQuery}"` : "No products found for this filter."}
              </p>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-xs text-zinc-500">
                Showing {(currentPage - 1) * itemsPerPage + 1}–{Math.min(currentPage * itemsPerPage, totalProducts)} of {totalProducts}
              </p>
              <div className="flex gap-1">
                <button
                  onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 text-xs bg-[#111] border border-[#333] text-zinc-400 hover:text-white disabled:opacity-30"
                >
                  ← Prev
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let page: number;
                  if (totalPages <= 7) {
                    page = i + 1;
                  } else if (currentPage <= 4) {
                    page = i + 1;
                  } else if (currentPage >= totalPages - 3) {
                    page = totalPages - 6 + i;
                  } else {
                    page = currentPage - 3 + i;
                  }
                  return (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`px-3 py-1.5 text-xs transition-all ${
                        currentPage === page
                          ? "bg-[#F7B500] text-black font-bold"
                          : "bg-[#111] border border-[#333] text-zinc-400 hover:text-white"
                      }`}
                    >
                      {page}
                    </button>
                  );
                })}
                <button
                  onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 text-xs bg-[#111] border border-[#333] text-zinc-400 hover:text-white disabled:opacity-30"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== ACTION CENTER TAB ==================== */}
      {activeTab === "action" && actionCenter && (() => {
        // P0: Compute aggregate metrics for summary strip
        const totalRevAtRisk = actionCenter.restock_now.reduce((s, p) => s + (p.revenue_lost_est || 0), 0);
        const totalCapitalTrapped = actionCenter.slow_movers.reduce((s, p) => {
          const cap = p.capital_tied_up ?? ((p.inventory_quantity ?? 0) * parseFloat(p.price || "0"));
          return s + cap;
        }, 0);
        const needsAction = actionCenter.counts.restock_now + actionCenter.counts.order_soon;
        const starRevenue = actionCenter.star_products.reduce((s, p) => s + (p.revenue_30d || 0), 0);
        const avgSupplyOrderSoon = actionCenter.order_soon.length > 0
          ? actionCenter.order_soon.reduce((s, p) => s + (p.days_of_supply && p.days_of_supply < 999 ? p.days_of_supply : 0), 0) / actionCenter.order_soon.filter(p => p.days_of_supply && p.days_of_supply < 999).length
          : 0;

        return (
        <div className="space-y-5">
          {/* ===== P0: IMPACT SUMMARY STRIP ===== */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-[#222]">
            <div className="bg-[#0e0e0e] p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="size-2 rounded-full bg-red-500" />
                <p className="text-[11px] uppercase tracking-wider text-zinc-500">Revenue at Risk</p>
              </div>
              <p className="text-2xl font-bold text-red-400 tabular-nums">{formatCurrency(totalRevAtRisk)}</p>
              <p className="text-[10px] text-zinc-500 mt-0.5">{actionCenter.counts.restock_now} OOS products with demand</p>
            </div>
            <div className="bg-[#0e0e0e] p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="size-2 rounded-full bg-orange-500" />
                <p className="text-[11px] uppercase tracking-wider text-zinc-500">Capital Trapped</p>
              </div>
              <p className="text-2xl font-bold text-orange-400 tabular-nums">{formatCurrency(totalCapitalTrapped)}</p>
              <p className="text-[10px] text-zinc-500 mt-0.5">{actionCenter.counts.slow_movers} dead stock products</p>
            </div>
            <div className="bg-[#0e0e0e] p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="size-2 rounded-full bg-yellow-500" />
                <p className="text-[11px] uppercase tracking-wider text-zinc-500">Need Action</p>
              </div>
              <p className="text-2xl font-bold text-yellow-400 tabular-nums">{needsAction}</p>
              <p className="text-[10px] text-zinc-500 mt-0.5">{avgSupplyOrderSoon > 0 ? `${Math.round(avgSupplyOrderSoon)}d avg before stockout` : "Products requiring attention"}</p>
            </div>
            <div className="bg-[#0e0e0e] p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="size-2 rounded-full bg-green-500" />
                <p className="text-[11px] uppercase tracking-wider text-zinc-500">Star Revenue</p>
              </div>
              <p className="text-2xl font-bold text-green-400 tabular-nums">{formatCurrency(starRevenue)}</p>
              <p className="text-[10px] text-zinc-500 mt-0.5">{actionCenter.counts.star_products} top performers / month</p>
            </div>
          </div>

          {/* Action bar */}
          <div className="flex items-center justify-between">
            <button
              onClick={syncCoPurchases}
              disabled={syncingCoPurchase}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111] border border-[#333] text-xs text-zinc-300 hover:text-white hover:border-purple-500/50 transition-colors disabled:opacity-40"
            >
              <SyncIcon size={14} className={syncingCoPurchase ? "animate-spin" : ""} />
              {syncingCoPurchase ? "Analyzing orders..." : "Sync Co-Purchases & Anchors"}
            </button>
            <button
              onClick={() => exportExcel("action_center")}
              disabled={exporting}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#111] border border-[#333] text-xs text-zinc-300 hover:text-white hover:border-[#F7B500]/50 transition-colors disabled:opacity-40"
            >
              <DownloadIcon size={14} />
              {exporting ? "Exporting..." : "Export Action Center"}
            </button>
          </div>

          {/* ===== RESTOCK NOW (Critical) ===== */}
          <ActionSection
            title="Restock Now"
            subtitle="Products losing you money right now"
            color="red"
            count={actionCenter.counts.restock_now}
            items={actionCenter.restock_now}
            aggregateLabel={totalRevAtRisk > 0 ? `${formatCurrency(totalRevAtRisk)} revenue at risk` : undefined}
            onCopySKUs={() => copySKUs(actionCenter.restock_now, "restock")}
            copiedSection={copiedSection === "restock"}
            columns={["Product", "SKU", "Price", "Demand", "Anchor", "Sold 30d", "Rev Lost", "Subs", "OOS", "Reorder"]}
            renderRow={(p, i) => {
              const isExpanded = expandedRows.has(`restock-${p.id}`);
              const hasCompanions = p.top_companions && p.top_companions.length > 0;
              return (
                <>
                  <tr
                    key={p.id}
                    className={`border-b border-[#1a1a1a] hover:bg-red-500/[0.04] transition-colors ${hasCompanions ? "cursor-pointer" : ""}`}
                    onClick={() => hasCompanions && toggleRowExpand(`restock-${p.id}`)}
                  >
                    <td className="px-4 py-2.5">
                      <div className={`flex size-6 items-center justify-center text-xs font-bold ${
                        i < 3 ? "bg-red-500/20 text-red-400" : "bg-[#2a2a2a] text-zinc-400"
                      }`}>{i + 1}</div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        {hasCompanions && <span className="text-[10px] text-zinc-500">{isExpanded ? "▼" : "▶"}</span>}
                        <div>
                          <p className="font-medium truncate max-w-[220px]">{p.title}</p>
                          <div className="flex items-center gap-2">
                            <p className="text-[10px] text-zinc-500">{p.product_type}</p>
                            <OosDuration lastStockoutDate={p.last_stockout_date} />
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-zinc-400 font-mono text-xs">{p.sku || "—"}</td>
                    <td className="px-4 py-2.5 text-right text-zinc-300 whitespace-nowrap tabular-nums">
                      {p.price ? `$${parseFloat(p.price).toFixed(0)}` : "—"}
                    </td>
                    <td className="px-4 py-2.5"><DemandBar score={p.demand_score} /></td>
                    <td className="px-4 py-2.5"><AnchorBar score={p.anchor_score} /></td>
                    <td className="px-4 py-2.5 text-right text-zinc-300 tabular-nums">{p.sold_30d > 0 ? p.sold_30d : "—"}</td>
                    <td className="px-4 py-2.5 text-right font-bold text-red-400 tabular-nums">
                      {p.revenue_lost_est > 0 ? formatCurrency(p.revenue_lost_est) : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {(p.active_subscribers || 0) > 0 ? (
                        <span className="text-[#F7B500] font-bold tabular-nums">{p.active_subscribers}</span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <span className={`tabular-nums ${p.stockout_frequency_90d > 2 ? "text-red-400 font-bold" : "text-zinc-400"}`}>
                        {p.stockout_frequency_90d}x
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {p.suggested_reorder_qty > 0 ? (
                        <span className="text-[#F7B500] font-bold tabular-nums">{p.suggested_reorder_qty}</span>
                      ) : "—"}
                    </td>
                  </tr>
                  {isExpanded && <CompanionRow companions={p.top_companions as CompanionProduct[] | null} />}
                </>
              );
            }}
            emptyMessage="No critical restocks needed"
            emptyIcon={<CheckIcon size={28} className="text-green-400 mx-auto mb-1" />}
          />

          {/* ===== ORDER SOON (Warning) ===== */}
          <ActionSection
            title="Order Soon"
            subtitle="Products approaching stockout"
            color="yellow"
            count={actionCenter.counts.order_soon}
            items={actionCenter.order_soon}
            aggregateLabel={avgSupplyOrderSoon > 0 ? `${Math.round(avgSupplyOrderSoon)}d avg supply left` : undefined}
            onCopySKUs={() => copySKUs(actionCenter.order_soon, "order")}
            copiedSection={copiedSection === "order"}
            columns={["Product", "SKU", "Price", "Qty", "By Location", "Supply", "Velocity", "Sold 30d", "Demand", "Reorder"]}
            renderRow={(p, i) => {
              const locStr = p.inventory_by_location
                ? Object.entries(p.inventory_by_location).map(([n, q]) => `${n}: ${q}`).join(" · ")
                : "";
              const hasCompanions = p.top_companions && p.top_companions.length > 0;
              const isExpanded = expandedRows.has(`order-${p.id}`);
              return (
                <>
                  <tr
                    key={p.id}
                    className={`border-b border-[#1a1a1a] hover:bg-yellow-500/[0.03] transition-colors ${hasCompanions ? "cursor-pointer" : ""}`}
                    onClick={() => hasCompanions && toggleRowExpand(`order-${p.id}`)}
                  >
                    <td className="px-4 py-2.5 text-zinc-500 text-xs">{i + 1}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        {hasCompanions && <span className="text-[10px] text-zinc-500">{isExpanded ? "▼" : "▶"}</span>}
                        <div>
                          <p className="font-medium truncate max-w-[200px]">{p.title}</p>
                          <p className="text-[10px] text-zinc-500">{p.product_type}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-zinc-400 font-mono text-xs">{p.sku || "—"}</td>
                    <td className="px-4 py-2.5 text-right text-zinc-300 whitespace-nowrap tabular-nums">
                      {p.price ? `$${parseFloat(p.price).toFixed(0)}` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right font-bold text-yellow-400 tabular-nums">{p.inventory_quantity ?? 0}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400 whitespace-nowrap max-w-[180px] truncate" title={locStr}>
                      {locStr || "—"}
                    </td>
                    <td className="px-4 py-2.5"><SupplyBar days={p.days_of_supply} /></td>
                    <td className="px-4 py-2.5 text-right text-green-400 tabular-nums">
                      {p.inventory_velocity ? `${p.inventory_velocity.toFixed(1)}/d` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right text-zinc-300 tabular-nums">{p.sold_30d > 0 ? p.sold_30d : "—"}</td>
                    <td className="px-4 py-2.5"><DemandBar score={p.demand_score} /></td>
                    <td className="px-4 py-2.5 text-right">
                      {p.suggested_reorder_qty > 0 ? (
                        <span className="text-[#F7B500] font-bold tabular-nums">{p.suggested_reorder_qty}</span>
                      ) : "—"}
                    </td>
                  </tr>
                  {isExpanded && <CompanionRow companions={p.top_companions as CompanionProduct[] | null} />}
                </>
              );
            }}
            emptyMessage="No products approaching stockout"
            emptyIcon={<CheckIcon size={28} className="text-green-400 mx-auto mb-1" />}
          />

          {/* ===== SLOW MOVERS (Optimize) ===== */}
          <ActionSection
            title="Slow Movers"
            subtitle="Capital tied up with no return"
            color="orange"
            count={actionCenter.counts.slow_movers}
            items={actionCenter.slow_movers}
            aggregateLabel={totalCapitalTrapped > 0 ? `${formatCurrency(totalCapitalTrapped)} capital trapped` : undefined}
            onCopySKUs={() => copySKUs(actionCenter.slow_movers, "slow")}
            copiedSection={copiedSection === "slow"}
            columns={["Product", "SKU", "Qty", "By Location", "Price", "Capital", "Sold 90d", "Sessions", "GSC", "Action", "Why"]}
            renderRow={(p, i) => {
              const capital = p.capital_tied_up ?? ((p.inventory_quantity ?? 0) * parseFloat(p.price || "0"));
              const locStr = p.inventory_by_location
                ? Object.entries(p.inventory_by_location).map(([n, q]) => `${n}: ${q}`).join(" · ")
                : "";
              const suggestion = getSlowMoverSuggestion(p);
              return (
                <tr key={p.id} className="border-b border-[#1a1a1a] hover:bg-[#151515] transition-colors">
                  <td className="px-4 py-2.5 text-zinc-500 text-xs">{i + 1}</td>
                  <td className="px-4 py-2.5">
                    <p className="font-medium truncate max-w-[200px]">{p.title}</p>
                    <p className="text-[10px] text-zinc-500">{p.product_type}</p>
                  </td>
                  <td className="px-4 py-2.5 text-zinc-400 font-mono text-xs">{p.sku || "—"}</td>
                  <td className="px-4 py-2.5 text-right text-zinc-300 tabular-nums">{p.inventory_quantity ?? 0}</td>
                  <td className="px-4 py-2.5 text-xs text-zinc-400 whitespace-nowrap max-w-[160px] truncate" title={locStr}>
                    {locStr || "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right text-zinc-300 whitespace-nowrap tabular-nums">
                    {p.price ? `$${parseFloat(p.price).toFixed(0)}` : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right font-bold text-orange-400 tabular-nums">
                    {capital > 0 ? formatCurrency(capital) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right text-zinc-500 tabular-nums">
                    {(p.sold_90d || 0) > 0 ? p.sold_90d : "0"}
                  </td>
                  <td className="px-4 py-2.5 text-right text-zinc-500 tabular-nums">
                    {(p.ga4_sessions || 0) > 0 ? p.ga4_sessions : "0"}
                  </td>
                  <td className="px-4 py-2.5 text-right text-zinc-500 tabular-nums">
                    {(p.gsc_impressions || 0) > 0 ? p.gsc_impressions : "0"}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant={suggestion.variant}>{suggestion.label}</Badge>
                  </td>
                  <td className="px-4 py-2.5 text-[10px] text-zinc-500 max-w-[140px] truncate" title={suggestion.reason}>
                    {suggestion.reason}
                  </td>
                </tr>
              );
            }}
            emptyMessage="No slow movers detected"
            emptyIcon={<TrendingUpIcon size={28} className="text-green-400 mx-auto mb-1" />}
          />

          {/* ===== STAR PRODUCTS ===== */}
          <ActionSection
            title="Star Products"
            subtitle="Healthy stock + strong velocity — your best performers"
            color="green"
            count={actionCenter.counts.star_products}
            items={actionCenter.star_products}
            aggregateLabel={starRevenue > 0 ? `${formatCurrency(starRevenue)}/mo revenue` : undefined}
            onCopySKUs={() => copySKUs(actionCenter.star_products, "star")}
            copiedSection={copiedSection === "star"}
            columns={["Product", "SKU", "Price", "Qty", "Velocity", "Supply", "Demand", "Anchor", "Sold 30d", "Rev 30d"]}
            renderRow={(p, i) => {
              const hasCompanions = p.top_companions && p.top_companions.length > 0;
              const isExpanded = expandedRows.has(`star-${p.id}`);
              return (
                <>
                  <tr
                    key={p.id}
                    className={`border-b border-[#1a1a1a] hover:bg-green-500/[0.03] transition-colors ${hasCompanions ? "cursor-pointer" : ""}`}
                    onClick={() => hasCompanions && toggleRowExpand(`star-${p.id}`)}
                  >
                    <td className="px-4 py-2.5 text-zinc-500 text-xs">{i + 1}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        {hasCompanions && <span className="text-[10px] text-zinc-500">{isExpanded ? "▼" : "▶"}</span>}
                        <div>
                          <p className="font-medium truncate max-w-[200px]">{p.title}</p>
                          <p className="text-[10px] text-zinc-500">{p.product_type}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-zinc-400 font-mono text-xs">{p.sku || "—"}</td>
                    <td className="px-4 py-2.5 text-right text-zinc-300 whitespace-nowrap tabular-nums">
                      {p.price ? `$${parseFloat(p.price).toFixed(0)}` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right text-green-400 font-bold tabular-nums">{p.inventory_quantity ?? 0}</td>
                    <td className="px-4 py-2.5 text-right text-green-400 tabular-nums">
                      {p.inventory_velocity ? `${p.inventory_velocity.toFixed(1)}/d` : "—"}
                    </td>
                    <td className="px-4 py-2.5"><SupplyBar days={p.days_of_supply} /></td>
                    <td className="px-4 py-2.5"><DemandBar score={p.demand_score} /></td>
                    <td className="px-4 py-2.5"><AnchorBar score={p.anchor_score} /></td>
                    <td className="px-4 py-2.5 text-right text-zinc-300 tabular-nums">{p.sold_30d > 0 ? p.sold_30d : "—"}</td>
                    <td className="px-4 py-2.5 text-right font-bold text-[#F7B500] tabular-nums">
                      {p.revenue_30d > 0 ? formatCurrency(p.revenue_30d) : "—"}
                    </td>
                  </tr>
                  {isExpanded && <CompanionRow companions={p.top_companions as CompanionProduct[] | null} />}
                </>
              );
            }}
            emptyMessage="No star products yet — needs more sales data"
            emptyIcon={<FireIcon size={28} className="text-[#F7B500] mx-auto mb-1" />}
          />

          {/* Recent Activity (alerts feed) */}
          {alerts.length > 0 && (
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm text-zinc-300">Recent Activity</h3>
                <span className="text-xs text-zinc-500">{alerts.length} active</span>
              </div>
              <div className="space-y-2 max-h-[240px] overflow-y-auto">
                {alerts.slice(0, 10).map(alert => (
                  <div key={alert.id} className={`flex items-center justify-between p-2 border rounded ${getSeverityColor(alert.severity)}`}>
                    <div className="flex items-center gap-2 min-w-0">
                      <Badge variant={alert.severity === "critical" ? "danger" : alert.severity === "warning" ? "warning" : "info"}>
                        {alert.severity}
                      </Badge>
                      <p className="text-xs truncate">{alert.message}</p>
                    </div>
                    <button
                      onClick={() => acknowledgeAlert(alert.id)}
                      className="text-[10px] text-zinc-500 hover:text-white shrink-0 ml-2"
                    >
                      Dismiss
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
        );
      })()}

      {/* ==================== WAITLIST TAB ==================== */}
      {activeTab === "waitlist" && (
        <div className="space-y-6">
          {/* Waitlist Summary Cards */}
          {waitlistSummary && waitlistSummary.total_subscribers > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <Card className="border border-[#F7B500]/20">
                <p className="text-xs text-zinc-400">Total Subscribers</p>
                <p className="text-2xl font-bold text-[#F7B500]">{waitlistSummary.total_subscribers}</p>
              </Card>
              <Card>
                <p className="text-xs text-zinc-400">Products with Waitlist</p>
                <p className="text-2xl font-bold">{waitlistSummary.total_products_with_subscribers}</p>
              </Card>
              <Card className="border border-red-500/20">
                <p className="text-xs text-zinc-400">OOS with Subscribers</p>
                <p className="text-2xl font-bold text-red-400">{waitlistSummary.oos_with_subscribers}</p>
              </Card>
              <Card>
                <p className="text-xs text-zinc-400">In Stock with Subs</p>
                <p className="text-2xl font-bold text-green-400">{waitlistSummary.in_stock_with_subscribers}</p>
              </Card>
              <Card className="border border-[#F7B500]/20">
                <p className="text-xs text-zinc-400">Potential Revenue</p>
                <p className="text-2xl font-bold text-[#F7B500]">{formatCurrency(waitlistSummary.potential_revenue)}</p>
                <p className="text-[10px] text-zinc-500">If all OOS products restocked</p>
              </Card>
            </div>
          )}

          {/* Sort Controls */}
          {waitlistProducts.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500">Sort by</span>
              {[
                { id: "subscribers", label: "Subscribers" },
                { id: "demand", label: "Demand" },
                { id: "revenue_lost", label: "Revenue Lost" },
              ].map(s => (
                <button
                  key={s.id}
                  onClick={() => {
                    setWaitlistSort(s.id);
                    fetchDashboardData(s.id);
                  }}
                  className={`px-3 py-1.5 text-xs font-medium transition-all ${
                    waitlistSort === s.id
                      ? "bg-[#F7B500] text-black"
                      : "bg-[#111] border border-[#333] text-zinc-400 hover:text-white hover:border-[#F7B500]/50"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}

          {/* Waitlist Table */}
          {waitlistProducts.length > 0 ? (
            <div className="bg-[#111] border border-[#222] overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[#888] text-xs uppercase tracking-wider border-b border-[#2a2a2a]">
                    <th className="p-3 w-8">#</th>
                    <th className="px-4 py-3">Product</th>
                    <th className="px-4 py-3">SKU</th>
                    <th className="px-4 py-3 text-right">Subscribers</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Price</th>
                    <th className="px-4 py-3 text-right">Potential Revenue</th>
                    <th className="px-4 py-3 text-right">Demand</th>
                    <th className="px-4 py-3 text-right">Qty</th>
                    <th className="px-4 py-3 text-right">Velocity</th>
                    <th className="px-4 py-3 text-right">Rev Lost</th>
                  </tr>
                </thead>
                <tbody>
                  {waitlistProducts.map((p, i) => (
                    <tr key={p.id} className={`border-b border-[#1a1a1a] hover:bg-[#151515] transition-colors ${
                      p.inventory_status === "out_of_stock" ? "bg-red-500/[0.03]" : ""
                    }`}>
                      <td className="p-3 text-center text-zinc-500 text-xs">{i + 1}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium truncate max-w-[260px]">{p.title}</p>
                        <p className="text-[10px] text-zinc-500">{p.product_type}</p>
                      </td>
                      <td className="px-4 py-3 text-zinc-400 font-mono text-xs">{p.sku || "—"}</td>
                      <td className="px-4 py-3 text-right">
                        <span className="inline-flex items-center gap-1.5">
                          <BellIcon size={14} className="text-[#F7B500]" />
                          <span className="font-bold text-[#F7B500]">{p.active_subscribers}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">{getStatusBadge(p.inventory_status)}</td>
                      <td className="px-4 py-3 text-right text-zinc-300 whitespace-nowrap">
                        {p.price ? `$${parseFloat(p.price).toFixed(2)}` : "—"}
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-[#F7B500] whitespace-nowrap">
                        {p.potential_revenue > 0 ? formatCurrency(p.potential_revenue) : "—"}
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <span className={`font-bold ${p.demand_score > 50 ? "text-[#F7B500]" : "text-zinc-300"}`}>
                          {p.demand_score}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-bold whitespace-nowrap">
                        <span className={
                          (p.inventory_quantity ?? 0) === 0 ? "text-red-400" :
                          (p.inventory_quantity ?? 0) <= (p.low_stock_threshold ?? 5) ? "text-yellow-400" :
                          "text-white"
                        }>
                          {p.inventory_quantity ?? "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        {p.inventory_velocity ? (
                          <span className="text-green-400">{p.inventory_velocity.toFixed(2)}/d</span>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-red-400 whitespace-nowrap">
                        {p.revenue_lost_est > 0 ? formatCurrency(p.revenue_lost_est) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Card accent className="text-center py-12">
              <BellIcon size={48} className="text-[#F7B500] mx-auto mb-4" />
              <h2 className="text-xl font-semibold mb-2">No Waitlist Data Yet</h2>
              <p className="text-zinc-400 mb-4 max-w-md mx-auto">
                Import subscriber data from AMP by Aisle to see which products have customers waiting for back-in-stock notifications.
              </p>
              <label className="inline-flex items-center gap-2 px-4 py-2 bg-[#F7B500] text-black font-medium text-sm cursor-pointer hover:bg-[#e5a800] transition-colors">
                <UploadIcon size={16} />
                Upload AMP CSV Export
                <input
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setUploading(true);
                    try {
                      const formData = new FormData();
                      formData.append("file", file);
                      const res = await fetch(`${API_BASE}/inventory/waitlist/import`, {
                        method: "POST",
                        body: formData,
                      });
                      if (res.ok) {
                        const result = await res.json();
                        let msg = `Imported ${result.updated} products.`;
                        if (result.stale_cleared > 0) {
                          msg += ` ${result.stale_cleared} old entries cleared.`;
                        }
                        if (result.not_found_count > 0) {
                          const skus = (result.not_found as string[]).slice(0, 20).join(", ");
                          msg += `\n\n${result.not_found_count} not matched:${result.not_found_count > 20 ? ` (showing first 20)` : ""}\n${skus}`;
                        }
                        alert(msg);
                        await fetchAll();
                      } else {
                        const err = await res.json();
                        alert(`Import failed: ${err.detail || "Unknown error"}`);
                      }
                    } catch (err) {
                      console.error("CSV upload failed:", err);
                    } finally {
                      setUploading(false);
                      e.target.value = "";
                    }
                  }}
                />
              </label>
              <p className="text-zinc-500 text-xs mt-3">
                CSV format: sku, subscriber_count (or shopify_id, handle)
              </p>
            </Card>
          )}

          {/* CSV Import button when there IS data */}
          {waitlistProducts.length > 0 && (
            <div className="flex items-center justify-between">
              <p className="text-xs text-zinc-500">
                Data from AMP by Aisle "Avísame si disponibilidad" subscribers
              </p>
              <label className="inline-flex items-center gap-2 px-3 py-1.5 bg-[#111] border border-[#333] text-zinc-400 text-xs cursor-pointer hover:text-white hover:border-[#F7B500]/50 transition-colors">
                <UploadIcon size={14} />
                {uploading ? "Uploading..." : "Update CSV"}
                <input
                  type="file"
                  accept=".csv"
                  className="hidden"
                  disabled={uploading}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setUploading(true);
                    try {
                      const formData = new FormData();
                      formData.append("file", file);
                      const res = await fetch(`${API_BASE}/inventory/waitlist/import`, {
                        method: "POST",
                        body: formData,
                      });
                      if (res.ok) {
                        const result = await res.json();
                        let msg = `Updated ${result.updated} products.`;
                        if (result.stale_cleared > 0) {
                          msg += ` ${result.stale_cleared} old entries cleared.`;
                        }
                        if (result.not_found_count > 0) {
                          const skus = (result.not_found as string[]).slice(0, 20).join(", ");
                          msg += `\n\n${result.not_found_count} not matched:${result.not_found_count > 20 ? ` (showing first 20)` : ""}\n${skus}`;
                        }
                        alert(msg);
                        await fetchAll();
                      } else {
                        const err = await res.json();
                        alert(`Import failed: ${err.detail || "Unknown error"}`);
                      }
                    } catch (err) {
                      console.error("CSV upload failed:", err);
                    } finally {
                      setUploading(false);
                      e.target.value = "";
                    }
                  }}
                />
              </label>
            </div>
          )}
        </div>
      )}

      {/* ==================== ANALYTICS TAB ==================== */}
      {activeTab === "analytics" && (
        <div className="space-y-6">
          {/* Health Score */}
          {health && (
            <Card accent>
              <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <svg className="size-28 transform -rotate-90">
                      <circle cx="56" cy="56" r="48" stroke="#3a3a3a" strokeWidth="10" fill="transparent" />
                      <circle cx="56" cy="56" r="48" stroke="#F7B500" strokeWidth="10" fill="transparent"
                        strokeDasharray={301.59} strokeDashoffset={301.59 - (301.59 * health.score) / 100} strokeLinecap="round" />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className={`text-2xl font-bold ${getScoreColor(health.score)}`}>{health.score}</span>
                    </div>
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold">Inventory Health</h2>
                    <p className={`text-lg font-semibold ${getScoreColor(health.score)}`}>{health.label}</p>
                    <p className="text-sm text-zinc-400">{health.total_products_tracked} products tracked</p>
                  </div>
                </div>
                {health.breakdown && (
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 text-sm">
                    {Object.entries(health.breakdown).map(([key, data]) => (
                      <div key={key} className="text-center bg-[#1a1a1a] p-3 rounded">
                        <p className={`text-lg font-bold ${getScoreColor(data.score)}`}>{Math.round(data.score)}</p>
                        <p className="text-xs text-zinc-400 capitalize">{key.replace(/_/g, " ")}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Revenue at Risk + Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="border border-red-500/20">
              <div className="flex items-center gap-3 mb-2">
                <TrendingDownIcon size={20} className="text-red-400" />
                <p className="text-sm text-zinc-400">Total Revenue at Risk</p>
              </div>
              <p className="text-3xl font-bold text-red-400">
                {revenueAtRisk ? formatCurrency(revenueAtRisk.total_revenue_lost) : "$0"}
              </p>
              <p className="text-xs text-zinc-500 mt-1">
                {revenueAtRisk?.products_affected || 0} OOS products with active demand
              </p>
            </Card>
            <Card>
              <div className="flex items-center gap-3 mb-2">
                <ClockIcon size={20} className="text-yellow-400" />
                <p className="text-sm text-zinc-400">Avg Days of Supply</p>
              </div>
              <p className="text-3xl font-bold">{Math.round(dashboard.avg_days_of_supply)}d</p>
              <p className="text-xs text-zinc-500 mt-1">Across in-stock products with velocity</p>
            </Card>
            <Card>
              <div className="flex items-center gap-3 mb-2">
                <ShoppingCartIcon size={20} className="text-green-400" />
                <p className="text-sm text-zinc-400">Recent Restocks</p>
              </div>
              <p className="text-3xl font-bold text-green-400">{dashboard.recent_restocks_7d}</p>
              <p className="text-xs text-zinc-500 mt-1">Products restocked in last 7 days</p>
            </Card>
          </div>

          {/* Stock Distribution */}
          <Card title="Stock Distribution" icon={<ChartIcon size={20} className="text-[#F7B500]" />}>
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "In Stock", count: dashboard.in_stock, pct: dashboard.in_stock_rate, color: "bg-green-500" },
                { label: "Low Stock", count: dashboard.low_stock, pct: dashboard.total_products > 0 ? (dashboard.low_stock / dashboard.total_products * 100) : 0, color: "bg-yellow-500" },
                { label: "Out of Stock", count: dashboard.out_of_stock, pct: dashboard.total_products > 0 ? (dashboard.out_of_stock / dashboard.total_products * 100) : 0, color: "bg-red-500" },
                { label: "Dead Stock", count: dashboard.dead_stock, pct: dashboard.total_products > 0 ? (dashboard.dead_stock / dashboard.total_products * 100) : 0, color: "bg-zinc-500" },
              ].map(cat => (
                <div key={cat.label} className="text-center">
                  <div className="h-24 flex items-end justify-center mb-2">
                    <div
                      className={`w-12 ${cat.color} rounded-t transition-all`}
                      style={{ height: `${Math.max(cat.pct, 2)}%` }}
                    />
                  </div>
                  <p className="text-lg font-bold">{cat.count}</p>
                  <p className="text-xs text-zinc-400">{cat.label}</p>
                  <p className="text-[10px] text-zinc-500">{cat.pct.toFixed(1)}%</p>
                </div>
              ))}
            </div>
          </Card>

          {/* Panels */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Fastest Movers */}
            <Card title="Top 10 Fastest Movers" icon={<TrendingUpIcon size={20} className="text-green-400" />}>
              <div className="space-y-2">
                {fastestMovers.map((p, i) => (
                  <div key={p.id} className="flex items-center justify-between p-2 bg-[#1a1a1a] rounded">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <span className="text-xs text-zinc-500 w-5 text-right shrink-0">{i + 1}</span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{p.title}</p>
                        <p className="text-xs text-zinc-500">{p.inventory_quantity} in stock</p>
                      </div>
                    </div>
                    <div className="text-right shrink-0 ml-3">
                      <p className="text-sm font-bold text-green-400">{p.inventory_velocity?.toFixed(1)}/day</p>
                      <p className="text-xs text-zinc-400">
                        {p.days_of_supply && p.days_of_supply < 999 ? `${Math.round(p.days_of_supply)}d supply` : "∞"}
                      </p>
                    </div>
                  </div>
                ))}
                {fastestMovers.length === 0 && (
                  <p className="text-zinc-400 text-sm text-center py-4">No velocity data yet.</p>
                )}
              </div>
            </Card>

            {/* Stockout Risk Timeline */}
            <Card title="Stockout Risk Timeline" icon={<WarningIcon size={20} className="text-red-400" />}>
              <div className="space-y-2">
                {stockoutRisk ? (
                  <>
                    {[
                      { label: "Runs out today", key: "today" as const, color: "text-red-500" },
                      { label: "Within 3 days", key: "3_days" as const, color: "text-red-400" },
                      { label: "Within 7 days", key: "7_days" as const, color: "text-orange-400" },
                      { label: "Within 14 days", key: "14_days" as const, color: "text-yellow-400" },
                    ].map(tier => (
                      <div key={tier.label} className="flex items-center justify-between p-2 bg-[#1a1a1a] rounded">
                        <span className="text-sm text-zinc-300">{tier.label}</span>
                        <span className={`text-lg font-bold ${tier.color}`}>{stockoutRisk[tier.key]}</span>
                      </div>
                    ))}
                    <div className="flex items-center justify-between p-2 bg-[#1a1a1a] rounded">
                      <span className="text-sm text-zinc-300">Currently OOS</span>
                      <span className="text-lg font-bold text-red-500">{stockoutRisk.currently_oos}</span>
                    </div>
                  </>
                ) : (
                  <p className="text-zinc-400 text-sm text-center py-4">No data yet.</p>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}


// ===================== ACTION SECTION COMPONENT =====================
function ActionSection({
  title,
  subtitle,
  color,
  count,
  items,
  columns,
  renderRow,
  emptyMessage,
  emptyIcon,
  aggregateLabel,
  onCopySKUs,
  copiedSection,
}: {
  title: string;
  subtitle: string;
  color: "red" | "yellow" | "orange" | "green";
  count: number;
  items: InventoryProduct[];
  columns: string[];
  renderRow: (item: InventoryProduct, index: number) => React.ReactNode;
  emptyMessage: string;
  emptyIcon: React.ReactNode;
  aggregateLabel?: string;
  onCopySKUs?: () => void;
  copiedSection?: boolean;
}) {
  const [expanded, setExpanded] = useState(color === "red" || color === "yellow");

  const colorMap = {
    red: { border: "border-red-500/30", bg: "bg-red-500/10", text: "text-red-400", dot: "bg-red-500", aggBg: "bg-red-500/8" },
    yellow: { border: "border-yellow-500/30", bg: "bg-yellow-500/10", text: "text-yellow-400", dot: "bg-yellow-500", aggBg: "bg-yellow-500/8" },
    orange: { border: "border-orange-500/30", bg: "bg-orange-500/10", text: "text-orange-400", dot: "bg-orange-500", aggBg: "bg-orange-500/8" },
    green: { border: "border-green-500/30", bg: "bg-green-500/10", text: "text-green-400", dot: "bg-green-500", aggBg: "bg-green-500/8" },
  };
  const c = colorMap[color];

  return (
    <div className={`border ${c.border} bg-[#111] overflow-hidden`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full flex items-center justify-between p-4 hover:${c.bg} transition-colors text-left`}
      >
        <div className="flex items-center gap-3">
          <span className={`size-3 rounded-full ${c.dot}`} />
          <div>
            <h3 className="font-semibold">{title}</h3>
            <div className="flex items-center gap-2">
              <p className="text-xs text-zinc-400">{subtitle}</p>
              {aggregateLabel && (
                <span className={`text-[10px] font-medium px-1.5 py-0.5 ${c.text} ${c.aggBg} border ${c.border}`}>
                  {aggregateLabel}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-2xl font-bold tabular-nums ${c.text}`}>{count}</span>
          <span className="text-zinc-500 text-xs">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {expanded && (
        items.length > 0 ? (
          <div>
            {/* P4: Quick actions bar */}
            {onCopySKUs && (
              <div className="flex items-center gap-2 px-4 py-1.5 border-t border-[#2a2a2a] bg-[#0e0e0e]">
                <button
                  onClick={(e) => { e.stopPropagation(); onCopySKUs(); }}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] text-zinc-400 hover:text-white border border-[#333] hover:border-zinc-500 transition-colors"
                >
                  {copiedSection ? (
                    <><CheckIcon size={10} className="text-green-400" /> Copied</>
                  ) : (
                    <><DownloadIcon size={10} /> Copy SKUs</>
                  )}
                </button>
                <span className="text-[10px] text-zinc-600">{items.filter(p => p.sku).length} SKUs</span>
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[#888] text-xs uppercase tracking-wider border-t border-b border-[#2a2a2a]">
                    <th className="px-4 py-2 w-8">#</th>
                    {columns.map(col => (
                      <th key={col} className="px-4 py-2">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>{items.map((item, i) => renderRow(item, i))}</tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="text-center py-6 border-t border-[#2a2a2a]">
            {emptyIcon}
            <p className="text-zinc-400 text-sm">{emptyMessage}</p>
          </div>
        )
      )}
    </div>
  );
}
