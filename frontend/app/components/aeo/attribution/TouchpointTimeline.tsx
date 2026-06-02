'use client';

import React from 'react';
import { ClockIcon, MousePointerIcon, ShoppingCartIcon, CreditCardIcon } from '../../ui/Icons';

interface Touchpoint {
  timestamp: string;
  source: string;
  action: string;
  url?: string;
  utm?: {
    source?: string;
    medium?: string;
    campaign?: string;
  };
}

interface CustomerJourney {
  customerId: string;
  totalValue: number;
  touchpoints: Touchpoint[];
  converted: boolean;
}

interface TouchpointTimelineProps {
  journeys: CustomerJourney[];
  maxJourneys?: number;
}

/**
 * TouchpointTimeline - Visual timeline of customer touchpoints
 * 
 * Features:
 * - Vertical timeline with connecting lines
 * - Source color coding at each touchpoint
 * - Time gaps between touchpoints
 * - 240° angled connection paths
 * - Conversion status indicators
 */
export const TouchpointTimeline: React.FC<TouchpointTimelineProps> = ({
  journeys,
  maxJourneys = 5,
}) => {
  const displayJourneys = journeys.slice(0, maxJourneys);

  return (
    <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm">
      <div className="px-6 py-4 border-b border-[#3a3a3a]">
        <h3 className="text-lg font-semibold text-white">Customer Journey Paths</h3>
        <p className="text-sm text-zinc-400">
          Showing {displayJourneys.length} recent conversion paths
        </p>
      </div>

      <div className="p-6 space-y-6">
        {displayJourneys.map((journey, journeyIndex) => (
          <div 
            key={journey.customerId}
            className="relative bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm p-4"
          >
            {/* Journey header */}
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#2a2a2a]">
              <div className="flex items-center gap-3">
                <div className="
                  size-8 rounded-sm flex items-center justify-center
                  bg-[#F7B500]/10 border border-[#F7B500]/30
                "
                >
                  <span className="text-xs font-bold text-[#F7B500]">
                    #{journeyIndex + 1}
                  </span>
                </div>
                <div>
                  <span className="text-sm font-medium text-white">Customer {journey.customerId.slice(-6)}</span>
                  <span className="text-xs text-zinc-500 ml-2">
                    {journey.touchpoints.length} touchpoints
                  </span>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-[#F7B500] font-mono">
                  ${journey.totalValue.toLocaleString()}
                </span>
                {journey.converted && (
                  <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 border border-green-500/30 rounded-sm">
                    Converted
                  </span>
                )}
              </div>
            </div>

            {/* Timeline */}
            <div className="relative pl-8">
              {/* Vertical connecting line with 240° gradient */}
              <div 
                className="absolute left-3 top-0 bottom-0 w-0.5"
                style={{
                  background: 'linear-gradient(180deg, #F7B500 0%, #3a3a3a 50%, #10A37F 100%)'
                }}
              />

              <div className="space-y-0">
                {journey.touchpoints.map((touchpoint, index) => {
                  const isFirst = index === 0;
                  const isLast = index === journey.touchpoints.length - 1;
                  const sourceColor = getSourceColor(touchpoint.source);
                  
                  return (
                    <div key={`${touchpoint.timestamp}-${touchpoint.source}-${touchpoint.action}`} className="relative pb-6 last:pb-0">
                      {/* Node */}
                      <div 
                        className="absolute left-[-22px] size-6 rounded-sm border-2 flex items-center justify-center"
                        style={{
                          backgroundColor: '#1a1a1a',
                          borderColor: sourceColor,
                          top: '2px'
                        }}
                      >
                        <div 
                          className="size-2 rounded-sm"
                          style={{ backgroundColor: sourceColor }}
                        />
                      </div>

                      {/* Content */}
                      <div className="flex-1">
                        {/* Time and source header */}
                        <div className="flex items-center gap-3 mb-1">
                          <span className="text-xs text-zinc-500 font-mono">
                            {formatTime(touchpoint.timestamp)}
                          </span>
                          
                          <span 
                            className="px-2 py-0.5 text-xs rounded-sm border"
                            style={{
                              borderColor: `${sourceColor}40`,
                              backgroundColor: `${sourceColor}15`,
                              color: sourceColor
                            }}
                          >
                            {touchpoint.source}
                          </span>
                          
                          {isFirst && (
                            <span className="text-xs text-zinc-500">First Touch</span>
                          )}
                          {isLast && (
                            <span className="text-xs text-[#F7B500]">Last Touch</span>
                          )}
                        </div>

                        {/* Action */}
                        <div className="flex items-center gap-2">
                          {getActionIcon(touchpoint.action)}
                          <span className="text-sm text-white">{touchpoint.action}</span>
                        </div>

                        {/* URL if available */}
                        {touchpoint.url && (
                          <div className="mt-1 text-xs text-zinc-500 truncate max-w-md">
                            {touchpoint.url}
                          </div>
                        )}

                        {/* UTM parameters */}
                        {touchpoint.utm && (
                          <div className="flex gap-2 mt-2">
                            {touchpoint.utm.source && (
                              <span className="text-xs px-1.5 py-0.5 bg-[#2a2a2a] text-zinc-400 rounded-sm">
                                utm_source: {touchpoint.utm.source}
                              </span>
                            )}
                            {touchpoint.utm.medium && (
                              <span className="text-xs px-1.5 py-0.5 bg-[#2a2a2a] text-zinc-400 rounded-sm">
                                utm_medium: {touchpoint.utm.medium}
                              </span>
                            )}
                          </div>
                        )}

                        {/* Time gap to next touchpoint */}
                        {!isLast && journey.touchpoints[index + 1] && (
                          <div className="mt-3 flex items-center gap-2">
                            <div className="h-px flex-1 bg-[#2a2a2a]" />
                            <span className="text-xs text-zinc-600">
                              {calculateTimeGap(touchpoint.timestamp, journey.touchpoints[index + 1].timestamp)}
                            </span>
                            <div className="h-px flex-1 bg-[#2a2a2a]" />
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ))}
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

function getActionIcon(action: string) {
  const lower = action.toLowerCase();
  if (lower.includes('visit') || lower.includes('click')) {
    return <MousePointerIcon size={14} className="text-zinc-400" />;
  }
  if (lower.includes('cart') || lower.includes('add')) {
    return <ShoppingCartIcon size={14} className="text-zinc-400" />;
  }
  if (lower.includes('purchase') || lower.includes('buy')) {
    return <CreditCardIcon size={14} className="text-[#F7B500]" />;
  }
  return <ClockIcon size={14} className="text-zinc-400" />;
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false 
  });
}

function calculateTimeGap(t1: string, t2: string): string {
  const date1 = new Date(t1);
  const date2 = new Date(t2);
  const diff = Math.abs(date2.getTime() - date1.getTime());
  
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  
  if (hours > 0) {
    return `${hours}h ${minutes}m later`;
  }
  return `${minutes}m later`;
}

export default TouchpointTimeline;
