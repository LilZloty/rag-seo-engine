"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card } from "@/app/components/ui/Card";
import { Button } from "@/app/components/ui/Button";
import { Badge } from "@/app/components/ui/Badge";
import { Tabs } from "@/app/components/ui/Tabs";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  ChartIcon,
  ClockIcon,
  DatabaseIcon,
  FireIcon,
  GearIcon,
  SearchIcon,
  SparklesIcon,
  SyncIcon,
  TrendingUpIcon,
  WarningIcon,
} from "@/app/components/ui/Icons";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

type OpportunityType =
  | "transmission_demand_gap"
  | "query_demand_gap"
  | "latent_inventory"
  | "marketing_gap";

type OpportunityStatus =
  | "open"
  | "investigating"
  | "in_progress"
  | "resolved"
  | "dismissed";

type OpportunityPriority = "high" | "medium" | "low";

interface GeneratedCopy {
  meta_title: string;
  meta_description: string;
  rationale: string;
  generated_at: string;
  provider?: string | null;
}

interface Opportunity {
  id: string;
  created_at: string;
  last_seen_at: string;
  opportunity_type: OpportunityType;
  priority: OpportunityPriority;
  target_type: string;
  target_transmission_code: string | null;
  target_vehicle_brand: string | null;
  target_product_id: string | null;
  target_query: string | null;
  signal_data: Record<string, any> & { _generated_copy?: GeneratedCopy };
  opportunity_score: number;
  estimated_monthly_sessions: number | null;
  estimated_monthly_revenue: number | null;
  title: string;
  description: string | null;
  recommended_action: string | null;
  action_steps: string[];
  status: OpportunityStatus;
  notes: string | null;
  resolved_at: string | null;
  dismissed_at: string | null;
}

interface ListResponse {
  total: number;
  counts_by_type: Record<string, number>;
  counts_by_priority: Record<string, number>;
  counts_by_status: Record<string, number>;
  opportunities: Opportunity[];
}

const TYPE_META: Record<
  OpportunityType,
  { label: string; icon: any; color: string; description: string }
> = {
  transmission_demand_gap: {
    label: "Demanda sin oferta",
    icon: SparklesIcon,
    color: "text-purple-400",
    description: "Búsquedas de transmisiones que no vendemos",
  },
  query_demand_gap: {
    label: "Búsqueda sin match",
    icon: SearchIcon,
    color: "text-blue-400",
    description: "Queries con impresiones que el catálogo no cubre",
  },
  latent_inventory: {
    label: "Inventario invisible",
    icon: DatabaseIcon,
    color: "text-orange-400",
    description: "Productos que venden pero no aparecen en búsqueda",
  },
  marketing_gap: {
    label: "Listing débil",
    icon: ChartIcon,
    color: "text-yellow-400",
    description: "Impresiones altas pero CTR bajo",
  },
};

const PRIORITY_VARIANT: Record<OpportunityPriority, "danger" | "warning" | "info"> = {
  high: "danger",
  medium: "warning",
  low: "info",
};

const STATUS_LABEL: Record<OpportunityStatus, string> = {
  open: "Abierto",
  investigating: "Investigando",
  in_progress: "En progreso",
  resolved: "Resuelto",
  dismissed: "Descartado",
};

function formatCurrencyMXN(value: number | null | undefined): string {
  if (!value) return "—";
  return `$${value.toLocaleString("es-MX", { maximumFractionDigits: 0 })}`;
}

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `hace ${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return `hace ${days}d`;
}

export default function OpportunitiesPage() {
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeType, setActiveType] = useState<OpportunityType | "all">("all");
  const [statusFilter, setStatusFilter] = useState<OpportunityStatus>("open");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  async function fetchOpportunities() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        status: statusFilter,
        limit: "200",
      });
      if (activeType !== "all") params.set("opportunity_type", activeType);

      const res = await fetch(
        `${API_BASE}/creative-intelligence/opportunities?${params.toString()}`
      );
      if (!res.ok) throw new Error("Failed to fetch opportunities");
      const json = (await res.json()) as ListResponse;
      setData(json);
    } catch (e) {
      console.error("Failed to fetch opportunities", e);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  async function refreshDetection() {
    setRefreshing(true);
    try {
      const res = await fetch(
        `${API_BASE}/creative-intelligence/opportunities/refresh?days=30`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Refresh failed");
      await fetchOpportunities();
    } catch (e) {
      console.error("Refresh failed", e);
    } finally {
      setRefreshing(false);
    }
  }

  async function updateStatus(id: string, status: OpportunityStatus) {
    try {
      const res = await fetch(`${API_BASE}/creative-intelligence/opportunities/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error("Update failed");
      await fetchOpportunities();
    } catch (e) {
      console.error("Update failed", e);
    }
  }

  useEffect(() => {
    fetchOpportunities();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeType, statusFilter]);

  const totalRevenue = useMemo(() => {
    if (!data) return 0;
    return data.opportunities.reduce(
      (sum, o) => sum + (o.estimated_monthly_revenue || 0),
      0
    );
  }, [data]);

  const tabs = useMemo(() => {
    const counts = data?.counts_by_type || {};
    return [
      { id: "all", label: `Todas (${data?.total ?? 0})` },
      ...(Object.keys(TYPE_META) as OpportunityType[]).map((t) => ({
        id: t,
        label: `${TYPE_META[t].label} (${counts[t] ?? 0})`,
      })),
    ];
  }, [data]);

  return (
    <main
      className="min-h-screen bg-[#0a0a0a] text-white p-6 space-y-6"
      aria-busy={loading || refreshing}
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm text-zinc-400 mb-1">
            <Link href="/intelligence" className="hover:text-[#F7B500] flex items-center gap-1">
              <ArrowLeftIcon size={14} /> Intelligence
            </Link>
            <span aria-hidden="true">/</span>
            <span>Oportunidades</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-semibold">Oportunidades Creativas</h1>
          <p className="text-zinc-400">
            Brechas de demanda y activos infrautilizados detectados a partir de GSC, GA4 y catálogo.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchOpportunities} icon={<SyncIcon size={16} />}>
            Recargar
          </Button>
          <Button
            onClick={refreshDetection}
            loading={refreshing}
            icon={<FireIcon size={16} />}
          >
            {refreshing ? "Detectando..." : "Re-detectar"}
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {(Object.keys(TYPE_META) as OpportunityType[]).map((type) => {
          const meta = TYPE_META[type];
          const count = data?.counts_by_type[type] ?? 0;
          const Icon = meta.icon;
          const isActive = activeType === type;
          return (
            <button
              key={type}
              type="button"
              onClick={() => setActiveType(type)}
              aria-pressed={isActive}
              aria-label={`Filtrar por ${meta.label} (${count} oportunidades)`}
              className="text-left rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0a]"
            >
              <Card
                accent={isActive}
                className="cursor-pointer hover:border-[#F7B500] transition-colors h-full"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-zinc-400">{meta.label}</p>
                    <p className={`text-3xl font-semibold mt-1 ${meta.color}`}>{count}</p>
                    <p className="text-xs text-zinc-400 mt-2 leading-tight">{meta.description}</p>
                  </div>
                  <Icon size={32} className={meta.color} aria-hidden="true" />
                </div>
              </Card>
            </button>
          );
        })}
      </div>

      {/* Aggregate impact */}
      {data && data.total > 0 && (
        <Card accent className="border-[#F7B500]/30">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <TrendingUpIcon size={28} className="text-green-400" />
              <div>
                <p className="text-sm text-zinc-400">Impacto mensual estimado total (status: {STATUS_LABEL[statusFilter]})</p>
                <p className="text-2xl font-bold text-green-400">
                  {formatCurrencyMXN(totalRevenue)} MXN/mes
                </p>
              </div>
            </div>
            <div className="text-sm text-zinc-400">
              Distribución: {Object.entries(data.counts_by_priority).map(([p, n]) => `${n} ${p}`).join(" · ") || "—"}
            </div>
          </div>
        </Card>
      )}

      {/* Filters */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Tabs
          tabs={tabs}
          activeTab={activeType}
          onChange={(id) => setActiveType(id as OpportunityType | "all")}
        />
        <div className="flex gap-2" role="group" aria-label="Filtrar por estado">
          {(["open", "in_progress", "resolved", "dismissed"] as OpportunityStatus[]).map((s) => (
            <Button
              key={s}
              variant={statusFilter === s ? "primary" : "ghost"}
              size="sm"
              onClick={() => setStatusFilter(s)}
              aria-pressed={statusFilter === s}
            >
              {STATUS_LABEL[s]}
            </Button>
          ))}
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3" aria-label="Cargando oportunidades" role="status">
          {["sk-1", "sk-2", "sk-3", "sk-4"].map((key) => (
            <Card key={key} className="animate-pulse">
              <div className="h-4 bg-[#3a3a3a] rounded w-1/2 mb-3" />
              <div className="h-3 bg-[#3a3a3a] rounded w-3/4 mb-2" />
              <div className="h-3 bg-[#3a3a3a] rounded w-2/3" />
            </Card>
          ))}
        </div>
      ) : !data || data.opportunities.length === 0 ? (
        <Card className="text-center py-12">
          <SparklesIcon size={48} className="text-zinc-600 mx-auto mb-4" />
          <p className="text-lg font-medium mb-1">
            {statusFilter === "open"
              ? "No hay oportunidades abiertas"
              : `No hay oportunidades en estado ${STATUS_LABEL[statusFilter]}`}
          </p>
          <p className="text-sm text-zinc-400 mb-6">
            {statusFilter === "open"
              ? "Ejecuta una detección para encontrar brechas de demanda."
              : "Cambia el filtro de estado para ver otras oportunidades."}
          </p>
          {statusFilter === "open" && (
            <Button
              onClick={refreshDetection}
              loading={refreshing}
              icon={<FireIcon size={16} />}
            >
              Re-detectar oportunidades
            </Button>
          )}
        </Card>
      ) : (
        <div
          className="space-y-3"
          aria-live="polite"
          aria-label={`${data.total} oportunidades`}
        >
          {data.opportunities.map((opp) => (
            <OpportunityCard
              key={opp.id}
              opportunity={opp}
              expanded={expandedId === opp.id}
              onToggle={() => setExpandedId(expandedId === opp.id ? null : opp.id)}
              onStatusChange={(status) => updateStatus(opp.id, status)}
              onCopyGenerated={(id, copy) => {
                setData((prev) => {
                  if (!prev) return prev;
                  return {
                    ...prev,
                    opportunities: prev.opportunities.map((o) =>
                      o.id === id
                        ? { ...o, signal_data: { ...o.signal_data, _generated_copy: copy } }
                        : o
                    ),
                  };
                });
              }}
            />
          ))}
        </div>
      )}
    </main>
  );
}

function OpportunityCard({
  opportunity,
  expanded,
  onToggle,
  onStatusChange,
  onCopyGenerated,
}: {
  opportunity: Opportunity;
  expanded: boolean;
  onToggle: () => void;
  onStatusChange: (status: OpportunityStatus) => void;
  onCopyGenerated: (id: string, copy: GeneratedCopy) => void;
}) {
  const meta = TYPE_META[opportunity.opportunity_type];
  const Icon = meta.icon;
  const isOpen = opportunity.status === "open" || opportunity.status === "investigating";
  const supportsCopy =
    opportunity.opportunity_type === "marketing_gap" ||
    opportunity.opportunity_type === "latent_inventory";
  const existingCopy: GeneratedCopy | undefined = (opportunity.signal_data || {})._generated_copy;
  const [generatingCopy, setGeneratingCopy] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<"title" | "description" | null>(null);

  // Confirmation toast clears itself so the user gets feedback without managing it manually.
  useEffect(() => {
    if (!copiedField) return;
    const t = setTimeout(() => setCopiedField(null), 1500);
    return () => clearTimeout(t);
  }, [copiedField]);

  async function copyToClipboard(text: string, field: "title" | "description") {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
    } catch {
      setCopyError("No se pudo copiar al portapapeles");
    }
  }

  async function generateCopy() {
    setGeneratingCopy(true);
    setCopyError(null);
    try {
      const res = await fetch(
        `${API_BASE}/creative-intelligence/opportunities/${opportunity.id}/generate-copy`,
        { method: "POST" }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `HTTP ${res.status}`);
      }
      const copy = (await res.json()) as GeneratedCopy;
      onCopyGenerated(opportunity.id, copy);
    } catch (e: any) {
      setCopyError(e?.message ?? "Error generando copy");
    } finally {
      setGeneratingCopy(false);
    }
  }

  return (
    <Card
      className={`border-l-4 ${
        opportunity.priority === "high"
          ? "border-l-red-500"
          : opportunity.priority === "medium"
          ? "border-l-yellow-500"
          : "border-l-blue-500"
      }`}
    >
      <div className="flex flex-col gap-3">
        {/* Top row: badges + score */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={PRIORITY_VARIANT[opportunity.priority]}>
              {opportunity.priority.toUpperCase()}
            </Badge>
            <Badge variant="brand" className="flex items-center gap-1">
              <Icon size={12} />
              {meta.label}
            </Badge>
            {opportunity.target_transmission_code && (
              <Badge variant="default">{opportunity.target_transmission_code}</Badge>
            )}
            {opportunity.target_vehicle_brand && (
              <Badge variant="default">{opportunity.target_vehicle_brand}</Badge>
            )}
            {!isOpen && (
              <Badge variant="info">{STATUS_LABEL[opportunity.status]}</Badge>
            )}
          </div>
          <div className="text-right">
            <p className="text-xs text-zinc-400">Score</p>
            <p className="text-2xl font-bold text-[#F7B500]">
              {Math.round(opportunity.opportunity_score)}
            </p>
          </div>
        </div>

        {/* Title + description */}
        <div>
          <h3 className="font-semibold text-lg">{opportunity.title}</h3>
          {opportunity.description && (
            <p className="text-sm text-zinc-400 mt-1">{opportunity.description}</p>
          )}
        </div>

        {/* Impact */}
        <div className="flex items-center gap-4 flex-wrap text-sm">
          {opportunity.estimated_monthly_revenue ? (
            <div className="flex items-center gap-1 text-green-400">
              <TrendingUpIcon size={14} />
              <span className="font-medium">
                +{formatCurrencyMXN(opportunity.estimated_monthly_revenue)} MXN/mes est.
              </span>
            </div>
          ) : null}
          {opportunity.estimated_monthly_sessions ? (
            <div className="flex items-center gap-1 text-blue-400">
              <ChartIcon size={14} />
              <span>+{opportunity.estimated_monthly_sessions.toLocaleString()} sesiones est.</span>
            </div>
          ) : null}
          <div className="flex items-center gap-1 text-zinc-400">
            <ClockIcon size={14} />
            <span>{relativeTime(opportunity.last_seen_at)}</span>
          </div>
        </div>

        {/* Expandable detail */}
        <div className="flex items-center justify-between border-t border-[#3a3a3a] pt-3 flex-wrap gap-2">
          <Button variant="ghost" size="sm" onClick={onToggle} icon={<ArrowRightIcon size={14} />}>
            {expanded ? "Ocultar detalle" : "Ver acciones recomendadas"}
          </Button>
          <div className="flex gap-2 flex-wrap">
            {supportsCopy && (
              <Button
                variant="outline"
                size="sm"
                loading={generatingCopy}
                onClick={generateCopy}
                icon={<SparklesIcon size={14} />}
              >
                {existingCopy ? "Regenerar copy" : "Generar copy sugerido"}
              </Button>
            )}
            {isOpen && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onStatusChange("in_progress")}
                  icon={<GearIcon size={14} />}
                >
                  En progreso
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onStatusChange("resolved")}
                  icon={<CheckIcon size={14} />}
                >
                  Resolver
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onStatusChange("dismissed")}
                  icon={<WarningIcon size={14} />}
                >
                  Descartar
                </Button>
              </>
            )}
          </div>
        </div>

        {copyError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-sm p-2 text-sm text-red-400">
            {copyError}
          </div>
        )}

        {existingCopy && (
          <div className="bg-[#F7B500]/10 border border-[#F7B500]/30 rounded-sm p-3 space-y-2">
            <div className="flex items-center gap-2">
              <SparklesIcon size={14} className="text-[#F7B500]" />
              <p className="text-xs uppercase tracking-wider text-[#F7B500] font-semibold">
                Copy sugerido por IA
              </p>
              <span className="text-xs text-zinc-400 ml-auto">
                {relativeTime(existingCopy.generated_at)}
                {existingCopy.provider ? ` · ${existingCopy.provider}` : ""}
              </span>
            </div>
            <div>
              <p className="text-xs text-zinc-400">Meta title ({existingCopy.meta_title.length}/70)</p>
              <p className="text-sm font-medium text-white">{existingCopy.meta_title}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-400">
                Meta description ({existingCopy.meta_description.length}/160)
              </p>
              <p className="text-sm text-zinc-300">{existingCopy.meta_description}</p>
            </div>
            {existingCopy.rationale && (
              <div>
                <p className="text-xs text-zinc-400">Por qué</p>
                <p className="text-sm text-zinc-400 italic">{existingCopy.rationale}</p>
              </div>
            )}
            <div className="flex gap-2 pt-1 items-center" role="group" aria-label="Copiar copy">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => copyToClipboard(existingCopy.meta_title, "title")}
                icon={copiedField === "title" ? <CheckIcon size={14} /> : undefined}
              >
                {copiedField === "title" ? "Copiado" : "Copiar título"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => copyToClipboard(existingCopy.meta_description, "description")}
                icon={copiedField === "description" ? <CheckIcon size={14} /> : undefined}
              >
                {copiedField === "description" ? "Copiado" : "Copiar descripción"}
              </Button>
              {copiedField && (
                <span role="status" aria-live="polite" className="sr-only">
                  {copiedField === "title" ? "Título copiado" : "Descripción copiada"}
                </span>
              )}
            </div>
          </div>
        )}

        {expanded && (
          <div className="space-y-3 pt-2 border-t border-[#3a3a3a]">
            {opportunity.recommended_action && (
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">Acción recomendada</p>
                <p className="text-sm text-zinc-300">{opportunity.recommended_action}</p>
              </div>
            )}
            {opportunity.action_steps && opportunity.action_steps.length > 0 && (
              <div>
                <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">Pasos</p>
                <ul className="space-y-1">
                  {opportunity.action_steps.map((step) => (
                    <li key={step} className="text-sm flex items-start gap-2 text-zinc-300">
                      <ArrowRightIcon size={14} className="mt-1 text-[#F7B500] shrink-0" aria-hidden="true" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <SignalDetail opportunity={opportunity} />
          </div>
        )}
      </div>
    </Card>
  );
}

function SignalDetail({ opportunity }: { opportunity: Opportunity }) {
  const signal = opportunity.signal_data || {};
  const entries = Object.entries(signal).filter(
    ([key]) => !["matched_queries", "top_matches"].includes(key) && !key.startsWith("_")
  );

  return (
    <div>
      <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">Señales</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {entries.map(([key, value]) => (
          <div key={key} className="bg-[#1a1a1a] rounded p-2">
            <p className="text-xs text-zinc-400 capitalize">{key.replace(/_/g, " ")}</p>
            <p className="text-sm font-medium">
              {typeof value === "number"
                ? value.toLocaleString("es-MX", { maximumFractionDigits: 2 })
                : String(value)}
            </p>
          </div>
        ))}
      </div>

      {Array.isArray(signal.matched_queries) && signal.matched_queries.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">Queries que matchean</p>
          <ul className="space-y-1 text-sm">
            {signal.matched_queries.slice(0, 5).map((q: any) => (
              <li
                key={q.query ?? q.id ?? `${q.impressions}-${q.position}`}
                className="flex items-center justify-between bg-[#1a1a1a] rounded px-2 py-1"
              >
                <span className="text-zinc-300 truncate flex-1">{q.query}</span>
                <span className="text-xs text-zinc-400 ml-2">
                  {q.impressions?.toLocaleString()} impr · pos {q.position?.toFixed?.(1) ?? q.position}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {Array.isArray(signal.top_matches) && signal.top_matches.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">
            Productos más parecidos en catálogo (similaridad)
          </p>
          <ul className="space-y-1 text-sm">
            {signal.top_matches.slice(0, 3).map((m: any) => (
              <li
                key={m.product_id ?? m.handle ?? m.title}
                className="flex items-center justify-between bg-[#1a1a1a] rounded px-2 py-1"
              >
                <span className="text-zinc-300 truncate flex-1">{m.title}</span>
                <span className="text-xs text-zinc-400 ml-2">
                  {(m.score * 100).toFixed(0)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
