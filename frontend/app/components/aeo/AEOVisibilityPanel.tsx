'use client';

import React from 'react';
import { formatDate } from '@/app/lib/dates';
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts';
import {
  ChartContainer, ChartTooltip, ChartTooltipContent,
  ChartLegend, ChartLegendContent, type ChartConfig,
} from '../ui/chart';
import { Button, Card, Badge } from '../';
import { SparklesIcon, GlobeIcon, ChartIcon, DatabaseIcon, CheckIcon, RefreshIcon, XIcon } from '../ui/Icons';
import { VisibilityPrompt, VisibilityDashboard, VisibilityWeeklyTrend } from '@/lib/api';

interface AEOVisibilityPanelProps {
    prompts: VisibilityPrompt[];
    dashboard: VisibilityDashboard | null;
    visibilityTrend?: VisibilityWeeklyTrend[] | null;
    onRunCheck: (promptIds?: number[]) => void;
    onRefresh: () => void;
    onAddPrompt: (promptText: string, category: string) => void;
    onRemovePrompt: (promptId: number) => void;
    loading: boolean;
    checking: boolean;
}

export const AEOVisibilityPanel: React.FC<AEOVisibilityPanelProps> = ({
    prompts,
    dashboard,
    visibilityTrend,
    onRunCheck,
    onRefresh,
    onAddPrompt,
    onRemovePrompt,
    loading,
    checking
}) => {
    const [newPrompt, setNewPrompt] = React.useState('');
    const [newCategory, setNewCategory] = React.useState('general');
    const [showAddForm, setShowAddForm] = React.useState(false);

    const handleAddPrompt = () => {
        if (newPrompt.trim()) {
            onAddPrompt(newPrompt.trim(), newCategory);
            setNewPrompt('');
            setShowAddForm(false);
        }
    };

    const getCategoryBadge = (category: string) => {
        const variants: Record<string, 'success' | 'warning' | 'danger' | 'default'> = {
            fault_code: 'danger',
            product: 'success',
            competitor: 'warning',
            general: 'default',
        };
        return <Badge variant={variants[category] || 'default'}>{category}</Badge>;
    };

    return (
        <div className="space-y-6">
            {/* Visibility Metrics Dashboard */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-[#1a1a1a] rounded-sm border border-[#F7B500]/50 p-6">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-[#F7B500]/20 rounded-sm">
                            <SparklesIcon className="text-[#F7B500]" size={24} />
                        </div>
                        <div>
                            <p className="text-sm text-zinc-400">Visibility Score</p>
                            <p className="text-2xl font-bold text-[#F7B500]">
                                {dashboard?.current.visibility_score?.toFixed(1) || 0}%
                            </p>
                        </div>
                    </div>
                </div>

                <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-green-500/10 rounded-sm">
                            <GlobeIcon className="text-green-400" size={24} />
                        </div>
                        <div>
                            <p className="text-sm text-zinc-400">Citation Rate</p>
                            <p className="text-2xl font-bold text-white">
                                {dashboard?.current.citation_score?.toFixed(1) || 0}%
                            </p>
                        </div>
                    </div>
                </div>

                <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-blue-500/10 rounded-sm">
                            <ChartIcon className="text-blue-400" size={24} />
                        </div>
                        <div>
                            <p className="text-sm text-zinc-400">Share of Voice</p>
                            <p className="text-2xl font-bold text-white">
                                {dashboard?.current.share_of_voice?.toFixed(1) || 0}%
                            </p>
                        </div>
                    </div>
                </div>

                <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-purple-500/10 rounded-sm">
                            <DatabaseIcon className="text-purple-400" size={24} />
                        </div>
                        <div>
                            <p className="text-sm text-zinc-400">Total Checks</p>
                            <p className="text-2xl font-bold text-white">
                                {dashboard?.totals.total_checks || 0}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Prompt Panel */}
            <Card
                title="Visibility Prompts"
                subtitle="Queries sent to LLMs to check if Example Store is mentioned"
                action={
                    <div className="flex gap-2">
                        <Button
                            variant="primary"
                            size="sm"
                            onClick={() => onRunCheck()}
                            loading={checking}
                            icon={<SparklesIcon size={16} />}
                        >
                            {checking ? 'Checking...' : 'Run Check'}
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowAddForm(!showAddForm)}
                            icon={<CheckIcon size={16} />}
                        >
                            Add Prompt
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onRefresh}
                            icon={<RefreshIcon size={16} />}
                        >
                            Refresh
                        </Button>
                    </div>
                }
            >
                {/* Add Prompt Form */}
                {showAddForm && (
                    <div className="mb-6 p-4 bg-[#0a0a0a] border border-[#3a3a3a] rounded-sm">
                        <div className="flex gap-4">
                            <input
                                type="text"
                                value={newPrompt}
                                onChange={(e) => setNewPrompt(e.target.value)}
                                placeholder="Enter prompt (e.g., ¿Dónde comprar kit de reparación 4L60E?)"
                                className="flex-1 bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm px-4 py-2 text-white focus:border-[#F7B500] focus:outline-none"
                            />
                            <select
                                value={newCategory}
                                onChange={(e) => setNewCategory(e.target.value)}
                                className="bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm px-4 py-2 text-white focus:border-[#F7B500] focus:outline-none"
                            >
                                <option value="general">General</option>
                                <option value="fault_code">Fault Code</option>
                                <option value="product">Product</option>
                                <option value="competitor">Competitor</option>
                            </select>
                            <Button variant="primary" size="sm" onClick={handleAddPrompt}>
                                Add
                            </Button>
                            <Button variant="secondary" size="sm" onClick={() => setShowAddForm(false)}>
                                Cancel
                            </Button>
                        </div>
                    </div>
                )}

                {/* Prompts Table */}
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-[#3a3a3a]">
                                <th className="text-left py-3 px-4 text-sm font-medium text-zinc-400">Prompt</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-zinc-400">Category</th>
                                <th className="text-center py-3 px-4 text-sm font-medium text-zinc-400">Priority</th>
                                <th className="text-center py-3 px-4 text-sm font-medium text-zinc-400">Checks</th>
                                <th className="text-center py-3 px-4 text-sm font-medium text-zinc-400">Last Checked</th>
                                <th className="text-center py-3 px-4 text-sm font-medium text-zinc-400">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {prompts.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="text-center py-8 text-zinc-500">
                                        No prompts configured. Add prompts to start tracking visibility.
                                    </td>
                                </tr>
                            ) : (
                                prompts.map((prompt) => (
                                    <tr
                                        key={prompt.id}
                                        className="border-b border-[#3a3a3a]/50 hover:bg-[#1a1a1a]/50"
                                    >
                                        <td className="py-3 px-4 text-sm text-white max-w-md truncate">
                                            {prompt.prompt_text}
                                        </td>
                                        <td className="py-3 px-4">
                                            {getCategoryBadge(prompt.category)}
                                        </td>
                                        <td className="py-3 px-4 text-center">
                                            <span className="font-mono text-[#F7B500]">{prompt.priority}</span>
                                        </td>
                                        <td className="py-3 px-4 text-center text-zinc-400">
                                            {prompt.check_count}
                                        </td>
                                        <td className="py-3 px-4 text-center text-zinc-500 text-xs">
                                            {prompt.last_checked
                                                ? formatDate(prompt.last_checked)
                                                : 'Never'}
                                        </td>
                                        <td className="py-3 px-4 text-center">
                                            <div className="flex justify-center gap-2">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => onRunCheck([prompt.id])}
                                                    disabled={checking}
                                                >
                                                    Check
                                                </Button>
                                                <Button
                                                    variant="danger"
                                                    size="sm"
                                                    onClick={() => onRemovePrompt(prompt.id)}
                                                    icon={<XIcon size={14} />}
                                                >
                                                </Button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </Card>

            {/* Weekly Trend Chart */}
            {visibilityTrend && visibilityTrend.length > 0 ? (
                <Card
                    title="Visibility Trend (Weekly)"
                    subtitle="Brand mention rate, citation rate, and competitor mention rate over time"
                >
                    {/* KPI delta row */}
                    {dashboard && (
                        <div className="grid grid-cols-3 gap-4 mb-6">
                            {(() => {
                                const current = dashboard.current.visibility_score || 0;
                                const weekAvg = dashboard.trends.week_avg_visibility || 0;
                                const delta = current - weekAvg;
                                return (
                                    <div className="bg-[#0a0a0a] border border-[#3a3a3a] p-4 rounded-sm">
                                        <div className="text-xs text-zinc-500 mb-1">Brand Mention Rate</div>
                                        <div className="text-2xl font-bold text-[#F7B500]">{current.toFixed(1)}%</div>
                                        <div className={`text-xs mt-1 ${delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {delta >= 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}% vs week avg
                                        </div>
                                    </div>
                                );
                            })()}
                            {(() => {
                                const current = dashboard.current.citation_score || 0;
                                return (
                                    <div className="bg-[#0a0a0a] border border-[#3a3a3a] p-4 rounded-sm">
                                        <div className="text-xs text-zinc-500 mb-1">URL Citation Rate</div>
                                        <div className="text-2xl font-bold text-blue-400">{current.toFixed(1)}%</div>
                                        <div className="text-xs text-zinc-600 mt-1">Current snapshot</div>
                                    </div>
                                );
                            })()}
                            {(() => {
                                const current = dashboard.current.share_of_voice || 0;
                                const weekAvg = dashboard.trends.week_avg_share || 0;
                                const delta = current - weekAvg;
                                return (
                                    <div className="bg-[#0a0a0a] border border-[#3a3a3a] p-4 rounded-sm">
                                        <div className="text-xs text-zinc-500 mb-1">Share of Voice</div>
                                        <div className="text-2xl font-bold text-green-400">{current.toFixed(1)}%</div>
                                        <div className={`text-xs mt-1 ${delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {delta >= 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}% vs week avg
                                        </div>
                                    </div>
                                );
                            })()}
                        </div>
                    )}

                    {/* Multi-line trend chart */}
                    <ChartContainer
                        config={{
                            brand_mention_pct:      { label: 'Brand Mention %',     color: 'hsl(var(--chart-1))' },
                            citation_pct:           { label: 'URL Citation %',       color: 'hsl(var(--chart-2))' },
                            share_of_voice:         { label: 'Share of Voice %',     color: 'hsl(var(--chart-4))' },
                            competitor_mention_pct: { label: 'Competitor Mention %', color: '#ef4444' },
                        } satisfies ChartConfig}
                        className="h-56 w-full"
                    >
                        <LineChart data={visibilityTrend ?? []}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                            <XAxis dataKey="week_label" stroke="#555" fontSize={11} />
                            <YAxis
                                stroke="#555"
                                fontSize={11}
                                tickFormatter={v => `${v}%`}
                                domain={[0, 100]}
                                width={40}
                            />
                            <ChartTooltip
                                content={<ChartTooltipContent indicator="dot" formatter={(v: any) => `${Number(v).toFixed(1)}%`} />}
                            />
                            <ChartLegend content={<ChartLegendContent />} />
                            <Line type="monotone" dataKey="brand_mention_pct"      stroke="var(--color-brand_mention_pct)"      strokeWidth={2} dot={{ r: 3 }} />
                            <Line type="monotone" dataKey="citation_pct"           stroke="var(--color-citation_pct)"           strokeWidth={2} dot={{ r: 3 }} />
                            <Line type="monotone" dataKey="share_of_voice"         stroke="var(--color-share_of_voice)"         strokeWidth={2} dot={{ r: 3 }} />
                            <Line type="monotone" dataKey="competitor_mention_pct" stroke="var(--color-competitor_mention_pct)" strokeWidth={1.5} strokeDasharray="4 3" dot={{ r: 2 }} />
                        </LineChart>
                    </ChartContainer>
                    <p className="text-xs text-zinc-600 mt-3 italic">
                        Competitor Mention % (red dashed) shows how often rival brands appear when Example Store doesn't.
                        Aim to push Share of Voice above the competitor line.
                    </p>
                </Card>
            ) : dashboard ? (
                /* Fallback: simple bars when no weekly trend data yet */
                <Card title="7-Day Averages" subtitle="Run visibility checks regularly to build trend data">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="bg-[#0a0a0a] border border-[#3a3a3a] p-5 rounded-sm">
                            <div className="text-xs text-zinc-500 mb-2">Weekly Avg. Visibility</div>
                            <div className="text-3xl font-bold text-[#F7B500]">
                                {dashboard.trends.week_avg_visibility?.toFixed(1) || 0}%
                            </div>
                            <div className="mt-4 h-3 bg-[#3a3a3a] rounded-sm overflow-hidden">
                                <div
                                    className="h-full bg-[#F7B500] transition-all duration-500"
                                    style={{ width: `${Math.min(dashboard.trends.week_avg_visibility || 0, 100)}%` }}
                                />
                            </div>
                        </div>
                        <div className="bg-[#0a0a0a] border border-[#3a3a3a] p-5 rounded-sm">
                            <div className="text-xs text-zinc-500 mb-2">Weekly Avg. Share of Voice</div>
                            <div className="text-3xl font-bold text-green-400">
                                {dashboard.trends.week_avg_share?.toFixed(1) || 0}%
                            </div>
                            <div className="mt-4 h-3 bg-[#3a3a3a] rounded-sm overflow-hidden">
                                <div
                                    className="h-full bg-green-400 transition-all duration-500"
                                    style={{ width: `${Math.min(dashboard.trends.week_avg_share || 0, 100)}%` }}
                                />
                            </div>
                        </div>
                    </div>
                    <p className="text-xs text-zinc-600 mt-4 italic">
                        Run visibility checks more frequently to accumulate weekly trend history.
                    </p>
                </Card>
            ) : null}
        </div>
    );
};
