'use client';

import React from 'react';
import { ArrowRightIcon, UsersIcon, ShoppingCartIcon, CreditCardIcon } from '../../ui/Icons';

interface AttributionStage {
  stage: string;
  count: number;
  percentage: number;
  sources: Record<string, number>;
}

interface AttributionFunnelProps {
  stages: AttributionStage[];
  totalValue: number;
}

/**
 * AttributionFunnel - A visual funnel showing the customer journey
 * 
 * Brand-aligned features:
 * - 240° diagonal accent lines
 * - Industrial sharp edges (rounded-sm)
 * - Brand yellow (#F7B500) for primary flow
 * - Source-specific colors for attribution breakdown
 * - Technical monospace for data values
 */
export const AttributionFunnel: React.FC<AttributionFunnelProps> = ({
  stages,
  totalValue,
}) => {
  const maxCount = Math.max(...stages.map(s => s.count));

  return (
    <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm">
      {/* Header with diagonal accent */}
      <div className="relative px-6 py-4 border-b border-[#3a3a3a] overflow-hidden">
        <div 
          className="absolute top-0 right-0 w-32 h-full opacity-10"
          style={{
            background: 'linear-gradient(240deg, transparent 40%, #F7B500 40%, #F7B500 42%, transparent 42%)'
          }}
        />
        <h3 className="text-lg font-semibold text-white relative z-10">Customer Journey Funnel</h3>
        <p className="text-sm text-zinc-400 relative z-10">
          {stages[0]?.count.toLocaleString()} visitors → {stages[stages.length - 1]?.count.toLocaleString()} conversions
        </p>
      </div>

      <div className="p-6">
        <div className="space-y-4">
          {stages.map((stage, index) => {
            const width = (stage.count / maxCount) * 100;
            const isLast = index === stages.length - 1;
            
            return (
              <div key={stage.stage} className="relative">
                {/* Connection line */}
                {!isLast && (
                  <div className="absolute left-1/2 -translate-x-1/2 -bottom-4 w-0.5 h-4 bg-[#3a3a3a]" />
                )}
                
                <div className="flex items-center gap-4">
                  {/* Stage icon */}
                  <div className={`
                    w-10 h-10 flex items-center justify-center rounded-sm border
                    ${index === 0 ? 'border-[#F7B500]/50 bg-[#F7B500]/10' : ''}
                    ${index === 1 ? 'border-blue-500/50 bg-blue-500/10' : ''}
                    ${index === 2 ? 'border-green-500/50 bg-green-500/10' : ''}
                    ${index === 3 ? 'border-purple-500/50 bg-purple-500/10' : ''}
                  `}>
                    {index === 0 && <UsersIcon size={18} className="text-[#F7B500]" />}
                    {index === 1 && <ArrowRightIcon size={18} className="text-blue-400" />}
                    {index === 2 && <ShoppingCartIcon size={18} className="text-green-400" />}
                    {index === 3 && <CreditCardIcon size={18} className="text-purple-400" />}
                  </div>

                  {/* Funnel bar */}
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">{stage.stage}</span>
                      <div className="text-right">
                        <span className="text-lg font-bold text-white font-mono">
                          {stage.count.toLocaleString()}
                        </span>
                        <span className="text-sm text-zinc-400 ml-2">
                          ({stage.percentage.toFixed(1)}%)
                        </span>
                      </div>
                    </div>
                    
                    {/* Progress bar with 240° gradient */}
                    <div className="h-3 bg-[#3a3a3a] rounded-sm overflow-hidden relative">
                      <div 
                        className="h-full transition-all duration-500 relative"
                        style={{ 
                          width: `${width}%`,
                          background: index === stages.length - 1 
                            ? 'linear-gradient(90deg, #F7B500, #ffc933)'
                            : `linear-gradient(240deg, ${getStageColor(index)}80, ${getStageColor(index)})`
                        }}
                      >
                        {/* Diagonal stripe pattern */}
                        <div 
                          className="absolute inset-0 opacity-20"
                          style={{
                            backgroundImage: 'repeating-linear-gradient(240deg, transparent, transparent 10px, rgba(0,0,0,0.3) 10px, rgba(0,0,0,0.3) 20px)'
                          }}
                        />
                      </div>
                    </div>

                    {/* Source breakdown pills */}
                    {Object.entries(stage.sources).length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {Object.entries(stage.sources).map(([source, count]) => (
                          <span 
                            key={source}
                            className="inline-flex items-center px-2 py-0.5 text-xs rounded-sm border"
                            style={{
                              borderColor: `${getSourceColor(source)}40`,
                              backgroundColor: `${getSourceColor(source)}15`,
                              color: getSourceColor(source)
                            }}
                          >
                            {source}: {count}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Total value footer */}
        <div className="mt-6 pt-4 border-t border-[#3a3a3a]">
          <div className="flex items-center justify-between">
            <span className="text-sm text-zinc-400">Total Attributed Revenue</span>
            <span className="text-2xl font-bold text-[#F7B500] font-mono">
              ${totalValue.toLocaleString()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

// Helper functions
function getStageColor(index: number): string {
  const colors = ['#F7B500', '#3B82F6', '#22C55E', '#A855F7'];
  return colors[index] || '#F7B500';
}

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

export default AttributionFunnel;
