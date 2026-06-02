'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  collectionsAIAPI,
  CannibalizationCheckResult,
  KeywordConflict,
  KeywordSafe,
} from '@/lib/api';

interface CannibalizationGuardProps {
  collectionId: number;
  onCheckComplete?: (result: CannibalizationCheckResult) => void;
  compact?: boolean;
}

export function CannibalizationGuard({
  collectionId,
  onCheckComplete,
  compact = false,
}: CannibalizationGuardProps) {
  const [result, setResult] = useState<CannibalizationCheckResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runCheck = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await collectionsAIAPI.checkCannibalization(collectionId);
      const data = response.data;
      setResult(data);
      onCheckComplete?.(data);
    } catch (err: any) {
      setError(err.message || 'Failed to run cannibalization check');
    } finally {
      setLoading(false);
    }
  }, [collectionId, onCheckComplete]);

  useEffect(() => {
    runCheck();
  }, [collectionId]);

  if (loading) {
    return (
      <div className="border border-zinc-700 rounded-lg p-4 bg-zinc-800/50">
        <div className="flex items-center gap-2">
          <div className="size-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-zinc-400">Analyzing keyword conflicts…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-red-500/30 rounded-lg p-4 bg-red-500/10">
        <p className="text-sm text-red-400">{error}</p>
        <button onClick={runCheck} className="text-xs text-red-300 underline mt-1">
          Retry
        </button>
      </div>
    );
  }

  if (!result) return null;

  const statusColors = {
    safe: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', badge: 'bg-green-500' },
    warning: { bg: 'bg-[#f7b500]/10', border: 'border-[#f7b500]/30', text: 'text-[#f7b500]', badge: 'bg-[#f7b500]' },
    blocked: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', badge: 'bg-red-500' },
  };

  const colors = statusColors[result.status] || statusColors.safe;

  if (compact) {
    return (
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${colors.bg} ${colors.border} border`}>
        <div className={`size-2 rounded-full ${colors.badge}`} />
        <span className={`text-xs font-medium ${colors.text}`}>
          {result.status === 'safe' && `Safe (${result.safe_keywords.length} keywords)`}
          {result.status === 'warning' && `Warning: ${result.warning_keywords.length} conflicts`}
          {result.status === 'blocked' && `Blocked: ${result.blocked_keywords.length} conflicts`}
        </span>
        <span className="text-xs text-zinc-500">Risk: {result.risk_score}%</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className={`border ${colors.border} rounded-lg p-4 ${colors.bg}`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className={`size-3 rounded-full ${colors.badge}`} />
            <h3 className={`font-semibold text-sm ${colors.text}`}>
              Cannibalization Guard:{' '}
              {result.status === 'safe' && 'Safe to Generate'}
              {result.status === 'warning' && 'Proceed with Caution'}
              {result.status === 'blocked' && 'Generation Blocked'}
            </h3>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-zinc-400">
              Risk: <span className={`font-bold ${colors.text}`}>{result.risk_score}%</span>
            </span>
            <button
              onClick={runCheck}
              className="text-xs text-zinc-400 hover:text-white transition-colors"
            >
              Re-check
            </button>
          </div>
        </div>
        <p className="text-xs text-zinc-400">
          {result.total_keywords_analyzed} keywords analyzed &mdash;{' '}
          <span className="text-green-400">{result.safe_keywords.length} safe</span>,{' '}
          <span className="text-[#f7b500]">{result.warning_keywords.length} warning</span>,{' '}
          <span className="text-red-400">{result.blocked_keywords.length} blocked</span>
        </p>
      </div>

      {/* Blocked Keywords */}
      {result.blocked_keywords.length > 0 && (
        <div className="border border-red-500/20 rounded-lg p-3 bg-red-500/5">
          <h4 className="text-xs font-semibold text-red-400 mb-2 uppercase tracking-wider">
            Blocked Keywords ({result.blocked_keywords.length})
          </h4>
          <div className="space-y-2">
            {result.blocked_keywords.map((kw) => (
              <KeywordConflictRow key={kw.keyword} conflict={kw} />
            ))}
          </div>
        </div>
      )}

      {/* Warning Keywords */}
      {result.warning_keywords.length > 0 && (
        <div className="border border-[#f7b500]/20 rounded-lg p-3 bg-[#f7b500]/5">
          <h4 className="text-xs font-semibold text-[#f7b500] mb-2 uppercase tracking-wider">
            Warning Keywords ({result.warning_keywords.length})
          </h4>
          <div className="space-y-2">
            {result.warning_keywords.slice(0, 5).map((kw) => (
              <KeywordConflictRow key={kw.keyword} conflict={kw} />
            ))}
            {result.warning_keywords.length > 5 && (
              <p className="text-xs text-zinc-500">
                +{result.warning_keywords.length - 5} more warnings
              </p>
            )}
          </div>
        </div>
      )}

      {/* Safe Keywords */}
      {result.safe_keywords.length > 0 && (
        <div className="border border-green-500/20 rounded-lg p-3 bg-green-500/5">
          <h4 className="text-xs font-semibold text-green-400 mb-2 uppercase tracking-wider">
            Safe Keywords ({result.safe_keywords.length})
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {result.safe_keywords.slice(0, 12).map((kw) => (
              <span
                key={kw.keyword}
                className="px-2 py-0.5 bg-green-500/10 border border-green-500/20 rounded text-xs text-green-300"
              >
                {kw.keyword}
                <span className="text-green-500/50 ml-1">{kw.impressions}imp</span>
              </span>
            ))}
            {result.safe_keywords.length > 12 && (
              <span className="px-2 py-0.5 text-xs text-zinc-500">
                +{result.safe_keywords.length - 12} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function KeywordConflictRow({ conflict }: { conflict: KeywordConflict }) {
  const severityColors = {
    blocked: 'text-red-400',
    warning: 'text-[#f7b500]',
    safe: 'text-green-400',
  };

  return (
    <div className="flex items-start gap-2 text-xs">
      <span className={`font-medium ${severityColors[conflict.severity]} min-w-0 flex-shrink-0`}>
        &quot;{conflict.keyword}&quot;
      </span>
      <span className="text-zinc-500 flex-1 min-w-0 truncate">
        {conflict.conflicting_page_type === 'blog' ? 'Blog' : 'Product'} ranks #{Math.round(conflict.conflicting_position)}{' '}
        ({conflict.conflicting_clicks} clicks)
      </span>
    </div>
  );
}

export default CannibalizationGuard;
