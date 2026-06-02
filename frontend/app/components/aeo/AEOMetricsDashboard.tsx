'use client';

import React, { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Cell,
  RadialBarChart, RadialBar, LabelList,
} from 'recharts';
import {
  ChartContainer, ChartTooltip, ChartTooltipContent,
  ChartLegend, ChartLegendContent, type ChartConfig,
} from '../ui/chart';
import { SchemaMetrics, AITrafficReport, VisibilitySalesCorrelation } from '@/lib/api';
import { formatCurrency } from './constants';

// ─── Source normalisation ────────────────────────────────────────────────────

const SOURCE_MAP: Record<string, { label: string; color: string }> = {
  'chatgpt.com':          { label: 'ChatGPT',   color: '#10A37F' },
  'chat.openai.com':      { label: 'ChatGPT',   color: '#10A37F' },
  'openai.com':           { label: 'ChatGPT',   color: '#10A37F' },
  'perplexity.ai':        { label: 'Perplexity', color: '#4F46E5' },
  'claude.ai':            { label: 'Claude',    color: '#CC785C' },
  'anthropic.com':        { label: 'Claude',    color: '#CC785C' },
  'gemini.google.com':    { label: 'Gemini',    color: '#4285F4' },
  'bard.google.com':      { label: 'Gemini',    color: '#4285F4' },
  'aistudio.google.com':  { label: 'Gemini',    color: '#4285F4' },
  'copilot.microsoft.com':{ label: 'Copilot',   color: '#0078D4' },
  'bing.com':             { label: 'Copilot',   color: '#0078D4' },
  'grok.x.ai':            { label: 'Grok',      color: '#F7B500' },
  'x.com':                { label: 'Grok',      color: '#F7B500' },
  'you.com':              { label: 'You.com',   color: '#A855F7' },
  'phind.com':            { label: 'Phind',     color: '#06B6D4' },
};

function normaliseReferrers(referrers: Record<string, number>) {
  const merged: Record<string, { label: string; color: string; count: number }> = {};
  for (const [domain, count] of Object.entries(referrers)) {
    const clean = domain.replace(/^www\./, '').toLowerCase();
    const def = SOURCE_MAP[clean] ?? { label: clean, color: '#6b7280' };
    if (merged[def.label]) {
      merged[def.label].count += count as number;
    } else {
      merged[def.label] = { ...def, count: count as number };
    }
  }
  return Object.values(merged)
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);
}

// ─── Chart configs ───────────────────────────────────────────────────────────

const platformConfig: ChartConfig = {
  count: { label: 'Sessions', color: 'hsl(var(--chart-2))' },
};

const schemaConfig: ChartConfig = {
  faq:   { label: 'FAQ Schema',   color: 'hsl(var(--chart-1))' },
  howto: { label: 'HowTo Schema', color: 'hsl(var(--chart-2))' },
  parts: { label: 'Parts Schema', color: 'hsl(var(--chart-4))' },
};

// ─── Props ───────────────────────────────────────────────────────────────────

interface AEOMetricsDashboardProps {
  metrics: SchemaMetrics | null;
  aiTraffic: AITrafficReport | null;
  correlation: VisibilitySalesCorrelation | null;
  onLoadData: () => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export const AEOMetricsDashboard: React.FC<AEOMetricsDashboardProps> = ({
  metrics,
  aiTraffic,
  correlation,
  onLoadData,
}) => {
  const aiSessions      = (aiTraffic?.summary.ai_sessions as number)      || 0;
  const totalSessions   = (aiTraffic?.summary.total_sessions as number)   || 1;
  const aiPct           = ((aiSessions / totalSessions) * 100);
  const schemaPct       = metrics?.total_coverage_pct || 0;
  const revenuePerMention = correlation?.summary.avg_revenue_per_mention ?? null;

  const sources = useMemo(
    () => aiTraffic ? normaliseReferrers(aiTraffic.summary.referrers) : [],
    [aiTraffic],
  );

  const schemaItems = [
    { name: 'FAQ',    value: metrics?.faq_schemas_deployed    || 0, fill: '#F7B500', total: 100 },
    { name: 'HowTo',  value: metrics?.howto_schemas_deployed  || 0, fill: '#4285F4', total: 100 },
    { name: 'Parts',  value: metrics?.vehiclepart_schemas_deployed || 0, fill: '#10A37F', total: 100 },
  ];

  return (
    <div className="space-y-6">

      {/* ── Attribution reliability note ─────────────────────────────────── */}
      <div className="flex items-start gap-3 bg-[#1a1a1a] border border-yellow-600/30 rounded-sm px-4 py-3">
        <span className="text-yellow-500 text-sm shrink-0 mt-0.5">⚠</span>
        <p className="text-xs text-zinc-400 leading-relaxed">
          <span className="text-yellow-400 font-medium">Attribution floor:</span>{' '}
          Referrer-based detection captures only sessions where the browser preserved the AI
          source. Privacy settings, new tabs and mobile apps strip referrers — real AI-influenced
          traffic is estimated{' '}
          <span className="text-white font-medium">3–5× higher</span> than shown below.
        </p>
      </div>

      {/* ── KPI row ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5 flex flex-col gap-2">
          <span className="text-xs text-zinc-500 uppercase tracking-wider">AI Sessions</span>
          <span className="text-3xl font-bold text-[#F7B500]">{aiSessions.toLocaleString()}</span>
          <div className="h-1.5 bg-[#3a3a3a] rounded-full overflow-hidden">
            <div className="h-full bg-[#F7B500]" style={{ width: `${Math.min(aiPct * 5, 100)}%` }} />
          </div>
          <span className="text-xs text-zinc-500">detected via GA4 referrer</span>
        </div>

        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5 flex flex-col gap-2">
          <span className="text-xs text-zinc-500 uppercase tracking-wider">AI % of Traffic</span>
          <span className="text-3xl font-bold text-blue-400">{aiPct.toFixed(2)}%</span>
          <div className="h-1.5 bg-[#3a3a3a] rounded-full overflow-hidden">
            <div className="h-full bg-blue-400" style={{ width: `${Math.min(aiPct * 10, 100)}%` }} />
          </div>
          <span className="text-xs text-zinc-500">of {totalSessions.toLocaleString()} total sessions</span>
        </div>

        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5 flex flex-col gap-2">
          <span className="text-xs text-zinc-500 uppercase tracking-wider">Schema Coverage</span>
          <span className="text-3xl font-bold text-green-400">{schemaPct}%</span>
          <div className="h-1.5 bg-[#3a3a3a] rounded-full overflow-hidden">
            <div className="h-full bg-green-400" style={{ width: `${Math.min(schemaPct, 100)}%` }} />
          </div>
          <span className="text-xs text-zinc-500">of target pages covered</span>
        </div>

        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5 flex flex-col gap-2">
          <span className="text-xs text-zinc-500 uppercase tracking-wider">Revenue / Mention</span>
          {revenuePerMention !== null ? (
            <>
              <span className="text-3xl font-bold text-purple-400">{formatCurrency(revenuePerMention)}</span>
              <div className="h-1.5 bg-[#3a3a3a] rounded-full overflow-hidden">
                <div className="h-full bg-purple-400" style={{ width: `${Math.min(revenuePerMention / 10, 100)}%` }} />
              </div>
              <span className="text-xs text-zinc-500">avg per AI brand mention</span>
            </>
          ) : (
            <>
              <span className="text-3xl font-bold text-zinc-600">—</span>
              <span className="text-xs text-zinc-600">Run visibility checks + sync Shopify</span>
            </>
          )}
        </div>
      </div>

      {/* ── Main panels ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* AI Source Breakdown — 3/5 width */}
        <div className="lg:col-span-3 bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-white">AI Platform Breakdown</h3>
            <p className="text-xs text-zinc-500 mt-0.5">Sessions by referring AI source (GA4 referrer)</p>
          </div>

          {sources.length > 0 ? (
            <ChartContainer config={platformConfig} className="h-56 w-full">
              <BarChart
                layout="vertical"
                data={sources}
                margin={{ top: 0, right: 50, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" horizontal={false} />
                <XAxis type="number" stroke="#444" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="label"
                  stroke="#444"
                  fontSize={12}
                  width={75}
                  tick={{ fill: '#d1d5db' }}
                />
                <ChartTooltip content={<ChartTooltipContent />} cursor={{ fill: '#ffffff08' }} />
                <Bar dataKey="count" radius={[0, 3, 3, 0]} maxBarSize={28}>
                  <LabelList dataKey="count" position="right" style={{ fill: '#9ca3af', fontSize: 11 }} />
                  {sources.map((s) => (
                    <Cell key={s.label} fill={s.color} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ChartContainer>
          ) : (
            <div className="h-56 flex flex-col items-center justify-center gap-3 text-center">
              <div className="text-4xl opacity-20">📡</div>
              <p className="text-sm text-zinc-500">No AI referrer data yet.</p>
              <p className="text-xs text-zinc-600 max-w-xs">
                Connect Google Analytics 4 and ensure AI sources like chatgpt.com, perplexity.ai
                are sending referrer headers when visitors click through to your store.
              </p>
              <button
                onClick={onLoadData}
                className="mt-2 px-4 py-1.5 text-xs border border-[#3a3a3a] text-zinc-400 rounded-sm hover:bg-[#2a2a2a] transition-colors"
              >
                Refresh data
              </button>
            </div>
          )}
        </div>

        {/* Schema Coverage — 2/5 width */}
        <div className="lg:col-span-2 bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-white">Schema Deployment</h3>
            <p className="text-xs text-zinc-500 mt-0.5">Structured data deployed across site</p>
          </div>

          <ChartContainer config={schemaConfig} className="h-40 w-full">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="30%"
              outerRadius="90%"
              data={schemaItems}
              startAngle={90}
              endAngle={-270}
            >
              <RadialBar
                dataKey="value"
                cornerRadius={4}
                background={{ fill: '#2a2a2a' }}
              />
              <ChartTooltip
                content={<ChartTooltipContent formatter={(v) => [`${v} schemas`]} />}
              />
              <ChartLegend content={<ChartLegendContent />} />
            </RadialBarChart>
          </ChartContainer>

          {/* Schema counts */}
          <div className="mt-3 grid grid-cols-3 gap-2">
            {schemaItems.map(s => (
              <div key={s.name} className="text-center">
                <div className="text-lg font-bold" style={{ color: s.fill }}>{s.value}</div>
                <div className="text-xs text-zinc-500">{s.name}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Correlation ROI ───────────────────────────────────────────────── */}
      {correlation && (() => {
        // Sample-size guard. The Value/Mention figure was the audit's
        // biggest offender — it displays a precise currency amount ($X.XX)
        // derived from dividing revenue by mention count, then presents it
        // as if it's actionable. Below 30 mentions it's noise. Hide the
        // derived figure in that case and show a clear warning instead.
        const mentions = correlation.summary.total_mentions || 0;
        const hasMinimumSample = mentions >= 30;
        return (
        <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-5">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Visibility → Revenue Correlation</h3>
              <p className="text-xs text-zinc-500 mt-0.5">How AI mentions correlate with Shopify revenue (last 30 days)</p>
            </div>
            {!hasMinimumSample && (
              <span
                className="shrink-0 inline-flex items-center gap-1 text-xs px-2 py-1 rounded-sm font-medium bg-yellow-900/40 text-yellow-400 border border-yellow-700/40"
                title={`Only ${mentions} mentions — derived per-mention metrics are too noisy to act on. Correlation is not causation.`}
              >
                ⚠ Low sample (n={mentions})
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-[#0f0f0f] border border-[#2a2a2a] rounded-sm p-4">
              <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider">AI Mentions</p>
              <p className="text-2xl font-bold text-white">{mentions.toLocaleString()}</p>
              <p className="text-xs text-zinc-600 mt-1">brand cited in LLM responses</p>
            </div>
            <div className="bg-[#0f0f0f] border border-[#2a2a2a] rounded-sm p-4">
              <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider">Correlated Revenue</p>
              <p className="text-2xl font-bold text-[#F7B500]">{formatCurrency(correlation.summary.total_revenue)}</p>
              <p className="text-xs text-zinc-600 mt-1">from AI-visible topics</p>
            </div>
            <div
              className={`bg-[#0f0f0f] border border-[#2a2a2a] rounded-sm p-4 border-l-2 border-l-green-500 ${
                hasMinimumSample ? '' : 'opacity-60'
              }`}
            >
              <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider">Value / Mention</p>
              {hasMinimumSample ? (
                <>
                  <p className="text-2xl font-bold text-green-400">
                    {formatCurrency(correlation.summary.avg_revenue_per_mention)}
                  </p>
                  <p className="text-xs text-zinc-600 mt-1">avg revenue per AI citation</p>
                </>
              ) : (
                <>
                  <p className="text-2xl font-bold text-zinc-500">—</p>
                  <p className="text-xs text-yellow-500/80 mt-1">Need ≥30 mentions to compute</p>
                </>
              )}
            </div>
            <div className="bg-[#0f0f0f] border border-[#2a2a2a] rounded-sm p-4 border-l-2 border-l-blue-500">
              <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider">Top Topic</p>
              <p className="text-lg font-bold text-blue-400 truncate leading-tight mt-1">
                {correlation.summary.top_performing_topic || '—'}
              </p>
              <p className="text-xs text-zinc-600 mt-1">highest revenue topic</p>
            </div>
          </div>

          {/* Methodology disclaimer — the audit flagged that this panel
              implies causation. Make the uncertainty explicit so the owner
              doesn't invest based on correlation artifacts. */}
          <p className="mt-3 text-[11px] text-zinc-500 leading-relaxed">
            Correlation is not causation. The revenue figure reflects orders within AI-visible topics;
            it does not prove that AI mentions caused them. Use this as a directional signal
            alongside other attribution data, not as a standalone KPI.
          </p>
        </div>
        );
      })()}
    </div>
  );
};
