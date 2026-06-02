'use client';

import React, { useState } from 'react';

export type DataSource = 'shopify' | 'analytics' | 'search';

// FilterFieldInput component - extracted to module scope to prevent re-creation on every render
interface FilterFieldInputProps {
    field: FilterField;
    value: string | number;
    onFilterChange: (key: keyof DataSourceFilters, value: string | number) => void;
}

const FilterFieldInput = ({ field, value, onFilterChange }: FilterFieldInputProps) => {
    if (field.type === 'select' && field.options) {
        return (
            <select
                value={value as string}
                onChange={(e) => onFilterChange(field.key as keyof DataSourceFilters, e.target.value)}
                className="w-full bg-[#0a0a0a] border border-[#333333] rounded-lg px-3 py-2 text-white text-sm focus:border-[#f7b500] focus:outline-none"
            >
                {field.options.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
            </select>
        );
    }

    if (field.type === 'text') {
        return (
            <input
                type="text"
                value={value as string}
                onChange={(e) => onFilterChange(field.key as keyof DataSourceFilters, e.target.value)}
                placeholder={field.placeholder}
                className="w-full bg-[#0a0a0a] border border-[#333333] rounded-lg px-3 py-2 text-white text-sm placeholder-[#666666] focus:border-[#f7b500] focus:outline-none"
            />
        );
    }

    return (
        <input
            type="number"
            value={value}
            onChange={(e) => onFilterChange(
                field.key as keyof DataSourceFilters,
                e.target.value === '' ? '' : Number(e.target.value)
            )}
            min={field.min}
            max={field.max}
            step={field.step}
            placeholder={field.placeholder}
            className="w-full bg-[#0a0a0a] border border-[#333333] rounded-lg px-3 py-2 text-white text-sm placeholder-[#666666] focus:border-[#f7b500] focus:outline-none"
        />
    );
};

// Filter field definitions for each data source
export interface FilterField {
    key: string;
    label: string;
    type: 'number' | 'range' | 'select' | 'text';
    options?: { value: string; label: string }[];
    min?: number;
    max?: number;
    step?: number;
    placeholder?: string;
}

export const DATA_SOURCE_FIELDS: Record<DataSource, FilterField[]> = {
    shopify: [
        {
            key: 'priceMin',
            label: 'Price Min ($)',
            type: 'number',
            min: 0,
            placeholder: 'Min price'
        },
        {
            key: 'priceMax',
            label: 'Price Max ($)',
            type: 'number',
            min: 0,
            placeholder: 'Max price'
        },
        {
            key: 'salesVolume',
            label: 'Sales Volume',
            type: 'select',
            options: [
                { value: 'all', label: 'All' },
                { value: '0', label: 'No sales' },
                { value: '1-10', label: '1-10 sold' },
                { value: '11-50', label: '11-50 sold' },
                { value: '50-100', label: '50-100 sold' },
                { value: '100+', label: '100+ sold' }
            ]
        },
        {
            key: 'revenueMin',
            label: 'Revenue Min ($)',
            type: 'number',
            min: 0,
            placeholder: 'Min revenue'
        },
        {
            key: 'vendor',
            label: 'Vendor',
            type: 'text',
            placeholder: 'Filter by vendor'
        },
        {
            key: 'productType',
            label: 'Product Type',
            type: 'text',
            placeholder: 'Filter by type'
        }
    ],
    analytics: [
        {
            key: 'sessionsMin',
            label: 'Sessions Min',
            type: 'number',
            min: 0,
            placeholder: 'Min sessions'
        },
        {
            key: 'sessionsMax',
            label: 'Sessions Max',
            type: 'number',
            min: 0,
            placeholder: 'Max sessions'
        },
        {
            key: 'engagementMin',
            label: 'Engagement (sec) Min',
            type: 'number',
            min: 0,
            placeholder: 'Min engagement'
        },
        {
            key: 'bounceRateMax',
            label: 'Bounce Rate Max (%)',
            type: 'number',
            min: 0,
            max: 100,
            placeholder: 'Max bounce rate'
        },
        {
            key: 'performanceScore',
            label: 'Performance Score',
            type: 'select',
            options: [
                { value: 'all', label: 'All' },
                { value: '0-25', label: 'Low (0-25)' },
                { value: '26-50', label: 'Medium (26-50)' },
                { value: '51-75', label: 'Good (51-75)' },
                { value: '76-100', label: 'Excellent (76-100)' }
            ]
        }
    ],
    search: [
        {
            key: 'impressionsMin',
            label: 'Impressions Min',
            type: 'number',
            min: 0,
            placeholder: 'Min impressions'
        },
        {
            key: 'clicksMin',
            label: 'Clicks Min',
            type: 'number',
            min: 0,
            placeholder: 'Min clicks'
        },
        {
            key: 'ctrMin',
            label: 'CTR Min (%)',
            type: 'number',
            min: 0,
            max: 100,
            step: 0.1,
            placeholder: 'Min CTR'
        },
        {
            key: 'positionMax',
            label: 'Position Max',
            type: 'number',
            min: 1,
            placeholder: 'Max position'
        }
    ]
};

const TAB_CONFIG: Record<DataSource, { label: string; icon: string; color: string }> = {
    shopify: { label: 'Shopify', icon: '🛒', color: '#95bf47' },
    analytics: { label: 'Analytics', icon: '📊', color: '#f7b500' },
    search: { label: 'Search', icon: '🔍', color: '#4285f4' }
};

export interface DataSourceFilters {
    // Shopify
    priceMin: number | '';
    priceMax: number | '';
    salesVolume: string;
    revenueMin: number | '';
    vendor: string;
    productType: string;
    // Analytics
    sessionsMin: number | '';
    sessionsMax: number | '';
    engagementMin: number | '';
    bounceRateMax: number | '';
    performanceScore: string;
    // Search
    impressionsMin: number | '';
    clicksMin: number | '';
    ctrMin: number | '';
    positionMax: number | '';
}

export const DEFAULT_DATA_SOURCE_FILTERS: DataSourceFilters = {
    priceMin: '',
    priceMax: '',
    salesVolume: 'all',
    revenueMin: '',
    vendor: '',
    productType: '',
    sessionsMin: '',
    sessionsMax: '',
    engagementMin: '',
    bounceRateMax: '',
    performanceScore: 'all',
    impressionsMin: '',
    clicksMin: '',
    ctrMin: '',
    positionMax: ''
};

interface DataSourceTabsProps {
    filters: DataSourceFilters;
    onFilterChange: (key: keyof DataSourceFilters, value: string | number) => void;
    onClearAll: () => void;
    activeFiltersCount: number;
}

export default function DataSourceTabs({
    filters,
    onFilterChange,
    onClearAll,
    activeFiltersCount
}: DataSourceTabsProps) {
    const [activeTab, setActiveTab] = useState<DataSource>('shopify');

    return (
        <div className="bg-[#111111] border border-[#222222] rounded-xl p-4">
            {/* Tab Headers */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex gap-1 bg-[#0a0a0a] rounded-lg p-1">
                    {(Object.keys(TAB_CONFIG) as DataSource[]).map((tab) => {
                        const config = TAB_CONFIG[tab];
                        const isActive = activeTab === tab;

                        return (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`
                                    flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium
                                    transition-all duration-200
                                    ${isActive
                                        ? 'bg-[#1a1a1a] text-white'
                                        : 'text-[#888888] hover:text-white'
                                    }
                                `}
                                style={{
                                    borderBottom: isActive ? `2px solid ${config.color}` : undefined
                                }}
                            >
                                <span>{config.icon}</span>
                                <span>{config.label}</span>
                            </button>
                        );
                    })}
                </div>

                {activeFiltersCount > 0 && (
                    <button
                        onClick={onClearAll}
                        className="text-sm text-red-400 hover:text-red-300 flex items-center gap-1"
                    >
                        <span>✕</span>
                        Clear {activeFiltersCount} filter{activeFiltersCount > 1 ? 's' : ''}
                    </button>
                )}
            </div>

            {/* Tab Content */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {DATA_SOURCE_FIELDS[activeTab].map((field) => (
                    <div key={field.key}>
                        <label className="block text-xs text-[#888888] mb-1">
                            {field.label}
                        </label>
                        <FilterFieldInput
                            field={field}
                            value={filters[field.key as keyof DataSourceFilters]}
                            onFilterChange={onFilterChange}
                        />
                    </div>
                ))}
            </div>
        </div>
    );
}
