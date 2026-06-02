'use client';

import React from 'react';
import { TrendingUpIcon, TrendingDownIcon, MinusIcon } from '../../ui/Icons';

interface SourceMetrics {
  source: string;
  directSales: number;
  assistedSales: number;
  totalInfluence: number;
  orderCount: number;
  avgOrderValue: number;
  growthRate: number; // percentage
  touchpoints: number;
}

interface SourceInfluenceGridProps {
  sources: SourceMetrics[];
  onSourceClick?: (source: string) => void;
}

/**
 * SourceInfluenceGrid - A grid showing influence scores for each source
 * 
 * Features:
 * - Large metric cards with prominent values
 * - Growth indicators with trend arrows
 * - Source-specific brand colors
 * - 240° diagonal corner accents
 * - Industrial monospace for data
 */
export const SourceInfluenceGrid: React.FC<SourceInfluenceGridProps> = ({
  sources,
  onSourceClick,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {sources.map((source) => {
        const isPositive = source.growthRate > 0;
        const isNeutral = source.growthRate === 0;
        const sourceColor = getSourceColor(source.source);
        
        return (
          <div
            key={source.source}
            role="button"
            tabIndex={0}
            aria-label={`Open detail for ${source.source}`}
            onClick={() => onSourceClick?.(source.source)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSourceClick?.(source.source); } }}
            className="
              group relative bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm
              p-5 cursor-pointer overflow-hidden
              focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]
              hover:border-[#F7B500]/50 transition-all
            "
          >
            {/* 240° diagonal corner accent */}
            <div 
              className="absolute -top-8 -right-8 size-16 opacity-20 transition-opacity group-hover:opacity-40"
              style={{
                background: `linear-gradient(240deg, ${sourceColor} 40%, transparent 40%)`
              }}
            />
            
            {/* Bottom corner accent */}
            <div 
              className="absolute -bottom-8 -left-8 size-16 opacity-10 transition-opacity group-hover:opacity-30"
              style={{
                background: `linear-gradient(60deg, ${sourceColor} 40%, transparent 40%)`
              }}
            />

            {/* Header */}
            <div className="relative flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                {/* Source icon/color block */}
                <div 
                  className="size-10 rounded-sm flex items-center justify-center"
                  style={{ 
                    backgroundColor: `${sourceColor}20`,
                    border: `1px solid ${sourceColor}40`
                  }}
                >
                  <span 
                    className="text-lg font-bold"
                    style={{ color: sourceColor }}
                  >
                    {source.source.charAt(0).toUpperCase()}
                  </span>
                </div>
                
                <div>
                  <h4 className="text-base font-semibold text-white">
                    {formatSourceName(source.source)}
                  </h4>
                  <div className="flex items-center gap-2">
                    <span className={`
                      text-xs font-medium flex items-center gap-1
                      ${isPositive ? 'text-green-400' : isNeutral ? 'text-zinc-400' : 'text-red-400'}
                    `}>
                      {isPositive && <TrendingUpIcon size={12} />}
                      {isNeutral && <MinusIcon size={12} />}
                      {!isPositive && !isNeutral && <TrendingDownIcon size={12} />}
                      {Math.abs(source.growthRate).toFixed(1)}%
                    </span>
                    <span className="text-xs text-zinc-500">vs last period</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Main metric */}
            <div className="relative mb-4">
              <span className="text-xs text-zinc-500 uppercase tracking-wider">Total Influence</span>
              <div className="text-3xl font-bold text-white font-mono mt-1">
                ${source.totalInfluence.toLocaleString()}
              </div>
            </div>

            {/* Metric grid */}
            <div className="relative grid grid-cols-2 gap-3">
              <div className="p-3 bg-[#0a0a0a] rounded-sm border border-[#2a2a2a]">
                <span className="text-xs text-zinc-500">Direct</span>
                <div className="text-sm font-semibold text-white font-mono mt-1">
                  ${(source.directSales / 1000).toFixed(1)}k
                </div>
              </div>
              
              <div className="p-3 bg-[#0a0a0a] rounded-sm border border-[#2a2a2a]">
                <span className="text-xs text-zinc-500">Assisted</span>
                <div className="text-sm font-semibold text-white font-mono mt-1">
                  ${(source.assistedSales / 1000).toFixed(1)}k
                </div>
              </div>
              
              <div className="p-3 bg-[#0a0a0a] rounded-sm border border-[#2a2a2a]">
                <span className="text-xs text-zinc-500">Orders</span>
                <div className="text-sm font-semibold text-white font-mono mt-1">
                  {source.orderCount}
                </div>
              </div>
              
              <div className="p-3 bg-[#0a0a0a] rounded-sm border border-[#2a2a2a]">
                <span className="text-xs text-zinc-500">AOV</span>
                <div className="text-sm font-semibold text-white font-mono mt-1">
                  ${source.avgOrderValue.toFixed(0)}
                </div>
              </div>
            </div>

            {/* Touchpoints bar */}
            <div className="relative mt-4">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-zinc-500">Touchpoints</span>
                <span className="text-zinc-400 font-mono">{source.touchpoints}</span>
              </div>
              <div className="h-1.5 bg-[#3a3a3a] rounded-sm overflow-hidden">
                <div 
                  className="h-full transition-all duration-500"
                  style={{ 
                    width: `${Math.min((source.touchpoints / 100) * 100, 100)}%`,
                    backgroundColor: sourceColor
                  }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

function getSourceColor(source: string): string {
  const colors: Record<string, string> = {
    chatgpt: '#10A37F',
    gemini: '#4285F4',
    perplexity: '#20808D',
    claude: '#CC785C',
    copilot: '#0078D4',
    grok: '#FFFFFF',
    other_ai: '#F7B500',
  };
  return colors[source.toLowerCase()] || '#F7B500';
}

function formatSourceName(source: string): string {
  const names: Record<string, string> = {
    chatgpt: 'ChatGPT',
    gemini: 'Google Gemini',
    perplexity: 'Perplexity',
    claude: 'Claude',
    copilot: 'Copilot',
    grok: 'Grok',
    other_ai: 'Other AI',
  };
  return names[source.toLowerCase()] || source;
}

export default SourceInfluenceGrid;
