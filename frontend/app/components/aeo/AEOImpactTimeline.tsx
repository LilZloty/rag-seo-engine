'use client';

import React, { useState } from 'react';
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { ChartContainer, ChartLegend, ChartLegendContent, type ChartConfig } from '../ui/chart';
import { AEOEvent, AEOEventType, MonthlyTrend } from '@/lib/api';
import { formatCurrency } from './constants';

// ─── helpers ────────────────────────────────────────────────────────────────

const EVENT_TYPE_LABELS: Record<AEOEventType, string> = {
  llms_txt_deployed: 'llms.txt',
  schema_added: 'Schema',
  content_updated: 'Content',
  visibility_check: 'Visibility',
  keyword_published: 'Keyword',
  other: 'Other',
};

const EVENT_TYPE_COLORS: Record<AEOEventType, string> = {
  llms_txt_deployed: '#F7B500',
  schema_added: '#10A37F',
  content_updated: '#4285F4',
  visibility_check: '#CC785C',
  keyword_published: '#A855F7',
  other: '#6b7280',
};

const EVENT_TYPE_OPTIONS: { value: AEOEventType; label: string }[] = [
  { value: 'llms_txt_deployed', label: 'llms.txt Deployed / Updated' },
  { value: 'schema_added', label: 'Schema.org Added' },
  { value: 'content_updated', label: 'Content Updated / Published' },
  { value: 'visibility_check', label: 'Visibility Check Run' },
  { value: 'keyword_published', label: 'Keyword Page Published' },
  { value: 'other', label: 'Other Improvement' },
];

/** Extract "MM" from "YYYY-MM" to match the MonthlyTrend monthLabel */
function eventMonthLabel(isoDate: string): string {
  // isoDate can be "2025-02-15" or "2025-02-15T..."
  return isoDate.slice(5, 7);
}

// ─── types ──────────────────────────────────────────────────────────────────

interface AEOImpactTimelineProps {
  monthlyTrend: MonthlyTrend[] | null | undefined;
  events: AEOEvent[];
  onAddEvent: (payload: {
    event_date: string;
    event_type: AEOEventType;
    title: string;
    description?: string;
  }) => Promise<void>;
  onDeleteEvent: (id: number) => Promise<void>;
  loading?: boolean;
}

// ─── Chart config ─────────────────────────────────────────────────────────────

const timelineConfig: ChartConfig = {
  orders: { label: 'AI Orders',  color: 'hsl(var(--chart-4))' },
  sales:  { label: 'AI Revenue', color: 'hsl(var(--chart-1))' },
};

// ─── Event-aware tooltip (kept custom — event list can't use ChartTooltipContent) ──

const EventTooltip: React.FC<any> = ({ active, payload, label, events }) => {
  if (!active || !payload?.length) return null;
  const monthEvents = events.filter((e: AEOEvent) => eventMonthLabel(e.event_date) === label);
  return (
    <div className="bg-[#1a1a1a] border border-[#333333] rounded-lg p-3 text-xs shadow-lg max-w-xs">
      <p className="text-[#888888] mb-2">Month {label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-mono">
          {p.name}: {formatCurrency(p.value)}
        </p>
      ))}
      {monthEvents.length > 0 && (
        <div className="mt-2 pt-2 border-t border-[#333333]">
          {monthEvents.map((e: AEOEvent) => (
            <p key={e.id} style={{ color: EVENT_TYPE_COLORS[e.event_type] }}>
              {EVENT_TYPE_LABELS[e.event_type]}: {e.title}
            </p>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Main component ──────────────────────────────────────────────────────────

export const AEOImpactTimeline: React.FC<AEOImpactTimelineProps> = ({
  monthlyTrend,
  events,
  onAddEvent,
  onDeleteEvent,
  loading = false,
}) => {
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    event_date: new Date().toISOString().slice(0, 10),
    event_type: 'llms_txt_deployed' as AEOEventType,
    title: '',
    description: '',
  });

  const chartData = (monthlyTrend ?? []).map(item => ({
    ...item,
    monthLabel: item.month.slice(5),
  }));

  // Build a deduplicated set of reference-line positions (one per month label)
  const eventsByMonth: Record<string, AEOEvent[]> = {};
  for (const e of events) {
    const ml = eventMonthLabel(e.event_date);
    if (!eventsByMonth[ml]) eventsByMonth[ml] = [];
    eventsByMonth[ml].push(e);
  }

  const handleSubmit = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    try {
      await onAddEvent({
        event_date: form.event_date,
        event_type: form.event_type,
        title: form.title.trim(),
        description: form.description.trim() || undefined,
      });
      setForm({ event_date: new Date().toISOString().slice(0, 10), event_type: 'llms_txt_deployed', title: '', description: '' });
      setShowForm(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-[#0f0f0f] border border-[#3a3a3a] rounded-sm">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#3a3a3a]">
        <div>
          <h2 className="text-base font-semibold text-white">AEO Impact Timeline</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Monthly AI sales trend with your improvement events overlaid — see what moved the needle.
          </p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="px-3 py-1.5 text-xs font-medium bg-[#F7B500] text-black rounded-sm hover:bg-[#FFD700] transition-colors"
        >
          + Add Event
        </button>
      </div>

      {/* Add Event Form */}
      {showForm && (
        <div className="p-4 bg-[#1a1a1a] border-b border-[#3a3a3a]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="block">
              <span className="block text-xs text-zinc-400 mb-1">Date</span>
              <input
                type="date"
                value={form.event_date}
                onChange={e => setForm(f => ({ ...f, event_date: e.target.value }))}
                className="w-full bg-[#0f0f0f] border border-[#3a3a3a] text-white text-sm rounded-sm px-3 py-2 focus:outline-none focus:border-[#F7B500]"
              />
            </label>
            <label className="block">
              <span className="block text-xs text-zinc-400 mb-1">Event Type</span>
              <select
                value={form.event_type}
                onChange={e => setForm(f => ({ ...f, event_type: e.target.value as AEOEventType }))}
                className="w-full bg-[#0f0f0f] border border-[#3a3a3a] text-white text-sm rounded-sm px-3 py-2 focus:outline-none focus:border-[#F7B500]"
              >
                {EVENT_TYPE_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
            <label className="md:col-span-2 block">
              <span className="block text-xs text-zinc-400 mb-1">Title *</span>
              <input
                type="text"
                placeholder="e.g., Published llms.txt v2 with 45 product categories"
                value={form.title}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                className="w-full bg-[#0f0f0f] border border-[#3a3a3a] text-white text-sm rounded-sm px-3 py-2 focus:outline-none focus:border-[#F7B500]"
              />
            </label>
            <label className="md:col-span-2 block">
              <span className="block text-xs text-zinc-400 mb-1">Description (optional)</span>
              <input
                type="text"
                placeholder="Additional context about this change"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                className="w-full bg-[#0f0f0f] border border-[#3a3a3a] text-white text-sm rounded-sm px-3 py-2 focus:outline-none focus:border-[#F7B500]"
              />
            </label>
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={handleSubmit}
              disabled={saving || !form.title.trim()}
              className="px-4 py-1.5 text-xs font-medium bg-[#F7B500] text-black rounded-sm hover:bg-[#FFD700] disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving…' : 'Save Event'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-1.5 text-xs text-zinc-400 border border-[#3a3a3a] rounded-sm hover:bg-[#2a2a2a] transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="p-5">
        {chartData.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center gap-4 text-center border border-dashed border-[#2a2a2a] rounded-sm">
            <div className="text-4xl opacity-20">📈</div>
            <div>
              <p className="text-sm text-zinc-400 font-medium">No LLM sales data yet</p>
              <p className="text-xs text-zinc-600 mt-1 max-w-xs">
                Once Shopify orders carry AI source UTM params or referrer data, monthly sales
                bars will appear here. Log improvement events now — they'll align with revenue
                spikes as data comes in.
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* Summary stats above the chart */}
            <div className="grid grid-cols-3 gap-4 mb-5">
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-sm p-3 text-center">
                <div className="text-xs text-zinc-500 mb-1">Total Revenue</div>
                <div className="text-lg font-bold text-[#F7B500]">
                  {formatCurrency(chartData.reduce((s, d) => s + (d.sales || 0), 0))}
                </div>
              </div>
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-sm p-3 text-center">
                <div className="text-xs text-zinc-500 mb-1">Total Orders</div>
                <div className="text-lg font-bold text-green-400">
                  {chartData.reduce((s, d) => s + (d.orders || 0), 0)}
                </div>
              </div>
              <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-sm p-3 text-center">
                <div className="text-xs text-zinc-500 mb-1">AEO Events</div>
                <div className="text-lg font-bold text-blue-400">{events.length}</div>
              </div>
            </div>

            {/* ComposedChart: bars for orders + line for revenue */}
            <ChartContainer config={timelineConfig} className="h-72 w-full">
              <ComposedChart data={chartData} margin={{ top: 16, right: 60, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="monthLabel" stroke="#555" fontSize={11} />

                {/* Left Y: orders (bars) */}
                <YAxis
                  yAxisId="orders"
                  orientation="left"
                  stroke="#555"
                  fontSize={11}
                  width={35}
                  tickFormatter={v => String(v)}
                  label={{ value: 'Orders', angle: -90, position: 'insideLeft', fill: '#666', fontSize: 10, dx: -2 }}
                />

                {/* Right Y: revenue (line) */}
                <YAxis
                  yAxisId="revenue"
                  orientation="right"
                  stroke="#555"
                  fontSize={11}
                  width={55}
                  tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                  label={{ value: 'Revenue', angle: 90, position: 'insideRight', fill: '#666', fontSize: 10, dx: 14 }}
                />

                <Tooltip content={<EventTooltip events={events} />} />
                <ChartLegend content={<ChartLegendContent />} />

                {/* Event reference lines — work unchanged inside ChartContainer */}
                {Object.entries(eventsByMonth).map(([monthLabel, evs]) => (
                  <ReferenceLine
                    key={monthLabel}
                    x={monthLabel}
                    yAxisId="revenue"
                    stroke={EVENT_TYPE_COLORS[evs[0].event_type]}
                    strokeDasharray="5 3"
                    strokeWidth={2}
                    label={{
                      value: evs.map(e => EVENT_TYPE_LABELS[e.event_type]).join(' + '),
                      position: 'insideTopLeft',
                      fontSize: 9,
                      fill: EVENT_TYPE_COLORS[evs[0].event_type],
                      offset: 4,
                    }}
                  />
                ))}

                <Bar
                  yAxisId="orders"
                  dataKey="orders"
                  name="AI Orders"
                  fill="var(--color-orders)"
                  fillOpacity={0.7}
                  radius={[2, 2, 0, 0]}
                  maxBarSize={40}
                />
                <Line
                  yAxisId="revenue"
                  type="monotone"
                  dataKey="sales"
                  name="AI Revenue"
                  stroke="var(--color-sales)"
                  strokeWidth={2.5}
                  dot={{ r: 4, strokeWidth: 0 }}
                  activeDot={{ r: 6 }}
                />
              </ComposedChart>
            </ChartContainer>
          </>
        )}

        {/* Event Legend */}
        {events.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-3">
            {EVENT_TYPE_OPTIONS.filter(o => events.some(e => e.event_type === o.value)).map(o => (
              <div key={o.value} className="flex items-center gap-1.5 text-xs text-zinc-400">
                <span className="w-3 h-0.5 inline-block" style={{ backgroundColor: EVENT_TYPE_COLORS[o.value] }} />
                {o.label}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Event Log Table */}
      {events.length > 0 && (
        <div className="border-t border-[#3a3a3a] px-4 pb-4">
          <p className="text-xs text-zinc-500 uppercase tracking-wider py-3">Event Log</p>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {[...events]
              .sort((a, b) => Date.parse(b.event_date) - Date.parse(a.event_date))
              .map(e => (
                <div key={e.id} className="flex items-center gap-3 py-1.5 px-2 rounded-sm hover:bg-[#1a1a1a] group">
                  <span
                    className="text-xs font-medium px-1.5 py-0.5 rounded-sm"
                    style={{ backgroundColor: EVENT_TYPE_COLORS[e.event_type] + '22', color: EVENT_TYPE_COLORS[e.event_type] }}
                  >
                    {EVENT_TYPE_LABELS[e.event_type]}
                  </span>
                  <span className="text-xs text-zinc-500 w-20 shrink-0">
                    {e.event_date.slice(0, 10)}
                  </span>
                  <span className="text-sm text-zinc-200 flex-1 truncate">{e.title}</span>
                  {e.description && (
                    <span className="text-xs text-zinc-500 truncate max-w-[180px] hidden md:block">{e.description}</span>
                  )}
                  <button
                    onClick={() => onDeleteEvent(e.id)}
                    className="text-zinc-600 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                    title="Remove event"
                  >
                    ✕
                  </button>
                </div>
              ))}
          </div>
        </div>
      )}

      {events.length === 0 && !showForm && (
        <div className="px-4 pb-4 text-center text-xs text-zinc-600 italic">
          No events logged yet. Click "+ Add Event" to mark an AEO improvement on the timeline.
        </div>
      )}
    </div>
  );
};
