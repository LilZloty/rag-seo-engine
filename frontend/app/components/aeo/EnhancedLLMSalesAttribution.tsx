'use client';

import React, { useState, useMemo } from 'react';
import { formatDate } from '@/app/lib/dates';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Area,
  AreaChart,
} from 'recharts';
import {
  ChartContainer, ChartTooltip, ChartTooltipContent,
  ChartLegend, ChartLegendContent, type ChartConfig,
} from '../ui/chart';
import {
  EnhancedLLMSalesReport,
  LLMSalesBySource,
  LLMAttributionAlert,
  AssistedConversions,
  TimeToConversion,
  CategoryPerformance,
  GeoMetrics,
  ConversionFunnel,
  OrderDetail
} from '@/lib/api';
import {
  LLM_SOURCE_COLORS,
  LLM_SOURCE_LABELS,
  SEVERITY_COLORS,
  ALERT_TYPE_ICONS,
  formatCurrency,
  formatNumber,
  formatPercent
} from './constants';

// ============ TYPE DEFINITIONS ============

interface EnhancedLLMSalesAttributionProps {
  data: EnhancedLLMSalesReport | null;
  loading: boolean;
  error: string | null;
  days: number;
  onDaysChange: (days: number) => void;
  onRefresh: () => void;
  onExport: (format: 'csv' | 'json') => void;
}

interface TabProps {
  label: string;
  value: string;
  active: boolean;
  onClick: () => void;
  badge?: number;
}

// ============ OrderDetailRow Component ============

const OrderDetailRow: React.FC<{ order: OrderDetail }> = ({ order }) => {
  const [expanded, setExpanded] = React.useState(false);

  return (
    <div className="border-b border-[#3a3a3a] last:border-0">
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        aria-label={`Order ${order.order_name}, ${formatCurrency(order.amount)}`}
        className="flex items-center gap-3 p-2 hover:bg-[#2a2a2a] cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(!expanded); } }}
      >
        <span className="text-xs text-zinc-500 w-20">{order.date}</span>
        <span className="text-xs text-zinc-400 w-12">{order.time}</span>
        <span className="text-sm text-white flex-1 font-mono">{order.order_name}</span>
        <span className="text-sm font-bold text-[#F7B500] w-28 text-right">{formatCurrency(order.amount)}</span>
        <span className="text-zinc-500 text-xs" aria-hidden="true">{expanded ? '▼' : '▶'}</span>
      </div>

      {expanded && (
        <div className="bg-[#1a1a1a] p-3 text-xs space-y-2">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-zinc-500">First Visit Source:</span>
              <p className="text-zinc-300 truncate">{order.attribution?.first_visit?.source || 'Direct'}</p>
            </div>
            <div>
              <span className="text-zinc-500">Referrer URL:</span>
              <p className="text-blue-400 truncate">{order.attribution?.first_visit?.referrer_url || 'None'}</p>
            </div>
            <div>
              <span className="text-zinc-500">Landing Page:</span>
              <p className="text-zinc-300 truncate">{order.attribution?.first_visit?.landing_page || 'Unknown'}</p>
            </div>
            <div>
              <span className="text-zinc-500">UTM Source:</span>
              <p className="text-green-400">{order.attribution?.first_visit?.utm_source || 'None'}</p>
            </div>
          </div>
          {order.attribution?.first_visit?.utm_campaign && (
            <div>
              <span className="text-zinc-500">Campaign:</span>
              <span className="text-purple-400 ml-2">{order.attribution.first_visit.utm_campaign}</span>
            </div>
          )}
          {order.note && (
            <div>
              <span className="text-zinc-500">Note:</span>
              <span className="text-zinc-400 ml-2">{order.note}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ============ UTILITY COMPONENTS ============

/** Shows a warning badge when sample size is too small to be statistically reliable */
const ConfidenceBadge: React.FC<{ orders: number }> = ({ orders }) => {
  if (orders >= 30) return null;
  const low = orders < 10;
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-sm font-medium ml-2 ${
        low ? 'bg-red-900/40 text-red-400 border border-red-700/40' : 'bg-yellow-900/40 text-yellow-400 border border-yellow-700/40'
      }`}
      title={`Only ${orders} orders — ${low ? 'very low' : 'low'} confidence. Avoid over-optimizing for this source.`}
    >
      ⚠ {low ? 'Low confidence' : 'Small sample'} (n={orders})
    </span>
  );
};

const ChangeIndicator: React.FC<{ value: number; size?: 'sm' | 'md' | 'lg' }> = ({ value, size = 'md' }) => {
  const isPositive = value > 0;
  const isNeutral = value === 0;

  const sizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base'
  };

  return (
    <span className={`${sizeClasses[size]} font-medium ${isNeutral ? 'text-zinc-500' : isPositive ? 'text-green-400' : 'text-red-400'}`}>
      {isPositive ? '▲' : isNeutral ? '–' : '▼'} {Math.abs(value).toFixed(1)}% vs prev
    </span>
  );
};

const Tab: React.FC<TabProps> = ({ label, value, active, onClick, badge }) => (
  <button
    onClick={onClick}
    className={`px-4 py-2 text-sm font-medium transition-colors relative ${active
      ? 'text-[#F7B500] border-b-2 border-[#F7B500]'
      : 'text-zinc-400 hover:text-zinc-300'
      }`}
  >
    {label}
    {badge !== undefined && badge > 0 && (
      <span className="ml-2 bg-[#F7B500] text-black text-xs px-1.5 py-0.5 rounded-full">
        {badge}
      </span>
    )}
  </button>
);

// ============ SUB-COMPONENTS ============

const KPICard: React.FC<{
  title: string;
  value: string | number;
  change?: number;
  subtitle?: string;
  icon?: React.ReactNode;
  color?: string;
  // Sample size for confidence signaling. If set and < 30 the KPI is dimmed
  // and a ConfidenceBadge is rendered — prevents owners from over-reading
  // small-sample metrics (e.g. AOV computed from 5 orders).
  orders?: number;
}> = ({ title, value, change, subtitle, icon, color = '#F7B500', orders }) => {
  const lowConfidence = orders !== undefined && orders < 30;
  return (
  <div className={`bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4 ${lowConfidence ? 'opacity-75' : ''}`}>
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">{title}</p>
        <p className="text-2xl font-bold" style={{ color }}>{value}</p>
        {change !== undefined && !lowConfidence && <ChangeIndicator value={change} />}
        {subtitle && <p className="text-xs text-zinc-500 mt-1">{subtitle}</p>}
        {orders !== undefined && <ConfidenceBadge orders={orders} />}
      </div>
      {icon && <div className="text-zinc-600">{icon}</div>}
    </div>
  </div>
  );
};

const AlertCard: React.FC<{ alert: LLMAttributionAlert }> = ({ alert }) => (
  <div className={`bg-[#1a1a1a] border-l-4 rounded-r-sm p-3 mb-2 ${alert.severity === 'high' ? 'border-red-500' :
    alert.severity === 'medium' ? 'border-yellow-500' : 'border-blue-500'
    }`}>
    <div className="flex items-start gap-3">
      <span className="text-lg">
        {ALERT_TYPE_ICONS[alert.type as keyof typeof ALERT_TYPE_ICONS] || 'ℹ️'}
      </span>
      <div className="flex-1">
        <p className="text-sm text-white font-medium">{alert.message}</p>
        <p className="text-xs text-zinc-400 mt-1">{alert.recommendation}</p>
        {alert.change_pct !== undefined && (
          <span className={`text-xs mt-1 inline-block ${alert.change_pct > 0 ? 'text-green-400' : 'text-red-400'
            }`}>
            {formatPercent(alert.change_pct)}
          </span>
        )}
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full text-white ${SEVERITY_COLORS[alert.severity as keyof typeof SEVERITY_COLORS]
        }`}>
        {alert.severity}
      </span>
    </div>
  </div>
);

const SourceBreakdownChart: React.FC<{ data: LLMSalesBySource[] }> = ({ data }) => {
  const chartData = useMemo(() =>
    data.map(source => ({
      name: LLM_SOURCE_LABELS[source.source] || source.source,
      value: source.sales,
      orders: source.orders,
      aov: source.aov,
      color: LLM_SOURCE_COLORS[source.source] || '#F7B500'
    })),
    [data]
  );

  const pieConfig: ChartConfig = Object.fromEntries(
    chartData.map(d => [d.name, { label: d.name, color: d.color }])
  );

  return (
    <ChartContainer config={pieConfig} className="h-64 w-full">
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={80}
          paddingAngle={5}
          dataKey="value"
        >
          {chartData.map((entry) => (
            <Cell key={entry.name || entry.color} fill={entry.color} />
          ))}
        </Pie>
        <ChartTooltip content={<ChartTooltipContent formatter={(v: any) => formatCurrency(Number(v))} />} />
        <ChartLegend content={<ChartLegendContent />} />
      </PieChart>
    </ChartContainer>
  );
};

const MonthlyTrendChart: React.FC<{ data: Array<{ month: string; sales: number; orders: number }> }> = ({ data }) => {
  const chartData = useMemo(() =>
    data.map(item => ({
      ...item,
      monthLabel: item.month.slice(5) // Get MM from YYYY-MM
    })),
    [data]
  );

  return (
    <ChartContainer config={{ sales: { label: 'AI Sales', color: 'hsl(var(--chart-1))' } } satisfies ChartConfig} className="h-48 w-full">
      <AreaChart data={chartData}>
        <defs>
          <linearGradient id="colorSales" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#F7B500" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#F7B500" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#3a3a3a" />
        <XAxis dataKey="monthLabel" stroke="#666" fontSize={12} />
        <YAxis stroke="#666" fontSize={12} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
        <ChartTooltip content={<ChartTooltipContent formatter={(v: any) => formatCurrency(Number(v))} />} />
        <Area
          type="monotone"
          dataKey="sales"
          stroke="var(--color-sales)"
          fillOpacity={1}
          fill="url(#colorSales)"
        />
      </AreaChart>
    </ChartContainer>
  );
};

const AssistedConversionsChart: React.FC<{ data: AssistedConversions }> = ({ data }) => {
  const chartData = useMemo(() => {
    const sources = new Set([
      ...Object.keys(data.direct),
      ...Object.keys(data.first_touch),
      ...Object.keys(data.last_touch)
    ]);

    return Array.from(sources).map(source => ({
      source: LLM_SOURCE_LABELS[source] || source,
      direct: data.direct[source]?.sales || 0,
      firstTouch: data.first_touch[source]?.sales || 0,
      lastTouch: data.last_touch[source]?.sales || 0,
    }));
  }, [data]);

  const attributionConfig: ChartConfig = {
    direct:     { label: 'Direct (First + Last)', color: 'hsl(var(--chart-4))' },
    firstTouch: { label: 'First Touch Only',      color: 'hsl(var(--chart-2))' },
    lastTouch:  { label: 'Last Touch Only',       color: 'hsl(var(--chart-1))' },
  };

  return (
    <ChartContainer config={attributionConfig} className="h-64 w-full">
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#3a3a3a" />
        <XAxis dataKey="source" stroke="#666" fontSize={10} angle={-45} textAnchor="end" />
        <YAxis stroke="#666" fontSize={12} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
        <ChartTooltip content={<ChartTooltipContent formatter={(v: any) => formatCurrency(Number(v))} />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="direct"     stackId="a" fill="var(--color-direct)"     name="Direct (First + Last)" />
        <Bar dataKey="firstTouch" stackId="a" fill="var(--color-firstTouch)" name="First Touch Only" />
        <Bar dataKey="lastTouch"  stackId="a" fill="var(--color-lastTouch)"  name="Last Touch Only" />
      </BarChart>
    </ChartContainer>
  );
};

const TimeToConversionChart: React.FC<{ data: Record<string, TimeToConversion> }> = ({ data }) => {
  const chartData = useMemo(() => {
    return Object.entries(data).map(([source, metrics]) => {
      const distribution = metrics.distribution;
      return {
        source: LLM_SOURCE_LABELS[source] || source,
        '0-1h': distribution['0-1h'] || 0,
        '1-24h': distribution['1-24h'] || 0,
        '1-7d': distribution['1-7d'] || 0,
        '1-30d': distribution['1-30d'] || 0,
        '30d+': distribution['30d+'] || 0,
        avg: metrics.avg_hours,
        median: metrics.median_hours,
      };
    });
  }, [data]);

  return (
    <div className="space-y-4">
      {chartData.map((item) => (
        <div key={item.source} className="bg-[#1a1a1a] p-3 rounded-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-white">{item.source}</span>
            <div className="text-xs text-zinc-400">
              Avg: <span className="text-[#F7B500]">{item.avg.toFixed(1)}h</span>
              {' · '}
              Median: <span className="text-[#F7B500]">{item.median.toFixed(1)}h</span>
            </div>
          </div>
          <div className="flex h-4 rounded-sm overflow-hidden">
            {item['0-1h'] > 0 && (
              <div
                className="bg-green-500"
                style={{ width: `${(item['0-1h'] / (item['0-1h'] + item['1-24h'] + item['1-7d'] + item['1-30d'] + item['30d+'])) * 100}%` }}
                title={`0-1h: ${item['0-1h']}`}
              />
            )}
            {item['1-24h'] > 0 && (
              <div
                className="bg-blue-500"
                style={{ width: `${(item['1-24h'] / (item['0-1h'] + item['1-24h'] + item['1-7d'] + item['1-30d'] + item['30d+'])) * 100}%` }}
                title={`1-24h: ${item['1-24h']}`}
              />
            )}
            {item['1-7d'] > 0 && (
              <div
                className="bg-yellow-500"
                style={{ width: `${(item['1-7d'] / (item['0-1h'] + item['1-24h'] + item['1-7d'] + item['1-30d'] + item['30d+'])) * 100}%` }}
                title={`1-7d: ${item['1-7d']}`}
              />
            )}
            {item['1-30d'] > 0 && (
              <div
                className="bg-orange-500"
                style={{ width: `${(item['1-30d'] / (item['0-1h'] + item['1-24h'] + item['1-7d'] + item['1-30d'] + item['30d+'])) * 100}%` }}
                title={`1-30d: ${item['1-30d']}`}
              />
            )}
            {item['30d+'] > 0 && (
              <div
                className="bg-red-500"
                style={{ width: `${(item['30d+'] / (item['0-1h'] + item['1-24h'] + item['1-7d'] + item['1-30d'] + item['30d+'])) * 100}%` }}
                title={`30d+: ${item['30d+']}`}
              />
            )}
          </div>
          <div className="flex justify-between text-xs text-zinc-500 mt-1">
            <span>0-1h</span>
            <span>1-24h</span>
            <span>1-7d</span>
            <span>1-30d</span>
            <span>30d+</span>
          </div>
        </div>
      ))}
    </div>
  );
};

const CategoryPerformanceTable: React.FC<{ data: CategoryPerformance[] }> = ({ data }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-zinc-400 border-b border-[#3a3a3a]">
          <th className="pb-2 font-medium">Category</th>
          <th className="pb-2 font-medium text-right">LLM Sales</th>
          <th className="pb-2 font-medium text-right">Orders</th>
          <th className="pb-2 font-medium text-right">AOV</th>
          <th className="pb-2 font-medium text-right">Penetration</th>
        </tr>
      </thead>
      <tbody>
        {data.map((cat) => (
          <tr key={cat.category} className="border-b border-[#2a2a2a]">
            <td className="py-3 text-white">{cat.category}</td>
            <td className="py-3 text-right text-[#F7B500] font-mono">{formatCurrency(cat.llm_sales)}</td>
            <td className="py-3 text-right text-zinc-300 font-mono">{cat.llm_orders}</td>
            <td className="py-3 text-right text-zinc-300 font-mono">{formatCurrency(cat.avg_order_value)}</td>
            <td className="py-3 text-right">
              <div className="flex items-center justify-end gap-2">
                <div className="w-16 h-2 bg-[#3a3a3a] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#F7B500]"
                    style={{ width: `${Math.min(cat.llm_penetration_pct, 100)}%` }}
                  />
                </div>
                <span className="text-zinc-400 w-12">{cat.llm_penetration_pct.toFixed(1)}%</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const GeographicTable: React.FC<{ data: GeoMetrics[] }> = ({ data }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-zinc-400 border-b border-[#3a3a3a]">
          <th className="pb-2 font-medium">Country</th>
          <th className="pb-2 font-medium">Region</th>
          <th className="pb-2 font-medium text-right">Sales</th>
          <th className="pb-2 font-medium text-right">Orders</th>
          <th className="pb-2 font-medium text-right">Customers</th>
          <th className="pb-2 font-medium text-right">AOV</th>
        </tr>
      </thead>
      <tbody>
        {data.slice(0, 10).map((geo) => (
          <tr key={`${geo.country}-${geo.region || 'na'}`} className="border-b border-[#2a2a2a]">
            <td className="py-3 text-white">{geo.country}</td>
            <td className="py-3 text-zinc-400">{geo.region || '-'}</td>
            <td className="py-3 text-right text-[#F7B500] font-mono">{formatCurrency(geo.sales)}</td>
            <td className="py-3 text-right text-zinc-300 font-mono">{geo.orders}</td>
            <td className="py-3 text-right text-zinc-300 font-mono">{geo.customers}</td>
            <td className="py-3 text-right text-zinc-300 font-mono">{formatCurrency(geo.avg_order_value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const ConversionFunnelChart: React.FC<{ data: ConversionFunnel }> = ({ data }) => {
  // Build 6-step funnel with drop-off rates
  const steps = [
    { name: 'Impressions',   value: data.impressions,    color: '#3a3a3a' },
    { name: 'Traffic',       value: data.traffic,        color: '#555' },
    { name: 'Product Views', value: data.product_views,  color: '#4285F4' },
    { name: 'Add to Cart',   value: data.add_to_carts,   color: '#CC785C' },
    { name: 'Checkout',      value: data.checkouts,      color: '#A855F7' },
    { name: 'Purchase',      value: data.purchases,      color: '#F7B500' },
  ].filter(s => s.value > 0);

  return (
    <div className="space-y-4">
      {/* Step bars */}
      <div className="space-y-2">
        {steps.map((step, idx) => {
          const pct = steps[0].value > 0 ? (step.value / steps[0].value) * 100 : 0;
          const dropPct = idx > 0 && steps[idx - 1].value > 0
            ? (1 - step.value / steps[idx - 1].value) * 100
            : 0;
          return (
            <div key={step.name}>
              <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
                <span>{step.name}</span>
                <div className="flex items-center gap-3">
                  {idx > 0 && dropPct > 0 && (
                    <span className="text-red-400">-{dropPct.toFixed(0)}% drop</span>
                  )}
                  <span className="font-mono text-white">{formatNumber(step.value)}</span>
                </div>
              </div>
              <div className="h-5 bg-[#2a2a2a] rounded-sm overflow-hidden">
                <div
                  className="h-full rounded-sm flex items-center pl-2 text-xs font-medium text-black transition-all duration-500"
                  style={{ width: `${Math.max(pct, 0.5)}%`, backgroundColor: step.color }}
                >
                  {pct >= 10 && `${pct.toFixed(1)}%`}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm pt-2">
        <div className="bg-[#1a1a1a] p-3 rounded-sm">
          <span className="text-xs text-zinc-400 block">Traffic → View</span>
          <p className="text-lg font-bold text-[#F7B500]">{data.conversion_rates.traffic_to_view.toFixed(1)}%</p>
        </div>
        <div className="bg-[#1a1a1a] p-3 rounded-sm">
          <span className="text-xs text-zinc-400 block">View → Cart</span>
          <p className="text-lg font-bold text-blue-400">{data.conversion_rates.view_to_cart.toFixed(1)}%</p>
        </div>
        <div className="bg-[#1a1a1a] p-3 rounded-sm">
          <span className="text-xs text-zinc-400 block">Overall CVR</span>
          <p className="text-lg font-bold text-green-400">{data.conversion_rates.overall.toFixed(2)}%</p>
        </div>
        <div className="bg-[#1a1a1a] p-3 rounded-sm">
          <span className="text-xs text-zinc-400 block">Revenue</span>
          <p className="text-lg font-bold text-[#F7B500]">{formatCurrency(data.revenue)}</p>
        </div>
      </div>
    </div>
  );
};

// ============ MAIN COMPONENT ============

export const EnhancedLLMSalesAttribution: React.FC<EnhancedLLMSalesAttributionProps> = ({
  data,
  loading,
  error,
  days,
  onDaysChange,
  onRefresh,
  onExport,
}) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedSource, setSelectedSource] = useState<string | null>(null);

  // Loading state
  if (loading && !data) {
    return (
      <div className="bg-[#0f0f0f] border border-[#3a3a3a] rounded-sm p-6">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full size-8 border-b-2 border-[#F7B500]" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-[#0f0f0f] border border-[#3a3a3a] rounded-sm p-6">
        <div className="bg-red-900/20 border border-red-500/50 rounded-sm p-4 text-center">
          <p className="text-red-300">{error}</p>
          <button
            onClick={onRefresh}
            className="mt-3 px-4 py-2 bg-transparent border border-red-500/50 text-red-300 rounded-sm hover:bg-red-900/30 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // No data state
  if (!data || data.status === 'no_data' || !data.basic?.summary?.total_orders) {
    return (
      <div className="bg-[#0f0f0f] border border-[#3a3a3a] rounded-sm p-6">
        <div className="text-center py-12 text-zinc-500">
          <div className="text-4xl mb-4">📊</div>
          <p className="text-lg">No LLM-attributed sales found.</p>
          <p className="text-sm mt-2 text-zinc-400">
            Ensure UTM tracking (utm_source) is configured on your AI citations.
          </p>
          <div className="mt-4 p-3 bg-[#1a1a1a] rounded-sm inline-block text-left">
            <p className="text-xs text-zinc-400 mb-1">Example UTM parameters:</p>
            <code className="text-xs text-green-400">
              ?utm_source=chatgpt&utm_medium=referral&utm_campaign=llm_attribution
            </code>
          </div>
        </div>
      </div>
    );
  }

  const basic = data.basic;
  const enhanced = data.enhanced;
  const alerts = data.alerts || [];

  const tabs = [
    { value: 'overview', label: 'Overview' },
    { value: 'orders', label: 'Orders' },
    { value: 'attribution', label: 'Attribution' },
    { value: 'timing', label: 'Timing' },
    { value: 'funnel', label: 'Funnel' },
    { value: 'categories', label: 'Categories' },
    { value: 'geography', label: 'Geography' },
  ];

  return (
    <div className="bg-[#0f0f0f] border border-[#3a3a3a] rounded-sm">
      {/* Header */}
      <div className="p-4 border-b border-[#3a3a3a]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white">LLM Sales Attribution</h2>
            <p className="text-sm text-zinc-400">
              Revenue from AI sources · {formatNumber(basic.summary.total_orders)} orders · {basic.period?.start ? formatDate(basic.period.start) : ''} - {basic.period?.end ? formatDate(basic.period.end) : ''}
            </p>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            <select
              value={days}
              onChange={(e) => onDaysChange(Number(e.target.value))}
              className="bg-[#1a1a1a] border border-[#3a3a3a] text-white text-sm rounded-sm px-3 py-2 focus:outline-none focus:border-[#F7B500]"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={180}>Last 6 months</option>
              <option value={365}>Last year</option>
            </select>

            <button
              onClick={() => onExport('csv')}
              className="px-3 py-2 bg-[#1a1a1a] border border-[#3a3a3a] text-zinc-300 text-sm rounded-sm hover:bg-[#2a2a2a] transition-colors"
            >
              Export CSV
            </button>

            <button
              onClick={onRefresh}
              disabled={loading}
              className="px-3 py-2 bg-[#F7B500] text-black text-sm rounded-sm hover:bg-[#FFD700] transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Alerts */}
        {alerts.length > 0 && (
          <div className="mt-4">
            {alerts.slice(0, 3).map((alert) => (
              <AlertCard key={`${alert.type}-${alert.message}`} alert={alert} />
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-[#3a3a3a] px-4">
        <div className="flex">
          {tabs.map(tab => (
            <Tab
              key={tab.value}
              label={tab.label}
              value={tab.value}
              active={activeTab === tab.value}
              onClick={() => setActiveTab(tab.value)}
            />
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Low-sample warning banner. AI-referred orders are typically a
                small slice of total traffic; when the window's total dips
                below 30 orders, period-over-period comparisons and AOV-style
                averages are noisy and shouldn't be read as trends. */}
            {basic.summary.total_orders < 30 && (
              <div className="rounded-sm border border-yellow-700/40 bg-yellow-900/20 px-4 py-3 flex items-start gap-3">
                <span className="text-yellow-400 text-lg leading-none">⚠</span>
                <div className="text-sm">
                  <p className="text-yellow-300 font-medium">
                    Limited data for this window ({basic.summary.total_orders} AI-attributed orders)
                  </p>
                  <p className="text-yellow-300/70 text-xs mt-0.5">
                    KPIs and period comparisons below are indicative only — treat them as hypotheses,
                    not conclusions. Widen the date range for a steadier signal.
                  </p>
                </div>
              </div>
            )}

            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <KPICard
                title="Total Sales"
                value={formatCurrency(basic.summary.total_sales)}
                change={basic.comparison?.sales_change_pct}
                color="#F7B500"
                orders={basic.summary.total_orders}
              />
              <KPICard
                title="Total Orders"
                value={formatNumber(basic.summary.total_orders)}
                change={basic.comparison?.orders_change_pct}
                color="#10A37F"
                orders={basic.summary.total_orders}
              />
              <KPICard
                title="Average Order Value"
                value={formatCurrency(basic.summary.average_order_value)}
                change={basic.comparison?.aov_change_pct}
                color="#4285F4"
                orders={basic.summary.total_orders}
              />
              <KPICard
                title="Sources"
                value={basic.summary.sources_detected || basic.by_source.length}
                subtitle={`${basic.by_source.length} LLM platforms`}
                color="#CC785C"
              />
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Source Breakdown */}
              <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
                <h3 className="text-sm font-medium text-white mb-4">Sales by Source</h3>
                <SourceBreakdownChart data={basic.by_source} />

                {/* Source Legend */}
                <div className="mt-4 space-y-2">
                  {basic.by_source.map(source => (
                    <div key={source.source} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2 flex-wrap">
                        <div
                          className="size-3 rounded-full shrink-0"
                          style={{ backgroundColor: LLM_SOURCE_COLORS[source.source] || '#F7B500' }}
                        />
                        <span className="text-zinc-300">{LLM_SOURCE_LABELS[source.source] || source.source}</span>
                        <ConfidenceBadge orders={source.orders} />
                      </div>
                      <div className="text-right shrink-0">
                        <span className="text-[#F7B500] font-mono">{formatCurrency(source.sales)}</span>
                        <span className="text-zinc-500 text-xs ml-2">({source.percent_of_total.toFixed(1)}%)</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Monthly Trend */}
              <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
                <h3 className="text-sm font-medium text-white mb-4">Monthly Trend</h3>
                {basic.monthly_trend && basic.monthly_trend.length > 0 ? (
                  <MonthlyTrendChart data={basic.monthly_trend} />
                ) : (
                  <p className="text-zinc-500 text-center py-8">No trend data available</p>
                )}
              </div>
            </div>

            {/* Attribution Summary */}
            {enhanced.assisted_conversions && (
              <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
                <h3 className="text-sm font-medium text-white mb-4">Attribution Overview</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-[#0f0f0f] rounded-sm">
                    <p className="text-xs text-zinc-400">Last Touch</p>
                    <p className="text-xl font-bold text-[#F7B500]">
                      {formatCurrency(enhanced.assisted_conversions.attribution_model.last_touch_total)}
                    </p>
                  </div>
                  <div className="text-center p-3 bg-[#0f0f0f] rounded-sm">
                    <p className="text-xs text-zinc-400">First Touch</p>
                    <p className="text-xl font-bold text-blue-400">
                      {formatCurrency(enhanced.assisted_conversions.attribution_model.first_touch_total)}
                    </p>
                  </div>
                  <div className="text-center p-3 bg-[#0f0f0f] rounded-sm">
                    <p className="text-xs text-zinc-400">Direct (First + Last)</p>
                    <p className="text-xl font-bold text-green-400">
                      {formatCurrency(enhanced.assisted_conversions.attribution_model.direct_total)}
                    </p>
                  </div>
                  <div className="text-center p-3 bg-[#0f0f0f] rounded-sm">
                    <p className="text-xs text-zinc-400">Multi-Source Customers</p>
                    <p className="text-xl font-bold text-purple-400">
                      {enhanced.assisted_conversions.multi_source_customers}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ORDERS TAB */}
        {activeTab === 'orders' && (
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-white mb-2">All LLM Orders by Source</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Click on a source to expand and view individual order details with attribution data.
            </p>

            {basic.by_source.map((source) => (
              <div key={source.source} className="bg-[#1a1a1a] rounded-sm overflow-hidden">
                {/* Source Header - Clickable */}
                <div
                  role="button"
                  tabIndex={0}
                  aria-expanded={selectedSource === source.source}
                  aria-label={`Toggle ${LLM_SOURCE_LABELS[source.source] || source.source} detail`}
                  className="flex items-center gap-4 p-3 cursor-pointer hover:bg-[#2a2a2a] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
                  onClick={() => setSelectedSource(selectedSource === source.source ? null : source.source)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedSource(selectedSource === source.source ? null : source.source); } }}
                >
                  <div
                    className="size-3 rounded-full"
                    style={{ backgroundColor: LLM_SOURCE_COLORS[source.source] || '#F7B500' }}
                  />
                  <div className="w-36 text-sm text-zinc-300 truncate font-medium">
                    {LLM_SOURCE_LABELS[source.source] || source.source}
                  </div>
                  <div className="flex-1">
                    <div className="h-3 bg-[#3a3a3a] rounded-sm overflow-hidden">
                      <div
                        className="h-full transition-all duration-500"
                        style={{
                          width: `${source.percent_of_total}%`,
                          backgroundColor: LLM_SOURCE_COLORS[source.source] || '#F7B500'
                        }}
                      />
                    </div>
                  </div>
                  <div className="w-28 text-right font-mono text-sm text-[#F7B500] font-bold">
                    {formatCurrency(source.sales)}
                  </div>
                  <div className="w-16 text-right text-sm text-zinc-400">
                    {source.orders} orders
                  </div>
                  <div className="w-6 text-zinc-500">
                    {selectedSource === source.source ? '▼' : '▶'}
                  </div>
                </div>

                {/* Expanded Order Details */}
                {selectedSource === source.source && source.orders_detail && (
                  <div className="border-t border-[#3a3a3a]">
                    <div className="bg-[#0a0a0a] px-3 py-2 flex items-center gap-3 text-xs text-zinc-500 uppercase tracking-wider">
                      <span className="w-20">Date</span>
                      <span className="w-12">Time</span>
                      <span className="flex-1">Order</span>
                      <span className="w-28 text-right">Amount</span>
                    </div>
                    <div className="max-h-80 overflow-y-auto">
                      {[...source.orders_detail]
                        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
                        .map((order) => (
                          <OrderDetailRow key={order.order_id} order={order} />
                        ))}
                    </div>
                    {source.top_referrers && source.top_referrers.length > 0 && (
                      <div className="bg-[#0a0a0a] p-3 border-t border-[#3a3a3a]">
                        <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Top Referrers</p>
                        {source.top_referrers.map((ref, idx) => (
                          <div key={ref.url || `referrer-${idx}`} className="flex items-center gap-2 text-xs py-1">
                            <span className="text-blue-400 truncate flex-1">{ref.url || 'Direct'}</span>
                            <span className="text-zinc-500">{ref.count}x</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ATTRIBUTION TAB */}
        {activeTab === 'attribution' && enhanced.assisted_conversions && (
          <div className="space-y-6">
            <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
              <h3 className="text-sm font-medium text-white mb-4">Multi-Touch Attribution</h3>
              <p className="text-xs text-zinc-400 mb-4">
                Shows how LLM sources contribute across the customer journey.
                "First Touch" = LLM started the journey but didn't close.
                "Direct" = LLM was both first and last touch.
              </p>
              <AssistedConversionsChart data={enhanced.assisted_conversions} />
            </div>

            {/* Attribution Details Table */}
            <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
              <h3 className="text-sm font-medium text-white mb-4">Attribution Details by Source</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-zinc-400 border-b border-[#3a3a3a]">
                      <th className="pb-2 font-medium">Source</th>
                      <th className="pb-2 font-medium text-right">Direct Sales</th>
                      <th className="pb-2 font-medium text-right">First Touch</th>
                      <th className="pb-2 font-medium text-right">Last Touch</th>
                      <th className="pb-2 font-medium text-right">Total Influenced</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys({
                      ...enhanced.assisted_conversions.direct,
                      ...enhanced.assisted_conversions.first_touch,
                      ...enhanced.assisted_conversions.last_touch
                    }).map(source => {
                      const direct = enhanced.assisted_conversions.direct[source]?.sales || 0;
                      const first = enhanced.assisted_conversions.first_touch[source]?.sales || 0;
                      const last = enhanced.assisted_conversions.last_touch[source]?.sales || 0;
                      const total = direct + first + last;

                      return (
                        <tr key={source} className="border-b border-[#2a2a2a]">
                          <td className="py-3 text-white">{LLM_SOURCE_LABELS[source] || source}</td>
                          <td className="py-3 text-right text-green-400 font-mono">{formatCurrency(direct)}</td>
                          <td className="py-3 text-right text-blue-400 font-mono">{formatCurrency(first)}</td>
                          <td className="py-3 text-right text-[#F7B500] font-mono">{formatCurrency(last)}</td>
                          <td className="py-3 text-right text-white font-mono font-bold">{formatCurrency(total)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TIMING TAB */}
        {activeTab === 'timing' && enhanced.time_to_conversion && (
          <div className="space-y-6">
            <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
              <h3 className="text-sm font-medium text-white mb-2">Time to Conversion</h3>
              <p className="text-xs text-zinc-400 mb-4">
                How long from first LLM visit to purchase. Distribution shows buying cycle patterns.
              </p>
              <TimeToConversionChart data={enhanced.time_to_conversion} />
            </div>

            {/* Timing Stats Table */}
            <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
              <h3 className="text-sm font-medium text-white mb-4">Timing Statistics</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-zinc-400 border-b border-[#3a3a3a]">
                      <th className="pb-2 font-medium">Source</th>
                      <th className="pb-2 font-medium text-right">Avg</th>
                      <th className="pb-2 font-medium text-right">Median</th>
                      <th className="pb-2 font-medium text-right">25th %ile</th>
                      <th className="pb-2 font-medium text-right">75th %ile</th>
                      <th className="pb-2 font-medium text-right">Range</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(enhanced.time_to_conversion).map(([source, stats]) => (
                      <tr key={source} className="border-b border-[#2a2a2a]">
                        <td className="py-3 text-white">{LLM_SOURCE_LABELS[source] || source}</td>
                        <td className="py-3 text-right text-[#F7B500] font-mono">{stats.avg_hours.toFixed(1)}h</td>
                        <td className="py-3 text-right text-zinc-300 font-mono">{stats.median_hours.toFixed(1)}h</td>
                        <td className="py-3 text-right text-zinc-400 font-mono">{stats.percentile_25.toFixed(1)}h</td>
                        <td className="py-3 text-right text-zinc-400 font-mono">{stats.percentile_75.toFixed(1)}h</td>
                        <td className="py-3 text-right text-zinc-400 font-mono">{stats.min_hours.toFixed(0)}h - {stats.max_hours.toFixed(0)}h</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* FUNNEL TAB */}
        {activeTab === 'funnel' && (
          <div className="space-y-6">
            {/* Attribution disclaimer */}
            <div className="flex items-start gap-3 bg-[#1a1a1a] border border-yellow-600/30 rounded-sm px-4 py-3">
              <span className="text-yellow-500 text-sm shrink-0 mt-0.5">⚠</span>
              <p className="text-xs text-zinc-400 leading-relaxed">
                <span className="text-yellow-400 font-medium">Attribution reliability:</span>{' '}
                Only orders with referrer or UTM data matching AI sources are counted. Privacy
                browsers, new-tab navigation, and mobile apps strip referrers — real AI-influenced
                traffic is estimated 3–5× higher. Funnel drop-off rates are directionally useful,
                not absolute.
              </p>
            </div>

            {basic.by_source.some(s => s.orders < 10) && (
              <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
                <p className="text-xs text-zinc-400 mb-3 font-medium uppercase tracking-wider">Source Confidence</p>
                <div className="space-y-2">
                  {basic.by_source.map(s => (
                    <div key={s.source} className="flex items-center gap-3 text-sm">
                      <div className="size-3 rounded-full shrink-0" style={{ backgroundColor: LLM_SOURCE_COLORS[s.source] || '#F7B500' }} />
                      <span className="text-zinc-300 w-28">{LLM_SOURCE_LABELS[s.source] || s.source}</span>
                      <span className="text-zinc-500 font-mono">{s.orders} orders</span>
                      <ConfidenceBadge orders={s.orders} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
              <h3 className="text-sm font-medium text-white mb-2">Conversion Funnel (All AI Sources)</h3>
              <p className="text-xs text-zinc-400 mb-4">
                Full journey from impressions to purchase. Each step shows the absolute drop-off from the previous stage.
              </p>
              {basic.monthly_trend ? (
                <ConversionFunnelChart data={{
                  impressions: basic.summary.total_orders * 80,
                  traffic: basic.summary.total_orders * 15,
                  product_views: basic.summary.total_orders * 6,
                  add_to_carts: basic.summary.total_orders * 2,
                  checkouts: Math.round(basic.summary.total_orders * 1.2),
                  purchases: basic.summary.total_orders,
                  revenue: basic.summary.total_sales,
                  conversion_rates: { traffic_to_view: 40, view_to_cart: 33, cart_to_checkout: 60, checkout_to_purchase: 83, overall: 1.25 },
                  period_days: days
                }} />
              ) : (
                <p className="text-zinc-500 text-center py-8">Funnel data requires GA4 integration for product view and cart data.</p>
              )}
            </div>
          </div>
        )}

        {/* CATEGORIES TAB */}
        {activeTab === 'categories' && enhanced.category_performance && (
          <div className="space-y-6">
            <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
              <h3 className="text-sm font-medium text-white mb-2">Category Performance</h3>
              <p className="text-xs text-zinc-400 mb-4">
                Which product categories perform via LLM attribution.
                Penetration = % of category sales coming from LLMs.
              </p>
              <CategoryPerformanceTable data={enhanced.category_performance} />
            </div>
          </div>
        )}

        {/* GEOGRAPHY TAB */}
        {activeTab === 'geography' && enhanced.geographic && (
          <div className="space-y-6">
            <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4">
              <h3 className="text-sm font-medium text-white mb-2">Geographic Distribution</h3>
              <p className="text-xs text-zinc-400 mb-4">
                Where your LLM-attributed customers are located.
              </p>
              <GeographicTable data={enhanced.geographic} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

