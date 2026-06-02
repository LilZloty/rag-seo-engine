'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  collectionsAIAPI,
  CollectionRecommendationsResponse,
  CollectionRecommendation,
} from '@/lib/api';

interface CollectionRecommendationsProps {
  collectionId: number;
  multiAgentEnabled?: boolean;
  compact?: boolean;
}

const categoryColors: Record<string, { bg: string; text: string; label: string }> = {
  seo: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: 'SEO' },
  aeo: { bg: 'bg-purple-500/10', text: 'text-purple-400', label: 'AEO' },
  geo: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', label: 'GEO' },
  conversion: { bg: 'bg-[#f7b500]/10', text: 'text-[#f7b500]', label: 'CRO' },
};

const priorityColors: Record<string, { dot: string; text: string }> = {
  high: { dot: 'bg-red-400', text: 'text-red-400' },
  medium: { dot: 'bg-[#f7b500]', text: 'text-[#f7b500]' },
  low: { dot: 'bg-zinc-400', text: 'text-zinc-400' },
};

export function CollectionRecommendations({
  collectionId,
  multiAgentEnabled = false,
  compact = false,
}: CollectionRecommendationsProps) {
  const [data, setData] = useState<CollectionRecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<string | null>(null);

  const loadRecommendations = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await collectionsAIAPI.getRecommendations(collectionId, {
        multiAgent: multiAgentEnabled,
        maxResults: compact ? 5 : 15,
      });
      setData(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to load recommendations');
    } finally {
      setLoading(false);
    }
  }, [collectionId, multiAgentEnabled, compact]);

  useEffect(() => {
    loadRecommendations();
  }, [collectionId]);

  if (loading) {
    return (
      <div className="border border-zinc-700 rounded-lg p-6 bg-zinc-800/50">
        <div className="flex items-center gap-3">
          <div className="size-5 border-2 border-[#f7b500] border-t-transparent rounded-full animate-spin" />
          <div>
            <p className="text-sm text-zinc-300">Generating recommendations…</p>
            <p className="text-xs text-zinc-500">
              {multiAgentEnabled ? 'Multi-agent consensus in progress' : 'Analyzing collection data'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-red-500/30 rounded-lg p-4 bg-red-500/10">
        <p className="text-sm text-red-400">{error}</p>
        <button onClick={loadRecommendations} className="text-xs text-red-300 underline mt-1">
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const recs = filterCategory
    ? data.recommendations.filter(r => r.category === filterCategory)
    : data.recommendations;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">
            Smart Recommendations
            <span className="text-zinc-500 font-normal ml-2">
              ({data.total_opportunities} opportunities)
            </span>
          </h3>
          {data._multi_agent && (
            <p className="text-xs text-[#f7b500]">
              Multi-agent consensus: {data._multi_agent.consensus_score}%
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {data.cannibalization_risk_score > 0 && (
            <span className="text-xs px-2 py-0.5 rounded bg-[#f7b500]/10 text-[#f7b500]">
              Cannibal risk: {data.cannibalization_risk_score}%
            </span>
          )}
          <button
            onClick={loadRecommendations}
            className="text-xs text-zinc-400 hover:text-white transition-colors px-2 py-1 rounded hover:bg-zinc-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Category Filters */}
      {!compact && (
        <div className="flex gap-1.5">
          <button
            onClick={() => setFilterCategory(null)}
            className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              !filterCategory ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            All
          </button>
          {Object.entries(categoryColors).map(([key, val]) => (
            <button
              key={key}
              onClick={() => setFilterCategory(key)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                filterCategory === key ? `${val.bg} ${val.text}` : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {val.label}
            </button>
          ))}
        </div>
      )}

      {/* Impact Summary */}
      {!compact && data.estimated_impact && (
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2">
            <p className="text-xs text-zinc-500">Traffic</p>
            <p className="text-sm font-semibold text-green-400">{data.estimated_impact.traffic_increase}</p>
          </div>
          <div className="bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2">
            <p className="text-xs text-zinc-500">Conversion</p>
            <p className="text-sm font-semibold text-[#f7b500]">{data.estimated_impact.conversion_increase}</p>
          </div>
          <div className="bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2">
            <p className="text-xs text-zinc-500">Timeline</p>
            <p className="text-sm font-semibold text-zinc-300">{data.estimated_impact.timeline}</p>
          </div>
        </div>
      )}

      {/* Recommendations List */}
      <div className="space-y-2">
        {recs.length === 0 ? (
          <p className="text-sm text-zinc-500 py-4 text-center">
            No recommendations match the current filters
          </p>
        ) : (
          recs.slice(0, compact ? 3 : undefined).map((rec) => (
            <RecommendationCard
              key={rec.id}
              recommendation={rec}
              expanded={expandedId === rec.id}
              onToggle={() => setExpandedId(expandedId === rec.id ? null : rec.id)}
            />
          ))
        )}
        {compact && recs.length > 3 && (
          <p className="text-xs text-zinc-500 text-center">
            +{recs.length - 3} more recommendations
          </p>
        )}
      </div>
    </div>
  );
}

function RecommendationCard({
  recommendation: rec,
  expanded,
  onToggle,
}: {
  recommendation: CollectionRecommendation;
  expanded: boolean;
  onToggle: () => void;
}) {
  const catColor = categoryColors[rec.category] || categoryColors.seo;
  const priColor = priorityColors[rec.priority] || priorityColors.medium;

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Toggle recommendation detail"
      className="border border-zinc-700 rounded-lg bg-zinc-800/30 hover:bg-zinc-800/50 transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
      onClick={onToggle}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
    >
      <div className="px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${catColor.bg} ${catColor.text}`}>
                {catColor.label}
              </span>
              <div className="flex items-center gap-1">
                <div className={`size-1.5 rounded-full ${priColor.dot}`} />
                <span className={`text-[10px] uppercase ${priColor.text}`}>{rec.priority}</span>
              </div>
            </div>
            <h4 className="text-sm font-medium text-white">{rec.title}</h4>
            <p className="text-xs text-zinc-400 mt-0.5">{rec.action}</p>
          </div>
          <div className="flex flex-col items-end gap-1 flex-shrink-0">
            <span className="text-xs font-semibold text-[#f7b500]">{rec.confidence}%</span>
            <span className="text-[10px] text-zinc-500">{rec.expected_impact}</span>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 py-3 border-t border-zinc-700 bg-zinc-900/30">
          {rec.implementation_steps.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-zinc-400 mb-1.5">Implementation Steps:</p>
              <ol className="space-y-1">
                {rec.implementation_steps.map((step, i) => (
                  <li key={step} className="text-xs text-zinc-300 flex gap-2">
                    <span className="text-zinc-600 flex-shrink-0">{i + 1}.</span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {rec.generated_content && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-zinc-400 mb-1">Generated Content:</p>
              <div className="bg-zinc-800 rounded p-2 text-xs text-green-300 font-mono">
                {rec.generated_content}
              </div>
            </div>
          )}

          {rec.agent_breakdown && (
            <div className="flex gap-3 text-[10px] text-zinc-500">
              {rec.agent_breakdown.harper?.verified !== undefined && (
                <span>Harper: {rec.agent_breakdown.harper.verified ? 'Verified' : 'Unverified'}</span>
              )}
              {rec.agent_breakdown.benjamin?.score !== undefined && (
                <span>Benjamin: {rec.agent_breakdown.benjamin.score}/100</span>
              )}
              {rec.agent_breakdown.lucas?.style_score !== undefined && (
                <span>Lucas: {rec.agent_breakdown.lucas.style_score}/100</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default CollectionRecommendations;
