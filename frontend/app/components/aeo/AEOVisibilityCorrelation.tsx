'use client';

import React from 'react';
import { Button, Card, Badge } from '../';
import { ChartIcon, CheckIcon, XIcon, RefreshIcon, DatabaseIcon, SparklesIcon } from '../ui/Icons';
import { VisibilitySalesCorrelation } from '@/lib/api';
import { formatCurrency } from './constants';

// Quadrant Component - extracted to module scope
interface QuadrantColor {
    bg: string;
    border: string;
    text: string;
}

interface QuadrantItem {
    topic: string;
    mentions: number;
    revenue: number;
    visibility_score: number;
}

interface QuadrantProps {
    title: string;
    subtitle: string;
    items: QuadrantItem[];
    color: QuadrantColor;
    icon: React.ReactNode;
}

const Quadrant: React.FC<QuadrantProps> = ({ title, subtitle, items, color, icon }) => (
    <div className={`p-4 border rounded-sm ${color.bg} ${color.border} flex flex-col h-full`}>
        <div className="flex items-center justify-between mb-2">
            <h3 className={`text-sm font-bold uppercase tracking-wider ${color.text}`}>{title}</h3>
            {icon}
        </div>
        <p className="text-xs text-zinc-400 mb-4">{subtitle}</p>
        <div className="flex-1 space-y-2 overflow-y-auto max-h-[300px] pr-2 scrollbar-thin">
            {items.map((item) => (
                <div key={item.topic} className="p-2 bg-[#0a0a0a]/50 rounded border border-[#3a3a3a] flex justify-between items-center group hover:border-[#F7B500]/50 transition-colors">
                    <div>
                        <p className="text-sm font-medium text-white">{item.topic}</p>
                        <p className="text-[10px] text-zinc-500">{item.mentions} Mentions</p>
                    </div>
                    <div className="text-right">
                        <p className="text-sm font-mono text-[#F7B500]">{formatCurrency(item.revenue)}</p>
                        <p className="text-[10px] text-zinc-500">{item.visibility_score}% Vis.</p>
                    </div>
                </div>
            ))}
            {items.length === 0 && (
                <p className="text-xs text-zinc-600 italic text-center py-4">No topics in this quadrant</p>
            )}
        </div>
    </div>
);

interface AEOVisibilityCorrelationProps {
    data: VisibilitySalesCorrelation;
    loading: boolean;
    onRefresh: () => void;
}

export const AEOVisibilityCorrelation: React.FC<AEOVisibilityCorrelationProps> = ({
    data,
    loading,
    onRefresh
}) => {
    const [activeView, setActiveView] = React.useState<'matrix' | 'list'>('matrix');

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm">
                <RefreshIcon className="animate-spin text-[#F7B500] mb-4" size={40} />
                <p className="text-zinc-400">Calculating Correlation Metrics…</p>
            </div>
        );
    }

    if (!data || data.topics.length === 0) {
        return (
            <div className="text-center py-16 text-zinc-400 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a]">
                <ChartIcon size={48} className="mx-auto mb-4 opacity-50" />
                <p>No correlation data available for the selected period.</p>
                <p className="text-sm text-zinc-500 mt-2">
                    Try running more AI visibility checks to populate this report.
                </p>
                <Button
                    variant="primary"
                    className="mt-6"
                    onClick={onRefresh}
                >
                    Check Now
                </Button>
            </div>
        );
    }

    const { summary, topics } = data;

    // Components for Matrix Visualization
    const renderMatrix = () => {
        // We categorize topics into quadrants
        const stars = topics.filter(t => t.status === 'star');
        const underperformers = topics.filter(t => t.status === 'underperformer');
        const potential = topics.filter(t => t.status === 'potential');
        const neutral = topics.filter(t => t.status === 'neutral');

        return (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                {/* Quadrant 1: Stars - High Visibility, High Revenue */}
                <Quadrant
                    title="Stars"
                    subtitle="Top performers driving both mentions and sales."
                    items={stars}
                    color={{ bg: 'bg-green-500/5', border: 'border-green-500/30', text: 'text-green-400' }}
                    icon={<CheckIcon className="text-green-400" size={16} />}
                />

                {/* Quadrant 2: Underperformers - High Visibility, Low Revenue (Conversion Gap) */}
                <Quadrant
                    title="Conversion Gaps"
                    subtitle="Mentioned often but low sales. Content isn't converting."
                    items={underperformers}
                    color={{ bg: 'bg-red-500/5', border: 'border-red-500/30', text: 'text-red-400' }}
                    icon={<XIcon className="text-red-400" size={16} />}
                />

                {/* Quadrant 3: Potential - Low Visibility, High Revenue (Visibility Gap) */}
                <Quadrant
                    title="Visibility Gaps"
                    subtitle="Selling well but rarely mentioned. Need more AEO prompts."
                    items={potential}
                    color={{ bg: 'bg-blue-500/5', border: 'border-blue-500/30', text: 'text-blue-400' }}
                    icon={<RefreshIcon className="text-blue-400" size={16} />}
                />

                {/* Quadrant 4: Stable/Niche */}
                <Quadrant
                    title="Stable / Niche"
                    subtitle="Supportive topics with balanced visibility and sales."
                    items={neutral}
                    color={{ bg: 'bg-zinc-500/5', border: 'border-zinc-500/30', text: 'text-zinc-400' }}
                    icon={<DatabaseIcon className="text-zinc-400" size={16} />}
                />
            </div>
        );
    };

    return (
        <div className="space-y-6">
            {/* No mentions banner */}
            {summary.total_mentions === 0 && (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-sm px-4 py-3 text-xs text-yellow-400">
                    <span className="font-semibold">Brand not yet mentioned in AI responses.</span>
                    {' '}Visibility checks ran but competitors are being cited instead. Run more AEO checks and build stronger content to get Example Store mentioned.
                    {' '}The revenue data below is real — it comes from Shopify regardless of AI mentions.
                </div>
            )}

            {/* ROI Summary Header */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-[#1a1a1a] p-5 rounded-sm border border-[#3a3a3a]">
                    <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Total Mentions</p>
                    <div className="flex items-end gap-2">
                        <span className="text-3xl font-bold text-white">{summary.total_mentions}</span>
                        <span className="text-sm text-green-400 mb-1">brand</span>
                    </div>
                    <p className="text-[10px] text-zinc-600 mt-1">Times brand was named in LLM responses</p>
                </div>

                <div className={`bg-[#1a1a1a] p-5 rounded-sm border ${
                    (summary.total_mentions || 0) >= 30 ? 'border-[#F7B500]/30' : 'border-yellow-700/40 opacity-70'
                }`}>
                    <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Value / Mention</p>
                    <div className="flex items-end gap-2">
                        {(summary.total_mentions || 0) >= 30 ? (
                            <span className="text-3xl font-bold text-[#F7B500] font-mono">{formatCurrency(summary.avg_revenue_per_mention)}</span>
                        ) : (
                            <span className="text-3xl font-bold text-zinc-500 font-mono">—</span>
                        )}
                    </div>
                    <p className="text-[10px] text-zinc-600 mt-1">
                        {(summary.total_mentions || 0) >= 30
                            ? 'Avg revenue per AI brand citation'
                            : `Need ≥30 mentions (have ${summary.total_mentions || 0})`}
                    </p>
                </div>

                <div className="bg-[#1a1a1a] p-5 rounded-sm border border-[#3a3a3a]">
                    <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Top Revenue Topic</p>
                    <p className="text-lg font-bold text-white truncate leading-tight mt-1">
                        {summary.top_performing_topic || 'N/A'}
                    </p>
                    <p className="text-[10px] text-zinc-600 mt-1">Highest revenue from tracked topics</p>
                </div>

                <div className="bg-[#1a1a1a] p-5 rounded-sm border border-blue-500/30">
                    <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Most Cited Topic</p>
                    <p className="text-lg font-bold text-blue-400 truncate leading-tight mt-1">
                        {summary.most_cited_topic || 'N/A'}
                    </p>
                    <p className="text-[10px] text-zinc-600 mt-1">Topic with most URL citations</p>
                </div>
            </div>

            {/* Main Analysis Section */}
            <Card
                title="Visibility-to-Sales Correlation"
                subtitle={`Analyzing ${topics.length} technical topics across ${data.days} days`}
                action={
                    <div className="flex gap-2">
                        <Button
                            size="sm"
                            variant={activeView === 'matrix' ? 'primary' : 'outline'}
                            onClick={() => setActiveView('matrix')}
                        >
                            Matrix View
                        </Button>
                        <Button
                            size="sm"
                            variant={activeView === 'list' ? 'primary' : 'outline'}
                            onClick={() => setActiveView('list')}
                        >
                            Details List
                        </Button>
                    </div>
                }
            >
                {activeView === 'matrix' ? renderMatrix() : (
                    <div className="overflow-x-auto mt-4">
                        <table className="w-full text-left border-collapse text-sm">
                            <thead>
                                <tr className="border-b border-[#3a3a3a] text-xs font-bold text-zinc-500 uppercase tracking-wider">
                                    <th className="px-4 py-3">Topic / Category</th>
                                    <th className="px-4 py-3">Mentions</th>
                                    <th className="px-4 py-3">URL Citations</th>
                                    <th className="px-4 py-3">Competitors</th>
                                    <th className="px-4 py-3">Revenue</th>
                                    <th className="px-4 py-3">ROI / Mention</th>
                                    <th className="px-4 py-3">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#1a1a1a]">
                                {topics.map((item) => {
                                    const citationRate = item.mentions > 0
                                        ? Math.round((item.citations / item.mentions) * 100)
                                        : 0;
                                    return (
                                        <tr key={item.topic} className="hover:bg-[#1a1a1a]/50 transition-colors group">
                                            <td className="p-4">
                                                <p className="font-medium text-white">{item.topic}</p>
                                                <p className="text-[10px] text-zinc-500 font-mono mt-0.5">{item.category}</p>
                                            </td>
                                            <td className="p-4">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-10 h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
                                                        <div className="h-full bg-[#F7B500]" style={{ width: `${Math.min(item.visibility_score, 100)}%` }} />
                                                    </div>
                                                    <span className="text-[#F7B500] font-mono text-xs">{item.visibility_score}%</span>
                                                </div>
                                                <p className="text-[10px] text-zinc-500 mt-1">{item.mentions} times</p>
                                            </td>
                                            <td className="p-4">
                                                <span className={`font-mono text-xs font-bold ${citationRate >= 30 ? 'text-green-400' : citationRate >= 10 ? 'text-yellow-400' : 'text-zinc-500'}`}>
                                                    {item.citations}
                                                </span>
                                                <p className="text-[10px] text-zinc-500 mt-1">{citationRate}% of mentions</p>
                                            </td>
                                            <td className="p-4">
                                                <span className={`font-mono text-xs font-bold ${item.competitor_mentions > 0 ? 'text-red-400' : 'text-zinc-600'}`}>
                                                    {item.competitor_mentions}
                                                </span>
                                                {item.competitor_mentions > 0 && (
                                                    <p className="text-[10px] text-red-500/70 mt-1">displacement risk</p>
                                                )}
                                            </td>
                                            <td className="p-4">
                                                <p className="font-bold text-white font-mono">{formatCurrency(item.revenue)}</p>
                                                <p className="text-[10px] text-zinc-500">{item.orders} orders</p>
                                            </td>
                                            <td className="p-4">
                                                {/* Per-topic value/mention — same ≥30 threshold as the
                                                    summary KPI. Under threshold we dim and label it
                                                    instead of hiding, since the topic row still needs
                                                    to show up in the table. */}
                                                {(item.mentions || 0) >= 30 ? (
                                                    <p className="text-[#F7B500] font-mono font-medium">{formatCurrency(item.revenue_per_mention)}</p>
                                                ) : (
                                                    <p
                                                        className="text-zinc-500 font-mono font-medium opacity-70"
                                                        title={`Only ${item.mentions} mentions — low confidence`}
                                                    >
                                                        {formatCurrency(item.revenue_per_mention)} <span className="text-[10px] text-yellow-500">⚠</span>
                                                    </p>
                                                )}
                                            </td>
                                            <td className="p-4">
                                                <Badge variant={
                                                    item.status === 'star' ? 'success' :
                                                        item.status === 'underperformer' ? 'danger' :
                                                            item.status === 'potential' ? 'warning' : 'default'
                                                }>
                                                    {item.status.toUpperCase()}
                                                </Badge>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </Card>

            {/* Recommendations Card */}
            {(() => {
                const convGaps   = topics.filter(t => t.status === 'underperformer').slice(0, 3);
                const visGaps    = topics.filter(t => t.status === 'potential').slice(0, 3);
                const highRisk   = topics.filter(t => t.competitor_mentions > t.mentions).slice(0, 3);
                return (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {/* Conversion Gaps */}
                        <div className="bg-[#1a1a1a] p-5 rounded-sm border border-red-500/20">
                            <div className="flex items-center gap-3 mb-3">
                                <div className="p-2 bg-red-500/10 rounded">
                                    <XIcon className="text-red-400" size={18} />
                                </div>
                                <h3 className="font-semibold text-white text-sm">Conversion Gaps</h3>
                            </div>
                            <p className="text-xs text-zinc-500 mb-3">Mentioned by AI but not converting to sales</p>
                            {convGaps.length > 0 ? (
                                <div className="space-y-1.5 mb-3">
                                    {convGaps.map(t => (
                                        <div key={t.topic} className="flex justify-between items-center px-2 py-1.5 bg-red-500/5 rounded border border-red-500/10">
                                            <span className="text-xs text-red-300 truncate max-w-[120px]">{t.topic}</span>
                                            <span className="text-xs text-zinc-500 font-mono">{t.visibility_score}% vis.</span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-xs text-zinc-600 italic mb-3">No conversion gaps — great!</p>
                            )}
                            <p className="text-[10px] text-red-400/80 leading-relaxed">
                                Action: Improve landing page CTA for these topics. Match AI-cited content to in-stock products.
                            </p>
                        </div>

                        {/* Visibility Gaps */}
                        <div className="bg-[#1a1a1a] p-5 rounded-sm border border-blue-500/20">
                            <div className="flex items-center gap-3 mb-3">
                                <div className="p-2 bg-blue-500/10 rounded">
                                    <RefreshIcon className="text-blue-400" size={18} />
                                </div>
                                <h3 className="font-semibold text-white text-sm">Visibility Gaps</h3>
                            </div>
                            <p className="text-xs text-zinc-500 mb-3">Selling well but rarely mentioned by AI</p>
                            {visGaps.length > 0 ? (
                                <div className="space-y-1.5 mb-3">
                                    {visGaps.map(t => (
                                        <div key={t.topic} className="flex justify-between items-center px-2 py-1.5 bg-blue-500/5 rounded border border-blue-500/10">
                                            <span className="text-xs text-blue-300 truncate max-w-[120px]">{t.topic}</span>
                                            <span className="text-xs text-zinc-500 font-mono">{formatCurrency(t.revenue)}</span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-xs text-zinc-600 italic mb-3">No visibility gaps found.</p>
                            )}
                            <p className="text-[10px] text-blue-400/80 leading-relaxed">
                                Action: Add AEO prompts for these topics in AI Visibility tab. Include them in llms.txt.
                            </p>
                        </div>

                        {/* Competitor Displacement Risk */}
                        <div className="bg-[#1a1a1a] p-5 rounded-sm border border-orange-500/20">
                            <div className="flex items-center gap-3 mb-3">
                                <div className="p-2 bg-orange-500/10 rounded">
                                    <ChartIcon className="text-orange-400" size={18} />
                                </div>
                                <h3 className="font-semibold text-white text-sm">Competitor Risk</h3>
                            </div>
                            <p className="text-xs text-zinc-500 mb-3">Topics where competitors outmention you</p>
                            {highRisk.length > 0 ? (
                                <div className="space-y-1.5 mb-3">
                                    {highRisk.map(t => (
                                        <div key={t.topic} className="flex justify-between items-center px-2 py-1.5 bg-orange-500/5 rounded border border-orange-500/10">
                                            <span className="text-xs text-orange-300 truncate max-w-[120px]">{t.topic}</span>
                                            <span className="text-xs text-red-400 font-mono">{t.competitor_mentions} rival</span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-xs text-zinc-600 italic mb-3">No high displacement risk topics.</p>
                            )}
                            <p className="text-[10px] text-orange-400/80 leading-relaxed">
                                Action: Run more visibility checks. Build stronger AEO chunks for these transmission types.
                            </p>
                        </div>
                    </div>
                );
            })()}
        </div>
    );
};
