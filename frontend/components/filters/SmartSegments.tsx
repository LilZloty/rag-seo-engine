'use client';

import React from 'react';
import { Product } from '../../lib/api';

// Smart segment definitions with filter logic
export interface SmartSegment {
    id: string;
    name: string;
    icon: string;
    description: string;
    color: string;
    filter: (product: Product) => boolean;
}

export const SMART_SEGMENTS: SmartSegment[] = [
    {
        id: 'quick-wins',
        name: 'Quick Wins',
        icon: '🎯',
        description: 'High impressions + Has traffic',
        color: '#22c55e',
        filter: (p) => (p.gsc_impressions || 0) > 100 && (p.ga4_sessions || 0) > 10
    },
    {
        id: 'revenue-at-risk',
        name: 'Revenue at Risk',
        icon: '💸',
        description: 'High traffic but low sales',
        color: '#ef4444',
        filter: (p) => (p.ga4_sessions || 0) > 50 && (p.total_sold || 0) < 5
    },
    {
        id: 'new-products',
        name: 'New Products',
        icon: '🆕',
        description: 'Added in last 30 days',
        color: '#3b82f6',
        filter: (p) => {
            if (!p.created_at) return false;
            const createdDate = new Date(p.created_at);
            const thirtyDaysAgo = new Date();
            thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
            return createdDate > thirtyDaysAgo;
        }
    },
    {
        id: 'zombie-products',
        name: 'Zombie Products',
        icon: '😴',
        description: 'No sales in 90 days',
        color: '#6b7280',
        filter: (p) => (p.total_sold || 0) === 0
    },
    {
        id: 'top-performers',
        name: 'Top Performers',
        icon: '🏆',
        description: 'High revenue products',
        color: '#f7b500',
        filter: (p) => (p.total_revenue || 0) > 500
    },
    {
        id: 'high-opportunity',
        name: 'High Opportunity',
        icon: '🔥',
        description: 'Backend-calculated high opportunity',
        color: '#f97316',
        filter: (p) => p.opportunity_level === 'high'
    },
    {
        id: 'needs-seo',
        name: 'Needs SEO',
        icon: '⚠️',
        description: 'Products flagged for SEO work',
        color: '#eab308',
        filter: (p) => p.needs_seo === true
    },
    {
        id: 'all',
        name: 'All Products',
        icon: '📦',
        description: 'Show all products',
        color: '#888888',
        filter: () => true
    }
];

interface SmartSegmentsProps {
    products: Product[];
    totalProducts?: number; // Total count from database for 'all' segment
    serverCounts?: Record<string, number>; // Counts from backend API for accurate segment totals
    activeSegment: string;
    onSegmentChange: (segmentId: string) => void;
}

export default function SmartSegments({ products, totalProducts, serverCounts, activeSegment, onSegmentChange }: SmartSegmentsProps) {
    // Use server counts if provided (accurate), otherwise fall back to client-side counting
    const segmentCounts = SMART_SEGMENTS.reduce((acc, segment) => {
        // If server provided counts, use them
        if (serverCounts && serverCounts[segment.id] !== undefined) {
            acc[segment.id] = serverCounts[segment.id];
        } else if (segment.id === 'all' && totalProducts !== undefined) {
            // Fallback for 'all' segment
            acc[segment.id] = totalProducts;
        } else {
            // Fallback to client-side filtering
            acc[segment.id] = products.filter(segment.filter).length;
        }
        return acc;
    }, {} as Record<string, number>);

    return (
        <div className="mb-6">
            <h3 className="text-sm font-medium text-[#888888] mb-3">Quick Filters</h3>
            <div className="flex flex-wrap gap-2">
                {SMART_SEGMENTS.map((segment) => {
                    const isActive = activeSegment === segment.id;
                    const count = segmentCounts[segment.id];

                    return (
                        <button
                            key={segment.id}
                            onClick={() => onSegmentChange(segment.id)}
                            title={segment.description}
                            className={`
                                flex items-center gap-2 px-3 py-2 rounded-lg 
                                transition-all duration-200 text-sm font-medium
                                ${isActive
                                    ? 'bg-[#1a1a1a] border-2 ring-1 ring-opacity-50'
                                    : 'bg-[#0a0a0a] border border-[#333333] hover:border-[#444444]'
                                }
                            `}
                            style={{
                                borderColor: isActive ? segment.color : undefined,
                                boxShadow: isActive ? `0 0 10px ${segment.color}30` : undefined
                            }}
                        >
                            <span className="text-lg">{segment.icon}</span>
                            <span className={isActive ? 'text-white' : 'text-[#cccccc]'}>
                                {segment.name}
                            </span>
                            <span
                                className="px-1.5 py-0.5 rounded text-xs font-mono"
                                style={{
                                    backgroundColor: `${segment.color}20`,
                                    color: segment.color
                                }}
                            >
                                {count}
                            </span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

// Helper function to apply smart segment filter
export function applySmartSegmentFilter(products: Product[], segmentId: string): Product[] {
    const segment = SMART_SEGMENTS.find(s => s.id === segmentId);
    if (!segment) return products;
    return products.filter(segment.filter);
}
