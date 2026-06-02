"use client";

import { useEffect, useState } from "react";
import { formatDate } from "@/app/lib/dates";
import { Card } from "@/app/components/ui/Card";
import { Button } from "@/app/components/ui/Button";
import { Badge } from "@/app/components/ui/Badge";
import { ProgressBar } from "@/app/components/ui/ProgressBar";
import { Tabs } from "@/app/components/ui/Tabs";
import Link from "next/link";
import {
  TrendingUpIcon,
  TrendingDownIcon,
  WarningIcon,
  SparklesIcon,
  ChartIcon,
  GlobeIcon,
  ShoppingCartIcon,
  SearchIcon,
  ChipIcon,
  SyncIcon,
  CheckIcon,
  ClockIcon,
  ArrowRightIcon,
  FireIcon,
  GearIcon,
  DatabaseIcon,
  ArrowLeftIcon
} from "@/app/components/ui/Icons";

// Types
interface ScoreDetails {
  commerce?: {
    revenue_30d: number;
    aov: number;
    orders_30d: number;
    top_products_count: number;
    slow_movers_count: number;
    calculation: string;
  };
  cro?: {
    conversion_rate: number;
    cart_abandonment: number;
    target_rate: number;
    calculation: string;
  };
  seo?: {
    avg_position: number;
    avg_ctr: number;
    products_optimized: number;
    products_needing_seo: number;
    indexed_pages: number;
    calculation: string;
  };
  geo?: {
    grok_score: number;
    openai_score: number;
    perplexity_score: number;
    total_citations: number;
    llm_traffic: number;
    calculation: string;
  };
  technical?: {
    cwv_status: string;
    lcp: number;
    cls: number;
    schema_coverage: number;
    calculation: string;
  };
}

interface HealthScore {
  overall: number;
  trend: string;
  breakdown: {
    commerce: number;
    cro: number;
    seo: number;
    geo: number;
    technical: number;
  };
  details?: ScoreDetails;
}

interface CriticalIssue {
  category: string;
  severity: string;
  title: string;
  description: string;
  impact: string;
  action: string;
}

interface Opportunity {
  category: string;
  title: string;
  description: string;
  potential_impact: string;
  effort: string;
}

interface AIRecommendation {
  id: string;
  category: string;
  priority: string;
  title: string;
  description: string;
  revenue_impact: string;
  traffic_impact: string;
  effort_required: string;
  action_steps: string[];
  confidence_score: number;
  status: string;
}

interface DashboardData {
  health: HealthScore;
  summary: string;
  critical_issues: CriticalIssue[];
  opportunities: Opportunity[];
  weekly_focus: any[];
  ai_recommendations: AIRecommendation[];
  quick_stats: {
    total_products: number;
    products_optimized: number;
    pending_recommendations: number;
  };
  seo_data?: {
    intelligence_preview?: {
      has_data: boolean;
      keywords_tracked: number;
      keywords_improving: number;
      keywords_declining: number;
      open_alerts: number;
      ctr_opportunities: number;
      potential_clicks: number;
      last_collection?: string;
    };
  };
  traffic_data?: {
    cro_preview?: {
      has_data?: boolean;
      sessions?: number;
      purchases?: number;
      conversion_rate?: number;
      revenue?: number;
      biggest_dropoff?: {
        step: string;
        rate: number;
      };
      device_breakdown?: Record<string, { share: number; conversion: number }>;
    };
  };
}

// Icon mapper using existing icons
const CategoryIcon = ({ category, size = 16 }: { category: string; size?: number }) => {
  switch (category) {
    case "COMMERCE":
      return <ShoppingCartIcon size={size} />;
    case "CRO":
      return <ChartIcon size={size} />;
    case "SEO":
      return <SearchIcon size={size} />;
    case "GEO":
      return <DatabaseIcon size={size} />;
    case "TECHNICAL":
      return <ChipIcon size={size} />;
    case "B2B":
      return <ShoppingCartIcon size={size} />;
    case "CONTENT":
      return <GlobeIcon size={size} />;
    default:
      return <GearIcon size={size} />;
  }
};

// Score breakdown card component
const ScoreBreakdownCard = ({
  title,
  score,
  icon: Icon,
  details,
  recommendations,
  link
}: {
  title: string;
  score: number;
  icon: any;
  details?: any;
  recommendations?: string[];
  link?: { href: string; label: string };
}) => {
  const getScoreColor = (s: number) => {
    if (s >= 80) return "text-green-400";
    if (s >= 60) return "text-yellow-400";
    if (s >= 40) return "text-orange-400";
    return "text-red-400";
  };

  const getScoreBg = (s: number) => {
    if (s >= 80) return "bg-green-500";
    if (s >= 60) return "bg-yellow-500";
    if (s >= 40) return "bg-orange-500";
    return "bg-red-500";
  };

  return (
    <Card className="h-full">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${getScoreBg(score)}/20`}>
            <Icon size={24} className={getScoreColor(score)} />
          </div>
          <div>
            <h3 className="font-semibold text-lg">{title}</h3>
            <p className="text-sm text-zinc-400">Score: <span className={`font-bold ${getScoreColor(score)}`}>{score}/100</span></p>
          </div>
        </div>
        <div className={`text-3xl font-bold ${getScoreColor(score)}`}>{score}</div>
      </div>

      <ProgressBar value={score} size="md" className="mb-4" />

      {details && (
        <div className="space-y-3 mb-4">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">Based On</p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {Object.entries(details).filter(([key]) => key !== 'calculation').map(([key, value]) => (
              <div key={key} className="bg-[#2a2a2a] rounded p-2">
                <p className="text-xs text-zinc-400 capitalize">{key.replace(/_/g, ' ')}</p>
                <p className="font-medium">
                  {typeof value === 'number' ? value.toLocaleString() : String(value)}
                </p>
              </div>
            ))}
          </div>
          {details.calculation && (
            <p className="text-xs text-zinc-500 italic">{details.calculation}</p>
          )}
        </div>
      )}

      {recommendations && recommendations.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">How to Improve</p>
          <ul className="space-y-1">
            {recommendations.map((rec, idx) => (
              <li key={typeof rec === 'string' ? rec : `rec-${idx}`} className="text-sm flex items-start gap-2">
                <ArrowRightIcon size={14} className="mt-1 text-[#F7B500] shrink-0" />
                <span className="text-zinc-300">{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {link && (
        <div className="mt-4 pt-4 border-t border-[#3a3a3a]">
          <Link href={link.href}>
            <Button variant="ghost" size="sm" icon={<ArrowRightIcon size={14} />}>
              {link.label}
            </Button>
          </Link>
        </div>
      )}
    </Card>
  );
};

export default function StoreIntelligenceDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

  const fetchDashboard = async () => {
    try {
      const response = await fetch(`${API_BASE}/intelligence/dashboard`);
      if (response.status === 404) {
        setData(null);
      } else if (!response.ok) {
        throw new Error("Failed to fetch");
      } else {
        const result = await response.json();
        setData(result);
      }
    } catch (error) {
      console.error("Error fetching dashboard:", error);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const generateIntelligence = async () => {
    setGenerating(true);
    try {
      const response = await fetch(`${API_BASE}/intelligence/scheduled/generate-all`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Failed to generate");
      await fetchDashboard();
    } catch (error) {
      console.error("Error generating intelligence:", error);
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-green-400";
    if (score >= 60) return "text-yellow-400";
    if (score >= 40) return "text-orange-400";
    return "text-red-400";
  };

  const getPriorityVariant = (priority: string) => {
    switch (priority) {
      case "CRITICAL":
        return "danger";
      case "HIGH":
        return "warning";
      case "MEDIUM":
        return "default";
      default:
        return "info";
    }
  };

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "scores", label: "Score Details" },
    { id: "issues", label: `Issues (${data?.critical_issues?.length || 0})` },
    { id: "opportunities", label: `Opportunities (${data?.opportunities?.length || 0})` },
    { id: "recommendations", label: `AI Recommendations (${data?.ai_recommendations?.length || 0})` },
  ];

  // Generate data-driven recommendations based on real scores and details
  const getScoreRecommendations = (category: string, score: number, details?: any): string[] => {
    if (score >= 85) return ["✅ Excelente — mantener estrategia actual"];

    const recs: string[] = [];

    switch (category) {
      case "commerce":
        if (details?.out_of_stock > 0)
          recs.push(`⚠️ ${details.out_of_stock} productos agotados — restock urgente`);
        if (details?.low_stock > 0)
          recs.push(`${details.low_stock} productos con stock bajo — revisar inventario`);
        if (details?.slow_movers_count > 0)
          recs.push(`${details.slow_movers_count} productos sin ventas — considerar bundles o descuentos`);
        if (details?.aov && details.aov < 200)
          recs.push(`AOV: $${details.aov.toFixed(0)} — incrementar con upsells y kits`);
        if (details?.customer_ltv && details.customer_ltv < 300)
          recs.push(`LTV promedio: $${details.customer_ltv.toFixed(0)} — mejorar retención`);
        break;
      case "cro":
        if (details?.cart_abandonment > 60)
          recs.push(`🔴 Abandono de carrito: ${details.cart_abandonment.toFixed(0)}% — agregar checkout exprés, trust badges`);
        if (details?.conversion_rate !== undefined && details.conversion_rate < 3)
          recs.push(`Conversión: ${details.conversion_rate.toFixed(2)}% (meta: ${details?.target_rate || 3}%)`);
        if (details?.bounce_rate > 50)
          recs.push(`Bounce rate: ${details.bounce_rate.toFixed(0)}% — mejorar landing pages`);
        if (details?.avg_session_duration < 60)
          recs.push(`Sesión promedio: ${details.avg_session_duration.toFixed(0)}s — mejorar engagement`);
        break;
      case "seo":
        if (details?.products_needing_seo > 100)
          recs.push(`🔴 ${details.products_needing_seo} productos sin SEO (solo ${details?.optimization_ratio || '?'} optimizados)`);
        else if (details?.products_needing_seo > 0)
          recs.push(`${details.products_needing_seo} productos pendientes de optimización SEO`);
        if (details?.avg_ctr < 2)
          recs.push(`CTR: ${details?.avg_ctr?.toFixed(1) || '0'}% — reescribir meta titles`);
        if (details?.avg_position > 15)
          recs.push(`Posición: ${details?.avg_position?.toFixed(0) || '?'} — optimizar top 20`);
        break;
      case "geo":
        if (details?.openai_score === 0)
          recs.push("OpenAI score: 0 — no apareces en ChatGPT");
        if (details?.perplexity_score === 0)
          recs.push("Perplexity score: 0 — no apareces en Perplexity");
        if (details?.llm_traffic < 50)
          recs.push(`Solo ${details?.llm_traffic || 0} sesiones de LLMs — crear contenido diagnóstico`);
        recs.push("Ir a AEO/GEO y ejecutar checks de visibilidad");
        break;
      case "technical":
        if (details?.lcp > 2.5)
          recs.push(`LCP: ${details.lcp.toFixed(1)}s (meta: <2.5s) — optimizar imágenes`);
        if (details?.cls > 0.1)
          recs.push(`CLS: ${details.cls.toFixed(2)} (meta: <0.1) — fijar layouts`);
        if (details?.schema_coverage < 50)
          recs.push(`Schema coverage: ${details?.schema_coverage?.toFixed(0) || 0}% — generar más schemas`);
        break;
    }

    if (recs.length === 0) recs.push("Revisar métricas y optimizar");
    return recs;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-semibold">Store Intelligence</h1>
          <Button variant="secondary" loading>
            Loading...
          </Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <Card key={`skel-${n}`} className="animate-pulse">
              <div className="h-4 bg-[#3a3a3a] rounded w-3/4 mb-4" />
              <div className="h-8 bg-[#3a3a3a] rounded w-1/2" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-semibold">Store Intelligence</h1>
            <p className="text-zinc-400">
              AI-powered insights across SEO, CRO, GEO, and Commerce
            </p>
          </div>
        </div>

        <Card accent className="text-center py-12">
          <SparklesIcon size={64} className="text-[#F7B500] mx-auto mb-6" />
          <h2 className="text-2xl font-semibold mb-4">Welcome to Store Intelligence</h2>
          <p className="text-zinc-400 mb-2 max-w-lg mx-auto">
            Get AI-powered recommendations by analyzing your store data across all channels.
          </p>
          <p className="text-zinc-500 text-sm mb-8 max-w-lg mx-auto">
            This will analyze your Shopify data, Google Analytics, Search Console, and AI visibility to provide actionable insights.
          </p>
          <Button
            onClick={generateIntelligence}
            loading={generating}
            icon={<FireIcon size={20} />}
            size="lg"
          >
            {generating ? 'Analyzing...' : 'Generate First Intelligence Report'}
          </Button>

          {generating && (
            <p className="text-zinc-400 text-sm mt-4">
              This may take 30-60 seconds...
            </p>
          )}
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
          <Card>
            <div className="text-center">
              <ChartIcon size={32} className="text-blue-400 mx-auto mb-3" />
              <h3 className="font-semibold mb-2">Health Scores</h3>
              <p className="text-sm text-zinc-400">Track SEO, CRO, GEO, and Commerce metrics</p>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <WarningIcon size={32} className="text-red-400 mx-auto mb-3" />
              <h3 className="font-semibold mb-2">Critical Issues</h3>
              <p className="text-sm text-zinc-400">Identify problems hurting your performance</p>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <SparklesIcon size={32} className="text-green-400 mx-auto mb-3" />
              <h3 className="font-semibold mb-2">AI Recommendations</h3>
              <p className="text-sm text-zinc-400">Get prioritized actions with revenue impact</p>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Store Intelligence</h1>
          <p className="text-zinc-400">
            AI-powered insights across SEO, CRO, GEO, and Commerce
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchDashboard} icon={<SyncIcon size={16} />}>
            Refresh
          </Button>
          <Button onClick={generateIntelligence} loading={generating} icon={<FireIcon size={16} />}>
            Generate Intelligence
          </Button>
        </div>
      </div>

      {/* Health Score Hero */}
      <Card accent>
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="relative">
              <svg className="size-32 transform -rotate-90">
                <circle
                  cx="64"
                  cy="64"
                  r="56"
                  stroke="#3a3a3a"
                  strokeWidth="12"
                  fill="transparent"
                />
                <circle
                  cx="64"
                  cy="64"
                  r="56"
                  stroke="#F7B500"
                  strokeWidth="12"
                  fill="transparent"
                  strokeDasharray={351.86}
                  strokeDashoffset={351.86 - (351.86 * data.health.overall) / 100}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-3xl font-bold ${getScoreColor(data.health.overall)}`}>
                  {data.health.overall}
                </span>
              </div>
            </div>
            <div>
              <h2 className="text-2xl font-semibold">Store Health Score</h2>
              <div className="flex items-center gap-2 mt-1">
                {data.health.trend === "improving" ? (
                  <TrendingUpIcon size={20} className="text-green-400" />
                ) : data.health.trend === "declining" ? (
                  <TrendingDownIcon size={20} className="text-red-400" />
                ) : (
                  <GearIcon size={20} className="text-zinc-400" />
                )}
                <span className="text-zinc-400 capitalize">
                  {data.health.trend} trend
                </span>
              </div>
              {data.summary && (
                <p className="text-sm text-zinc-400 mt-2 max-w-md">
                  {data.summary}
                </p>
              )}
            </div>
          </div>

          {/* Category Breakdown */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { key: "commerce", label: "Commerce", icon: ShoppingCartIcon },
              { key: "cro", label: "CRO", icon: ChartIcon },
              { key: "seo", label: "SEO", icon: SearchIcon },
              { key: "geo", label: "GEO", icon: DatabaseIcon },
              { key: "technical", label: "Technical", icon: ChipIcon },
            ].map(({ key, label, icon: Icon }) => {
              const score = data.health.breakdown[key as keyof typeof data.health.breakdown];
              return (
                <div key={key} className="text-center">
                  <div className="flex items-center justify-center gap-1 mb-1">
                    <Icon size={16} className="text-zinc-400" />
                    <span className="text-xs text-zinc-400">{label}</span>
                  </div>
                  <div className={`text-xl font-bold ${getScoreColor(score)}`}>
                    {score}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-400">Total Products</p>
              <p className="text-2xl font-bold">{data.quick_stats.total_products}</p>
            </div>
            <DatabaseIcon size={32} className="text-zinc-400" />
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-400">SEO Optimized</p>
              <p className="text-2xl font-bold">{data.quick_stats.products_optimized}</p>
            </div>
            <CheckIcon size={32} className="text-green-400" />
          </div>
          <ProgressBar
            value={(data.quick_stats.products_optimized / data.quick_stats.total_products) * 100}
            size="sm"
            className="mt-2"
          />
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-400">Pending Actions</p>
              <p className="text-2xl font-bold">{data.quick_stats.pending_recommendations}</p>
            </div>
            <ClockIcon size={32} className="text-orange-400" />
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-400">Critical Issues</p>
              <p className={`text-2xl font-bold ${data.critical_issues.length > 0 ? 'text-red-400' : ''}`}>
                {data.critical_issues.length}
              </p>
            </div>
            <WarningIcon size={32} className={data.critical_issues.length > 0 ? 'text-red-400' : 'text-zinc-400'} />
          </div>
        </Card>
      </div>

      {/* Quick Tools Navigation */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-4">
        <Link href="/intelligence/seo">
          <Card className="p-4 hover:border-[#F7B500] transition-colors cursor-pointer">
            <div className="flex items-center gap-3">
              <SearchIcon size={24} className="text-[#F7B500]" />
              <div>
                <p className="font-medium">SEO Intelligence</p>
                <p className="text-xs text-zinc-400">Keywords, CTR, Alerts</p>
              </div>
            </div>
          </Card>
        </Link>
        <Link href="/intelligence/cro-technical">
          <Card className="p-4 hover:border-[#F7B500] transition-colors cursor-pointer">
            <div className="flex items-center gap-3">
              <ChartIcon size={24} className="text-[#F7B500]" />
              <div>
                <p className="font-medium">CRO Technical</p>
                <p className="text-xs text-zinc-400">Funnel & Performance</p>
              </div>
            </div>
          </Card>
        </Link>
        <Link href="/aeo">
          <Card className="p-4 hover:border-[#F7B500] transition-colors cursor-pointer">
            <div className="flex items-center gap-3">
              <DatabaseIcon size={24} className="text-[#F7B500]" />
              <div>
                <p className="font-medium">AEO / GEO</p>
                <p className="text-xs text-zinc-400">AI Visibility</p>
              </div>
            </div>
          </Card>
        </Link>
        <Link href="/seo/dashboard">
          <Card className="p-4 hover:border-[#F7B500] transition-colors cursor-pointer">
            <div className="flex items-center gap-3">
              <GlobeIcon size={24} className="text-[#F7B500]" />
              <div>
                <p className="font-medium">SEO Content</p>
                <p className="text-xs text-zinc-400">Product Optimization</p>
              </div>
            </div>
          </Card>
        </Link>
        <Link href="/intelligence/sucursales">
          <Card className="p-4 hover:border-[#F7B500] transition-colors cursor-pointer">
            <div className="flex items-center gap-3">
              <ShoppingCartIcon size={24} className="text-[#F7B500]" />
              <div>
                <p className="font-medium">Sucursales</p>
                <p className="text-xs text-zinc-400">In-store sales (90d)</p>
              </div>
            </div>
          </Card>
        </Link>
      </div>

      {/* Main Content Tabs */}
      <div className="space-y-4">
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Weekly Focus */}
              <Card
                title="This Week's Focus"
                icon={<FireIcon size={20} className="text-[#F7B500]" />}
              >
                {data.weekly_focus.length > 0 ? (
                  <div className="space-y-3">
                    {data.weekly_focus.map((focus, index) => (
                      <div key={focus.title || `focus-${index}`} className="flex items-start gap-3 p-3 bg-[#2a2a2a] rounded-sm">
                        <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[#F7B500] text-black text-xs font-bold">
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <Badge variant="brand">{focus.category}</Badge>
                            <span className="text-xs text-zinc-400">{focus.effort}</span>
                          </div>
                          <p className="font-medium mt-1">{focus.title}</p>
                          <p className="text-sm text-zinc-400">{focus.action}</p>
                          <p className="text-sm text-green-400 mt-1">{focus.impact}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-zinc-400">
                    No focus items defined. Generate intelligence to get recommendations.
                  </p>
                )}
              </Card>

              {/* Priority Actions */}
              <Card
                title="Priority Actions"
                icon={<WarningIcon size={20} className="text-red-400" />}
              >
                {data.critical_issues.length > 0 ? (
                  <div className="space-y-3">
                    {data.critical_issues.slice(0, 3).map((issue, index) => (
                      <div key={issue.title || `issue-${index}`} className="p-3 bg-red-500/10 border border-red-500/30 rounded-sm">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="danger">{issue.severity}</Badge>
                          <Badge variant="brand">{issue.category}</Badge>
                        </div>
                        <p className="font-medium text-sm">{issue.title}</p>
                        <p className="text-xs text-zinc-400 mt-1">{issue.impact}</p>
                        <p className="text-xs text-red-400 mt-1">{issue.action}</p>
                      </div>
                    ))}
                    {data.critical_issues.length > 3 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setActiveTab("issues")}
                        icon={<ArrowRightIcon size={14} />}
                      >
                        View {data.critical_issues.length - 3} more issues
                      </Button>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <CheckIcon size={32} className="text-green-400 mx-auto mb-2" />
                    <p className="text-zinc-400">No critical issues!</p>
                  </div>
                )}
              </Card>
            </div>

            {/* SEO Intelligence & CRO Preview Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
              {/* SEO Intelligence Preview */}
              <Card className="border border-[#F7B500]/20">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <SearchIcon size={24} className="text-[#F7B500]" />
                    <div>
                      <h3 className="font-semibold">SEO Intelligence</h3>
                      <p className="text-xs text-zinc-400">Keyword tracking & CTR optimization</p>
                    </div>
                  </div>
                  <Link href="/intelligence/seo">
                    <Button variant="ghost" size="sm" icon={<ArrowRightIcon size={14} />}>
                      Deep Analysis
                    </Button>
                  </Link>
                </div>

                {data.seo_data?.intelligence_preview?.has_data ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-4 gap-3">
                      <div className="text-center p-2 bg-[#1a1a1a] rounded">
                        <p className="text-lg font-bold">{data.seo_data.intelligence_preview.keywords_tracked}</p>
                        <p className="text-xs text-zinc-400">Tracked</p>
                      </div>
                      <div className="text-center p-2 bg-[#1a1a1a] rounded">
                        <p className="text-lg font-bold text-green-400">{data.seo_data.intelligence_preview.keywords_improving}</p>
                        <p className="text-xs text-zinc-400">Improving</p>
                      </div>
                      <div className="text-center p-2 bg-[#1a1a1a] rounded">
                        <p className="text-lg font-bold text-red-400">{data.seo_data.intelligence_preview.keywords_declining}</p>
                        <p className="text-xs text-zinc-400">Declining</p>
                      </div>
                      <div className="text-center p-2 bg-[#1a1a1a] rounded">
                        <p className="text-lg font-bold text-[#F7B500]">{data.seo_data.intelligence_preview.open_alerts}</p>
                        <p className="text-xs text-zinc-400">Alerts</p>
                      </div>
                    </div>

                    {data.seo_data.intelligence_preview.ctr_opportunities > 0 && (
                      <div className="p-3 bg-[#F7B500]/10 border border-[#F7B500]/30 rounded">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium">CTR Opportunities Found</p>
                            <p className="text-xs text-zinc-400">{data.seo_data.intelligence_preview.ctr_opportunities} queries underperforming</p>
                          </div>
                          <p className="text-lg font-bold text-green-400">+{data.seo_data.intelligence_preview.potential_clicks} clicks</p>
                        </div>
                      </div>
                    )}

                    <p className="text-xs text-zinc-500">
                      Last collected: {data.seo_data.intelligence_preview.last_collection
                        ? formatDate(data.seo_data.intelligence_preview.last_collection)
                        : 'Never'}
                    </p>
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <SearchIcon size={32} className="text-zinc-600 mx-auto mb-2" />
                    <p className="text-zinc-400 text-sm">No SEO intelligence data yet</p>
                    <Link href="/intelligence/seo">
                      <Button size="sm" className="mt-3">Run Collection</Button>
                    </Link>
                  </div>
                )}
              </Card>

              {/* CRO Preview */}
              <Card className="border border-[#F7B500]/20">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <ChartIcon size={24} className="text-[#F7B500]" />
                    <div>
                      <h3 className="font-semibold">CRO & Funnel</h3>
                      <p className="text-xs text-zinc-400">Conversion optimization analysis</p>
                    </div>
                  </div>
                  <Link href="/intelligence/cro-technical">
                    <Button variant="ghost" size="sm" icon={<ArrowRightIcon size={14} />}>
                      Deep Analysis
                    </Button>
                  </Link>
                </div>

                {data.traffic_data?.cro_preview?.has_data ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-4 gap-3">
                      <div className="text-center p-2 bg-[#1a1a1a] rounded">
                        <p className="text-lg font-bold">{data.traffic_data.cro_preview.sessions?.toLocaleString()}</p>
                        <p className="text-xs text-zinc-400">Sessions (7d)</p>
                      </div>
                      <div className="text-center p-2 bg-[#1a1a1a] rounded">
                        <p className="text-lg font-bold text-green-400">{data.traffic_data.cro_preview.purchases}</p>
                        <p className="text-xs text-zinc-400">Purchases</p>
                      </div>
                      <div className="text-center p-2 bg-[#1a1a1a] rounded">
                        <p className="text-lg font-bold text-[#F7B500]">{data.traffic_data.cro_preview.conversion_rate?.toFixed(2)}%</p>
                        <p className="text-xs text-zinc-400">Conv. Rate</p>
                      </div>
                      <div className="text-center p-2 bg-[#1a1a1a] rounded">
                        <p className="text-lg font-bold">${data.traffic_data.cro_preview.revenue?.toLocaleString()}</p>
                        <p className="text-xs text-zinc-400">Revenue</p>
                      </div>
                    </div>

                    {data.traffic_data.cro_preview.biggest_dropoff && (
                      <div className="p-3 bg-red-500/10 border border-red-500/30 rounded">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-red-400">Biggest Dropoff</p>
                            <p className="text-xs text-zinc-400">{data.traffic_data.cro_preview.biggest_dropoff.step}</p>
                          </div>
                          <p className="text-lg font-bold text-red-400">{data.traffic_data.cro_preview.biggest_dropoff.rate}%</p>
                        </div>
                      </div>
                    )}

                    {data.traffic_data.cro_preview.device_breakdown && Object.keys(data.traffic_data.cro_preview.device_breakdown).length > 0 && (
                      <div className="flex gap-2">
                        {Object.entries(data.traffic_data.cro_preview.device_breakdown).map(([device, info]: [string, any]) => (
                          <div key={device} className="flex-1 text-center p-2 bg-[#1a1a1a] rounded">
                            <p className="text-xs text-zinc-400 capitalize">{device}</p>
                            <p className="text-sm font-medium">{info.share?.toFixed(0)}%</p>
                            <p className="text-xs text-zinc-500">{info.conversion?.toFixed(2)}% conv</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <ChartIcon size={32} className="text-zinc-600 mx-auto mb-2" />
                    <p className="text-zinc-400 text-sm">No CRO data available</p>
                    <Link href="/intelligence/cro-technical">
                      <Button size="sm" className="mt-3">View Technical Analysis</Button>
                    </Link>
                  </div>
                )}
              </Card>
            </div>
          </div>
        )}

        {/* Score Details Tab */}
        {activeTab === "scores" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <ScoreBreakdownCard
                title="Commerce"
                score={data.health.breakdown.commerce}
                icon={ShoppingCartIcon}
                details={data.health.details?.commerce}
                recommendations={getScoreRecommendations("commerce", data.health.breakdown.commerce, data.health.details?.commerce)}
              />
              <ScoreBreakdownCard
                title="CRO (Conversion)"
                score={data.health.breakdown.cro}
                icon={ChartIcon}
                details={data.health.details?.cro}
                recommendations={getScoreRecommendations("cro", data.health.breakdown.cro, data.health.details?.cro)}
                link={{ href: "/intelligence/cro-technical", label: "Deep CRO Analysis" }}
              />
              <ScoreBreakdownCard
                title="SEO"
                score={data.health.breakdown.seo}
                icon={SearchIcon}
                details={data.health.details?.seo}
                recommendations={getScoreRecommendations("seo", data.health.breakdown.seo, data.health.details?.seo)}
                link={{ href: "/intelligence/seo", label: "SEO Intelligence Dashboard" }}
              />
              <ScoreBreakdownCard
                title="GEO (AI Visibility)"
                score={data.health.breakdown.geo}
                icon={DatabaseIcon}
                details={data.health.details?.geo}
                recommendations={getScoreRecommendations("geo", data.health.breakdown.geo, data.health.details?.geo)}
              />
              <ScoreBreakdownCard
                title="Technical"
                score={data.health.breakdown.technical}
                icon={ChipIcon}
                details={data.health.details?.technical}
                recommendations={getScoreRecommendations("technical", data.health.breakdown.technical, data.health.details?.technical)}
              />
            </div>

            {/* Quick Actions Based on Low Scores */}
            {data.health.breakdown.geo < 50 && (
              <Card accent className="border-yellow-500/30">
                <div className="flex items-start gap-4">
                  <DatabaseIcon size={32} className="text-yellow-400" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg mb-2">GEO Score Needs Attention ({data.health.breakdown.geo}/100)</h3>
                    <p className="text-zinc-400 mb-4">
                      AI platforms (ChatGPT, Grok, Perplexity) aren't citing your products. When mechanics ask "what solenoide for P0700?", competitors are being recommended instead.
                    </p>
                    <div className="flex gap-2">
                      <Link href="/aeo">
                        <Button icon={<ArrowRightIcon size={16} />}>
                          Go to AEO/GEO Page
                        </Button>
                      </Link>
                    </div>
                  </div>
                </div>
              </Card>
            )}

            {data.health.breakdown.cro < 60 && (
              <Card accent className="border-orange-500/30">
                <div className="flex items-start gap-4">
                  <ChartIcon size={32} className="text-orange-400" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg mb-2">Low Conversion Rate ({data.health.breakdown.cro}/100)</h3>
                    <p className="text-zinc-400 mb-4">
                      Visitors are coming but not buying. Your conversion rate is {data.health.details?.cro?.conversion_rate.toFixed(1)}% vs industry average of 2.5%.
                    </p>
                    <ul className="text-sm text-zinc-400 space-y-1 mb-4">
                      <li>• Add express checkout options</li>
                      <li>• Show shipping costs upfront</li>
                      <li>• Add trust badges</li>
                    </ul>
                    <div className="flex gap-2">
                      <Link href="/intelligence/cro-technical">
                        <Button icon={<ArrowRightIcon size={16} />}>
                          View Detailed CRO Analysis
                        </Button>
                      </Link>
                    </div>
                  </div>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* Issues Tab */}
        {activeTab === "issues" && (
          <Card
            title="Critical Issues Requiring Attention"
            icon={<WarningIcon size={20} className="text-red-400" />}
          >
            <div className="space-y-4 max-h-[500px] overflow-y-auto">
              {data.critical_issues.length > 0 ? (
                data.critical_issues.map((issue, index) => (
                  <div key={issue.title || `crit-issue-${index}`} className="p-4 bg-red-500/10 border border-red-500/30 rounded-sm">
                    <div className="flex items-start gap-3">
                      <div className="mt-1 text-zinc-400">
                        <CategoryIcon category={issue.category} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-white">{issue.title}</h3>
                          <Badge variant="danger">{issue.severity}</Badge>
                        </div>
                        <p className="text-zinc-400 mt-1">{issue.description}</p>
                        <p className="font-semibold text-red-400 mt-1">Impact: {issue.impact}</p>
                        <p className="text-sm text-zinc-400 mt-1">Action: {issue.action}</p>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8">
                  <CheckIcon size={48} className="text-green-400 mx-auto mb-4" />
                  <p className="text-lg font-medium">No Critical Issues!</p>
                  <p className="text-zinc-400">Your store is in good health.</p>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Opportunities Tab */}
        {activeTab === "opportunities" && (
          <Card
            title="Growth Opportunities"
            icon={<SparklesIcon size={20} className="text-green-400" />}
          >
            <div className="space-y-4 max-h-[500px] overflow-y-auto">
              {data.opportunities.length > 0 ? (
                data.opportunities.map((opp, index) => (
                  <Card key={opp.title || `opp-${index}`} accent className="border-l-4 border-l-[#F7B500]">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="brand" className="flex items-center gap-1">
                            <CategoryIcon category={opp.category} size={12} />
                            {opp.category}
                          </Badge>
                          <Badge variant="default">{opp.effort}</Badge>
                        </div>
                        <h3 className="font-semibold mt-2">{opp.title}</h3>
                        <p className="text-sm text-zinc-400 mt-1">
                          {opp.description}
                        </p>
                        <p className="text-sm font-medium text-green-400 mt-2">
                          Potential Impact: {opp.potential_impact}
                        </p>
                      </div>
                    </div>
                  </Card>
                ))
              ) : (
                <div className="text-center py-8">
                  <p className="text-zinc-400">No opportunities identified yet.</p>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* AI Recommendations Tab */}
        {activeTab === "recommendations" && (
          <div className="space-y-4">
            {data.ai_recommendations.length > 0 ? (
              data.ai_recommendations.map((rec) => (
                <Card key={rec.id} accent>
                  <div className="flex">
                    <div className={`w-1 ${rec.priority === 'CRITICAL' ? 'bg-red-500' : rec.priority === 'HIGH' ? 'bg-orange-500' : rec.priority === 'MEDIUM' ? 'bg-yellow-500' : 'bg-blue-500'}`} />
                    <div className="flex-1 p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant={getPriorityVariant(rec.priority)}>
                              {rec.priority}
                            </Badge>
                            <Badge variant="brand" className="flex items-center gap-1">
                              <CategoryIcon category={rec.category} size={12} />
                              {rec.category}
                            </Badge>
                            <Badge variant="default">{rec.effort_required}</Badge>
                          </div>
                          <h3 className="font-semibold text-lg mt-2">{rec.title}</h3>
                          <p className="text-zinc-400 mt-1">{rec.description}</p>

                          {rec.action_steps && rec.action_steps.length > 0 && (
                            <div className="mt-3">
                              <p className="text-sm font-medium mb-2">Action Steps:</p>
                              <ul className="space-y-1">
                                {rec.action_steps.map((step) => (
                                  <li key={`${rec.id}-${step}`} className="text-sm flex items-start gap-2">
                                    <ArrowRightIcon size={16} className="mt-0.5 shrink-0 text-zinc-400" />
                                    {step}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          <div className="flex gap-4 mt-3">
                            <div className="flex items-center gap-1 text-green-400">
                              <TrendingUpIcon size={16} />
                              <span className="text-sm font-medium">{rec.revenue_impact}</span>
                            </div>
                            <div className="flex items-center gap-1 text-blue-400">
                              <ChartIcon size={16} />
                              <span className="text-sm font-medium">{rec.traffic_impact}</span>
                            </div>
                            <div className="flex items-center gap-1 text-zinc-400">
                              <FireIcon size={16} />
                              <span className="text-sm">
                                Confidence: {Math.round(rec.confidence_score * 100)}%
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>
              ))
            ) : (
              <Card className="text-center">
                <div className="p-8">
                  <DatabaseIcon size={48} className="text-zinc-400 mx-auto mb-4" />
                  <p className="text-lg font-medium">No AI Recommendations Yet</p>
                  <p className="text-zinc-400 mb-4">
                    Generate intelligence to get AI-powered recommendations
                  </p>
                  <Button onClick={generateIntelligence} loading={generating} icon={<FireIcon size={16} />}>
                    Generate Now
                  </Button>
                </div>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
