"use client";

import { useEffect, useState } from "react";
import { formatDate, formatDateTime } from "@/app/lib/dates";
import { Card } from "@/app/components/ui/Card";
import { Button } from "@/app/components/ui/Button";
import { Badge } from "@/app/components/ui/Badge";
import { Tabs } from "@/app/components/ui/Tabs";
import { ProgressBar } from "@/app/components/ui/ProgressBar";
import Link from "next/link";
import {
  TrendingUpIcon,
  TrendingDownIcon,
  WarningIcon,
  SearchIcon,
  ChartIcon,
  SyncIcon,
  CheckIcon,
  ClockIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  FireIcon,
  AlertIcon,
  TargetIcon,
  GlobeIcon,
  DeviceIcon,
} from "@/app/components/ui/Icons";

// ============================================================================
// TYPES
// ============================================================================

interface KeywordMetric {
  query: string;
  date: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
  position_change_7d?: number;
  position_change_30d?: number;
  ctr_change_7d?: number;
  expected_ctr?: number;
  ctr_gap?: number;
  is_underperforming: boolean;
}

interface CTRUnderperformer {
  query: string;
  position: number;
  actual_ctr: number;
  expected_ctr: number;
  ctr_gap: number;
  impressions: number;
  potential_extra_clicks: number;
  page_url?: string;
}

interface CTRSummary {
  total_underperforming: number;
  total_potential_clicks: number;
  avg_ctr_gap: number;
  top_opportunities: CTRUnderperformer[];
  by_position_bucket: Record<string, { count: number; avg_gap: number; total_potential_clicks: number }>;
}

interface SEOAlert {
  id: string;
  created_at: string;
  alert_type: string;
  severity: string;
  title: string;
  description?: string;
  affected_query?: string;
  affected_page?: string;
  metric_before?: number;
  metric_after?: number;
  metric_change?: number;
  status: string;
}

interface AlertSummary {
  open_alerts: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  recent: SEOAlert[];
}

interface PositionSummary {
  total_tracked: number;
  improving: number;
  stable: number;
  declining: number;
  new_in_top_10: number;
  lost_from_top_10: number;
}

interface MoversShakers {
  biggest_gains: Array<{ query: string; change: number; from_position: number; to_position: number; impressions: number }>;
  biggest_losses: Array<{ query: string; change: number; from_position: number; to_position: number; impressions: number }>;
}

interface GA4Funnel {
  date: string;
  device_category: string;
  sessions: number;
  product_views: number;
  add_to_carts: number;
  begin_checkouts: number;
  purchases: number;
  revenue: number;
  view_rate: number;
  cart_rate: number;
  checkout_rate: number;
  purchase_rate: number;
  overall_conversion: number;
}

interface CollectionStatus {
  queries_stored: number;
  mappings_stored: number;
  funnel_days_stored: number;
  pages_stored: number;
  alerts_generated: number;
  harvested_at: string;
  status: string;
  error?: string;
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function SEOIntelligencePage() {
  const [activeTab, setActiveTab] = useState("keywords");
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [days, setDays] = useState(30);
  
  // Data states
  const [keywords, setKeywords] = useState<KeywordMetric[]>([]);
  const [ctrSummary, setCTRSummary] = useState<CTRSummary | null>(null);
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null);
  const [positionSummary, setPositionSummary] = useState<PositionSummary | null>(null);
  const [moversShakers, setMoversShakers] = useState<MoversShakers | null>(null);
  const [funnelData, setFunnelData] = useState<GA4Funnel[]>([]);
  const [collectionStatus, setCollectionStatus] = useState<CollectionStatus | null>(null);
  const [collectionError, setCollectionError] = useState<string | null>(null);
  const [ga4Diagnostics, setGa4Diagnostics] = useState<any>(null);
  const [testingGa4, setTestingGa4] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const [dataRangeInfo, setDataRangeInfo] = useState<any>(null);
  const [testCollectionResult, setTestCollectionResult] = useState<any>(null);
  const [testingCollection, setTestingCollection] = useState(false);

  const API_BASE = "http://localhost:8000/api/v1/seo-intelligence";

  // Fetch all data
  const fetchData = async () => {
    setLoading(true);
    console.log(`[Frontend] Fetching data for days=${days}`);
    try {
      const keywordsUrl = `${API_BASE}/keywords?limit=50&days=${days}`;
      console.log(`[Frontend] Fetching: ${keywordsUrl}`);
      
      const [
        statusRes,
        keywordsRes,
        ctrRes,
        alertsRes,
        positionRes,
        moversRes,
        funnelRes,
      ] = await Promise.all([
        fetch(`${API_BASE}/collect/status`),
        fetch(keywordsUrl),
        fetch(`${API_BASE}/ctr/summary?days=${days}`),
        fetch(`${API_BASE}/alerts/summary?days=${days}`),
        fetch(`${API_BASE}/keywords/summary?days=${days}`),
        fetch(`${API_BASE}/keywords/movers/shakers?days=${days}`),
        fetch(`${API_BASE}/funnel?days=${days}`),
      ]);

      if (statusRes.ok) setCollectionStatus(await statusRes.json());
      if (keywordsRes.ok) {
        const kwData = await keywordsRes.json();
        console.log('[Frontend] Keywords response:', kwData.length, 'records');
        console.log('[Frontend] First keyword sample:', kwData[0]);
        setKeywords(kwData);
      }
      if (ctrRes.ok) {
        const ctrData = await ctrRes.json();
        console.log('[SEO Intelligence] CTR Summary:', ctrData);
        setCTRSummary(ctrData);
      }
      if (alertsRes.ok) {
        const alertData = await alertsRes.json();
        console.log('[SEO Intelligence] Alerts:', alertData);
        setAlertSummary(alertData);
      }
      if (positionRes.ok) {
        const posData = await positionRes.json();
        console.log('[SEO Intelligence] Position Summary:', posData, 'type:', typeof posData, 'isArray:', Array.isArray(posData));
        setPositionSummary(posData);
      }
      if (moversRes.ok) {
        const moversData = await moversRes.json();
        console.log('[SEO Intelligence] Movers & Shakers:', moversData);
        setMoversShakers(moversData);
      }
      if (funnelRes.ok) {
        const funnelData = await funnelRes.json();
        console.log('[SEO Intelligence] Funnel:', funnelData.length, 'records');
        setFunnelData(funnelData);
      }
    } catch (error) {
      console.error("Error fetching SEO intelligence data:", error);
    } finally {
      setLoading(false);
    }
  };

  const runCollection = async () => {
    setCollecting(true);
    setCollectionError(null);
    try {
      const response = await fetch(`${API_BASE}/collect`, { method: "POST" });
      const result = await response.json();
      
      if (response.ok) {
        setCollectionStatus(result);
        // Show any warnings
        if (result.error) {
          setCollectionError(result.error);
        }
        fetchData();
      } else {
        setCollectionError(result.detail || result.error || "Collection failed");
      }
    } catch (error) {
      console.error("Error running collection:", error);
      setCollectionError("Failed to connect to server");
    } finally {
      setCollecting(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [days]);

  const testGa4Connection = async () => {
    setTestingGa4(true);
    try {
      const response = await fetch(`${API_BASE}/diagnostics/ga4`);
      if (response.ok) {
        const result = await response.json();
        setGa4Diagnostics(result);
      }
    } catch (error) {
      console.error("Error testing GA4:", error);
    } finally {
      setTestingGa4(false);
    }
  };

  const checkDataRange = async () => {
    try {
      const response = await fetch(`${API_BASE}/diagnostics/data-range`);
      if (response.ok) {
        const result = await response.json();
        setDataRangeInfo(result);
        console.log('[Frontend] Data range:', result);
      }
    } catch (error) {
      console.error("Error checking data range:", error);
    }
  };

  const testCollectionDirectly = async () => {
    setTestingCollection(true);
    try {
      const response = await fetch(`${API_BASE}/diagnostics/test-collection`, { method: "POST" });
      if (response.ok) {
        const result = await response.json();
        setTestCollectionResult(result);
        console.log('[Frontend] Test collection result:', result);
      }
    } catch (error) {
      console.error("Error testing collection:", error);
    } finally {
      setTestingCollection(false);
    }
  };

  const tabs = [
    { id: "keywords", label: "Keywords", icon: <SearchIcon size={16} /> },
    { id: "ctr", label: "CTR Optimizer", icon: <TargetIcon size={16} /> },
    { id: "alerts", label: `Alerts (${alertSummary?.open_alerts || 0})`, icon: <AlertIcon size={16} /> },
    { id: "funnel", label: "GA4 Funnel", icon: <ChartIcon size={16} /> },
  ];

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical": return "bg-red-500";
      case "high": return "bg-orange-500";
      case "medium": return "bg-yellow-500";
      case "low": return "bg-blue-500";
      default: return "bg-zinc-500";
    }
  };

  const formatPercent = (value: number | undefined | null) => value != null ? `${(value * 100).toFixed(1)}%` : '-';
  const formatNumber = (value: number | undefined | null) => value != null ? value.toLocaleString() : '-';

  // ========================================================================
  // RENDER
  // ========================================================================

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-6">
      {/* Header */}
      <div className="mb-6">
        <Link href="/intelligence" className="inline-flex items-center gap-2 text-zinc-400 hover:text-white mb-4">
          <ArrowLeftIcon size={16} />
          Back to Intelligence
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold flex items-center gap-3">
              <SearchIcon size={28} className="text-[#F7B500]" />
              SEO Intelligence
            </h1>
            <p className="text-zinc-400 mt-1">Semrush-level keyword tracking, CTR optimization & alerts</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Time Period Selector */}
            <div className="flex items-center gap-2 bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-1">
              {[7, 30, 90].map((d) => (
                <button
                  key={`skel-${d}`}
                  onClick={() => setDays(d)}
                  className={`px-3 py-1.5 text-sm rounded-sm transition-colors ${
                    days === d
                      ? "bg-[#F7B500] text-black font-medium"
                      : "text-zinc-400 hover:text-white hover:bg-[#2a2a2a]"
                  }`}
                >
                  {d}d
                </button>
              ))}
            </div>
            <div className="text-right text-sm">
              <p className="text-zinc-400">Last collected</p>
              <p className="text-white">
                {collectionStatus?.harvested_at === "never" 
                  ? "Never" 
                  : collectionStatus?.harvested_at 
                    ? formatDateTime(collectionStatus.harvested_at)
                    : "-"}
              </p>
            </div>
            <Button
              onClick={runCollection}
              disabled={collecting}
              icon={collecting ? <SyncIcon size={16} className="animate-spin" /> : <SyncIcon size={16} />}
            >
              {collecting ? "Collecting..." : "Collect Now"}
            </Button>
          </div>
        </div>
      </div>

      {/* Debug Toggle */}
      <div className="mb-4 flex justify-end gap-2">
        <button
          onClick={checkDataRange}
          className="text-xs text-blue-500 hover:text-blue-300"
        >
          Check Data Range
        </button>
        <button
          onClick={() => setShowDebug(!showDebug)}
          className="text-xs text-zinc-500 hover:text-zinc-300"
        >
          {showDebug ? "Hide Debug" : "Show Debug"}
        </button>
      </div>

      {/* Data Range Info */}
      {dataRangeInfo && (
        <div className="mb-4 p-4 bg-blue-500/10 border border-blue-500/30 rounded-sm">
          <h4 className="font-medium mb-2 text-blue-400">Data Range Info</h4>
          <p className="text-sm text-zinc-300">
            Database has <strong>{dataRangeInfo.keyword_data?.unique_date_count}</strong> unique date(s) of data
          </p>
          <p className="text-xs text-zinc-400">
            Earliest: {dataRangeInfo.keyword_data?.earliest_date || 'N/A'} | 
            Latest: {dataRangeInfo.keyword_data?.latest_date || 'N/A'}
          </p>
          {dataRangeInfo.keyword_data?.all_dates && (
            <p className="text-xs text-zinc-500 mt-1">
              Dates: {dataRangeInfo.keyword_data.all_dates.join(', ')}
            </p>
          )}
          <p className="text-xs text-yellow-400 mt-2">
            {dataRangeInfo.keyword_data?.unique_date_count === 1 
              ? "⚠️ Only 1 day of data! Time period filters won't show different results until you collect data for multiple days."
              : "✅ Multiple days of data available. Time period filters should work correctly."}
          </p>
        </div>
      )}

      {/* Debug Panel */}
      {showDebug && (
        <div className="mb-4 p-4 bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm text-xs">
          <h4 className="font-medium mb-2 text-zinc-400">Debug Info</h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-zinc-500">Keywords array length: {keywords.length}</p>
              <p className="text-zinc-500">Position Summary: {positionSummary ? JSON.stringify(positionSummary) : 'null'}</p>
              <p className="text-zinc-500">Movers & Shakers: {moversShakers ? `gains: ${moversShakers.biggest_gains.length}, losses: ${moversShakers.biggest_losses.length}` : 'null'}</p>
            </div>
            <div>
              <p className="text-zinc-500">CTR Summary: {ctrSummary ? `opportunities: ${ctrSummary.total_underperforming}` : 'null'}</p>
              <p className="text-zinc-500">Alert Summary: {alertSummary ? `alerts: ${alertSummary.open_alerts}` : 'null'}</p>
              <p className="text-zinc-500">Funnel Data: {funnelData.length} records</p>
            </div>
          </div>
          {keywords.length > 0 && (
            <div className="mt-2">
              <p className="text-zinc-500">First keyword sample:</p>
              <pre className="text-[10px] text-zinc-400 overflow-x-auto">{JSON.stringify(keywords[0], null, 2)}</pre>
            </div>
          )}
        </div>
      )}

      {/* Collection Error */}
      {collectionError && (
        <div className="mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-sm">
          <p className="text-red-400 text-sm flex items-center gap-2">
            <WarningIcon size={16} />
            {collectionError}
          </p>
        </div>
      )}

      {/* Quick Stats */}
      {(positionSummary && !Array.isArray(positionSummary) ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Tracked Keywords</p>
            <p className="text-2xl font-bold">{formatNumber(positionSummary.total_tracked)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Improving ({days}d)</p>
            <p className="text-2xl font-bold text-green-400">{positionSummary.improving}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Declining ({days}d)</p>
            <p className="text-2xl font-bold text-red-400">{positionSummary.declining}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">CTR Opportunities ({days}d)</p>
            <p className="text-2xl font-bold text-[#F7B500]">{ctrSummary?.total_underperforming || 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Potential Clicks ({days}d)</p>
            <p className="text-2xl font-bold text-[#F7B500]">+{ctrSummary?.total_potential_clicks || 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Open Alerts ({days}d)</p>
            <p className={`text-2xl font-bold ${(alertSummary?.open_alerts || 0) > 0 ? "text-red-400" : "text-green-400"}`}>
              {alertSummary?.open_alerts || 0}
            </p>
          </Card>
        </div>
      ) : (
        // Fallback: show stats from keywords array when positionSummary is broken
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Tracked Keywords</p>
            <p className="text-2xl font-bold">{formatNumber(keywords.length)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Improving ({days}d)</p>
            <p className="text-2xl font-bold text-green-400">
              {keywords.filter(k => {
                const change = days <= 7 ? k.position_change_7d : k.position_change_30d;
                return change !== null && change !== undefined && change < -0.5;
              }).length}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Declining ({days}d)</p>
            <p className="text-2xl font-bold text-red-400">
              {keywords.filter(k => {
                const change = days <= 7 ? k.position_change_7d : k.position_change_30d;
                return change !== null && change !== undefined && change > 0.5;
              }).length}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">CTR Opportunities ({days}d)</p>
            <p className="text-2xl font-bold text-[#F7B500]">{ctrSummary?.total_underperforming || 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Potential Clicks ({days}d)</p>
            <p className="text-2xl font-bold text-[#F7B500]">+{ctrSummary?.total_potential_clicks || 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-400 uppercase">Open Alerts ({days}d)</p>
            <p className={`text-2xl font-bold ${(alertSummary?.open_alerts || 0) > 0 ? "text-red-400" : "text-green-400"}`}>
              {alertSummary?.open_alerts || 0}
            </p>
          </Card>
        </div>
      ))}

      {/* Tabs */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} className="mb-6" />

      {loading ? (
        <Card className="p-8 text-center">
          <SyncIcon size={32} className="animate-spin mx-auto mb-4 text-[#F7B500]" />
          <p className="text-zinc-400">Loading SEO intelligence data…</p>
        </Card>
      ) : (
        <>
          {/* ========== KEYWORDS TAB ========== */}
          {activeTab === "keywords" && (
            <div className="space-y-6">
              {/* Debug: Tab Active Indicator - Remove after debugging */}
              {showDebug && (
                <div className="p-2 bg-green-500/20 border border-green-500/50 rounded text-xs text-green-400">
                  Keywords Tab Active - {keywords.length} keywords loaded
                </div>
              )}
              
              {/* Movers & Shakers - Always show section */}
              <div className="mb-6">
                {moversShakers && (moversShakers.biggest_gains.length > 0 || moversShakers.biggest_losses.length > 0) ? (
                  <div className="grid md:grid-cols-2 gap-6">
                    <Card className="p-4">
                      <h3 className="font-semibold mb-4 flex items-center gap-2">
                        <TrendingUpIcon size={18} className="text-green-400" />
                        Biggest Gains ({days} days)
                      </h3>
                      <div className="space-y-2">
                        {moversShakers.biggest_gains.slice(0, 5).map((item) => (
                          <div key={item.query} className="flex items-center justify-between p-2 bg-[#1a1a1a] rounded">
                            <div className="flex-1">
                              <p className="font-medium truncate" style={{maxWidth: "200px"}}>{item.query}</p>
                              <p className="text-xs text-zinc-400">
                                {item.from_position.toFixed(1)} → {item.to_position.toFixed(1)}
                              </p>
                            </div>
                            <Badge variant="success">{item.change.toFixed(1)}</Badge>
                          </div>
                        ))}
                      </div>
                    </Card>
                    <Card className="p-4">
                      <h3 className="font-semibold mb-4 flex items-center gap-2">
                        <TrendingDownIcon size={18} className="text-red-400" />
                        Biggest Losses ({days} days)
                      </h3>
                      <div className="space-y-2">
                        {moversShakers.biggest_losses.slice(0, 5).map((item) => (
                          <div key={item.query} className="flex items-center justify-between p-2 bg-[#1a1a1a] rounded">
                            <div className="flex-1">
                              <p className="font-medium truncate" style={{maxWidth: "200px"}}>{item.query}</p>
                              <p className="text-xs text-zinc-400">
                                {item.from_position.toFixed(1)} → {item.to_position.toFixed(1)}
                              </p>
                            </div>
                            <Badge variant="danger">+{item.change.toFixed(1)}</Badge>
                          </div>
                        ))}
                      </div>
                    </Card>
                  </div>
                ) : (
                  <Card className="p-4 text-center">
                    <p className="text-zinc-400">No position changes detected in the last {days} days.</p>
                    <p className="text-sm text-zinc-500 mt-1">
                      {keywords.length > 0 && keywords.every(k => !k.position_change_7d && !k.position_change_30d)
                        ? "Position deltas not computed - need consecutive days of data. Run collection daily."
                        : "Keywords are stable - no significant gains or losses."}
                    </p>
                  </Card>
                )}
              </div>

              {/* Keywords Table */}
              <Card className="p-4">
                <h3 className="font-semibold mb-4">
                  All Tracked Keywords 
                  <span className="text-sm font-normal text-zinc-400 ml-2">({keywords.length} found)</span>
                </h3>
                {showDebug && (
                  <p className="text-xs text-zinc-500 mb-2">Table render: {keywords.length > 0 ? 'WITH DATA' : 'EMPTY'}</p>
                )}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-zinc-400 border-b border-[#3a3a3a]">
                        <th className="pb-2 pr-4">Query</th>
                        <th className="pb-2 px-4 text-right">Position</th>
                        <th className="pb-2 px-4 text-right">Change ({days}d)</th>
                        <th className="pb-2 px-4 text-right">Impressions</th>
                        <th className="pb-2 px-4 text-right">Clicks</th>
                        <th className="pb-2 px-4 text-right">CTR</th>
                        <th className="pb-2 px-4 text-right">CTR Gap</th>
                      </tr>
                    </thead>
                    <tbody>
                      {keywords.map((kw, idx) => (
                        <tr key={kw.query || `kw-${idx}`} className="border-b border-[#2a2a2a] hover:bg-[#1a1a1a]">
                          <td className="py-2 pr-4">
                            <div className="flex items-center gap-2">
                              {kw.is_underperforming && (
                                <WarningIcon size={14} className="text-[#F7B500]" />
                              )}
                              <span className="truncate" style={{maxWidth: "200px"}}>{kw.query}</span>
                            </div>
                          </td>
                          <td className="py-2 px-4 text-right font-medium">{kw.position.toFixed(1)}</td>
                          <td className="py-2 px-4 text-right">
                            {(() => {
                              const change = days <= 7 ? kw.position_change_7d : kw.position_change_30d;
                              return change !== null && change !== undefined ? (
                                <span className={change < 0 ? "text-green-400" : change > 0 ? "text-red-400" : "text-zinc-400"}>
                                  {change > 0 ? "+" : ""}{change.toFixed(1)}
                                </span>
                              ) : "-";
                            })()}
                          </td>
                          <td className="py-2 px-4 text-right">{formatNumber(kw.impressions)}</td>
                          <td className="py-2 px-4 text-right">{formatNumber(kw.clicks)}</td>
                          <td className="py-2 px-4 text-right">{formatPercent(kw.ctr)}</td>
                          <td className="py-2 px-4 text-right">
                            {kw.ctr_gap !== null && kw.ctr_gap !== undefined ? (
                              <span className={kw.ctr_gap < 0 ? "text-red-400" : "text-green-400"}>
                                {kw.ctr_gap > 0 ? "+" : ""}{formatPercent(kw.ctr_gap)}
                              </span>
                            ) : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {keywords.length === 0 && (
                  <div className="text-center text-zinc-400 py-8">
                    <p className="mb-2">No keyword data for the last {days} days.</p>
                    <p className="text-sm text-zinc-500">
                      Try selecting a shorter time period (7 days) or run collection to fetch new data.
                    </p>
                    <div className="mt-4 p-3 bg-[#1a1a1a] rounded text-left text-xs text-zinc-500 max-w-lg mx-auto">
                      <p className="font-medium text-zinc-400 mb-1">Debug Info:</p>
                      <p>• Collection Status: {collectionStatus?.status || 'unknown'}</p>
                      <p>• Last Collected: {collectionStatus?.harvested_at === 'never' ? 'Never' : collectionStatus?.harvested_at ? formatDate(collectionStatus.harvested_at) : 'Unknown'}</p>
                      <p>• Queries Stored: {collectionStatus?.queries_stored || 0}</p>
                      <p>• Selected Period: {days} days</p>
                    </div>
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* ========== CTR TAB ========== */}
          {activeTab === "ctr" && (
            <div className="space-y-6">
              {/* Summary Cards */}
              {ctrSummary && (
                <div className="grid md:grid-cols-3 gap-4">
                  <Card className="p-4">
                    <p className="text-xs text-zinc-400 uppercase">Underperforming Queries</p>
                    <p className="text-3xl font-bold text-[#F7B500]">{ctrSummary.total_underperforming}</p>
                    <p className="text-sm text-zinc-400">Queries below position-based CTR benchmark</p>
                  </Card>
                  <Card className="p-4">
                    <p className="text-xs text-zinc-400 uppercase">Potential Extra Clicks</p>
                    <p className="text-3xl font-bold text-green-400">+{ctrSummary.total_potential_clicks}</p>
                    <p className="text-sm text-zinc-400">If all queries hit benchmark CTR</p>
                  </Card>
                  <Card className="p-4">
                    <p className="text-xs text-zinc-400 uppercase">Average CTR Gap</p>
                    <p className="text-3xl font-bold text-red-400">{formatPercent(ctrSummary.avg_ctr_gap)}</p>
                    <p className="text-sm text-zinc-400">Negative = leaving clicks on the table</p>
                  </Card>
                </div>
              )}

              {/* By Position Bucket */}
              {ctrSummary?.by_position_bucket && (
                <Card className="p-4">
                  <h3 className="font-semibold mb-4">CTR Gaps by Position</h3>
                  <div className="grid md:grid-cols-4 gap-4">
                    {Object.entries(ctrSummary.by_position_bucket).map(([bucket, data]) => (
                      <div key={bucket} className="bg-[#1a1a1a] p-3 rounded">
                        <p className="text-xs text-zinc-400">Position {bucket}</p>
                        <p className="text-lg font-bold">{data.count} queries</p>
                        <p className="text-sm text-red-400">Gap: {formatPercent(data.avg_gap)}</p>
                        <p className="text-sm text-green-400">+{data.total_potential_clicks} clicks</p>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Top Opportunities Table */}
              <Card className="p-4">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <FireIcon size={18} className="text-[#F7B500]" />
                  Top CTR Optimization Opportunities
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-zinc-400 border-b border-[#3a3a3a]">
                        <th className="pb-2 pr-4">Query</th>
                        <th className="pb-2 px-4 text-right">Position</th>
                        <th className="pb-2 px-4 text-right">Actual CTR</th>
                        <th className="pb-2 px-4 text-right">Expected CTR</th>
                        <th className="pb-2 px-4 text-right">Gap</th>
                        <th className="pb-2 px-4 text-right">Impressions</th>
                        <th className="pb-2 px-4 text-right">Potential Clicks</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ctrSummary?.top_opportunities.map((item, idx) => (
                        <tr key={`${item.query}-${item.page_url || idx}`} className="border-b border-[#2a2a2a] hover:bg-[#1a1a1a]">
                          <td className="py-2 pr-4">
                            <p className="font-medium truncate" style={{maxWidth: "200px"}}>{item.query}</p>
                            {item.page_url && (
                              <p className="text-xs text-zinc-500 truncate" style={{maxWidth: "200px"}}>{item.page_url}</p>
                            )}
                          </td>
                          <td className="py-2 px-4 text-right">{item.position.toFixed(1)}</td>
                          <td className="py-2 px-4 text-right">{formatPercent(item.actual_ctr)}</td>
                          <td className="py-2 px-4 text-right text-zinc-400">{formatPercent(item.expected_ctr)}</td>
                          <td className="py-2 px-4 text-right text-red-400">{formatPercent(item.ctr_gap)}</td>
                          <td className="py-2 px-4 text-right">{formatNumber(item.impressions)}</td>
                          <td className="py-2 px-4 text-right text-green-400 font-medium">+{item.potential_extra_clicks}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {(!ctrSummary?.top_opportunities || ctrSummary.top_opportunities.length === 0) && (
                  <p className="text-center text-zinc-400 py-8">
                    All queries are performing at or above benchmark CTR!
                  </p>
                )}
              </Card>
            </div>
          )}

          {/* ========== ALERTS TAB ========== */}
          {activeTab === "alerts" && (
            <div className="space-y-6">
              {/* Summary */}
              {alertSummary && (
                <div className="grid md:grid-cols-4 gap-4">
                  <Card className="p-4">
                    <p className="text-xs text-zinc-400 uppercase">Open Alerts</p>
                    <p className="text-3xl font-bold">{alertSummary.open_alerts}</p>
                  </Card>
                  <Card className="p-4">
                    <p className="text-xs text-zinc-400 uppercase">Critical</p>
                    <p className="text-3xl font-bold text-red-400">{alertSummary.by_severity?.critical || 0}</p>
                  </Card>
                  <Card className="p-4">
                    <p className="text-xs text-zinc-400 uppercase">High</p>
                    <p className="text-3xl font-bold text-orange-400">{alertSummary.by_severity?.high || 0}</p>
                  </Card>
                  <Card className="p-4">
                    <p className="text-xs text-zinc-400 uppercase">Medium</p>
                    <p className="text-3xl font-bold text-yellow-400">{alertSummary.by_severity?.medium || 0}</p>
                  </Card>
                </div>
              )}

              {/* Recent Alerts */}
              <Card className="p-4">
                <h3 className="font-semibold mb-4">Recent Alerts</h3>
                <div className="space-y-3">
                  {alertSummary?.recent.map((alert) => (
                    <div 
                      key={alert.id} 
                      className={`p-4 rounded border-l-4 ${
                        alert.severity === "critical" ? "border-red-500 bg-red-500/10" :
                        alert.severity === "high" ? "border-orange-500 bg-orange-500/10" :
                        alert.severity === "medium" ? "border-yellow-500 bg-yellow-500/10" :
                        "border-blue-500 bg-blue-500/10"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant={
                              alert.severity === "critical" ? "danger" :
                              alert.severity === "high" ? "warning" :
                              "default"
                            }>
                              {alert.severity}
                            </Badge>
                            <Badge variant="info">{alert.alert_type.replace("_", " ")}</Badge>
                          </div>
                          <p className="font-medium">{alert.title}</p>
                          {alert.description && (
                            <p className="text-sm text-zinc-400 mt-1">{alert.description}</p>
                          )}
                        </div>
                        <p className="text-xs text-zinc-500">
                          {formatDateTime(alert.created_at)}
                        </p>
                      </div>
                    </div>
                  ))}
                  {(!alertSummary?.recent || alertSummary.recent.length === 0) && (
                    <p className="text-center text-zinc-400 py-8">
                      No alerts. Your SEO is healthy!
                    </p>
                  )}
                </div>
              </Card>
            </div>
          )}

          {/* ========== FUNNEL TAB ========== */}
          {activeTab === "funnel" && (
            <div className="space-y-6">
              {/* Debug: Tab Active Indicator */}
              {showDebug && (
                <div className="p-2 bg-blue-500/20 border border-blue-500/50 rounded text-xs text-blue-400">
                  Funnel Tab Active - {funnelData.length} records, 
                  Device categories: {funnelData.map(f => f.device_category).join(', ')}
                </div>
              )}
              
              <Card className="p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">GA4 Ecommerce Funnel (Last {days} Days)</h3>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => fetchData()}
                      className="text-xs px-2 py-1 bg-[#2a2a2a] hover:bg-[#3a3a3a] rounded text-zinc-300"
                    >
                      Refresh Data
                    </button>
                  </div>
                </div>
                {collectionStatus?.harvested_at && (
                  <p className="text-xs text-zinc-500 mb-3">
                    Last collected: {formatDateTime(collectionStatus.harvested_at)}
                    {funnelData.length > 0 && funnelData[0]?.date && (
                      <> | Funnel data date: {formatDate(funnelData[0].date)}</>
                    )}
                  </p>
                )}
                {funnelData.length > 0 ? (
                  <div className="space-y-4">
                    {/* Aggregate row - Use "all" if available, otherwise sum all devices */}
                    {(() => {
                      let allData = funnelData.filter(f => f.device_category === "all");
                      // If no "all" category, aggregate all device categories
                      if (allData.length === 0) {
                        allData = funnelData;
                      }
                      const total = allData.reduce((acc, f) => ({
                        sessions: acc.sessions + f.sessions,
                        product_views: acc.product_views + f.product_views,
                        add_to_carts: acc.add_to_carts + f.add_to_carts,
                        begin_checkouts: acc.begin_checkouts + f.begin_checkouts,
                        purchases: acc.purchases + f.purchases,
                        revenue: acc.revenue + f.revenue,
                      }), { sessions: 0, product_views: 0, add_to_carts: 0, begin_checkouts: 0, purchases: 0, revenue: 0 });
                      
                      return (
                        <div className="grid grid-cols-6 gap-4 p-4 bg-[#1a1a1a] rounded">
                          <div className="text-center">
                            <p className="text-xs text-zinc-400">Sessions</p>
                            <p className="text-xl font-bold">{formatNumber(total.sessions)}</p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-zinc-400">Product Views</p>
                            <p className="text-xl font-bold">{formatNumber(total.product_views)}</p>
                            <p className="text-xs text-zinc-500">{total.sessions > 0 ? ((total.product_views / total.sessions) * 100).toFixed(1) : 0}%</p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-zinc-400">Add to Cart</p>
                            <p className="text-xl font-bold">{formatNumber(total.add_to_carts)}</p>
                            <p className="text-xs text-zinc-500">{total.product_views > 0 ? ((total.add_to_carts / total.product_views) * 100).toFixed(1) : 0}%</p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-zinc-400">Checkout</p>
                            <p className="text-xl font-bold">{formatNumber(total.begin_checkouts)}</p>
                            <p className="text-xs text-zinc-500">{total.add_to_carts > 0 ? ((total.begin_checkouts / total.add_to_carts) * 100).toFixed(1) : 0}%</p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-zinc-400">Purchases</p>
                            <p className="text-xl font-bold text-green-400">{formatNumber(total.purchases)}</p>
                            <p className="text-xs text-zinc-500">{total.begin_checkouts > 0 ? ((total.purchases / total.begin_checkouts) * 100).toFixed(1) : 0}%</p>
                          </div>
                          <div className="text-center">
                            <p className="text-xs text-zinc-400">Revenue</p>
                            <p className="text-xl font-bold text-[#F7B500]">${(total.revenue || 0).toFixed(2)}</p>
                            <p className="text-xs text-zinc-500">{total.sessions > 0 ? ((total.purchases / total.sessions) * 100).toFixed(2) : 0}% conv</p>
                          </div>
                        </div>
                      );
                    })()}

                    {/* Funnel visualization */}
                    <div className="relative">
                      {(() => {
                        let allData = funnelData.filter(f => f.device_category === "all");
                        if (allData.length === 0) {
                          allData = funnelData;
                        }
                        const total = allData.reduce((acc, f) => ({
                          sessions: acc.sessions + f.sessions,
                          product_views: acc.product_views + f.product_views,
                          add_to_carts: acc.add_to_carts + f.add_to_carts,
                          begin_checkouts: acc.begin_checkouts + f.begin_checkouts,
                          purchases: acc.purchases + f.purchases,
                        }), { sessions: 0, product_views: 0, add_to_carts: 0, begin_checkouts: 0, purchases: 0 });
                        
                        const stages = [
                          { label: "Sessions", value: total.sessions, pct: 100 },
                          { label: "Product Views", value: total.product_views, pct: total.sessions > 0 ? (total.product_views / total.sessions) * 100 : 0 },
                          { label: "Add to Cart", value: total.add_to_carts, pct: total.sessions > 0 ? (total.add_to_carts / total.sessions) * 100 : 0 },
                          { label: "Checkout", value: total.begin_checkouts, pct: total.sessions > 0 ? (total.begin_checkouts / total.sessions) * 100 : 0 },
                          { label: "Purchase", value: total.purchases, pct: total.sessions > 0 ? (total.purchases / total.sessions) * 100 : 0 },
                        ];
                        
                        return stages.map((stage) => (
                          <div key={stage.label} className="mb-2">
                            <div className="flex items-center gap-4">
                              <p className="text-sm w-28 text-zinc-400">{stage.label}</p>
                              <div className="flex-1 bg-[#2a2a2a] rounded h-8 overflow-hidden">
                                <div 
                                  className="h-full bg-gradient-to-r from-[#F7B500] to-[#F7B500]/70 flex items-center px-3"
                                  style={{ width: `${Math.max(stage.pct, 2)}%` }}
                                >
                                  <span className="text-black text-sm font-medium">{formatNumber(stage.value)}</span>
                                </div>
                              </div>
                              <p className="text-sm w-16 text-right text-zinc-400">{stage.pct.toFixed(1)}%</p>
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
                    
                    {/* Device Breakdown */}
                    {funnelData.some(f => f.device_category !== "all") && (
                      <div className="mt-6">
                        <h4 className="font-medium mb-3 text-sm text-zinc-400">By Device Category</h4>
                        <div className="grid md:grid-cols-3 gap-4">
                          {Array.from(new Set(funnelData.map(f => f.device_category)))
                            .filter(cat => cat !== "all")
                            .map(device => {
                              const deviceData = funnelData.filter(f => f.device_category === device);
                              const total = deviceData.reduce((acc, f) => ({
                                sessions: acc.sessions + f.sessions,
                                purchases: acc.purchases + f.purchases,
                                revenue: acc.revenue + f.revenue,
                              }), { sessions: 0, purchases: 0, revenue: 0 });
                              
                              return (
                                <div key={device} className="p-3 bg-[#1a1a1a] rounded">
                                  <p className="text-xs text-zinc-400 capitalize">{device}</p>
                                  <p className="text-lg font-bold">{formatNumber(total.sessions)} sessions</p>
                                  <p className="text-sm text-green-400">{formatNumber(total.purchases)} purchases</p>
                                  <p className="text-xs text-zinc-500">${(total.revenue || 0).toFixed(2)} revenue</p>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-zinc-400 mb-2">
                      No funnel data for the selected period.
                    </p>
                    <p className="text-sm text-zinc-500 mb-4">
                      Click "Collect Now" at the top of the page to fetch fresh GA4 data.
                    </p>
                    <div className="flex justify-center gap-2">
                      <Button 
                        onClick={testGa4Connection} 
                        loading={testingGa4}
                        variant="outline"
                        icon={<DeviceIcon size={16} />}
                      >
                        Test GA4 Connection
                      </Button>
                    </div>
                  </div>
                )}

                {/* Test Collection Button */}
                <div className="mt-4 flex justify-center">
                  <Button 
                    onClick={testCollectionDirectly} 
                    loading={testingCollection}
                    variant="outline"
                    icon={<SyncIcon size={16} />}
                  >
                    Test Direct Collection
                  </Button>
                </div>

                {/* Test Collection Result */}
                {testCollectionResult && (
                  <div className="mt-4 p-4 bg-[#1a1a1a] rounded border border-[#3a3a3a]">
                    <h4 className="font-medium mb-3">Direct Collection Test Result</h4>
                    <p className="text-xs text-zinc-400 mb-2">Target Date: {testCollectionResult.target_date}</p>
                    
                    {testCollectionResult.ecommerce_metrics?.totals && (
                      <div className="mb-4">
                        <h5 className="text-sm font-medium text-zinc-300 mb-2">Ecommerce Metrics</h5>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                          <div className="p-2 bg-[#2a2a2a] rounded">
                            <p className="text-zinc-400">Sessions</p>
                            <p className="text-white">{testCollectionResult.ecommerce_metrics.totals.sessions?.toLocaleString()}</p>
                          </div>
                          <div className="p-2 bg-[#2a2a2a] rounded">
                            <p className="text-zinc-400">Views</p>
                            <p className="text-white">{testCollectionResult.ecommerce_metrics.totals.views?.toLocaleString()}</p>
                          </div>
                          <div className="p-2 bg-[#2a2a2a] rounded">
                            <p className="text-zinc-400">Add to Cart</p>
                            <p className={testCollectionResult.ecommerce_metrics.totals.add_carts > 0 ? "text-green-400" : "text-red-400"}>
                              {testCollectionResult.ecommerce_metrics.totals.add_carts?.toLocaleString()}
                            </p>
                          </div>
                          <div className="p-2 bg-[#2a2a2a] rounded">
                            <p className="text-zinc-400">Checkout</p>
                            <p className={testCollectionResult.ecommerce_metrics.totals.checkouts > 0 ? "text-green-400" : "text-red-400"}>
                              {testCollectionResult.ecommerce_metrics.totals.checkouts?.toLocaleString()}
                            </p>
                          </div>
                          <div className="p-2 bg-[#2a2a2a] rounded">
                            <p className="text-zinc-400">Purchases</p>
                            <p className="text-white">{testCollectionResult.ecommerce_metrics.totals.purchases?.toLocaleString()}</p>
                          </div>
                          <div className="p-2 bg-[#2a2a2a] rounded">
                            <p className="text-zinc-400">Revenue</p>
                            <p className="text-white">${testCollectionResult.ecommerce_metrics.totals.revenue?.toFixed(2)}</p>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {testCollectionResult.event_metrics && (
                      <div className="mb-4">
                        <h5 className="text-sm font-medium text-zinc-300 mb-2">Event-Based Metrics (Fallback)</h5>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {Object.entries(testCollectionResult.event_metrics).map(([event, data]: [string, any]) => (
                            <div key={event} className="p-2 bg-[#2a2a2a] rounded flex justify-between">
                              <span className="text-zinc-400">{event}</span>
                              <span className={data.total > 0 ? "text-green-400" : "text-red-400"}>
                                {data.total?.toLocaleString()}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {testCollectionResult.combined_result && (
                      <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded">
                        <h5 className="text-sm font-medium text-blue-400 mb-2">What Collector Would Use</h5>
                        <p className="text-xs text-zinc-300">
                          Using Event Fallback: {testCollectionResult.combined_result.use_event_fallback ? "YES" : "NO"}
                        </p>
                        <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                          <div>Add to Carts: <span className="text-green-400">{testCollectionResult.combined_result.final_add_to_carts}</span></div>
                          <div>Checkouts: <span className="text-green-400">{testCollectionResult.combined_result.final_checkouts}</span></div>
                          <div>Purchases: <span className="text-white">{testCollectionResult.combined_result.final_purchases}</span></div>
                          <div>Revenue: <span className="text-white">${testCollectionResult.combined_result.final_revenue?.toFixed(2)}</span></div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* GA4 Diagnostics */}
                {ga4Diagnostics && (
                  <div className="mt-4 p-4 bg-[#1a1a1a] rounded border border-[#3a3a3a]">
                    <h4 className="font-medium mb-3">GA4 Connection Diagnostics</h4>
                    <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                      <div>
                        <p className="text-zinc-400">Credentials File</p>
                        <p className={ga4Diagnostics.credentials_exist ? "text-green-400" : "text-red-400"}>
                          {ga4Diagnostics.credentials_exist ? "✓ Found" : "✗ Not Found"}
                        </p>
                      </div>
                      <div>
                        <p className="text-zinc-400">GA4 Property ID</p>
                        <p className={ga4Diagnostics.ga4_property_id ? "text-green-400" : "text-red-400"}>
                          {ga4Diagnostics.ga4_property_id || "Not Set"}
                        </p>
                      </div>
                      <div>
                        <p className="text-zinc-400">Credentials Loaded</p>
                        <p className={ga4Diagnostics.credentials_loaded ? "text-green-400" : "text-red-400"}>
                          {ga4Diagnostics.credentials_loaded ? "✓ Yes" : "✗ No"}
                        </p>
                      </div>
                      <div>
                        <p className="text-zinc-400">Property Accessible</p>
                        <p className={ga4Diagnostics.property_accessible ? "text-green-400" : "text-red-400"}>
                          {ga4Diagnostics.property_accessible ? "✓ Yes" : "✗ No"}
                        </p>
                      </div>
                    </div>
                    
                    {/* Ecommerce Metrics Status */}
                    {ga4Diagnostics.ecommerce_metrics && Object.keys(ga4Diagnostics.ecommerce_metrics).length > 0 && (
                      <div className="mt-4">
                        <h5 className="text-sm font-medium mb-2 text-zinc-300">Ecommerce Metrics (Last 7 Days)</h5>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {Object.entries(ga4Diagnostics.ecommerce_metrics).map(([key, metric]: [string, any]) => (
                            <div key={key} className="flex items-center justify-between p-2 bg-[#2a2a2a] rounded">
                              <span className="text-zinc-400">{metric.label}</span>
                              <span className={metric.status === 'available' ? 'text-green-400' : 'text-red-400'}>
                                {metric.status === 'available' 
                                  ? metric['7_day_total']?.toLocaleString() || '0'
                                  : '✗ Error'
                                }
                              </span>
                            </div>
                          ))}
                        </div>
                        <p className="text-xs text-zinc-500 mt-2">
                          If Add to Cart and Checkout show 0 but Purchases show data, 
                          your GA4 may not have enhanced ecommerce properly configured.
                        </p>
                      </div>
                    )}
                    
                    {ga4Diagnostics.error && (
                      <div className="mt-4">
                        <p className="text-zinc-400">Error</p>
                        <p className="text-red-400 text-xs">{ga4Diagnostics.error}</p>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
