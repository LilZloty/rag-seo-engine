"use client";

import { useState, useEffect } from "react";
import { Card } from "@/app/components/ui/Card";
import { Button } from "@/app/components/ui/Button";
import { Badge } from "@/app/components/ui/Badge";
import { ProgressBar } from "@/app/components/ui/ProgressBar";
import { Tabs } from "@/app/components/ui/Tabs";
import {
  ChartIcon,
  WarningIcon,
  CheckIcon,
  ClockIcon,
  DeviceIcon,
  SpeedIcon,
  FireIcon,
  ArrowRightIcon,
  GearIcon
} from "@/app/components/ui/Icons";

interface TechnicalReport {
  core_web_vitals: {
    lcp: { value: number; status: string; target: number; impact: string };
    fid: { value: number; status: string; target: number; impact?: string };
    cls: { value: number; status: string; target: number; impact?: string };
    overall_status: string;
  };
  page_speed: {
    homepage: PageSpeedData;
    product_page: PageSpeedData;
    checkout: PageSpeedData;
  };
  checkout_funnel: {
    steps: FunnelStep[];
    biggest_dropoff: { step: string; conversion: number; loss: number };
    abandoned_carts_value: number;
  };
  device_performance: {
    mobile: DeviceData;
    desktop: DeviceData;
    tablet: DeviceData;
  };
  friction_points: FrictionPoint[];
  recommendations: TechnicalRecommendation[];
}

interface PageSpeedData {
  load_time: number;
  size: string;
  requests: number;
  issues: { issue: string; impact: string; fix: string }[];
}

interface FunnelStep {
  step: string;
  users: number;
  conversion: number;
  drop_off: number;
  friction?: string;
}

interface DeviceData {
  traffic_share: number;
  conversion_rate: number;
  avg_order_value: number;
  page_load: number;
  bounce_rate: number;
  issues: string[];
  priority: string;
  note?: string;
}

interface FrictionPoint {
  location: string;
  issue: string;
  impact: string;
  severity: string;
  fix: string;
}

interface TechnicalRecommendation {
  priority: string;
  category: string;
  title: string;
  impact: string;
  effort: string;
  steps: string[];
}

export default function CROTechnicalReport() {
  const [report, setReport] = useState<TechnicalReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("performance");

  useEffect(() => {
    fetchTechnicalReport();
  }, []);

  const fetchTechnicalReport = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/intelligence/cro-technical-report");
      if (!response.ok) throw new Error("Failed to fetch");
      const data = await response.json();
      setReport(data);
    } catch (error) {
      console.error("Error fetching technical report:", error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "good":
        return "text-green-400";
      case "needs_improvement":
        return "text-yellow-400";
      case "poor":
        return "text-red-400";
      default:
        return "text-zinc-400";
    }
  };

  const getStatusBg = (status: string) => {
    switch (status) {
      case "good":
        return "bg-green-500";
      case "needs_improvement":
        return "bg-yellow-500";
      case "poor":
        return "bg-red-500";
      default:
        return "bg-zinc-500";
    }
  };

  const tabs = [
    { id: "performance", label: "Performance" },
    { id: "funnel", label: "Checkout Funnel" },
    { id: "devices", label: "Devices" },
    { id: "friction", label: "Friction Points" },
    { id: "fixes", label: "Fixes" },
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white p-6">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-semibold">CRO Technical Analysis</h1>
            <p className="text-zinc-400">Deep dive into performance & friction</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map((n) => (
            <Card key={`skel-${n}`} className="animate-pulse h-48" />
          ))}
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white p-6">
        <Card accent>
          <div className="text-center py-12">
            <WarningIcon size={48} className="text-yellow-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Technical Report Unavailable</h2>
            <p className="text-zinc-400 mb-4">Could not load CRO technical analysis</p>
            <Button onClick={fetchTechnicalReport} icon={<FireIcon size={16} />}>
              Retry
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">CRO Technical Analysis</h1>
          <p className="text-zinc-400">
            Performance metrics, friction points &amp; specific fixes
          </p>
        </div>
        <Button variant="outline" onClick={fetchTechnicalReport} icon={<FireIcon size={16} />}>
          Refresh Analysis
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="flex items-center gap-3">
            <div className="p-3 bg-yellow-500/20 rounded-lg">
              <SpeedIcon size={24} className="text-yellow-400" />
            </div>
            <div>
              <p className="text-sm text-zinc-400">Page Load</p>
              <p className="text-2xl font-bold">
                {report.page_speed.homepage.load_time}s
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-500/20 rounded-lg">
              <WarningIcon size={24} className="text-red-400" />
            </div>
            <div>
              <p className="text-sm text-zinc-400">CWV Status</p>
              <p className={`text-2xl font-bold ${getStatusColor(report.core_web_vitals.overall_status)}`}>
                {report.core_web_vitals.overall_status === "needs_improvement" ? "NEEDS WORK" : "GOOD"}
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-500/20 rounded-lg">
              <ChartIcon size={24} className="text-red-400" />
            </div>
            <div>
              <p className="text-sm text-zinc-400">Biggest Dropoff</p>
              <p className="text-2xl font-bold">
                {report.checkout_funnel.biggest_dropoff.step}
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="p-3 bg-orange-500/20 rounded-lg">
              <DeviceIcon size={24} className="text-orange-400" />
            </div>
            <div>
              <p className="text-sm text-zinc-400">Mobile Conv.</p>
              <p className="text-2xl font-bold">
                {report.device_performance.mobile.conversion_rate}%
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="space-y-4">
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

        {/* Performance Tab */}
        {activeTab === "performance" && (
          <div className="space-y-6">
            {/* Core Web Vitals */}
            <Card title="Core Web Vitals" icon={<SpeedIcon size={20} className="text-[#F7B500]" />}>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* LCP */}
                <div className="p-4 bg-[#2a2a2a] rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-zinc-400">LCP (Loading)</span>
                    <Badge
                      variant={report.core_web_vitals.lcp.status === "needs_improvement" ? "warning" : "brand"}
                    >
                      {report.core_web_vitals.lcp.status}
                    </Badge>
                  </div>
                  <p className={`text-3xl font-bold ${getStatusColor(report.core_web_vitals.lcp.status)}`}>
                    {report.core_web_vitals.lcp.value}s
                  </p>
                  <p className="text-sm text-zinc-400 mt-1">Target: {report.core_web_vitals.lcp.target}s</p>
                  <p className="text-xs text-zinc-500 mt-2">{report.core_web_vitals.lcp.impact}</p>
                </div>

                {/* FID */}
                <div className="p-4 bg-[#2a2a2a] rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-zinc-400">FID (Interactive)</span>
                    <Badge variant="brand">{report.core_web_vitals.fid.status}</Badge>
                  </div>
                  <p className={`text-3xl font-bold ${getStatusColor(report.core_web_vitals.fid.status)}`}>
                    {report.core_web_vitals.fid.value}ms
                  </p>
                  <p className="text-sm text-zinc-400 mt-1">Target: {report.core_web_vitals.fid.target}ms</p>
                  <p className="text-xs text-zinc-500 mt-2">{report.core_web_vitals.fid.impact}</p>
                </div>

                {/* CLS */}
                <div className="p-4 bg-[#2a2a2a] rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-zinc-400">CLS (Stability)</span>
                    <Badge variant={report.core_web_vitals.cls.status === "needs_improvement" ? "warning" : "brand"}>
                      {report.core_web_vitals.cls.status}
                    </Badge>
                  </div>
                  <p className={`text-3xl font-bold ${getStatusColor(report.core_web_vitals.cls.status)}`}>
                    {report.core_web_vitals.cls.value}
                  </p>
                  <p className="text-sm text-zinc-400 mt-1">Target: {report.core_web_vitals.cls.target}</p>
                  <p className="text-xs text-zinc-500 mt-2">
                    Content shifts while loading
                  </p>
                </div>
              </div>
            </Card>

            {/* Page Speed Details */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(report.page_speed).map(([page, data]) => (
                <Card key={page} title={page.replace("_", " ").toUpperCase()}>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-400">Load Time</span>
                      <span className={`font-bold ${data.load_time > 3 ? "text-red-400" : "text-green-400"}`}>
                        {data.load_time}s
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-400">Page Size</span>
                      <span className="font-medium">{data.size}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-400">Requests</span>
                      <span className="font-medium">{data.requests}</span>
                    </div>
                    <div className="mt-4 space-y-2">
                      <p className="text-xs text-zinc-500 uppercase">Issues</p>
                      {data.issues && data.issues.length > 0 ? (
                        data.issues.slice(0, 2).map((issue, idx) => (
                          <div key={issue.issue || `issue-${idx}`} className="text-sm p-2 bg-[#2a2a2a] rounded">
                            <p className="text-yellow-400">{issue.issue}</p>
                            <p className="text-xs text-zinc-400">{issue.impact} - {issue.fix}</p>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-zinc-500">No issues detected</p>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Funnel Tab */}
        {activeTab === "funnel" && (
          <Card title="Checkout Funnel Analysis" icon={<ChartIcon size={20} className="text-[#F7B500]" />}>
            <div className="space-y-6">
              {/* Funnel Visualization */}
              <div className="space-y-3">
                {report.checkout_funnel?.steps && report.checkout_funnel.steps.length > 0 ? (
                  report.checkout_funnel.steps.map((step, index) => {
                    const prevStep = index > 0 ? report.checkout_funnel.steps[index - 1] : null;
                    const dropOff = prevStep ? ((prevStep.users - step.users) / prevStep.users * 100).toFixed(1) : "0";
                  
                  return (
                    <div key={step.step} className="relative">
                      <div className="flex items-center gap-4">
                        <div className="w-32 text-sm text-zinc-400">{step.step}</div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-[#2a2a2a] rounded-full h-8 overflow-hidden">
                              <div
                                className="h-full bg-[#F7B500] transition-all"
                                style={{ width: `${step.conversion}%` }}
                              />
                            </div>
                            <span className="w-12 text-right text-sm font-medium">{step.users}</span>
                          </div>
                        </div>
                        <div className="w-24 text-right">
                          {index > 0 && (
                            <span className="text-xs text-red-400">-{dropOff}%</span>
                          )}
                        </div>
                      </div>
                      {step.friction && (
                        <p className="text-xs text-red-400 mt-1 ml-36">⚠️ {step.friction}</p>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-8 text-zinc-400">
                  <p>No funnel data available</p>
                  <p className="text-sm mt-2">Run SEO Intelligence collection to get funnel data</p>
                </div>
              )}
              </div>

              {/* Biggest Dropoff Alert */}
              {report.checkout_funnel?.biggest_dropoff && (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <div className="flex items-start gap-3">
                    <WarningIcon size={20} className="text-red-400 mt-1" />
                    <div>
                      <h3 className="font-semibold text-red-400">Biggest Dropoff: {report.checkout_funnel.biggest_dropoff?.step || 'Unknown'}</h3>
                      <p className="text-sm text-zinc-400 mt-1">
                        {report.checkout_funnel.biggest_dropoff?.loss || 0}% of users leave here
                      </p>
                      {report.checkout_funnel.abandoned_carts_value && (
                        <p className="text-sm text-zinc-400">
                          ${report.checkout_funnel.abandoned_carts_value.toLocaleString()} in abandoned carts
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Devices Tab */}
        {activeTab === "devices" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(report.device_performance || {}).map(([device, data]) => {
              // Skip non-device entries like 'data_source'
              if (typeof data !== 'object' || data === null || !('traffic_share' in data)) {
                return null;
              }
              return (
              <Card key={device} title={device.toUpperCase()}>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400">Traffic Share</span>
                    <span className="font-medium">{data.traffic_share ?? 0}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400">Conversion</span>
                    <span className={`font-bold ${(data.conversion_rate ?? 0) < 1 ? "text-red-400" : "text-green-400"}`}>
                      {data.conversion_rate ?? 0}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400">Load Time</span>
                    <span className="font-medium">{data.page_load ?? '-'}s</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400">Bounce Rate</span>
                    <span className="font-medium">{data.bounce_rate ?? '-'}%</span>
                  </div>
                  <div className="mt-4 space-y-2">
                    <p className="text-xs text-zinc-500 uppercase">Issues</p>
                    {data.issues && data.issues.length > 0 ? (
                      data.issues.map((issue, idx) => (
                        <p key={typeof issue === 'string' ? issue : `issue-${idx}`} className="text-sm text-yellow-400">• {issue}</p>
                      ))
                    ) : (
                      <p className="text-sm text-zinc-500">{data.note || 'No issues detected'}</p>
                    )}
                  </div>
                  {data.priority === "HIGH" && (
                    <Badge variant="danger" className="mt-2">HIGH PRIORITY</Badge>
                  )}
                </div>
              </Card>
              );
            })}
          </div>
        )}

        {/* Friction Tab */}
        {activeTab === "friction" && (
          <div className="space-y-4">
            {report.friction_points.map((point, index) => (
              <Card key={point.issue || `friction-${index}`} className={`border-l-4 ${point.severity === "HIGH" ? "border-l-red-500" : "border-l-yellow-500"}`}>
                <div className="flex items-start gap-4">
                  <div className={`p-2 rounded ${point.severity === "HIGH" ? "bg-red-500/20" : "bg-yellow-500/20"}`}>
                    <WarningIcon size={20} className={point.severity === "HIGH" ? "text-red-400" : "text-yellow-400"} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={point.severity === "HIGH" ? "danger" : "warning"}>{point.severity}</Badge>
                      <span className="text-sm text-zinc-400">{point.location}</span>
                    </div>
                    <h3 className="font-semibold">{point.issue}</h3>
                    <p className="text-sm text-zinc-400 mt-1">Impact: {point.impact}</p>
                    <p className="text-sm text-green-400 mt-2">Fix: {point.fix}</p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Fixes Tab */}
        {activeTab === "fixes" && (
          <div className="space-y-4">
            {report.recommendations.map((rec, index) => (
              <Card key={rec.title || `rec-${index}`} accent className="border-l-4 border-l-[#F7B500]">
                <div className="flex items-start gap-4">
                  <div className="p-2 bg-[#F7B500]/20 rounded">
                    <GearIcon size={20} className="text-[#F7B500]" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <Badge variant={rec.priority === "CRITICAL" ? "danger" : rec.priority === "HIGH" ? "warning" : "brand"}>
                        {rec.priority}
                      </Badge>
                      <Badge variant="default">{rec.category}</Badge>
                      <Badge variant="outline">{rec.effort}</Badge>
                    </div>
                    <h3 className="font-semibold text-lg">{rec.title}</h3>
                    <p className="text-green-400 text-sm mt-1">Impact: {rec.impact}</p>
                    <div className="mt-3 space-y-1">
                      <p className="text-xs text-zinc-500 uppercase">Steps</p>
                      {rec.steps.map((step, idx) => (
                        <p key={typeof step === 'string' ? step : `step-${idx}`} className="text-sm flex items-start gap-2">
                          <ArrowRightIcon size={14} className="mt-1 text-zinc-400 shrink-0" />
                          {step}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
