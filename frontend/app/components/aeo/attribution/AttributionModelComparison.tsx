'use client';

import React from 'react';
import { CheckIcon } from '../../ui/Icons';

interface ModelComparison {
  model: string;
  description: string;
  sources: Array<{
    source: string;
    sales: number;
    percentage: number;
    orders: number;
  }>;
  total: number;
}

interface AttributionModelComparisonProps {
  models: ModelComparison[];
  activeModel: string;
  onModelChange: (model: string) => void;
}

/**
 * AttributionModelComparison - Compare different attribution models
 * 
 * Features:
 * - Tabbed interface for model selection
 * - Side-by-side comparison view
 * - 240° diagonal accents
 * - Source color coding
 * - Industrial data table styling
 */
export const AttributionModelComparison: React.FC<AttributionModelComparisonProps> = ({
  models,
  activeModel,
  onModelChange,
}) => {
  const activeData = models.find(m => m.model === activeModel);

  return (
    <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm">
      {/* Header with diagonal accent */}
      <div className="relative px-6 py-4 border-b border-[#3a3a3a]">
        <div 
          className="absolute top-0 left-0 w-24 h-full opacity-10"
          style={{
            background: 'linear-gradient(240deg, #F7B500 30%, transparent 30%)'
          }}
        />
        <h3 className="text-lg font-semibold text-white relative z-10">Attribution Model Comparison</h3>
        <p className="text-sm text-zinc-400 relative z-10">
          Compare how different attribution models assign credit to touchpoints
        </p>
      </div>

      <div className="p-6">
        {/* Model selector tabs */}
        <div className="flex gap-2 mb-6">
          {models.map((model) => (
            <button
              key={model.model}
              onClick={() => onModelChange(model.model)}
              className={`
                relative px-4 py-3 text-sm font-medium rounded-sm transition-all
                ${activeModel === model.model 
                  ? 'bg-[#F7B500] text-black' 
                  : 'bg-[#0a0a0a] text-zinc-400 hover:text-white border border-[#3a3a3a]'
                }
              `}
            >
              <div className="flex items-center gap-2">
                {activeModel === model.model && <CheckIcon size={16} />}
                <span>{model.model}</span>
              </div>
              
              {/* Active indicator with 240° angle */}
              {activeModel === model.model && (
                <div 
                  className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-4 h-1 bg-[#F7B500]"
                  style={{ clipPath: 'polygon(0 0, 100% 0, 50% 100%)' }}
                />
              )}
            </button>
          ))}
        </div>

        {/* Active model description */}
        {activeData && (
          <div className="mb-6 p-4 bg-[#0a0a0a] border-l-2 border-[#F7B500] rounded-r-sm">
            <p className="text-sm text-zinc-300">{activeData.description}</p>
          </div>
        )}

        {/* Comparison visualization */}
        <div className="space-y-4">
          {activeData?.sources.map((source, index) => {
            const allModelValues = models.map(m => {
              const s = m.sources.find(s => s.source === source.source);
              return s?.sales || 0;
            });
            const maxValue = Math.max(...allModelValues);
            
            return (
              <div 
                key={source.source}
                className="group relative p-4 bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm hover:border-[#F7B500]/30 transition-colors"
              >
                {/* Rank indicator with 240° angle */}
                <div className="absolute -left-1 top-1/2 -translate-y-1/2">
                  <div 
                    className="size-6 flex items-center justify-center text-xs font-bold"
                    style={{
                      background: index === 0 ? '#F7B500' : '#3a3a3a',
                      color: index === 0 ? '#000' : '#fff',
                      clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)'
                    }}
                  >
                    {index + 1}
                  </div>
                </div>

                <div className="ml-6">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      {/* Source color indicator */}
                      <div 
                        className="size-3 rounded-sm"
                        style={{ backgroundColor: getSourceColor(source.source) }}
                      />
                      <span className="text-base font-medium text-white">
                        {source.source}
                      </span>
                    </div>
                    
                    <div className="text-right">
                      <span className="text-xl font-bold text-white font-mono">
                        ${source.sales.toLocaleString()}
                      </span>
                      <span className="text-sm text-zinc-400 ml-2">
                        ({source.percentage.toFixed(1)}%)
                      </span>
                    </div>
                  </div>

                  {/* Comparison bars across all models */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-zinc-500 w-20">{activeModel}</span>
                      <div className="flex-1 h-2 bg-[#3a3a3a] rounded-sm overflow-hidden">
                        <div 
                          className="h-full bg-[#F7B500] relative"
                          style={{ width: `${(source.sales / maxValue) * 100}%` }}
                        >
                          <div 
                            className="absolute inset-0 opacity-30"
                            style={{
                              backgroundImage: 'repeating-linear-gradient(240deg, transparent, transparent 6px, rgba(0,0,0,0.5) 6px, rgba(0,0,0,0.5) 12px)'
                            }}
                          />
                        </div>
                      </div>
                      <span className="text-xs text-zinc-400 w-16 text-right font-mono">
                        {source.orders} orders
                      </span>
                    </div>
                    
                    {/* Show other models as ghost bars */}
                    {models.filter(m => m.model !== activeModel).map((model) => {
                      const otherSource = model.sources.find(s => s.source === source.source);
                      if (!otherSource) return null;
                      
                      return (
                        <div key={model.model} className="flex items-center gap-4">
                          <span className="text-xs text-zinc-600 w-20">{model.model}</span>
                          <div className="flex-1 h-1.5 bg-[#2a2a2a] rounded-sm overflow-hidden">
                            <div 
                              className="h-full bg-zinc-600"
                              style={{ width: `${(otherSource.sales / maxValue) * 100}%` }}
                            />
                          </div>
                          <span className="text-xs text-zinc-600 w-16 text-right font-mono">
                            ${(otherSource.sales / 1000).toFixed(1)}k
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Model comparison summary */}
        <div className="mt-6 grid grid-cols-3 gap-4">
          {models.map((model) => (
            <div 
              key={model.model}
              className={`
                p-4 border rounded-sm transition-all
                ${activeModel === model.model 
                  ? 'border-[#F7B500] bg-[#F7B500]/5' 
                  : 'border-[#3a3a3a] bg-[#0a0a0a]'
                }
              `}
            >
              <span className="text-xs text-zinc-500 uppercase tracking-wider">{model.model}</span>
              <div className="text-2xl font-bold text-white font-mono mt-1">
                ${model.total.toLocaleString()}
              </div>
              <div className="text-xs text-zinc-400 mt-1">
                {model.sources.reduce((acc, s) => acc + s.orders, 0)} orders
              </div>
            </div>
          ))}
        </div>
      </div>
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

export default AttributionModelComparison;
