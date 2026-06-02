'use client';

import React, { useState } from 'react';
import { Product } from '../../lib/api';

// Available fields for filtering
export type FilterFieldKey =
    | 'seo_score' | 'total_sold' | 'total_revenue'
    | 'ga4_sessions' | 'ga4_engagement_time' | 'ga4_bounce_rate'
    | 'gsc_impressions' | 'gsc_clicks' | 'gsc_ctr' | 'gsc_position'
    | 'performance_score' | 'description_length' | 'image_count';

export type FilterOperator = 'equals' | 'greater_than' | 'less_than' | 'between' | 'not_equals';

export interface FilterCondition {
    id: string;
    field: FilterFieldKey;
    operator: FilterOperator;
    value: number;
    value2?: number; // For 'between' operator
}

export interface FilterGroup {
    logic: 'AND' | 'OR';
    conditions: FilterCondition[];
}

const FILTER_FIELDS: { key: FilterFieldKey; label: string; category: string }[] = [
    // SEO & Content
    { key: 'seo_score', label: 'SEO Score', category: 'SEO' },
    { key: 'description_length', label: 'Description Length', category: 'SEO' },
    { key: 'image_count', label: 'Image Count', category: 'SEO' },
    // Shopify
    { key: 'total_sold', label: 'Total Sold', category: 'Shopify' },
    { key: 'total_revenue', label: 'Total Revenue ($)', category: 'Shopify' },
    // GA4
    { key: 'ga4_sessions', label: 'GA4 Sessions', category: 'Analytics' },
    { key: 'ga4_engagement_time', label: 'Engagement Time (sec)', category: 'Analytics' },
    { key: 'ga4_bounce_rate', label: 'Bounce Rate (%)', category: 'Analytics' },
    { key: 'performance_score', label: 'Performance Score', category: 'Analytics' },
    // GSC
    { key: 'gsc_impressions', label: 'Search Impressions', category: 'Search' },
    { key: 'gsc_clicks', label: 'Search Clicks', category: 'Search' },
    { key: 'gsc_ctr', label: 'Search CTR (%)', category: 'Search' },
    { key: 'gsc_position', label: 'Search Position', category: 'Search' },
];

const OPERATORS: { value: FilterOperator; label: string }[] = [
    { value: 'greater_than', label: 'is greater than' },
    { value: 'less_than', label: 'is less than' },
    { value: 'equals', label: 'equals' },
    { value: 'not_equals', label: 'does not equal' },
    { value: 'between', label: 'is between' },
];

function generateId(): string {
    return Math.random().toString(36).substring(2, 9);
}

interface VisualFilterBuilderProps {
    filterGroup: FilterGroup;
    onFilterChange: (filterGroup: FilterGroup) => void;
    isOpen: boolean;
    onToggle: () => void;
}

export default function VisualFilterBuilder({
    filterGroup,
    onFilterChange,
    isOpen,
    onToggle
}: VisualFilterBuilderProps) {

    const addCondition = () => {
        const newCondition: FilterCondition = {
            id: generateId(),
            field: 'seo_score',
            operator: 'less_than',
            value: 50
        };
        onFilterChange({
            ...filterGroup,
            conditions: [...filterGroup.conditions, newCondition]
        });
    };

    const removeCondition = (id: string) => {
        onFilterChange({
            ...filterGroup,
            conditions: filterGroup.conditions.filter(c => c.id !== id)
        });
    };

    const updateCondition = (id: string, updates: Partial<FilterCondition>) => {
        onFilterChange({
            ...filterGroup,
            conditions: filterGroup.conditions.map(c =>
                c.id === id ? { ...c, ...updates } : c
            )
        });
    };

    const toggleLogic = () => {
        onFilterChange({
            ...filterGroup,
            logic: filterGroup.logic === 'AND' ? 'OR' : 'AND'
        });
    };

    const clearAll = () => {
        onFilterChange({ logic: 'AND', conditions: [] });
    };

    return (
        <div className="bg-[#111111] border border-[#222222] rounded-xl overflow-hidden">
            {/* Header */}
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#1a1a1a] transition-colors"
            >
                <div className="flex items-center gap-2">
                    <span className="text-lg">🔧</span>
                    <span className="font-medium text-white">Custom Filter Builder</span>
                    {filterGroup.conditions.length > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-xs bg-[#f7b500] text-black font-medium">
                            {filterGroup.conditions.length} active
                        </span>
                    )}
                </div>
                <span className={`text-[#888888] transition-transform ${isOpen ? 'rotate-180' : ''}`}>
                    ▼
                </span>
            </button>

            {/* Content */}
            {isOpen && (
                <div className="px-4 pb-4 border-t border-[#222222]">
                    <div className="pt-4 space-y-3">
                        {filterGroup.conditions.length === 0 ? (
                            <p className="text-[#666666] text-sm text-center py-4">
                                No custom filters. Click "Add Condition" to create one.
                            </p>
                        ) : (
                            filterGroup.conditions.map((condition, index) => (
                                <div key={condition.id} className="space-y-2">
                                    {index > 0 && (
                                        <button
                                            onClick={toggleLogic}
                                            className="mx-auto block px-3 py-1 text-xs font-medium rounded-full
                                                bg-[#1a1a1a] border border-[#333333] text-[#f7b500]
                                                hover:border-[#f7b500] transition-colors"
                                        >
                                            {filterGroup.logic}
                                        </button>
                                    )}

                                    <div className="flex items-center gap-2 bg-[#0a0a0a] rounded-lg p-3">
                                        {/* Field selector */}
                                        <select
                                            value={condition.field}
                                            onChange={(e) => updateCondition(condition.id, {
                                                field: e.target.value as FilterFieldKey
                                            })}
                                            className="flex-1 bg-[#1a1a1a] border border-[#333333] rounded px-2 py-1.5 text-white text-sm"
                                        >
                                            {Object.entries(
                                                FILTER_FIELDS.reduce((acc, f) => {
                                                    acc[f.category] = acc[f.category] || [];
                                                    acc[f.category].push(f);
                                                    return acc;
                                                }, {} as Record<string, typeof FILTER_FIELDS>)
                                            ).map(([category, fields]) => (
                                                <optgroup key={category} label={category}>
                                                    {fields.map(f => (
                                                        <option key={f.key} value={f.key}>{f.label}</option>
                                                    ))}
                                                </optgroup>
                                            ))}
                                        </select>

                                        {/* Operator selector */}
                                        <select
                                            value={condition.operator}
                                            onChange={(e) => updateCondition(condition.id, {
                                                operator: e.target.value as FilterOperator
                                            })}
                                            className="bg-[#1a1a1a] border border-[#333333] rounded px-2 py-1.5 text-white text-sm"
                                        >
                                            {OPERATORS.map(op => (
                                                <option key={op.value} value={op.value}>{op.label}</option>
                                            ))}
                                        </select>

                                        {/* Value input */}
                                        <input
                                            type="number"
                                            value={condition.value}
                                            onChange={(e) => updateCondition(condition.id, {
                                                value: Number(e.target.value)
                                            })}
                                            className="w-20 bg-[#1a1a1a] border border-[#333333] rounded px-2 py-1.5 text-white text-sm"
                                        />

                                        {/* Second value for 'between' */}
                                        {condition.operator === 'between' && (
                                            <>
                                                <span className="text-[#666666] text-sm">and</span>
                                                <input
                                                    type="number"
                                                    value={condition.value2 || 0}
                                                    onChange={(e) => updateCondition(condition.id, {
                                                        value2: Number(e.target.value)
                                                    })}
                                                    className="w-20 bg-[#1a1a1a] border border-[#333333] rounded px-2 py-1.5 text-white text-sm"
                                                />
                                            </>
                                        )}

                                        {/* Remove button */}
                                        <button
                                            onClick={() => removeCondition(condition.id)}
                                            className="p-1.5 text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-[#222222]">
                        <button
                            onClick={addCondition}
                            className="flex items-center gap-2 px-3 py-2 text-sm font-medium
                                bg-[#1a1a1a] border border-[#333333] rounded-lg
                                text-[#f7b500] hover:border-[#f7b500] transition-colors"
                        >
                            <span>+</span>
                            <span>Add Condition</span>
                        </button>

                        {filterGroup.conditions.length > 0 && (
                            <button
                                onClick={clearAll}
                                className="text-sm text-red-400 hover:text-red-300"
                            >
                                Clear All
                            </button>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

// Helper function to apply visual filter builder conditions
export function applyVisualFilters(products: Product[], filterGroup: FilterGroup): Product[] {
    if (filterGroup.conditions.length === 0) return products;

    return products.filter(product => {
        const results = filterGroup.conditions.map(condition => {
            const value = (product as any)[condition.field] || 0;

            switch (condition.operator) {
                case 'equals':
                    return value === condition.value;
                case 'not_equals':
                    return value !== condition.value;
                case 'greater_than':
                    return value > condition.value;
                case 'less_than':
                    return value < condition.value;
                case 'between':
                    return value >= condition.value && value <= (condition.value2 || condition.value);
                default:
                    return true;
            }
        });

        if (filterGroup.logic === 'AND') {
            return results.every(r => r);
        } else {
            return results.some(r => r);
        }
    });
}

// Default empty filter group
export const DEFAULT_FILTER_GROUP: FilterGroup = {
    logic: 'AND',
    conditions: []
};
