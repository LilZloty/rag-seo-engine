/**
 * Smart Recommendations Panel - Example Store Design System
 * 
 * AI-powered recommendations using multi-agent consensus
 * Uses: Card, Badge, Button components with brand colors
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, Button, Badge } from '../ui';
import { SparklesIcon, RefreshIcon } from '../ui/Icons';
import { 
  productsAIAPI, 
  SmartRecommendation, 
  SmartRecommendationsResponse,
  RecommendationFilters
} from '@/lib/api';

interface SmartRecommendationsPanelProps {
  productId: string;
  multiAgentEnabled?: boolean;
  onRecommendationApply?: (rec: SmartRecommendation) => void;
  compact?: boolean;
}

export function SmartRecommendationsPanel({
  productId,
  multiAgentEnabled = false,
  onRecommendationApply,
  compact = false
}: SmartRecommendationsPanelProps) {
  const [recommendations, setRecommendations] = useState<SmartRecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  
  const [filters] = useState<Partial<RecommendationFilters>>({
    min_confidence: 60,
    categories: ['seo', 'aeo', 'geo', 'conversion'],
    max_results: 10,
    sort_by: 'impact'
  });

  const loadRecommendations = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await productsAIAPI.getSmartRecommendations(productId, {
        multiAgent: multiAgentEnabled,
        minConfidence: filters.min_confidence,
        maxResults: filters.max_results,
        sortBy: filters.sort_by,
        categories: filters.categories?.join(',')
      });
      setRecommendations(result);
    } catch (err: any) {
      console.error('Failed to load recommendations:', err);
      setError(err.message || 'Failed to load recommendations');
    } finally {
      setLoading(false);
    }
  }, [productId, multiAgentEnabled, filters]);

  useEffect(() => {
    if (productId) loadRecommendations();
  }, [productId, multiAgentEnabled]);

  const handleApply = (rec: SmartRecommendation) => {
    if (onRecommendationApply) onRecommendationApply(rec);
    if (rec.generated_content) {
      navigator.clipboard.writeText(rec.generated_content);
    }
  };

  // Category badge variant
  const getCategoryVariant = (category: string): 'info' | 'warning' | 'success' | 'default' | 'brand' => {
    switch (category) {
      case 'seo': return 'info';
      case 'aeo': return 'warning';
      case 'geo': return 'success';
      case 'conversion': return 'brand';
      default: return 'default';
    }
  };

  // Compact mode - minimal inline display
  if (compact) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <SparklesIcon size={16} className="text-[#F7B500]" />
            <span className="text-sm font-medium">AI Recommendations</span>
            {recommendations?._multi_agent && (
              <Badge variant="brand">{recommendations._multi_agent.consensus_score}%</Badge>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={loadRecommendations} loading={loading}>
            <RefreshIcon size={14} />
          </Button>
        </div>

        {loading ? (
          <p className="text-sm text-zinc-400 py-2">Loading…</p>
        ) : error ? (
          <p className="text-sm text-red-400">{error}</p>
        ) : (
          <div className="space-y-2">
            {recommendations?.recommendations.slice(0, 3).map(rec => (
              <div key={rec.id} className="flex items-center justify-between py-1.5 border-b border-[#3a3a3a] last:border-0">
                <div className="flex items-center gap-2">
                  <Badge variant={getCategoryVariant(rec.category)}>{rec.category.toUpperCase()}</Badge>
                  <span className="text-sm text-zinc-300 truncate max-w-[180px]">{rec.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500">{rec.confidence}%</span>
                  {rec.auto_applicable && (
                    <button onClick={() => handleApply(rec)} className="text-xs text-[#F7B500] hover:underline">
                      Apply
                    </button>
                  )}
                </div>
              </div>
            ))}
            {recommendations && recommendations.total_opportunities > 3 && (
              <p className="text-xs text-zinc-500 text-center">+{recommendations.total_opportunities - 3} more</p>
            )}
          </div>
        )}
      </Card>
    );
  }

  // Full mode - standard panel
  return (
    <Card 
      title="AI Recommendations" 
      icon={<SparklesIcon size={20} className="text-[#F7B500]" />}
      action={
        <div className="flex items-center gap-2">
          {recommendations?._multi_agent && (
            <Badge variant="brand">{recommendations._multi_agent.consensus_score}% consensus</Badge>
          )}
          <Button variant="ghost" size="sm" onClick={loadRecommendations} loading={loading}>
            <RefreshIcon size={14} />
          </Button>
        </div>
      }
    >
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-sm p-3 mb-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(n => <div key={`skel-${n}`} className="animate-pulse bg-[#2a2a2a] rounded-sm h-16" />)}
        </div>
      ) : (
        <div className="space-y-3">
          {recommendations?.recommendations.map(rec => (
            <div
              key={rec.id}
              role="button"
              tabIndex={0}
              aria-expanded={expandedId === rec.id}
              aria-label={`Toggle recommendation ${rec.id}`}
              className="bg-[#2a2a2a] rounded-sm p-4 hover:bg-[#3a3a3a] cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
              onClick={() => setExpandedId(expandedId === rec.id ? null : rec.id)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedId(expandedId === rec.id ? null : rec.id); } }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant={getCategoryVariant(rec.category)}>{rec.category.toUpperCase()}</Badge>
                    <Badge variant={rec.priority === 'high' ? 'danger' : rec.priority === 'medium' ? 'warning' : 'success'}>
                      {rec.priority.toUpperCase()}
                    </Badge>
                    {rec.auto_applicable && <Badge variant="outline">AUTO</Badge>}
                  </div>
                  <h4 className="font-medium">{rec.title}</h4>
                  <p className="text-sm text-zinc-400 mt-1">{rec.action}</p>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold text-[#F7B500]">{rec.confidence}%</div>
                </div>
              </div>

              {expandedId === rec.id && (
                <div className="mt-4 pt-4 border-t border-[#3a3a3a] space-y-3">
                  <div>
                    <p className="text-xs text-zinc-500 uppercase mb-1">Expected Impact</p>
                    <p className="text-sm text-green-400">{rec.expected_impact}</p>
                  </div>

                  {rec.generated_content && (
                    <div>
                      <p className="text-xs text-zinc-500 uppercase mb-1">Generated Content</p>
                      <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm p-3 text-sm">
                        {rec.generated_content}
                      </div>
                      <div className="flex gap-3 mt-2">
                        <button 
                          onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(rec.generated_content!); }}
                          className="text-xs text-[#F7B500] hover:underline"
                        >
                          Copy
                        </button>
                        {rec.auto_applicable && (
                          <button 
                            onClick={(e) => { e.stopPropagation(); handleApply(rec); }}
                            className="text-xs text-green-400 hover:underline"
                          >
                            Apply
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {rec.implementation_steps.length > 0 && (
                    <div>
                      <p className="text-xs text-zinc-500 uppercase mb-2">Steps</p>
                      <ol className="list-decimal list-inside text-sm text-zinc-400 space-y-1">
                        {rec.implementation_steps.map((step) => <li key={`${rec.id || rec.title || 'rec'}-${step}`}>{step}</li>)}
                      </ol>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {!recommendations?.recommendations.length && !loading && (
            <p className="text-sm text-zinc-400 text-center py-6">No recommendations available</p>
          )}
        </div>
      )}
    </Card>
  );
}
