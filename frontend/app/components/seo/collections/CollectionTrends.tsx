'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { collectionsAIAPI, CollectionTrendsResponse, CollectionTrendSnapshot } from '@/lib/api';
import { formatDate } from '@/app/lib/dates';

interface CollectionTrendsProps {
  collectionId: number;
  days?: number;
}

export function CollectionTrends({
  collectionId,
  days = 30,
}: CollectionTrendsProps) {
  const [data, setData] = useState<CollectionTrendsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTrends = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await collectionsAIAPI.getTrends(collectionId, days);
      setData(response);
    } catch (err: any) {
      setError(err.message || 'Failed to load trends');
    } finally {
      setLoading(false);
    }
  }, [collectionId, days]);

  useEffect(() => {
    loadTrends();
  }, [collectionId, days]);

  if (loading) {
    return (
      <div className="border border-zinc-700 rounded-lg p-4 bg-zinc-800/50">
        <div className="flex items-center gap-2">
          <div className="size-4 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-zinc-400">Loading trends…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-red-500/30 rounded-lg p-4 bg-red-500/10">
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  if (!data || data.total_snapshots === 0) {
    return (
      <div className="border border-zinc-700 rounded-lg p-6 bg-zinc-800/30 text-center">
        <p className="text-sm text-zinc-500">No trend data available yet</p>
        <p className="text-xs text-zinc-600 mt-1">
          Snapshots are captured daily. Check back after analytics sync.
        </p>
        <button
          onClick={async () => {
            await collectionsAIAPI.createSnapshots([collectionId]);
            loadTrends();
          }}
          className="mt-3 px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-xs text-zinc-300 rounded transition-colors"
        >
          Create Snapshot Now
        </button>
      </div>
    );
  }

  const deltas = data.deltas;

  return (
    <div className="space-y-4">
      {/* Delta Cards */}
      {deltas && (
        <div className="grid grid-cols-4 gap-2">
          <DeltaCard
            label="Impressions"
            delta={deltas.gsc_impressions_delta}
            format="number"
          />
          <DeltaCard
            label="Clicks"
            delta={deltas.gsc_clicks_delta}
            format="number"
          />
          <DeltaCard
            label="Position"
            delta={deltas.gsc_position_delta}
            format="position"
          />
          <DeltaCard
            label="Revenue"
            delta={deltas.shopify_revenue_delta}
            format="currency"
          />
        </div>
      )}

      {/* Mini Sparklines */}
      <div className="grid grid-cols-2 gap-3">
        <SparklineCard
          title="Impressions"
          data={data.snapshots}
          valueKey="gsc_impressions"
          color="#3b82f6"
        />
        <SparklineCard
          title="Sessions"
          data={data.snapshots}
          valueKey="ga4_sessions"
          color="#22c55e"
        />
        <SparklineCard
          title="Position"
          data={data.snapshots}
          valueKey="gsc_position"
          color="#f7b500"
          invertGood
        />
        <SparklineCard
          title="Revenue"
          data={data.snapshots}
          valueKey="shopify_revenue"
          color="#a855f7"
        />
      </div>

      {/* Optimization Events */}
      {data.optimization_events && data.optimization_events.length > 0 && (
        <div className="border border-zinc-700 rounded-lg p-3 bg-zinc-800/30">
          <h4 className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
            Optimization Events
          </h4>
          <div className="space-y-1.5">
            {data.optimization_events.map((event) => (
              <div key={`${event.date || 'no-date'}-${event.event || ''}`} className="flex items-center gap-2 text-xs">
                <span className="text-zinc-600">{event.date ? formatDate(event.date) : ''}</span>
                {event.event === 'content_generated' ? (
                  <span className="text-green-400">Content generated</span>
                ) : (
                  <span className="text-[#f7b500]">
                    {event.from_status} &rarr; {event.to_status}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[10px] text-zinc-600 text-right">
        {data.total_snapshots} snapshots over {days} days
      </p>
    </div>
  );
}

function DeltaCard({
  label,
  delta,
  format,
}: {
  label: string;
  delta: number;
  format: 'number' | 'position' | 'currency';
}) {
  // For position, negative delta = improvement (lower position = better)
  const isGood = format === 'position' ? delta < 0 : delta > 0;
  const color = delta === 0 ? 'text-zinc-400' : isGood ? 'text-green-400' : 'text-red-400';
  const arrow = delta === 0 ? '' : isGood ? '+' : '';

  let formatted = '';
  if (format === 'currency') {
    formatted = `${arrow}$${Math.abs(delta).toLocaleString()}`;
  } else if (format === 'position') {
    formatted = `${delta > 0 ? '+' : ''}${delta.toFixed(1)}`;
  } else {
    formatted = `${arrow}${delta.toLocaleString()}`;
  }

  return (
    <div className="bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2">
      <p className="text-[10px] text-zinc-500">{label}</p>
      <p className={`text-sm font-semibold ${color}`}>{formatted}</p>
    </div>
  );
}

function SparklineCard({
  title,
  data,
  valueKey,
  color,
  invertGood = false,
}: {
  title: string;
  data: CollectionTrendSnapshot[];
  valueKey: keyof CollectionTrendSnapshot;
  color: string;
  invertGood?: boolean;
}) {
  if (data.length < 2) return null;

  const values = data.map((d) => Number(d[valueKey]) || 0);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const current = values[values.length - 1];
  const first = values[0];
  const changed = current - first;
  const isGood = invertGood ? changed < 0 : changed > 0;

  // Generate SVG path
  const width = 200;
  const height = 40;
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  });
  const pathD = `M ${points.join(' L ')}`;

  return (
    <div className="bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-zinc-500">{title}</span>
        <span className={`text-[10px] font-medium ${changed === 0 ? 'text-zinc-400' : isGood ? 'text-green-400' : 'text-red-400'}`}>
          {valueKey === 'shopify_revenue' ? `$${current.toLocaleString()}` : current.toLocaleString()}
        </span>
      </div>
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

export default CollectionTrends;
