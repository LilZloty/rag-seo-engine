'use client';

import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Modal } from '../';
import { SearchIcon, PlusIcon, CheckIcon, DatabaseIcon, TrendingUpIcon, FilterIcon, ChevronDownIcon, ChevronUpIcon } from '../ui/Icons';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Cell } from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '../ui/chart';

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Types
interface GSCQuerySuggestion {
    query: string;
    impressions: number;
    clicks: number;
    ctr: number;
    position: number;
    suggested_prompt: string;
    suggested_category: string;
    suggested_transmission: string | null;
    suggested_priority: number;
    opportunity_score: number;
}

interface GSCSuggestionsResponse {
    status: string;
    message?: string;
    total_gsc_queries: number;
    suggestions_count: number;
    suggestions: GSCQuerySuggestion[];
}

interface ImportResult {
    status: string;
    imported_count: number;
    skipped_count: number;
    imported: Array<{
        query: string;
        prompt_text: string;
        category: string;
        transmission: string | null;
    }>;
    skipped?: Array<{
        query: string;
        reason: string;
    }>;
}

interface GSCPromptImporterProps {
    onImportComplete?: () => void;
}

// Category colors
const CATEGORY_COLORS: Record<string, string> = {
    product: '#10B981',
    fault_code: '#F59E0B',
    competitor: '#8B5CF6',
    general: '#6B7280',
};

// Opportunity score gradient
const getScoreColor = (score: number): string => {
    if (score >= 80) return '#EF4444'; // Red (high opportunity)
    if (score >= 60) return '#F59E0B'; // Orange
    if (score >= 40) return '#F7B500'; // Yellow
    return '#10B981'; // Green (low opportunity)
};

export const GSCPromptImporter: React.FC<GSCPromptImporterProps> = ({
    onImportComplete
}) => {
    const [suggestions, setSuggestions] = useState<GSCQuerySuggestion[]>([]);
    const [loading, setLoading] = useState(false);
    const [importing, setImporting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedQueries, setSelectedQueries] = useState<Set<string>>(new Set());
    const [importResult, setImportResult] = useState<ImportResult | null>(null);
    const [showFilters, setShowFilters] = useState(false);
    
    // Filter states
    const [filters, setFilters] = useState({
        minImpressions: 50,
        minPosition: 1,
        maxPosition: 30,
        minOpportunity: 30,
        category: 'all',
    });

    // Fetch suggestions
    const fetchSuggestions = async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                min_impressions: filters.minImpressions.toString(),
                min_position: filters.minPosition.toString(),
                max_position: filters.maxPosition.toString(),
                limit: '100',
                exclude_existing: 'true',
            });
            
            const response = await fetch(`${API_BASE}/api/v1/aeo/visibility/prompts/gsc-suggestions?${params}`);
            if (response.ok) {
                const data: GSCSuggestionsResponse = await response.json();
                if (data.status === 'success') {
                    // Apply opportunity filter client-side
                    const filtered = data.suggestions.filter(s => 
                        s.opportunity_score >= filters.minOpportunity &&
                        (filters.category === 'all' || s.suggested_category === filters.category)
                    );
                    setSuggestions(filtered);
                } else {
                    setError(data.message || 'No data available');
                }
            } else {
                setError('Failed to fetch suggestions');
            }
        } catch (err) {
            setError('Failed to connect to API');
        } finally {
            setLoading(false);
        }
    };

    // Import selected queries
    const importSelected = async () => {
        if (selectedQueries.size === 0) return;
        
        setImporting(true);
        setError(null);
        try {
            const queries = Array.from(selectedQueries);
            const response = await fetch(`${API_BASE}/api/v1/aeo/visibility/prompts/import-from-gsc?auto_format=true&default_priority=60`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(queries)
            });
            
            if (response.ok) {
                const data: ImportResult = await response.json();
                setImportResult(data);
                // Remove imported from suggestions
                setSuggestions(prev => prev.filter(s => !selectedQueries.has(s.query)));
                setSelectedQueries(new Set());
                if (onImportComplete) onImportComplete();
            } else {
                setError('Import failed');
            }
        } catch (err) {
            setError('Failed to import queries');
        } finally {
            setImporting(false);
        }
    };

    // Bulk import top opportunities
    const bulkImport = async () => {
        setImporting(true);
        setError(null);
        try {
            const response = await fetch(`${API_BASE}/api/v1/aeo/visibility/prompts/bulk-import-gsc?min_impressions=${filters.minImpressions}&max_queries=20&min_opportunity_score=${filters.minOpportunity}`, {
                method: 'POST',
            });
            
            if (response.ok) {
                const data: ImportResult = await response.json();
                setImportResult(data);
                // Refresh suggestions
                await fetchSuggestions();
                if (onImportComplete) onImportComplete();
            } else {
                setError('Bulk import failed');
            }
        } catch (err) {
            setError('Failed to bulk import');
        } finally {
            setImporting(false);
        }
    };

    // Toggle query selection
    const toggleSelection = (query: string) => {
        setSelectedQueries(prev => {
            const newSet = new Set(prev);
            if (newSet.has(query)) {
                newSet.delete(query);
            } else {
                newSet.add(query);
            }
            return newSet;
        });
    };

    // Select/deselect all
    const toggleAll = () => {
        if (selectedQueries.size === suggestions.length) {
            setSelectedQueries(new Set());
        } else {
            setSelectedQueries(new Set(suggestions.map(s => s.query)));
        }
    };

    // Initial load
    useEffect(() => {
        fetchSuggestions();
    }, []);

    // Stats for charts
    const categoryStats = suggestions.reduce((acc, s) => {
        acc[s.suggested_category] = (acc[s.suggested_category] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    const chartData = Object.entries(categoryStats).map(([category, count]) => ({
        category,
        count,
        color: CATEGORY_COLORS[category] || '#6B7280'
    }));

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div>
                    <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                        <DatabaseIcon className="text-[#F7B500]" size={24} />
                        Import GSC Queries to Prompt Library
                    </h2>
                    <p className="text-zinc-400 text-sm mt-1">
                        Import real search queries from Google Search Console as visibility tracking prompts
                    </p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Button
                        onClick={() => setShowFilters(!showFilters)}
                        variant="outline"
                        className="flex items-center gap-2"
                    >
                        <FilterIcon size={16} />
                        Filters
                        {showFilters ? <ChevronUpIcon size={16} /> : <ChevronDownIcon size={16} />}
                    </Button>
                    <Button
                        onClick={fetchSuggestions}
                        disabled={loading}
                        variant="outline"
                    >
                        <SearchIcon size={16} className="mr-2" />
                        {loading ? 'Loading...' : 'Refresh'}
                    </Button>
                    <Button
                        onClick={bulkImport}
                        disabled={importing || suggestions.length === 0}
                        className="bg-[#F7B500] text-black hover:bg-[#F7B500]/80"
                    >
                        <TrendingUpIcon size={16} className="mr-2" />
                        {importing ? 'Importing...' : 'Auto-Import Top 20'}
                    </Button>
                </div>
            </div>

            {/* Filters */}
            {showFilters && (
                <Card className="bg-[#1a1a1a] border-[#333] p-4">
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <label className="block">
                            <span className="text-xs text-zinc-400 block mb-1">Min Impressions</span>
                            <input
                                type="number"
                                value={filters.minImpressions}
                                onChange={(e) => setFilters(f => ({ ...f, minImpressions: parseInt(e.target.value) || 0 }))}
                                className="w-full bg-[#0f0f0f] border border-[#333] rounded-sm px-3 py-2 text-sm text-white"
                            />
                        </label>
                        <label className="block">
                            <span className="text-xs text-zinc-400 block mb-1">Min Position</span>
                            <input
                                type="number"
                                value={filters.minPosition}
                                onChange={(e) => setFilters(f => ({ ...f, minPosition: parseFloat(e.target.value) || 0 }))}
                                className="w-full bg-[#0f0f0f] border border-[#333] rounded-sm px-3 py-2 text-sm text-white"
                            />
                        </label>
                        <label className="block">
                            <span className="text-xs text-zinc-400 block mb-1">Max Position</span>
                            <input
                                type="number"
                                value={filters.maxPosition}
                                onChange={(e) => setFilters(f => ({ ...f, maxPosition: parseFloat(e.target.value) || 100 }))}
                                className="w-full bg-[#0f0f0f] border border-[#333] rounded-sm px-3 py-2 text-sm text-white"
                            />
                        </label>
                        <label className="block">
                            <span className="text-xs text-zinc-400 block mb-1">Min Opportunity</span>
                            <input
                                type="number"
                                value={filters.minOpportunity}
                                onChange={(e) => setFilters(f => ({ ...f, minOpportunity: parseFloat(e.target.value) || 0 }))}
                                className="w-full bg-[#0f0f0f] border border-[#333] rounded-sm px-3 py-2 text-sm text-white"
                            />
                        </label>
                        <label className="block">
                            <span className="text-xs text-zinc-400 block mb-1">Category</span>
                            <select
                                value={filters.category}
                                onChange={(e) => setFilters(f => ({ ...f, category: e.target.value }))}
                                className="w-full bg-[#0f0f0f] border border-[#333] rounded-sm px-3 py-2 text-sm text-white"
                            >
                                <option value="all">All</option>
                                <option value="product">Product</option>
                                <option value="fault_code">Fault Code</option>
                                <option value="competitor">Competitor</option>
                                <option value="general">General</option>
                            </select>
                        </label>
                    </div>
                    <div className="mt-4 flex justify-end">
                        <Button onClick={fetchSuggestions} disabled={loading} size="sm">
                            Apply Filters
                        </Button>
                    </div>
                </Card>
            )}

            {error && (
                <div className="bg-red-500/10 border border-red-500/50 rounded-sm p-4 text-red-400">
                    {error}
                </div>
            )}

            {/* Stats */}
            {!loading && suggestions.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card className="bg-[#1a1a1a] border-[#333] p-4">
                        <p className="text-2xl font-bold text-white">{suggestions.length}</p>
                        <p className="text-xs text-zinc-400">Suggested Queries</p>
                    </Card>
                    <Card className="bg-[#1a1a1a] border-[#333] p-4">
                        <p className="text-2xl font-bold text-[#F7B500]">
                            {Math.round(suggestions.reduce((acc, s) => acc + s.opportunity_score, 0) / suggestions.length)}
                        </p>
                        <p className="text-xs text-zinc-400">Avg Opportunity Score</p>
                    </Card>
                    <Card className="bg-[#1a1a1a] border-[#333] p-4">
                        <p className="text-2xl font-bold text-green-400">
                            {suggestions.filter(s => s.opportunity_score >= 70).length}
                        </p>
                        <p className="text-xs text-zinc-400">High Opportunity (&gt;=70)</p>
                    </Card>
                    <Card className="bg-[#1a1a1a] border-[#333] p-4">
                        <p className="text-2xl font-bold text-blue-400">{selectedQueries.size}</p>
                        <p className="text-xs text-zinc-400">Selected for Import</p>
                    </Card>
                </div>
            )}

            {/* Category Distribution Chart */}
            {!loading && chartData.length > 0 && (
                <Card className="bg-[#1a1a1a] border-[#333] p-4">
                    <h3 className="text-sm text-zinc-400 mb-4">Query Distribution by Category</h3>
                    <ChartContainer config={{ count: { label: "Queries" } } satisfies ChartConfig} className="h-[150px] w-full">
                        <BarChart data={chartData} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" horizontal={false} />
                            <XAxis type="number" stroke="#444" fontSize={11} />
                            <YAxis dataKey="category" type="category" stroke="#444" fontSize={12} width={100} tick={{ fill: '#d1d5db' }} />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                                {chartData.map((entry) => (
                                    <Cell key={entry.category || entry.color} fill={entry.color} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ChartContainer>
                </Card>
            )}

            {/* Actions Bar */}
            {!loading && suggestions.length > 0 && (
                <div className="flex items-center justify-between bg-[#0f0f0f] p-3 rounded-sm">
                    <div className="flex items-center gap-4">
                        <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={selectedQueries.size === suggestions.length && suggestions.length > 0}
                                onChange={toggleAll}
                                className="rounded border-[#555] bg-[#1a1a1a] text-[#F7B500]"
                            />
                            Select All ({selectedQueries.size}/{suggestions.length})
                        </label>
                    </div>
                    {selectedQueries.size > 0 && (
                        <Button
                            onClick={importSelected}
                            disabled={importing}
                            className="bg-[#F7B500] text-black hover:bg-[#F7B500]/80"
                        >
                            <PlusIcon size={16} className="mr-2" />
                            {importing ? 'Importing...' : `Import ${selectedQueries.size} Selected`}
                        </Button>
                    )}
                </div>
            )}

            {/* Suggestions List */}
            {loading ? (
                <div className="text-center py-12">
                    <div className="animate-pulse text-zinc-400">Loading GSC queries…</div>
                </div>
            ) : suggestions.length === 0 ? (
                <Card className="bg-[#1a1a1a] border-[#333] p-12 text-center">
                    <SearchIcon className="text-zinc-500 mx-auto mb-4" size={48} />
                    <h3 className="text-lg text-zinc-300 mb-2">No Suggestions Found</h3>
                    <p className="text-zinc-500 mb-4">
                        Try adjusting your filters or check your GSC data connection
                    </p>
                    <Button onClick={fetchSuggestions} variant="outline">
                        Refresh
                    </Button>
                </Card>
            ) : (
                <div className="space-y-3">
                    {suggestions.map((suggestion) => (
                        <Card
                            key={suggestion.query}
                            className={`bg-[#1a1a1a] border-[#333] p-4 transition-all ${
                                selectedQueries.has(suggestion.query) 
                                    ? 'border-[#F7B500] bg-[#F7B500]/5' 
                                    : 'hover:border-[#555]'
                            }`}
                        >
                            <div className="flex items-start gap-4">
                                <input
                                    type="checkbox"
                                    checked={selectedQueries.has(suggestion.query)}
                                    onChange={() => toggleSelection(suggestion.query)}
                                    className="mt-1 rounded border-[#555] bg-[#0f0f0f] text-[#F7B500]"
                                />
                                <div className="flex-1 min-w-0">
                                    {/* Original Query */}
                                    <div className="flex items-center gap-2 mb-2">
                                        <p className="text-white font-medium truncate">{suggestion.query}</p>
                                        <Badge 
                                            style={{ backgroundColor: CATEGORY_COLORS[suggestion.suggested_category] || '#6B7280' }}
                                            className="text-white text-xs shrink-0"
                                        >
                                            {suggestion.suggested_category}
                                        </Badge>
                                        {suggestion.suggested_transmission && (
                                            <Badge variant="outline" className="text-[#F7B500] border-[#F7B500]/50 text-xs shrink-0">
                                                {suggestion.suggested_transmission}
                                            </Badge>
                                        )}
                                    </div>
                                    
                                    {/* Suggested Prompt */}
                                    <p className="text-sm text-zinc-400 mb-3 italic">
                                        → {suggestion.suggested_prompt}
                                    </p>
                                    
                                    {/* Metrics */}
                                    <div className="flex flex-wrap items-center gap-4 text-xs">
                                        <span className="text-zinc-500">
                                            <span className="text-zinc-400">Impressions:</span> {suggestion.impressions.toLocaleString()}
                                        </span>
                                        <span className="text-zinc-500">
                                            <span className="text-zinc-400">Clicks:</span> {suggestion.clicks}
                                        </span>
                                        <span className="text-zinc-500">
                                            <span className="text-zinc-400">CTR:</span> {suggestion.ctr}%
                                        </span>
                                        <span className="text-zinc-500">
                                            <span className="text-zinc-400">Position:</span> #{suggestion.position}
                                        </span>
                                        <span className="text-zinc-500">
                                            <span className="text-zinc-400">Priority:</span> {suggestion.suggested_priority}
                                        </span>
                                        <span 
                                            className="font-medium px-2 py-0.5 rounded"
                                            style={{ 
                                                backgroundColor: `${getScoreColor(suggestion.opportunity_score)}20`,
                                                color: getScoreColor(suggestion.opportunity_score)
                                            }}
                                        >
                                            Score: {suggestion.opportunity_score}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </Card>
                    ))}
                </div>
            )}

            {/* Import Result Modal */}
            {importResult && (
                <Modal isOpen={!!importResult} onClose={() => setImportResult(null)}>
                    <div className="bg-[#1a1a1a] p-6 rounded-lg max-w-2xl w-full">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="size-12 rounded-full bg-green-500/20 flex items-center justify-center">
                                <CheckIcon className="text-green-400" size={24} />
                            </div>
                            <div>
                                <h3 className="text-lg font-semibold text-white">Import Complete!</h3>
                                <p className="text-zinc-400 text-sm">
                                    {importResult.imported_count} prompts added to library
                                </p>
                            </div>
                        </div>
                        
                        {importResult.imported.length > 0 && (
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                                <h4 className="text-sm text-zinc-400 mb-2">Imported Prompts:</h4>
                                {importResult.imported.map((item, idx) => (
                                    <div key={item.prompt_text || `imported-${idx}`} className="bg-[#0f0f0f] p-3 rounded-sm">
                                        <p className="text-zinc-300 text-sm">{item.prompt_text}</p>
                                        <div className="flex gap-2 mt-1">
                                            <Badge variant="outline" className="text-zinc-500 text-xs">
                                                {item.category}
                                            </Badge>
                                            {item.transmission && (
                                                <Badge variant="outline" className="text-[#F7B500] text-xs">
                                                    {item.transmission}
                                                </Badge>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                        
                        {importResult.skipped && importResult.skipped.length > 0 && (
                            <div className="mt-4 pt-4 border-t border-[#333]">
                                <h4 className="text-sm text-yellow-500 mb-2">
                                    Skipped ({importResult.skipped.length}):
                                </h4>
                                <div className="space-y-1 max-h-32 overflow-y-auto">
                                    {importResult.skipped.map((item, idx) => (
                                        <p key={item.query || `skipped-${idx}`} className="text-xs text-zinc-500">
                                            • {item.query}: {item.reason}
                                        </p>
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        <div className="mt-6 flex justify-end">
                            <Button onClick={() => setImportResult(null)}>
                                Close
                            </Button>
                        </div>
                    </div>
                </Modal>
            )}
        </div>
    );
};

