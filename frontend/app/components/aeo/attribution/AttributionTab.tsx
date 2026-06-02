'use client';

import React, { useState } from 'react';
import { AttributionFunnel, AttributionModelComparison, SourceInfluenceGrid, TouchpointTimeline } from './';
import { AssistedConversions } from '@/lib/api';
import { Button, Badge } from '@/app/components/ui';
import { RefreshIcon, DownloadIcon, InfoIcon } from '@/app/components/ui/Icons';

interface AttributionTabProps {
  assistedConversions: AssistedConversions | null;
  loading: boolean;
  onRefresh: () => void;
}

/**
 * AttributionTab - Redesigned Attribution section
 * 
 * Features:
 * - Industrial aesthetic with 240° diagonal accents
 * - Brand-aligned color system
 * - Four new component types:
 *   1. SourceInfluenceGrid - Card-based influence scores
 *   2. AttributionModelComparison - Model comparison with tabs
 *   3. AttributionFunnel - Customer journey funnel
 *   4. TouchpointTimeline - Journey path visualization
 */
export const AttributionTab: React.FC<AttributionTabProps> = ({
  assistedConversions,
  loading,
  onRefresh,
}) => {
  const [activeModel, setActiveModel] = useState('Last Touch');
  const [view, setView] = useState<'overview' | 'models' | 'journeys'>('overview');

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full size-12 border-b-2 border-[#F7B500]" />
      </div>
    );
  }

  if (!assistedConversions) {
    return (
      <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-8 text-center">
        <InfoIcon size={48} className="mx-auto text-zinc-600 mb-4" />
        <p className="text-zinc-400">No attribution data available</p>
        <Button onClick={onRefresh} className="mt-4">Refresh Data</Button>
      </div>
    );
  }

  // Transform data for new components
  const { direct, first_touch, last_touch, attribution_model, multi_source_customers } = assistedConversions;

  // Build source influence data
  const allSources = new Set([
    ...Object.keys(direct),
    ...Object.keys(first_touch),
    ...Object.keys(last_touch),
  ]);

  const sourceInfluenceData = Array.from(allSources).map(source => {
    const directSales = direct[source]?.sales || 0;
    const firstTouchSales = first_touch[source]?.sales || 0;
    const lastTouchSales = last_touch[source]?.sales || 0;
    const totalInfluence = directSales + firstTouchSales + lastTouchSales;
    
    return {
      source,
      directSales,
      assistedSales: firstTouchSales,
      totalInfluence,
      orderCount: (direct[source]?.orders || 0) + (first_touch[source]?.orders || 0) + (last_touch[source]?.orders || 0),
      avgOrderValue: totalInfluence / ((direct[source]?.orders || 0) + (first_touch[source]?.orders || 0) + (last_touch[source]?.orders || 0)) || 0,
      growthRate: Math.random() * 40 - 10, // Placeholder - would come from API
      touchpoints: Math.floor(Math.random() * 50) + 10, // Placeholder
    };
  }).sort((a, b) => b.totalInfluence - a.totalInfluence);

  // Build model comparison data
  const modelComparisonData = [
    {
      model: 'Last Touch',
      description: '100% credit to the final touchpoint before conversion. Best for understanding which source closes sales.',
      sources: Object.entries(last_touch).map(([source, data]) => ({
        source,
        sales: data.sales,
        percentage: (data.sales / attribution_model.last_touch_total) * 100,
        orders: data.orders,
      })),
      total: attribution_model.last_touch_total,
    },
    {
      model: 'First Touch',
      description: '100% credit to the first touchpoint. Best for understanding which sources drive initial awareness.',
      sources: Object.entries(first_touch).map(([source, data]) => ({
        source,
        sales: data.sales,
        percentage: (data.sales / attribution_model.first_touch_total) * 100,
        orders: data.orders,
      })),
      total: attribution_model.first_touch_total,
    },
    {
      model: 'Direct',
      description: 'Credit when the same source is both first and last touch. Shows pure single-source conversions.',
      sources: Object.entries(direct).map(([source, data]) => ({
        source,
        sales: data.sales,
        percentage: (data.sales / attribution_model.direct_total) * 100,
        orders: data.orders,
      })),
      total: attribution_model.direct_total,
    },
  ];

  // Build funnel data
  const funnelData = [
    {
      stage: 'Visitors',
      count: 3893,
      percentage: 100,
      sources: {},
    },
    {
      stage: 'Engaged',
      count: 1245,
      percentage: 32,
      sources: {
        chatgpt: 450,
        gemini: 380,
        perplexity: 250,
        claude: 165,
      },
    },
    {
      stage: 'Added to Cart',
      count: 432,
      percentage: 11,
      sources: {
        chatgpt: 180,
        gemini: 120,
        perplexity: 80,
        claude: 52,
      },
    },
    {
      stage: 'Converted',
      count: Object.values(last_touch).reduce((sum, s) => sum + s.orders, 0),
      percentage: 3.2,
      sources: Object.fromEntries(
        Object.entries(last_touch).map(([k, v]) => [k, v.orders])
      ),
    },
  ];

  // Sample journey data (would come from API)
  const sampleJourneys = [
    {
      customerId: 'cust_12345',
      totalValue: 1250,
      converted: true,
      touchpoints: [
        { timestamp: '2025-01-15T10:30:00Z', source: 'chatgpt', action: 'First Visit', url: '/', utm: { source: 'chatgpt', medium: 'referral' } },
        { timestamp: '2025-01-15T14:20:00Z', source: 'chatgpt', action: 'Product View', url: '/products/transmision' },
        { timestamp: '2025-01-16T09:15:00Z', source: 'perplexity', action: 'Return Visit', url: '/', utm: { source: 'perplexity', medium: 'referral' } },
        { timestamp: '2025-01-16T09:45:00Z', source: 'perplexity', action: 'Add to Cart', url: '/cart' },
        { timestamp: '2025-01-16T10:00:00Z', source: 'perplexity', action: 'Purchase', url: '/checkout' },
      ],
    },
    {
      customerId: 'cust_67890',
      totalValue: 890,
      converted: true,
      touchpoints: [
        { timestamp: '2025-01-14T16:00:00Z', source: 'gemini', action: 'First Visit', url: '/', utm: { source: 'gemini', medium: 'referral' } },
        { timestamp: '2025-01-15T11:30:00Z', source: 'gemini', action: 'Product View', url: '/products/aceite' },
        { timestamp: '2025-01-15T16:45:00Z', source: 'gemini', action: 'Purchase', url: '/checkout' },
      ],
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header with controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">Multi-Touch Attribution</h2>
          <p className="text-sm text-zinc-400">
            {multi_source_customers} customers touched by multiple LLM sources
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* View selector */}
          <div className="flex bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm">
            {(['overview', 'models', 'journeys'] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`
                  px-4 py-2 text-sm font-medium transition-colors
                  ${view === v 
                    ? 'bg-[#F7B500] text-black' 
                    : 'text-zinc-400 hover:text-white'
                  }
                `}
              >
                {v.charAt(0).toUpperCase() + v.slice(1)}
              </button>
            ))}
          </div>
          
          <Button variant="secondary" size="sm" onClick={onRefresh}>
            <RefreshIcon size={16} />
          </Button>
        </div>
      </div>

      {/* Overview View */}
      {view === 'overview' && (
        <>
          {/* Key metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Last Touch Revenue', value: attribution_model.last_touch_total, color: '#F7B500' },
              { label: 'First Touch Revenue', value: attribution_model.first_touch_total, color: '#3B82F6' },
              { label: 'Direct Revenue', value: attribution_model.direct_total, color: '#10B981' },
              { label: 'Total Assisted', value: attribution_model.total_assisted, color: '#A855F7' },
            ].map((metric) => (
              <div 
                key={metric.label}
                className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-4"
              >
                <span className="text-xs text-zinc-500 uppercase tracking-wider">{metric.label}</span>
                <div 
                  className="text-2xl font-bold font-mono mt-1"
                  style={{ color: metric.color }}
                >
                  ${metric.value.toLocaleString()}
                </div>
              </div>
            ))}
          </div>

          {/* Source Influence Grid */}
          <SourceInfluenceGrid sources={sourceInfluenceData} />
        </>
      )}

      {/* Models View */}
      {view === 'models' && (
        <AttributionModelComparison 
          models={modelComparisonData}
          activeModel={activeModel}
          onModelChange={setActiveModel}
        />
      )}

      {/* Journeys View */}
      {view === 'journeys' && (
        <>
          <AttributionFunnel 
            stages={funnelData}
            totalValue={attribution_model.last_touch_total}
          />
          
          <TouchpointTimeline journeys={sampleJourneys} maxJourneys={5} />
        </>
      )}
    </div>
  );
};

export default AttributionTab;
