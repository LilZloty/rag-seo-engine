'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { formatDate, formatDateTime } from '@/app/lib/dates';
import {
    ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    BarChart, Bar, Cell, LabelList,
    LineChart, Line,
} from 'recharts';
import { productAPI, snapshotAPI, Product } from '../../../lib/api';

// ─────────────────────────────────────────────
// TYPES
// ─────────────────────────────────────────────

interface SnapshotFields {
    snapshot_date?: string | null;
    seo_score: number | null;
    gsc_position: number | null;
    gsc_impressions: number | null;
    gsc_clicks: number | null;
    gsc_ctr: number | null;
    ga4_sessions: number | null;
    sold_30d: number | null;
    revenue_30d: number | null;
    sold_90d?: number | null;
    revenue_90d?: number | null;
    sold_365d?: number | null;
    revenue_365d?: number | null;
    // Shopify state fields (only present on before/after, not current)
    price?: string | null;
    inventory_quantity?: number | null;
    image_count?: number | null;
    description_length?: number | null;
}

interface OverlapChange {
    type: 'price' | 'inventory' | 'images';
    before: number | null;
    after: number | null;
    pct_change: number | null;
}

interface OptimizedProduct {
    product_id: string;
    title: string;
    handle: string | null;
    product_type: string | null;
    optimized_at: string | null;
    generation_count: number;
    llm_used: string | null;
    verdict: 'positive' | 'negative' | 'mixed' | 'neutral' | 'pending' | 'no_baseline' | 'tracked_only' | 'inconclusive';
    baseline_source: 'pre_edit' | 'post_edit' | null;
    days_until_verdict: number;
    real_impact_score: number | null;
    sales_flag: 'converting' | 'dropping' | null;
    overlaps: OverlapChange[];
    current: SnapshotFields;
    before: SnapshotFields | null;
    after: SnapshotFields | null;
    deltas: {
        seo_score: number;
        gsc_position: number;
        gsc_impressions: number;
        gsc_clicks: number;
        gsc_ctr: number;
        ga4_sessions: number;
        sold_30d: number;
        revenue_30d: number;
        gsc_impressions_pct: number | null;
        gsc_clicks_pct: number | null;
        ga4_sessions_pct: number | null;
        revenue_30d_pct: number | null;
        sold_30d_pct: number | null;
    } | null;
}

interface VerdictSummary {
    positive: number;
    negative: number;
    mixed: number;
    neutral: number;
    pending: number;
    no_baseline: number;
    tracked_only: number;
    inconclusive: number;
}

interface FreshnessData {
    last_analytics_sync: string | null;
    last_snapshot_at: string | null;
    last_snapshot_count: number;
    hours_since_sync: number | null;
    hours_since_snapshot: number | null;
    status: 'fresh' | 'stale' | 'very_stale';
}

interface SnapshotData {
    id: string;
    date: string | null;
    seo_score: number | null;
    performance_score: number | null;
    gsc_impressions: number | null;
    gsc_clicks: number | null;
    gsc_ctr: number | null;
    gsc_position: number | null;
    gsc_top_queries: Array<{ query: string; clicks?: number; impressions?: number; ctr?: number; position?: number }> | null;
    ga4_sessions: number | null;
    ga4_bounce_rate: number | null;
    ga4_revenue: number | null;
    sold_30d: number | null;
    revenue_30d: number | null;
    sold_90d: number | null;
    revenue_90d: number | null;
    sold_365d: number | null;
    revenue_365d: number | null;
    ai_visibility_score: number | null;
}

interface HistoryEvent {
    id: string;
    status: string;
    h1_title: string | null;
    meta_title: string | null;
    // What Google actually sees in the SERP: custom meta_title OR the H1 fallback.
    // meta_title_inherited=true means the custom metafield was empty and Shopify
    // was using the product title — that's what we need to compare for real diffs.
    effective_meta_title: string | null;
    meta_title_inherited: boolean;
    meta_description: string | null;
    url_handle: string | null;
    llm_used: string | null;
    generated_at: string | null;
}

// ─────────────────────────────────────────────
// CONSTANTS
// ─────────────────────────────────────────────

const GOLD = '#F7B500';
const GOLD_DIM = 'rgba(247, 181, 0, 0.15)';
const BG_CARD = '#111111';
const BG_SURFACE = '#0a0a0a';
const BORDER = '#222222';
const TEXT_DIM = '#666666';
const TEXT_MID = '#999999';
const GREEN = '#22c55e';
const RED = '#ef4444';
const AMBER = '#f59e0b';

const HISTOGRAM_COLORS = ['#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e'];
const HISTOGRAM_BINS = ['0–20', '20–40', '40–60', '60–80', '80–100'];

// ─────────────────────────────────────────────
// QUICK WINS CLASSIFICATION
// ─────────────────────────────────────────────
//
// A "quick win" is a product where a small SEO investment is likely to yield
// disproportionate traffic. The criteria combine four signals:
//
//   1. Visibility — must have demonstrable impressions (Google sees it)
//   2. Movable position — too high (top 5) is hard to improve, too low (>30) is hard to rescue
//   3. Room to improve — current SEO score must be below ceiling
//   4. Tier — based on the strength of the signals
//
// Tiers:
//   gold   = best opportunities. High impressions, page-1 rank, weak content.
//            Fix the meta + title and watch traffic jump.
//   silver = solid opportunities. Decent impressions, page-1 or just below.
//   bronze = worth investigating. Smaller signal but still has potential.
//   null   = not an opportunity (no visibility, already optimized, or unrescuable).

type OpportunityTier = 'gold' | 'silver' | 'bronze' | null;

const TIER_COLORS: Record<NonNullable<OpportunityTier>, string> = {
    gold: '#F7B500',     // brand amarillo
    silver: '#94a3b8',   // neutral gray
    bronze: '#b45309',   // burnt orange
};

function classifyOpportunity(p: {
    gsc_impressions?: number | null;
    gsc_position?: number | null;
    seo_score?: number | null;
}): OpportunityTier {
    const impr = p.gsc_impressions || 0;
    const pos = p.gsc_position || 0;
    const seo = p.seo_score || 0;

    // 1. Must have demonstrated visibility
    if (impr < 30) return null;

    // 2. Movable position window (between top 5 and rank 30)
    //    pos === 0 means "no position data" — skip
    if (pos === 0 || pos < 5 || pos > 30) return null;

    // 3. Room to improve (SEO score below 60)
    if (seo >= 60) return null;

    // 4. Tier
    if (impr >= 200 && pos <= 15 && seo < 40) return 'gold';
    if (impr >= 100 && pos <= 20 && seo < 50) return 'silver';
    return 'bronze';
}

const DAYS_OPTIONS = [
    { value: 7, label: '7d' },
    { value: 30, label: '30d' },
    { value: 90, label: '90d' },
    { value: 365, label: '1y' },
    { value: 3650, label: 'All' },
];

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────

const fmtNum = (n: number | null | undefined) =>
    n == null ? '—' : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n.toString();

const fmtDelta = (n: number | null | undefined, invert = false) => {
    if (n == null) return { text: '—', color: TEXT_DIM, arrow: '' };
    if (n === 0) return { text: '0', color: TEXT_MID, arrow: '→' };
    const positive = invert ? n < 0 : n > 0;
    const absVal = Math.abs(n);
    const display = Number.isInteger(absVal) ? absVal.toString() : absVal.toFixed(1);
    return {
        text: positive ? `+${display}` : `-${display}`,
        color: positive ? GREEN : RED,
        arrow: positive ? '↑' : '↓',
    };
};

// Percent delta — the primary language of the card. Traffic is a ratio game:
// "-30%" tells a clearer story than "-1,338 impressions."
const fmtPct = (n: number | null | undefined, invert = false) => {
    if (n == null) return { text: '—', color: TEXT_DIM, arrow: '' };
    if (n === 0) return { text: '0%', color: TEXT_MID, arrow: '→' };
    const positive = invert ? n < 0 : n > 0;
    const absVal = Math.abs(n);
    const display = absVal >= 100 ? absVal.toFixed(0) : absVal.toFixed(1);
    return {
        text: positive ? `+${display}%` : `-${display}%`,
        color: positive ? GREEN : RED,
        arrow: positive ? '↑' : '↓',
    };
};

// Color bucket for the Real Impact hero badge
const impactColor = (score: number | null | undefined) => {
    if (score == null) return TEXT_DIM;
    if (score >= 15) return GREEN;
    if (score >= 5) return '#84cc16';     // lime — modest positive
    if (score <= -20) return RED;
    if (score <= -5) return '#f97316';    // orange — modest regression
    return TEXT_MID;
};

const impactLabel = (score: number | null | undefined) => {
    if (score == null) return '—';
    if (score >= 15) return 'STRONG WIN';
    if (score >= 5) return 'MODEST WIN';
    if (score <= -20) return 'REGRESSION';
    if (score <= -5) return 'DROP';
    if (Math.abs(score) < 2) return 'NO CHANGE';
    return 'MIXED';
};

// ─────────────────────────────────────────────
// TRIAGE CLASSIFIER
// ─────────────────────────────────────────────
//
// Groups regressions into actionable buckets so a human can decide what to
// actually rollback. All logic is deterministic and explainable — the "reason"
// string on the card should always point to the signal that drove the tier.
//
// Tiers:
//   rollback      → clear loss, high confidence, safe to restore
//   medium        → traffic dropped but mixed signals — review first
//   paradox       → traffic dropped but revenue / position improved — DO NOT rollback
//   too_early     → recent edit, Google still indexing — wait
//   no_action     → nothing regressed (positive / neutral verdicts)

type TriageTier = 'rollback' | 'recovering' | 'medium' | 'paradox' | 'too_early' | 'no_action';

interface TriageResult {
    tier: TriageTier;
    reason: string;
}

const DAY = 1000 * 60 * 60 * 24;

function triage(p: OptimizedProduct): TriageResult {
    const d = p.deltas;
    // No deltas, still pending, or soft-baseline → can't judge
    if (!d || p.verdict === 'pending' || p.verdict === 'no_baseline') {
        return { tier: 'no_action', reason: 'No baseline yet — waiting for the verdict window to elapse.' };
    }
    if (p.verdict === 'positive' || p.verdict === 'neutral') {
        return { tier: 'no_action', reason: 'Not a regression.' };
    }

    const imprPct = d.gsc_impressions_pct ?? 0;
    const clicksPct = d.gsc_clicks_pct ?? d.ga4_sessions_pct ?? 0;
    const posDelta = d.gsc_position ?? 0;             // positive = worse rank
    const revPct = d.revenue_30d_pct;                 // null when no revenue to compare
    const revBefore = p.before?.revenue_30d ?? 0;
    const revAfter = p.after?.revenue_30d ?? 0;

    // Edit recency — anything <14d might just be re-indexing lag
    const ageDays = p.optimized_at ? (Date.now() - new Date(p.optimized_at).getTime()) / DAY : 999;
    const bothZeroImpressions = (p.before?.gsc_impressions ?? 0) === 0 && (p.after?.gsc_impressions ?? 0) === 0;

    // ── TOO EARLY: recent edit OR re-indexing window ──
    if (ageDays < 14 || bothZeroImpressions) {
        return {
            tier: 'too_early',
            reason: bothZeroImpressions
                ? 'Zero impressions before and after — Google may not have re-indexed yet. Give it 4+ weeks.'
                : `Edit is only ${Math.round(ageDays)}d old — Google re-indexes over 2-6 weeks. Check back later.`,
        };
    }

    // ── RECOVERING: current state clearly better than post-edit bottom ──
    // The before/after deltas use the FIRST meaningful post-edit snapshot, which
    // usually captures the crash floor — not the current trajectory. If the live
    // product is climbing back from that bottom, we should not flag it for
    // rollback even though the "delta" metric looks awful. This overrides the
    // rollback rules below for trajectory wins.
    const curImpr = p.current.gsc_impressions ?? 0;
    const curPos = p.current.gsc_position ?? 0;
    const curRev = p.current.revenue_30d ?? 0;
    const aftImpr = p.after?.gsc_impressions ?? 0;
    const aftPos = p.after?.gsc_position ?? 0;
    const aftRev = p.after?.revenue_30d ?? 0;

    // Traffic climbing at least 30% above the post-edit bottom, meaningful volume
    const trafficRecovering = aftImpr > 0 && curImpr > 10 && curImpr >= aftImpr * 1.3;
    // Position clearly better than the bottom (lower = better)
    const positionRecovering = aftPos > 0 && curPos > 0 && curPos < aftPos - 0.3;
    // Revenue climbing at least 50% above the post-edit bottom (or emerged from zero)
    const revenueRecovering = (aftRev > 0 && curRev > aftRev * 1.5) || (aftRev === 0 && curRev >= 100);

    // Need at least 2 of 3 positive signals to call it recovery (avoid false
    // positives from single-metric blips)
    const signals = [trafficRecovering, positionRecovering, revenueRecovering].filter(Boolean).length;
    if (signals >= 2) {
        const parts: string[] = [];
        if (trafficRecovering) parts.push(`impressions climbing ${aftImpr}→${curImpr} (+${Math.round((curImpr / aftImpr - 1) * 100)}%)`);
        if (positionRecovering) parts.push(`position ${aftPos.toFixed(1)}→${curPos.toFixed(1)}`);
        if (revenueRecovering && aftRev > 0) parts.push(`revenue +${Math.round((curRev / aftRev - 1) * 100)}%`);
        else if (revenueRecovering && aftRev === 0) parts.push(`revenue emerged ($0→$${Math.round(curRev)})`);
        return {
            tier: 'recovering',
            reason: `Climbing back from the post-edit crash — ${parts.join(' · ')}. Do NOT rollback; the edit is working its way through Google's re-index.`,
        };
    }

    // ── PARADOX: traffic down BUT something else materially improved ──
    // Revenue genuinely up >10% (not just noise) is the clearest hidden win
    if (revPct != null && revPct >= 10 && revBefore >= 100) {
        return {
            tier: 'paradox',
            reason: `Traffic collapsed but revenue is UP ${revPct.toFixed(0)}% ($${Math.round(revBefore)} → $${Math.round(revAfter)}). Google likely consolidated the query surface to higher-intent traffic. Do NOT rollback.`,
        };
    }
    // Big position improvement (≥3 positions better) — means the edit moved the
    // product into a more specific/relevant bucket. Rollback would undo this gain.
    if (posDelta <= -3 && imprPct <= -50) {
        return {
            tier: 'paradox',
            reason: `Position improved by ${Math.abs(posDelta).toFixed(1)} ranks despite traffic drop. The edit likely narrowed the query set. Verify revenue before rolling back.`,
        };
    }

    // ── ROLLBACK: clear losses, high confidence ──
    // Revenue went from meaningful → zero
    if (revBefore >= 500 && revAfter === 0) {
        return {
            tier: 'rollback',
            reason: `Revenue went from $${Math.round(revBefore)} → $0 while traffic collapsed ${imprPct.toFixed(0)}%. No positive offset.`,
        };
    }
    // Massive impression drop + no position improvement
    if (imprPct <= -80 && posDelta > -1) {
        const revNote = revPct != null && revPct >= 0
            ? `Revenue holding (+${revPct.toFixed(0)}%), but traffic pipeline is gutted — risk compounds over time.`
            : `Revenue also dropping (${revPct != null ? revPct.toFixed(0) : '?'}%).`;
        return {
            tier: 'rollback',
            reason: `Impressions ${imprPct.toFixed(0)}%, no position gain to offset it. ${revNote}`,
        };
    }
    // Revenue dropped significantly + traffic tanked
    if (revPct != null && revPct <= -40 && imprPct <= -50) {
        return {
            tier: 'rollback',
            reason: `Both traffic (${imprPct.toFixed(0)}%) and revenue (${revPct.toFixed(0)}%) collapsed — compounding signal.`,
        };
    }

    // ── MEDIUM: drop but mixed or moderate ──
    return {
        tier: 'medium',
        reason: `Traffic down ${imprPct.toFixed(0)}%, clicks ${clicksPct.toFixed(0)}%. Review the drawer before acting — could be re-indexing or a real loss.`,
    };
}

const TRIAGE_CONFIG: Record<TriageTier, { label: string; color: string; bg: string; icon: string }> = {
    rollback:   { label: 'ROLLBACK',    color: RED,        bg: 'rgba(239,68,68,0.12)',  icon: '↶' },
    recovering: { label: 'RECOVERING',  color: GREEN,      bg: 'rgba(34,197,94,0.12)',  icon: '↗' },
    medium:     { label: 'REVIEW',      color: AMBER,      bg: 'rgba(245,158,11,0.12)', icon: '?' },
    paradox:    { label: 'HIDDEN WIN',  color: '#3b82f6',  bg: 'rgba(59,130,246,0.12)', icon: '✦' },
    too_early:  { label: 'TOO EARLY',   color: TEXT_MID,   bg: 'rgba(150,150,150,0.1)', icon: '⏳' },
    no_action:  { label: '',            color: TEXT_DIM,   bg: 'transparent',           icon: '' },
};

// One-line summary of a non-content change that happened in the verdict window
const overlapLabel = (o: OverlapChange) => {
    if (o.type === 'price') {
        const pct = o.pct_change;
        const dir = pct != null && pct > 0 ? '↑' : '↓';
        return `Price ${dir}${pct != null ? Math.abs(pct).toFixed(0) : '?'}% ($${o.before}→$${o.after})`;
    }
    if (o.type === 'inventory') {
        if (o.before != null && o.after === 0) return `Went out of stock (was ${o.before})`;
        if (o.before === 0 && o.after != null && o.after > 0) return `Restocked (now ${o.after})`;
        const pct = o.pct_change;
        return `Inventory ${pct != null && pct > 0 ? '↑' : '↓'}${pct != null ? Math.abs(pct).toFixed(0) : '?'}% (${o.before}→${o.after})`;
    }
    if (o.type === 'images') {
        return `Images ${o.before}→${o.after}`;
    }
    return o.type;
};

const timeSince = (iso: string | null) => {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const days = Math.max(0, Math.floor(diff / 86400000));
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    return `${days}d ago`;
};

// ─────────────────────────────────────────────
// CUSTOM TOOLTIP
// ─────────────────────────────────────────────

const V07Tooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    const tierColor = d.tier ? TIER_COLORS[d.tier as 'gold' | 'silver' | 'bronze'] : null;
    return (
        <div className="bg-[#111] border border-[#333] px-4 py-3 shadow-xl" style={{ fontFamily: 'Montserrat' }}>
            <p className="text-white font-semibold text-sm mb-1 truncate max-w-[240px]">{d.title || d.name || d.category}</p>
            {d.tier && tierColor && (
                <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: tierColor }}>
                    ★ {d.tier} quick win
                </p>
            )}
            {d.gsc_impressions != null && (
                <p className="text-xs" style={{ color: TEXT_MID }}>Impressions: <span className="text-white font-mono">{fmtNum(d.gsc_impressions)}</span></p>
            )}
            {d.gsc_position != null && d.gsc_position > 0 && (
                <p className="text-xs" style={{ color: TEXT_MID }}>Position: <span className="text-white font-mono">{d.gsc_position.toFixed(1)}</span></p>
            )}
            {d.seo_score != null && (
                <p className="text-xs" style={{ color: TEXT_MID }}>SEO Score: <span style={{ color: GOLD }} className="font-mono">{d.seo_score}</span></p>
            )}
            {d.revenue != null && d.revenue > 0 && (
                <p className="text-xs" style={{ color: TEXT_MID }}>Revenue: <span className="text-white font-mono">${fmtNum(d.revenue)}</span></p>
            )}
            {d.performance != null && (
                <p className="text-xs" style={{ color: TEXT_MID }}>Avg SEO: <span style={{ color: GOLD }} className="font-mono">{d.performance}</span></p>
            )}
        </div>
    );
};

// ─────────────────────────────────────────────
// PRODUCT TIMELINE DRAWER
// ─────────────────────────────────────────────

// ─────────────────────────────────────────────
// MINI TREND CHART — one metric, colored, with before/after markers
// ─────────────────────────────────────────────

function MiniTrend({
    snapshots,
    field,
    label,
    color,
    invert = false,
    format = fmtNum,
    domain,
}: {
    snapshots: SnapshotData[];
    field: keyof SnapshotData;
    label: string;
    color: string;
    invert?: boolean;
    format?: (n: number | null | undefined) => string;
    domain?: [number | 'auto', number | 'auto'];
}) {
    // Latest + first non-null values for headline delta
    const values = snapshots
        .map(s => s[field] as number | null)
        .filter(v => v != null && !isNaN(v as number)) as number[];

    if (values.length === 0) {
        return (
            <div className="px-3 py-2" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                <p className="text-[9px] uppercase tracking-wider" style={{ color: TEXT_DIM }}>{label}</p>
                <p className="text-xs mt-1" style={{ color: TEXT_DIM }}>No data</p>
            </div>
        );
    }

    const first = values[0];
    const last = values[values.length - 1];
    const pct = first === 0 ? null : ((last - first) / Math.abs(first)) * 100;
    const improved = invert ? last < first : last > first;
    const trendColor = pct == null || Math.abs(pct) < 1 ? TEXT_MID : improved ? GREEN : RED;

    return (
        <div className="px-3 py-2" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
            <div className="flex items-baseline justify-between mb-1">
                <p className="text-[9px] uppercase tracking-wider" style={{ color: TEXT_DIM }}>{label}</p>
                <span className="text-[10px] font-mono" style={{ color: trendColor }}>
                    {pct == null ? '—' : `${pct >= 0 ? '+' : ''}${pct.toFixed(0)}%`}
                </span>
            </div>
            <div className="flex items-baseline justify-between gap-2 mb-1">
                <span className="text-xs font-mono" style={{ color: TEXT_MID }}>{format(first)}</span>
                <ResponsiveContainer width="55%" height={24}>
                    <LineChart data={snapshots}>
                        <Line type="monotone" dataKey={field as string} stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                        <YAxis domain={domain || ['auto', 'auto']} hide reversed={invert} />
                        <XAxis dataKey="date" hide />
                    </LineChart>
                </ResponsiveContainer>
                <span className="text-xs font-mono font-semibold text-white">{format(last)}</span>
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────
// TOP QUERIES DIFF — gained vs lost between two snapshots
// ─────────────────────────────────────────────

function topQueriesDiff(before: SnapshotData | null | undefined, after: SnapshotData | null | undefined) {
    const b = (before?.gsc_top_queries || []).filter(q => q && q.query);
    const a = (after?.gsc_top_queries || []).filter(q => q && q.query);
    const beforeSet = new Set(b.map(q => q.query.toLowerCase()));
    const afterSet = new Set(a.map(q => q.query.toLowerCase()));
    const gained = a.filter(q => !beforeSet.has(q.query.toLowerCase())).slice(0, 5);
    const lost = b.filter(q => !afterSet.has(q.query.toLowerCase())).slice(0, 5);
    return { gained, lost };
}

// ─────────────────────────────────────────────
// TIMELINE DRAWER
// ─────────────────────────────────────────────

function TimelineDrawer({
    productId,
    productTitle,
    overlaps,
    onClose,
    onRollback,
}: {
    productId: string;
    productTitle: string;
    overlaps?: OverlapChange[];
    onClose: () => void;
    onRollback?: (historyId: string) => void;
}) {
    const [snapshots, setSnapshots] = useState<SnapshotData[]>([]);
    const [history, setHistory] = useState<HistoryEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [rollbackBusy, setRollbackBusy] = useState<string | null>(null);
    const [rollbackMsg, setRollbackMsg] = useState<{ ok: boolean; text: string } | null>(null);
    // Historical description detail — fetched on-demand when the user expands
    const [expandedHistoryId, setExpandedHistoryId] = useState<string | null>(null);
    const [historyDetail, setHistoryDetail] = useState<Record<string, { description_html: string | null; short_description: string | null; meta_description: string | null } | 'loading' | 'error'>>({});

    useEffect(() => {
        const load = async () => {
            setLoading(true);
            try {
                const [snapRes, histRes] = await Promise.all([
                    snapshotAPI.getProductSnapshots(productId, 90),
                    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1'}/products/${productId}/history?limit=20`)
                        .then(r => r.json())
                        .catch(() => ({ versions: [] })),
                ]);
                setSnapshots(snapRes.snapshots || []);
                setHistory((histRes.versions || []).map((v: any) => ({
                    id: v.id,
                    status: v.status,
                    h1_title: v.h1_title,
                    meta_title: v.meta_title,
                    effective_meta_title: v.effective_meta_title ?? (v.meta_title || v.h1_title),
                    meta_title_inherited: !!v.meta_title_inherited,
                    meta_description: v.meta_description,
                    url_handle: v.url_handle,
                    llm_used: v.llm_used,
                    generated_at: v.generated_at,
                })));
            } catch (e) {
                console.error('Timeline load error:', e);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [productId]);

    // Most recent published version vs the one before it — that's the "current" optimization diff
    const currentVersion = useMemo(
        () => history.find(h => ['published', 'approved'].includes(h.status)) || history[0] || null,
        [history]
    );
    // Previous version = the pre-edit snapshot. Our pipeline stores this as
    // status='previous' right before a publish. Fall back to older published/rollback/manual_edit
    // entries if no 'previous' row exists. The filter tolerates empty strings (old buggy rows).
    const previousVersion = useMemo(() => {
        if (!currentVersion) return null;
        const idx = history.indexOf(currentVersion);
        const rest = history.slice(idx + 1);
        const hasContent = (h: HistoryEvent) => !!(h.h1_title || h.meta_title || h.url_handle);
        // 1) Explicit pre-edit snapshot
        const prev = rest.find(h => h.status === 'previous' && hasContent(h));
        if (prev) return prev;
        // 2) Older published / rollback / manual edit with actual content
        const prior = rest.find(h => ['published', 'approved', 'rollback', 'manual_edit'].includes(h.status) && hasContent(h));
        if (prior) return prior;
        // 3) Last resort — first older entry with any content
        return rest.find(hasContent) || null;
    }, [history, currentVersion]);

    // Before/after snapshots for query diff — anchor on the publish date
    const [beforeSnap, afterSnap] = useMemo(() => {
        if (!currentVersion?.generated_at || snapshots.length === 0) return [null, null];
        const optTime = new Date(currentVersion.generated_at).getTime();
        let before: SnapshotData | null = null;
        let after: SnapshotData | null = null;
        for (const s of snapshots) {
            if (!s.date) continue;
            const t = new Date(s.date).getTime();
            if (t < optTime) before = s;
            if (t >= optTime && !after) after = s;
        }
        return [before, after];
    }, [snapshots, currentVersion]);

    const { gained: queriesGained, lost: queriesLost } = useMemo(
        () => topQueriesDiff(beforeSnap, afterSnap),
        [beforeSnap, afterSnap]
    );

    const timeline = useMemo(() => {
        const events: Array<{ date: string; type: 'snapshot' | 'generation'; data: any }> = [];
        snapshots.forEach(s => { if (s.date) events.push({ date: s.date, type: 'snapshot', data: s }); });
        history.forEach(h => { if (h.generated_at) events.push({ date: h.generated_at, type: 'generation', data: h }); });
        events.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
        return events.slice(0, 40);
    }, [snapshots, history]);

    const toggleHistoryDetail = async (historyId: string) => {
        // Collapse if already expanded
        if (expandedHistoryId === historyId) {
            setExpandedHistoryId(null);
            return;
        }
        setExpandedHistoryId(historyId);
        // Use cached detail if we've already fetched it
        if (historyDetail[historyId] && historyDetail[historyId] !== 'error') return;
        setHistoryDetail(prev => ({ ...prev, [historyId]: 'loading' }));
        try {
            const res = await fetch(
                `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1'}/products/${productId}/history/${historyId}`
            );
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const data = await res.json();
            setHistoryDetail(prev => ({
                ...prev,
                [historyId]: {
                    description_html: data.description_html || null,
                    short_description: data.short_description || null,
                    meta_description: data.meta_description || null,
                },
            }));
        } catch {
            setHistoryDetail(prev => ({ ...prev, [historyId]: 'error' }));
        }
    };

    const handleRollback = async (historyId: string) => {
        if (!confirm('Roll back to this version? This will push the old title, meta, and URL handle to Shopify. Shopify will auto-create a redirect from the current URL.')) return;
        setRollbackBusy(historyId);
        setRollbackMsg(null);
        try {
            const res = await fetch(
                `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1'}/products/${productId}/rollback/${historyId}`,
                { method: 'POST' }
            );
            if (!res.ok) throw new Error(`Status ${res.status}`);
            setRollbackMsg({ ok: true, text: '✓ Rolled back. Refreshing…' });
            onRollback?.(historyId);
            // Reload history so the new rollback entry appears
            setTimeout(() => {
                fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1'}/products/${productId}/history?limit=20`)
                    .then(r => r.json())
                    .then(h => setHistory((h.versions || []).map((v: any) => ({
                        id: v.id,
                        status: v.status,
                        h1_title: v.h1_title,
                        meta_title: v.meta_title,
                        effective_meta_title: v.effective_meta_title ?? (v.meta_title || v.h1_title),
                        meta_title_inherited: !!v.meta_title_inherited,
                        meta_description: v.meta_description,
                        url_handle: v.url_handle,
                        llm_used: v.llm_used,
                        generated_at: v.generated_at,
                    }))))
                    .catch(() => {});
            }, 1000);
        } catch (e: any) {
            setRollbackMsg({ ok: false, text: `Error: ${e.message || 'rollback failed'}` });
        } finally {
            setRollbackBusy(null);
            setTimeout(() => setRollbackMsg(null), 5000);
        }
    };

    // Escape key closes the modal
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [onClose]);

    return (
        <>
            {/* Backdrop — click anywhere outside to close. Escape key handled in onClose hook. */}
            <div
                className="fixed inset-0 bg-black/70 z-40 backdrop-blur-sm"
                onClick={onClose}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClose(); } }}
                role="presentation"
            />

            {/* Centered modal */}
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8 pointer-events-none">
                <div
                    role="dialog"
                    aria-modal="true"
                    aria-label={productTitle ? `Timeline for ${productTitle}` : "Product timeline"}
                    className="pointer-events-auto w-full max-w-[1100px] max-h-[92vh] flex flex-col shadow-2xl"
                    style={{ background: BG_SURFACE, border: `1px solid ${BORDER}` }}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between px-8 py-5" style={{ borderBottom: `1px solid ${BORDER}` }}>
                        <div className="min-w-0 flex-1 mr-4">
                            <p className="text-[10px] uppercase tracking-[0.2em] mb-1" style={{ color: GOLD }}>Product Timeline</p>
                            <h3 className="text-white font-semibold text-base truncate">{productTitle}</h3>
                        </div>
                        <button onClick={onClose} className="text-[#555] hover:text-white transition-colors p-2" title="Close (Esc)">
                            <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                {loading ? (
                    <div className="flex items-center justify-center flex-1">
                        <div className="size-5 border-2 border-[#333] border-t-[#F7B500] rounded-full animate-spin" />
                    </div>
                ) : (
                <div className="flex-1 overflow-y-auto">

                    {/* ─── MULTI-METRIC TRENDS (90d) ─── */}
                    {snapshots.length > 1 && (
                        <div className="px-8 py-5" style={{ borderBottom: `1px solid ${BORDER}` }}>
                            <p className="text-[10px] uppercase tracking-[0.2em] mb-3" style={{ color: TEXT_DIM }}>
                                Metric Trends · last 90d
                            </p>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                <MiniTrend snapshots={snapshots} field="gsc_impressions" label="Impressions" color={GREEN} />
                                <MiniTrend snapshots={snapshots} field="gsc_clicks" label="Clicks" color="#3b82f6" />
                                <MiniTrend snapshots={snapshots} field="gsc_position" label="Position" color={AMBER} invert format={v => v == null ? '—' : v.toFixed(1)} />
                                <MiniTrend snapshots={snapshots} field="revenue_30d" label="Revenue 30d" color={GOLD} format={v => v == null ? '—' : `$${fmtNum(v)}`} />
                            </div>
                            {/* SEO score trend — dim ghost line, technical-health reference */}
                            <div className="mt-2 flex items-center gap-3 px-2 py-1.5" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                                <span className="text-[9px] uppercase tracking-wider" style={{ color: TEXT_DIM }}>SEO score</span>
                                <ResponsiveContainer width={120} height={20}>
                                    <LineChart data={snapshots}>
                                        <Line type="monotone" dataKey="seo_score" stroke={TEXT_MID} strokeWidth={1} dot={false} isAnimationActive={false} />
                                        <YAxis domain={[0, 100]} hide />
                                        <XAxis dataKey="date" hide />
                                    </LineChart>
                                </ResponsiveContainer>
                                <span className="text-[10px] font-mono" style={{ color: TEXT_MID }}>
                                    {snapshots[0]?.seo_score ?? '—'} → <span className="text-white">{snapshots[snapshots.length - 1]?.seo_score ?? '—'}</span>
                                </span>
                            </div>
                        </div>
                    )}

                    {/* ─── REVENUE WINDOWS: 30d / 90d / 365d side-by-side ─── */}
                    {snapshots.length > 0 && (() => {
                        const latest = snapshots[snapshots.length - 1];
                        const first = snapshots[0];
                        const window = (lbl: string, latestVal: number | null | undefined, firstVal: number | null | undefined, units: number | null | undefined) => {
                            const pct = (firstVal && firstVal > 0 && latestVal != null)
                                ? ((latestVal - firstVal) / firstVal) * 100
                                : null;
                            const color = pct == null || Math.abs(pct) < 2 ? TEXT_MID : pct > 0 ? GREEN : RED;
                            return (
                                <div className="px-3 py-2" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                                    <p className="text-[9px] uppercase tracking-wider" style={{ color: TEXT_DIM }}>{lbl}</p>
                                    <p className="text-sm font-mono font-semibold text-white mt-0.5">${fmtNum(latestVal)}</p>
                                    <div className="flex items-baseline justify-between mt-1 text-[9px] font-mono">
                                        <span style={{ color: TEXT_DIM }}>{fmtNum(units)} units</span>
                                        {pct != null && (
                                            <span style={{ color }}>
                                                {pct >= 0 ? '+' : ''}{pct.toFixed(0)}%
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        };
                        return (
                            <div className="px-8 py-5" style={{ borderBottom: `1px solid ${BORDER}` }}>
                                <p className="text-[10px] uppercase tracking-[0.2em] mb-3" style={{ color: TEXT_DIM }}>
                                    Revenue windows · signal vs. noise
                                </p>
                                <div className="grid grid-cols-3 gap-2">
                                    {window('Revenue 30d', latest?.revenue_30d, first?.revenue_30d, latest?.sold_30d)}
                                    {window('Revenue 90d', latest?.revenue_90d, first?.revenue_90d, latest?.sold_90d)}
                                    {window('Revenue 365d', latest?.revenue_365d, first?.revenue_365d, latest?.sold_365d)}
                                </div>
                                <p className="text-[9px] mt-2" style={{ color: TEXT_DIM }}>
                                    30d is sensitive to recent changes; 90d and 365d show the real trend for slow-moving parts.
                                </p>
                            </div>
                        );
                    })()}

                    {/* ─── TITLE / URL DIFF ─── */}
                    {currentVersion && previousVersion && (
                        <div className="px-8 py-5" style={{ borderBottom: `1px solid ${BORDER}` }}>
                            <div className="flex items-center justify-between mb-3">
                                <p className="text-[10px] uppercase tracking-[0.2em]" style={{ color: TEXT_DIM }}>
                                    What changed
                                </p>
                                <button
                                    onClick={() => previousVersion.id && handleRollback(previousVersion.id)}
                                    disabled={rollbackBusy === previousVersion.id || !previousVersion.id}
                                    className="text-[10px] font-mono px-2 py-1 transition-all disabled:opacity-50"
                                    style={{ background: 'rgba(239,68,68,0.1)', color: RED, border: `1px solid rgba(239,68,68,0.3)` }}
                                    title="Restore the previous title + meta + URL to Shopify. A redirect is created automatically."
                                >
                                    {rollbackBusy === previousVersion.id ? 'Rolling back…' : '↶ Rollback to previous'}
                                </button>
                            </div>
                            {rollbackMsg && (
                                <p className="mb-2 text-[10px] font-mono px-2 py-1" style={{
                                    background: rollbackMsg.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                                    color: rollbackMsg.ok ? GREEN : RED,
                                    border: `1px solid ${rollbackMsg.ok ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                                }}>{rollbackMsg.text}</p>
                            )}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
                                <TitleDiffRow label="Title" before={previousVersion.h1_title} after={currentVersion.h1_title} />
                                <TitleDiffRow
                                    label="Meta title (what Google sees)"
                                    before={previousVersion.effective_meta_title}
                                    after={currentVersion.effective_meta_title}
                                    beforeInherited={previousVersion.meta_title_inherited}
                                    afterInherited={currentVersion.meta_title_inherited}
                                />
                                <div className="md:col-span-2">
                                    <TitleDiffRow label="URL handle" before={previousVersion.url_handle} after={currentVersion.url_handle} mono />
                                </div>
                            </div>

                            {/* ─── Expandable: full old description HTML ─── */}
                            {previousVersion.id && (
                                <div className="mt-4 pt-3" style={{ borderTop: `1px solid ${BORDER}` }}>
                                    <button
                                        onClick={() => toggleHistoryDetail(previousVersion.id!)}
                                        className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider hover:text-white transition-colors"
                                        style={{ color: TEXT_MID }}
                                    >
                                        <span>{expandedHistoryId === previousVersion.id ? '▼' : '▶'}</span>
                                        View old content (description + meta)
                                    </button>
                                    {expandedHistoryId === previousVersion.id && (() => {
                                        const detail = historyDetail[previousVersion.id!];
                                        if (detail === 'loading') {
                                            return <p className="mt-2 text-[10px]" style={{ color: TEXT_DIM }}>Loading…</p>;
                                        }
                                        if (detail === 'error' || !detail) {
                                            return <p className="mt-2 text-[10px]" style={{ color: RED }}>Failed to load historical content.</p>;
                                        }
                                        return (
                                            <div className="mt-3 space-y-3">
                                                {detail.meta_description && (
                                                    <div>
                                                        <p className="text-[9px] uppercase tracking-wider mb-1" style={{ color: TEXT_DIM }}>Meta description (prev)</p>
                                                        <p className="text-[11px] leading-snug" style={{ color: TEXT_MID }}>{detail.meta_description}</p>
                                                    </div>
                                                )}
                                                {detail.short_description && (
                                                    <div>
                                                        <p className="text-[9px] uppercase tracking-wider mb-1" style={{ color: TEXT_DIM }}>Short description (prev)</p>
                                                        <p className="text-[11px] leading-snug" style={{ color: TEXT_MID }}>{detail.short_description}</p>
                                                    </div>
                                                )}
                                                {detail.description_html ? (
                                                    <div>
                                                        <p className="text-[9px] uppercase tracking-wider mb-1" style={{ color: TEXT_DIM }}>Full description HTML (prev)</p>
                                                        <div
                                                            className="text-[11px] leading-relaxed p-3 max-h-[320px] overflow-y-auto prose prose-invert prose-sm"
                                                            style={{ background: BG_SURFACE, border: `1px solid ${BORDER}`, color: TEXT_MID }}
                                                            dangerouslySetInnerHTML={{ __html: detail.description_html }}
                                                        />
                                                    </div>
                                                ) : (
                                                    <p className="text-[10px]" style={{ color: TEXT_DIM }}>No description HTML captured in the previous version.</p>
                                                )}
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}
                        </div>
                    )}

                    {/* ─── CONCURRENT CHANGES (overlaps) ─── */}
                    {overlaps && overlaps.length > 0 && (
                        <div className="px-8 py-5" style={{ borderBottom: `1px solid ${BORDER}` }}>
                            <p className="text-[10px] uppercase tracking-[0.2em] mb-3" style={{ color: '#a855f7' }}>
                                ⚠ Concurrent changes · attribution unclear
                            </p>
                            <p className="text-[10px] mb-3" style={{ color: TEXT_MID }}>
                                These happened in the same window as the content edit. The traffic delta
                                cannot be cleanly attributed to SEO alone.
                            </p>
                            <div className="space-y-2">
                                {overlaps.map((o, i) => (
                                    <div key={o.type || `overlap-${i}`} className="flex items-center justify-between px-3 py-2" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                                        <div>
                                            <p className="text-[10px] uppercase tracking-wider" style={{ color: TEXT_DIM }}>
                                                {o.type}
                                            </p>
                                            <p className="text-xs text-white font-mono mt-0.5">
                                                {o.before ?? '—'} → {o.after ?? '—'}
                                            </p>
                                        </div>
                                        {o.pct_change != null && (
                                            <p className="text-sm font-mono font-semibold" style={{
                                                color: (o.type === 'price' ? (o.pct_change < 0 ? GREEN : RED) :
                                                       (o.pct_change > 0 ? GREEN : RED))
                                            }}>
                                                {o.pct_change >= 0 ? '+' : ''}{o.pct_change.toFixed(1)}%
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* ─── TOP QUERIES GAINED / LOST ─── */}
                    {(queriesGained.length > 0 || queriesLost.length > 0) && (
                        <div className="px-8 py-5" style={{ borderBottom: `1px solid ${BORDER}` }}>
                            <p className="text-[10px] uppercase tracking-[0.2em] mb-3" style={{ color: TEXT_DIM }}>
                                Top queries · before vs after
                            </p>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <p className="text-[10px] font-mono mb-2" style={{ color: GREEN }}>+ GAINED</p>
                                    {queriesGained.length === 0 ? (
                                        <p className="text-[10px]" style={{ color: TEXT_DIM }}>None</p>
                                    ) : queriesGained.map((q, i) => (
                                        <div key={q.query || `gained-${i}`} className="mb-1.5">
                                            <p className="text-[11px] text-white truncate">{q.query}</p>
                                            <p className="text-[9px] font-mono" style={{ color: TEXT_DIM }}>
                                                {fmtNum(q.impressions)} impr · {fmtNum(q.clicks)} clicks
                                            </p>
                                        </div>
                                    ))}
                                </div>
                                <div>
                                    <p className="text-[10px] font-mono mb-2" style={{ color: RED }}>− LOST</p>
                                    {queriesLost.length === 0 ? (
                                        <p className="text-[10px]" style={{ color: TEXT_DIM }}>None</p>
                                    ) : queriesLost.map((q, i) => (
                                        <div key={q.query || `lost-${i}`} className="mb-1.5">
                                            <p className="text-[11px] text-white truncate">{q.query}</p>
                                            <p className="text-[9px] font-mono" style={{ color: TEXT_DIM }}>
                                                {fmtNum(q.impressions)} impr · {fmtNum(q.clicks)} clicks
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ─── FULL TIMELINE ─── */}
                    <div className="px-8 py-5">
                        <p className="text-[10px] uppercase tracking-[0.2em] mb-3" style={{ color: TEXT_DIM }}>History</p>
                        {timeline.length === 0 ? (
                            <p className="text-sm" style={{ color: TEXT_DIM }}>No timeline data.</p>
                        ) : (
                            <div className="relative">
                                <div className="absolute left-[7px] top-2 bottom-2 w-px" style={{ background: BORDER }} />
                                {timeline.map((evt) => (
                                    <div key={`${evt.type}-${evt.date}`} className="relative pl-7 pb-5 last:pb-0">
                                        <div
                                            className="absolute left-0 top-1.5 size-[15px] rounded-full border-2"
                                            style={{
                                                borderColor: evt.type === 'generation' ? GOLD : '#444',
                                                background: evt.type === 'generation' ? GOLD_DIM : BG_SURFACE,
                                            }}
                                        />
                                        <p className="text-[10px] font-mono mb-1" style={{ color: TEXT_DIM }}>
                                            {formatDate(evt.date)}
                                        </p>
                                        {evt.type === 'generation' ? (
                                            <div className="p-3" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5" style={{ background: GOLD_DIM, color: GOLD }}>
                                                        {evt.data.status}
                                                    </span>
                                                    {evt.data.llm_used && (
                                                        <span className="text-[10px] font-mono" style={{ color: TEXT_MID }}>{evt.data.llm_used}</span>
                                                    )}
                                                </div>
                                                {evt.data.h1_title && (
                                                    <p className="text-xs text-white leading-snug mt-1">{evt.data.h1_title}</p>
                                                )}
                                            </div>
                                        ) : (
                                            <div className="grid grid-cols-5 gap-2 text-[10px] font-mono">
                                                <span style={{ color: TEXT_MID }}>Imp <span className="text-white">{fmtNum(evt.data.gsc_impressions)}</span></span>
                                                <span style={{ color: TEXT_MID }}>Clk <span className="text-white">{fmtNum(evt.data.gsc_clicks)}</span></span>
                                                <span style={{ color: TEXT_MID }}>Pos <span className="text-white">{evt.data.gsc_position?.toFixed(1) ?? '—'}</span></span>
                                                <span style={{ color: TEXT_MID }}>Rev <span className="text-white">${fmtNum(evt.data.revenue_30d)}</span></span>
                                                <span style={{ color: TEXT_MID }}>SEO <span className="text-white">{evt.data.seo_score ?? '—'}</span></span>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
                )}
                </div>
            </div>
        </>
    );
}

// Hoisted out of TitleDiffRow so it's a stable component reference — defining
// it inside the parent re-created it on every render.
function InheritedChip() {
    return (
        <span
            className="text-[8px] font-mono uppercase tracking-wider px-1 py-0.5 ml-1 align-middle"
            style={{ background: 'rgba(59,130,246,0.12)', color: '#3b82f6' }}
            title="No custom meta title set — Shopify falls back to the product H1 in the SERP. This IS what Google saw."
        >
            inherited
        </span>
    );
}

function TitleDiffRow({
    label,
    before,
    after,
    mono = false,
    beforeInherited = false,
    afterInherited = false,
}: {
    label: string;
    before: string | null;
    after: string | null;
    mono?: boolean;
    // When true, the value shown was inherited from the H1 (no custom metafield
    // set in Shopify). Display a small chip so the user understands the empty
    // raw metafield was actually Google-visible as the H1 fallback.
    beforeInherited?: boolean;
    afterInherited?: boolean;
}) {
    const changed = (before || '') !== (after || '');
    return (
        <div>
            <p className="text-[9px] uppercase tracking-wider mb-1" style={{ color: TEXT_DIM }}>{label}</p>
            <div className="space-y-1">
                <div className="flex gap-2">
                    <span className="text-[10px] font-mono w-10 flex-shrink-0" style={{ color: RED }}>prev</span>
                    <p className={`text-[11px] ${mono ? 'font-mono' : ''} ${changed ? 'line-through opacity-70' : ''}`} style={{ color: changed ? TEXT_MID : 'white' }}>
                        {before || <span style={{ color: TEXT_DIM }}>—</span>}
                        {beforeInherited && before && <InheritedChip />}
                    </p>
                </div>
                <div className="flex gap-2">
                    <span className="text-[10px] font-mono w-10 flex-shrink-0" style={{ color: GREEN }}>now</span>
                    <p className={`text-[11px] text-white ${mono ? 'font-mono' : ''}`}>
                        {after || <span style={{ color: TEXT_DIM }}>—</span>}
                        {afterInherited && after && <InheritedChip />}
                    </p>
                </div>
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────
// BEFORE/AFTER CARD
// ─────────────────────────────────────────────

function OptimizationCard({ product }: { product: OptimizedProduct }) {
    const d = product.deltas;
    // Traffic metrics — percent-based, the primary story
    const impr = fmtPct(d?.gsc_impressions_pct);
    // Clicks → fall back to sessions if GSC clicks is absent
    const clicksPct = d?.gsc_clicks_pct ?? d?.ga4_sessions_pct ?? null;
    const clicks = fmtPct(clicksPct);
    // Position: absolute delta (0.3 positions better), inverted so lower = green
    const pos = fmtDelta(d?.gsc_position, true);
    // Revenue is a separate signal, rendered as a percent
    const rev = fmtPct(d?.revenue_30d_pct);

    const impact = product.real_impact_score;
    const impactC = impactColor(impact);
    const triageResult = triage(product);
    const triageCfg = TRIAGE_CONFIG[triageResult.tier];

    // Border: drive visual weight off the Real Impact, not a boolean verdict.
    // A regression with impact = -54 gets a loud red border regardless of "mixed".
    const verdictBorder = impact != null ? impactC : ({
        positive: GREEN,
        negative: RED,
        mixed: AMBER,
        neutral: BORDER,
        pending: GOLD,
        no_baseline: BORDER,
        tracked_only: '#3b82f6',
    }[product.verdict] || BORDER);

    return (
        <div
            className="h-full p-5 transition-all duration-200 hover:border-[#333]"
            style={{ background: BG_CARD, borderTop: `3px solid ${verdictBorder}`, borderLeft: `1px solid ${BORDER}`, borderRight: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}` }}
        >
            {/* Product title + time */}
            <div className="mb-3">
                <p className="text-white text-sm font-semibold line-clamp-2 leading-snug">{product.title}</p>
                <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-[10px] font-mono" style={{ color: TEXT_DIM }}>{timeSince(product.optimized_at)}</span>
                    {product.llm_used && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5" style={{ background: GOLD_DIM, color: GOLD }}>
                            {product.llm_used}
                        </span>
                    )}
                </div>
            </div>

            {/* ─── TRIAGE BADGE — the "what do I do about this?" signal ─── */}
            {triageResult.tier !== 'no_action' && (
                <div
                    className="mb-3 px-2.5 py-2"
                    style={{ background: triageCfg.bg, border: `1px solid ${triageCfg.color}40` }}
                >
                    <div className="flex items-center gap-1.5 mb-1">
                        <span className="text-[11px] font-mono font-bold" style={{ color: triageCfg.color }}>
                            {triageCfg.icon} {triageCfg.label}
                        </span>
                    </div>
                    <p className="text-[10px] leading-snug" style={{ color: TEXT_MID }}>
                        {triageResult.reason}
                    </p>
                </div>
            )}

            {/* ─── HERO: Real Impact badge ─── */}
            {d && impact != null ? (
                <div
                    className="mb-4 px-3 py-2.5 flex items-baseline justify-between"
                    style={{ background: `${impactC}14`, border: `1px solid ${impactC}40` }}
                >
                    <div>
                        <p className="text-[9px] uppercase tracking-[0.15em]" style={{ color: impactC }}>Real Impact</p>
                        <p className="text-[10px] font-mono font-semibold mt-0.5" style={{ color: impactC }}>
                            {impactLabel(impact)}
                        </p>
                    </div>
                    <p className="text-2xl font-mono font-bold" style={{ color: impactC }}>
                        {impact > 0 ? '+' : ''}{impact.toFixed(0)}
                    </p>
                </div>
            ) : (
                <div className="mb-4 px-3 py-2.5" style={{ background: BG_SURFACE, border: `1px solid ${BORDER}` }}>
                    <p className="text-[9px] uppercase tracking-[0.15em]" style={{ color: TEXT_DIM }}>Real Impact</p>
                    <p className="text-xs font-mono mt-0.5" style={{ color: TEXT_MID }}>
                        <VerdictBadge verdict={product.verdict} daysUntil={product.days_until_verdict} />
                    </p>
                </div>
            )}

            {/* ─── PRIMARY ROW: Impressions + Clicks (what SEO moves) ─── */}
            {d ? (
                <>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                        <div>
                            <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: TEXT_DIM }}>Impressions</p>
                            <p className="text-lg font-mono font-bold" style={{ color: impr.color }}>
                                {impr.arrow} {impr.text}
                            </p>
                            <p className="text-[9px] font-mono" style={{ color: TEXT_DIM }}>
                                {fmtNum(product.before?.gsc_impressions)} → {fmtNum(product.after?.gsc_impressions)}
                            </p>
                        </div>
                        <div>
                            <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: TEXT_DIM }}>Clicks</p>
                            <p className="text-lg font-mono font-bold" style={{ color: clicks.color }}>
                                {clicks.arrow} {clicks.text}
                            </p>
                            <p className="text-[9px] font-mono" style={{ color: TEXT_DIM }}>
                                {fmtNum(product.before?.gsc_clicks ?? product.before?.ga4_sessions)} → {fmtNum(product.after?.gsc_clicks ?? product.after?.ga4_sessions)}
                            </p>
                        </div>
                    </div>

                    {/* ─── SECONDARY ROW: Position + Revenue ─── */}
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: TEXT_DIM }}>Position</p>
                            <p className="text-base font-mono font-semibold" style={{ color: pos.color }}>
                                {pos.arrow} {pos.text}
                            </p>
                            <p className="text-[9px] font-mono" style={{ color: TEXT_DIM }}>
                                {product.before?.gsc_position?.toFixed(1) ?? '—'} → {product.after?.gsc_position?.toFixed(1) ?? '—'}
                            </p>
                        </div>
                        <div>
                            <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: TEXT_DIM }}>Revenue 30d</p>
                            <p className="text-base font-mono font-semibold" style={{ color: rev.color }}>
                                {rev.arrow} {rev.text}
                            </p>
                            <p className="text-[9px] font-mono" style={{ color: TEXT_DIM }}>
                                ${fmtNum(product.before?.revenue_30d)} → ${fmtNum(product.after?.revenue_30d)}
                            </p>
                        </div>
                    </div>
                </>
            ) : (
                /* No deltas — show current state */
                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: TEXT_DIM }}>Impressions</p>
                        <p className="text-lg font-mono font-bold text-white">{fmtNum(product.current.gsc_impressions)}</p>
                    </div>
                    <div>
                        <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: TEXT_DIM }}>Clicks</p>
                        <p className="text-lg font-mono font-bold text-white">{fmtNum(product.current.gsc_clicks)}</p>
                    </div>
                    <div>
                        <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: TEXT_DIM }}>Position</p>
                        <p className="text-base font-mono font-semibold text-white">
                            {product.current.gsc_position ? product.current.gsc_position.toFixed(1) : '—'}
                        </p>
                    </div>
                    <div>
                        <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: TEXT_DIM }}>Revenue 30d</p>
                        <p className="text-base font-mono font-semibold text-white">
                            ${fmtNum(product.current.revenue_30d)}
                        </p>
                    </div>
                </div>
            )}

            {/* Sales flag — separate line, only shown when signal is strong */}
            {product.sales_flag === 'converting' && (
                <p className="mt-3 text-[10px] font-mono px-2 py-1" style={{ background: 'rgba(34,197,94,0.1)', color: GREEN, border: `1px solid rgba(34,197,94,0.25)` }}>
                    ✨ Traffic is converting — sales up
                </p>
            )}
            {product.sales_flag === 'dropping' && (
                <p className="mt-3 text-[10px] font-mono px-2 py-1" style={{ background: 'rgba(245,158,11,0.1)', color: AMBER, border: `1px solid rgba(245,158,11,0.25)` }}>
                    ⚠ Sales dropped — check price / stock
                </p>
            )}

            {/* Overlapping changes warning — attribution is unclear when multiple things moved */}
            {product.overlaps && product.overlaps.length > 0 && (
                <div
                    className="mt-3 px-2 py-1.5"
                    style={{ background: 'rgba(168,85,247,0.1)', border: `1px solid rgba(168,85,247,0.3)` }}
                    title="Other product changes happened in the same window as the content edit. The Real Impact cannot be cleanly attributed to SEO alone."
                >
                    <p className="text-[10px] font-mono font-semibold mb-0.5" style={{ color: '#a855f7' }}>
                        ⚠ Also changed in this window:
                    </p>
                    {product.overlaps.slice(0, 3).map((o, i) => (
                        <p key={o.type || `prod-overlap-${i}`} className="text-[10px]" style={{ color: TEXT_MID }}>
                            · {overlapLabel(o)}
                        </p>
                    ))}
                </div>
            )}

            {product.baseline_source === 'post_edit' && (
                <p className="mt-2 text-[9px]" style={{ color: TEXT_DIM }}>
                    Soft baseline (post-edit + GSC lag)
                </p>
            )}

            {/* Footer — SEO score demoted here, as a technical-health reference */}
            <div className="mt-4 pt-3 flex items-center justify-between text-[10px] font-mono" style={{ borderTop: `1px solid ${BORDER}`, color: TEXT_DIM }}>
                <span className="flex items-center gap-2">
                    <span>SEO</span>
                    {d ? (
                        <span style={{ color: fmtDelta(d.seo_score).color }}>
                            {fmtDelta(d.seo_score).arrow}{fmtDelta(d.seo_score).text}
                        </span>
                    ) : null}
                    <span className="text-white">{product.current.seo_score ?? '—'}</span>
                </span>
                <span><span className="text-white">{product.generation_count}</span> gen{product.generation_count !== 1 ? 's' : ''}</span>
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────
// FRESHNESS BADGE
// ─────────────────────────────────────────────

function FreshnessBadge({ data }: { data: FreshnessData }) {
    const colors = {
        fresh: { fg: GREEN, bg: 'rgba(34,197,94,0.1)', border: 'rgba(34,197,94,0.3)' },
        stale: { fg: AMBER, bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.3)' },
        very_stale: { fg: RED, bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.3)' },
    };
    const c = colors[data.status];

    const formatHours = (h: number | null): string => {
        if (h == null) return 'never';
        if (h < 1) return `${Math.round(h * 60)}m ago`;
        if (h < 24) return `${Math.round(h)}h ago`;
        return `${Math.round(h / 24)}d ago`;
    };

    const tooltip = [
        data.last_analytics_sync ? `GSC/GA4 sync: ${formatDateTime(data.last_analytics_sync)}` : 'Never synced',
        data.last_snapshot_at ? `Last snapshot: ${formatDateTime(data.last_snapshot_at)} (${data.last_snapshot_count} products)` : 'No snapshots yet',
        '',
        'Click "Refresh & Snapshot" to update now.',
        'Auto-refreshes daily at 06:00 (Mexico City).',
    ].join('\n');

    return (
        <span
            title={tooltip}
            className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono cursor-help"
            style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.fg }}
        >
            <span className="size-1.5 rounded-full" style={{ background: c.fg }} />
            data {formatHours(data.hours_since_sync)}
        </span>
    );
}

// ─────────────────────────────────────────────
// VERDICT BADGE
// ─────────────────────────────────────────────

function VerdictBadge({ verdict, daysUntil }: { verdict: OptimizedProduct['verdict']; daysUntil: number }) {
    const map = {
        positive: { label: 'POSITIVE', color: GREEN, bg: 'rgba(34,197,94,0.12)' },
        negative: { label: 'NEGATIVE', color: RED, bg: 'rgba(239,68,68,0.12)' },
        mixed: { label: 'MIXED', color: AMBER, bg: 'rgba(245,158,11,0.12)' },
        neutral: { label: 'NEUTRAL', color: TEXT_MID, bg: 'rgba(150,150,150,0.1)' },
        pending: { label: `PENDING ${daysUntil}d`, color: GOLD, bg: GOLD_DIM },
        no_baseline: { label: 'NO BASELINE', color: TEXT_DIM, bg: 'rgba(80,80,80,0.15)' },
        tracked_only: { label: 'TRACKED', color: '#3b82f6', bg: 'rgba(59,130,246,0.12)' },
        inconclusive: { label: 'INCONCLUSIVE', color: '#a855f7', bg: 'rgba(168,85,247,0.12)' },
    };
    const cfg = map[verdict] || map.no_baseline;
    return (
        <span
            className="px-1.5 py-0.5 text-[9px] font-mono font-semibold tracking-wider"
            style={{ background: cfg.bg, color: cfg.color }}
        >
            {cfg.label}
        </span>
    );
}

// ─────────────────────────────────────────────
// MAIN PAGE
// ─────────────────────────────────────────────

export default function SEOIntelligencePage() {
    const [days, setDays] = useState(30);
    const [products, setProducts] = useState<Product[]>([]);
    const [totalCatalog, setTotalCatalog] = useState<number>(0);
    const [optimized, setOptimized] = useState<OptimizedProduct[]>([]);
    const [verdictSummary, setVerdictSummary] = useState<VerdictSummary | null>(null);
    const [freshness, setFreshness] = useState<FreshnessData | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedProduct, setSelectedProduct] = useState<{ id: string; title: string; overlaps?: OverlapChange[] } | null>(null);
    const [refreshRunning, setRefreshRunning] = useState(false);
    const [snapshotMsg, setSnapshotMsg] = useState<{ text: string; ok: boolean } | null>(null);
    // Action popover state — { x, y, product } for the floating menu on scatter dot click
    const [actionPopover, setActionPopover] = useState<{ x: number; y: number; product: { id: string; title: string; handle: string | null } } | null>(null);

    // Refresh GSC + GA4 data and snapshot in one call (replaces "Create Snapshot")
    const handleRefreshAndSnapshot = useCallback(async () => {
        setRefreshRunning(true);
        setSnapshotMsg(null);
        try {
            const res = await snapshotAPI.refreshAndSnapshot();
            // Async (Celery) returns { task_id, status: 'queued' }; sync returns { steps: ... }
            if (res.task_id) {
                setSnapshotMsg({ text: `✓ Refresh queued (task ${res.task_id.slice(0, 8)}…). Reload in ~30s for fresh data.`, ok: true });
            } else if (res.steps) {
                const snap = res.steps.snapshot || {};
                const sync = res.steps.analytics_sync || {};
                const recalc = res.steps.seo_recalc || {};
                setSnapshotMsg({
                    text: `✓ Sync ${sync.products_updated || 0}, recalc ${recalc.updated || 0}, snap ${snap.created || 0}`,
                    ok: true,
                });
            }
            // Reload everything
            const [prodData, optData, freshData] = await Promise.all([
                productAPI.getProducts({ limit: 10000, offset: 0 }),
                snapshotAPI.getOptimizedRecently(days, 5000).catch(() => ({ days, verdict_lag_days: 7, soft_baseline_window_days: 5, total_optimized: 0, verdict_summary: { positive: 0, negative: 0, mixed: 0, neutral: 0, pending: 0, no_baseline: 0, tracked_only: 0, inconclusive: 0 }, sales_summary: { converting: 0, dropping: 0 }, products: [] })),
                snapshotAPI.getFreshness().catch(() => null),
            ]);
            setProducts(prodData.products || []);
            setTotalCatalog(prodData.total || 0);
            setOptimized(optData.products || []);
            setVerdictSummary(optData.verdict_summary || null);
            if (freshData) setFreshness(freshData);
        } catch (e: any) {
            setSnapshotMsg({ text: `Error: ${e.message || 'Failed'}`, ok: false });
        } finally {
            setRefreshRunning(false);
            setTimeout(() => setSnapshotMsg(null), 8000);
        }
    }, [days]);

    // Load data
    useEffect(() => {
        const load = async () => {
            setLoading(true);
            try {
                const [prodData, optData, freshData] = await Promise.all([
                    productAPI.getProducts({ limit: 10000, offset: 0 }),
                    snapshotAPI.getOptimizedRecently(days, 5000).catch(() => ({ days, verdict_lag_days: 7, soft_baseline_window_days: 5, total_optimized: 0, verdict_summary: { positive: 0, negative: 0, mixed: 0, neutral: 0, pending: 0, no_baseline: 0, tracked_only: 0, inconclusive: 0 }, sales_summary: { converting: 0, dropping: 0 }, products: [] })),
                    snapshotAPI.getFreshness().catch(() => null),
                ]);
                setProducts(prodData.products || []);
                setTotalCatalog(prodData.total || 0);
                setOptimized(optData.products || []);
                setVerdictSummary(optData.verdict_summary || null);
                setFreshness(freshData);
            } catch (e) {
                console.error('Load error:', e);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [days]);

    // Refresh freshness badge every 60 seconds
    useEffect(() => {
        const interval = setInterval(async () => {
            const f = await snapshotAPI.getFreshness().catch(() => null);
            if (f) setFreshness(f);
        }, 60000);
        return () => clearInterval(interval);
    }, []);

    // Close action popover on outside click / Escape
    useEffect(() => {
        if (!actionPopover) return;
        const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') setActionPopover(null); };
        const handleClick = () => setActionPopover(null);
        window.addEventListener('keydown', handleEsc);
        // Defer click handler so the click that opened the popover doesn't immediately close it
        const t = setTimeout(() => window.addEventListener('click', handleClick), 0);
        return () => {
            clearTimeout(t);
            window.removeEventListener('keydown', handleEsc);
            window.removeEventListener('click', handleClick);
        };
    }, [actionPopover]);

    // ── Before/After filters: verdict + triage + free-text search ──
    type VerdictFilter = 'all' | OptimizedProduct['verdict'];
    type TriageFilter = 'all' | TriageTier;
    const [verdictFilter, setVerdictFilter] = useState<VerdictFilter>('all');
    const [triageFilter, setTriageFilter] = useState<TriageFilter>('all');
    const [optimizedSearch, setOptimizedSearch] = useState('');

    const filteredOptimized = useMemo(() => {
        const q = optimizedSearch.trim().toLowerCase();
        return optimized.filter(p => {
            if (verdictFilter !== 'all' && p.verdict !== verdictFilter) return false;
            if (triageFilter !== 'all' && triage(p).tier !== triageFilter) return false;
            if (q && !p.title.toLowerCase().includes(q)) return false;
            return true;
        });
    }, [optimized, verdictFilter, triageFilter, optimizedSearch]);

    // Triage counts per tier — shown on the filter chips
    const triageCounts = useMemo(() => {
        const counts: Record<TriageTier, number> = { rollback: 0, recovering: 0, medium: 0, paradox: 0, too_early: 0, no_action: 0 };
        for (const p of optimized) counts[triage(p).tier]++;
        return counts;
    }, [optimized]);

    // ── Scatter: products plotted by impressions × SEO score, classified into tiers ──
    // State: tier filter for the scatter (null = show all classified opportunities)
    const [tierFilter, setTierFilter] = useState<OpportunityTier | 'all'>('all');

    const scatterData = useMemo(() => {
        const all = products
            .filter(p => (p.gsc_impressions || 0) > 0 || p.seo_score > 0)
            .map(p => ({
                id: p.id,
                title: p.title,
                handle: (p as any).handle || null,
                gsc_impressions: p.gsc_impressions || 0,
                gsc_position: p.gsc_position || 0,
                seo_score: p.seo_score,
                revenue: p.total_revenue || 0,
                tier: classifyOpportunity(p as any),
            }))
            .sort((a, b) => b.gsc_impressions - a.gsc_impressions);

        // Apply tier filter if active
        const filtered = tierFilter === 'all'
            ? all
            : all.filter(p => p.tier === tierFilter);

        return filtered.slice(0, 200);
    }, [products, tierFilter]);

    // ── Pending verdicts (Fix 7) — optimizations awaiting their 7-day verdict window ──
    const pendingVerdicts = useMemo(
        () => optimized.filter(p => p.verdict === 'pending'),
        [optimized]
    );

    // ── Histogram: SEO Score Distribution ──
    const histogramData = useMemo(() => {
        const bins = [0, 0, 0, 0, 0];
        products.forEach(p => {
            const s = p.seo_score;
            if (s < 20) bins[0]++;
            else if (s < 40) bins[1]++;
            else if (s < 60) bins[2]++;
            else if (s < 80) bins[3]++;
            else bins[4]++;
        });
        return HISTOGRAM_BINS.map((name, i) => ({ name, count: bins[i], fill: HISTOGRAM_COLORS[i] }));
    }, [products]);

    // ── Heatmap: Category Opportunity ──
    const heatmapData = useMemo(() => {
        const byType: Record<string, { seoSum: number; count: number; revenue: number }> = {};
        products.forEach(p => {
            const t = p.product_type || 'Sin tipo';
            if (!byType[t]) byType[t] = { seoSum: 0, count: 0, revenue: 0 };
            byType[t].seoSum += p.seo_score;
            byType[t].count++;
            byType[t].revenue += p.total_revenue || 0;
        });
        return Object.entries(byType)
            .map(([category, d]) => ({
                category: category.length > 22 ? category.slice(0, 22) + '…' : category,
                performance: Math.round(d.seoSum / d.count),
                revenue: Math.round(d.revenue),
                count: d.count,
            }))
            .filter(d => d.count >= 2)
            .sort((a, b) => b.revenue - a.revenue)
            .slice(0, 10);
    }, [products]);

    // Stats summary
    const avgSeo = useMemo(() => {
        if (!products.length) return 0;
        return Math.round(products.reduce((s, p) => s + p.seo_score, 0) / products.length);
    }, [products]);

    // Tiered opportunity breakdown (replaces the old single quickWinCount)
    const opportunityCounts = useMemo(() => {
        const counts = { gold: 0, silver: 0, bronze: 0, total: 0 };
        for (const p of products) {
            const tier = classifyOpportunity(p as any);
            if (tier) {
                counts[tier]++;
                counts.total++;
            }
        }
        return counts;
    }, [products]);

    const quickWinCount = opportunityCounts.total;  // legacy reference

    return (
        <div className="min-h-screen" style={{ background: BG_SURFACE }}>
            {/* ═══ HEADER ═══ */}
            <header className="px-8 py-6 flex items-center justify-between" style={{ borderBottom: `1px solid ${BORDER}` }}>
                <div className="flex items-center gap-5">
                    <Link href="/seo/dashboard" className="text-[#555] hover:text-white transition-colors">
                        <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                    </Link>
                    <div>
                        <h1 className="text-xl font-semibold text-white tracking-tight">SEO Intelligence</h1>
                        <div className="flex items-center gap-3 mt-0.5">
                            <p className="text-xs" style={{ color: TEXT_DIM }}>
                                {products.length === totalCatalog || totalCatalog === 0
                                    ? `${products.length} products analyzed`
                                    : `${products.length} of ${totalCatalog} products analyzed`}
                            </p>
                            {freshness && (
                                <FreshnessBadge data={freshness} />
                            )}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Refresh & Snapshot — replaces the old Create Snapshot + Recalculate SEO buttons */}
                    <button
                        onClick={handleRefreshAndSnapshot}
                        disabled={refreshRunning}
                        className="flex items-center gap-2 px-4 py-2 text-xs font-medium transition-all duration-200 disabled:opacity-50"
                        style={{
                            background: BG_CARD,
                            border: `1px solid ${BORDER}`,
                            color: refreshRunning ? TEXT_DIM : GOLD,
                        }}
                        title="Pulls fresh GSC + GA4 data, recalculates SEO scores, and stores a snapshot. Runs automatically every day at 06:00 — use this to refresh on demand."
                    >
                        {refreshRunning ? (
                            <div className="size-3.5 border-2 border-[#333] border-t-[#F7B500] rounded-full animate-spin" />
                        ) : (
                            <svg className="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                        )}
                        {refreshRunning ? 'Refreshing...' : 'Refresh & Snapshot'}
                    </button>

                    {/* Snapshot result toast */}
                    {snapshotMsg && (
                        <span className="text-[10px] font-mono px-2 py-1 rounded" style={{
                            background: snapshotMsg.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                            color: snapshotMsg.ok ? GREEN : RED,
                            border: `1px solid ${snapshotMsg.ok ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                        }}>
                            {snapshotMsg.text}
                        </span>
                    )}

                    {/* Days selector */}
                    <div className="flex gap-1 p-1 rounded" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                        {DAYS_OPTIONS.map(opt => (
                            <button
                                key={opt.value}
                                onClick={() => setDays(opt.value)}
                                className="px-3 py-1.5 text-xs font-mono rounded transition-all"
                                style={{
                                    background: days === opt.value ? GOLD : 'transparent',
                                    color: days === opt.value ? '#000' : TEXT_MID,
                                    fontWeight: days === opt.value ? 700 : 400,
                                }}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>
            </header>

            {loading ? (
                <div className="flex items-center justify-center h-[60vh]">
                    <div className="size-8 border-2 border-[#333] border-t-[#F7B500] rounded-full animate-spin" />
                </div>
            ) : (
                <div className="p-8 space-y-8">

                    {/* ═══ TOP STATS ROW ═══ */}
                    <div className="grid grid-cols-4 gap-4">
                        {/* Avg SEO Score */}
                        <div
                            className="p-5"
                            style={{
                                background: BG_CARD,
                                borderTop: avgSeo < 50 ? `2px solid ${GOLD}` : `1px solid ${BORDER}`,
                                borderLeft: `1px solid ${BORDER}`, borderRight: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`,
                            }}
                        >
                            <p className="text-[10px] uppercase tracking-[0.15em] mb-2" style={{ color: TEXT_DIM }}>Avg SEO Score</p>
                            <p className="text-2xl font-bold font-mono" style={{ color: avgSeo < 50 ? GOLD : 'white' }}>{avgSeo}</p>
                        </div>

                        {/* Quick Wins (tiered) */}
                        <div
                            className="p-5"
                            style={{
                                background: BG_CARD,
                                borderTop: opportunityCounts.total > 0 ? `2px solid ${GOLD}` : `1px solid ${BORDER}`,
                                borderLeft: `1px solid ${BORDER}`, borderRight: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`,
                            }}
                            title="Products with demonstrated visibility (impr ≥30) at a movable position (rank 5-30) and SEO score below 60. Tiered: gold = 200+ impr, top 15, SEO<40 / silver = 100+ impr, top 20, SEO<50 / bronze = the rest."
                        >
                            <p className="text-[10px] uppercase tracking-[0.15em] mb-2" style={{ color: TEXT_DIM }}>Quick Wins</p>
                            <p className="text-2xl font-bold font-mono" style={{ color: opportunityCounts.total > 0 ? GOLD : 'white' }}>
                                {opportunityCounts.total}
                            </p>
                            {opportunityCounts.total > 0 && (
                                <div className="mt-1 flex gap-2 text-[9px] font-mono">
                                    <span title="High impressions, top 15, SEO<40">
                                        <span style={{ color: TIER_COLORS.gold }}>{opportunityCounts.gold}</span> gold
                                    </span>
                                    <span title="Solid impressions, top 20, SEO<50">
                                        <span style={{ color: TIER_COLORS.silver }}>{opportunityCounts.silver}</span> silver
                                    </span>
                                    <span title="Worth investigating">
                                        <span style={{ color: TIER_COLORS.bronze }}>{opportunityCounts.bronze}</span> bronze
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Optimized (last Nd) */}
                        <div
                            className="p-5"
                            style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}
                        >
                            <p className="text-[10px] uppercase tracking-[0.15em] mb-2" style={{ color: TEXT_DIM }}>Optimized (last {days}d)</p>
                            <p className="text-2xl font-bold font-mono text-white">{optimized.length}</p>
                        </div>

                        {/* Total Products */}
                        <div
                            className="p-5"
                            style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}
                        >
                            <p className="text-[10px] uppercase tracking-[0.15em] mb-2" style={{ color: TEXT_DIM }}>Total Products</p>
                            <p className="text-2xl font-bold font-mono text-white">{products.length}</p>
                        </div>
                    </div>

                    {/* ═══ ROW 1: SCATTER + HISTOGRAM ═══ */}
                    <div className="grid gap-4" style={{ gridTemplateColumns: '2fr 1fr' }}>

                        {/* Quick Wins Scatter */}
                        <div className="p-6" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                            <div className="flex items-center justify-between mb-3">
                                <div>
                                    <h2 className="text-sm font-semibold text-white">Quick Wins</h2>
                                    <p className="text-[10px] mt-0.5" style={{ color: TEXT_DIM }}>
                                        Impressions × SEO score · dots colored by opportunity tier · click to act
                                    </p>
                                </div>
                                <div className="flex items-center gap-3 text-[10px]" style={{ color: TEXT_DIM }}>
                                    <span className="flex items-center gap-1" title="Top 15 rank · 200+ impr · SEO<40">
                                        <span className="size-2 rounded-full" style={{ background: TIER_COLORS.gold }} /> gold
                                    </span>
                                    <span className="flex items-center gap-1" title="Top 20 rank · 100+ impr · SEO<50">
                                        <span className="size-2 rounded-full" style={{ background: TIER_COLORS.silver }} /> silver
                                    </span>
                                    <span className="flex items-center gap-1" title="Worth investigating · rank 5-30 · SEO<60">
                                        <span className="size-2 rounded-full" style={{ background: TIER_COLORS.bronze }} /> bronze
                                    </span>
                                    <span className="flex items-center gap-1" title="Not classified as a Quick Win — outside the impression/position window or already optimized">
                                        <span className="size-2 rounded-full" style={{ background: '#374151' }} /> other
                                    </span>
                                </div>
                            </div>
                            {/* Tier filter chips */}
                            <div className="flex gap-1 mb-4">
                                {(['all', 'gold', 'silver', 'bronze'] as const).map(t => {
                                    const isActive = tierFilter === t;
                                    const count = t === 'all'
                                        ? opportunityCounts.total
                                        : opportunityCounts[t];
                                    const accentColor = t === 'all' ? GOLD : TIER_COLORS[t];
                                    return (
                                        <button
                                            key={t}
                                            onClick={() => setTierFilter(t)}
                                            className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-all"
                                            style={{
                                                background: isActive ? accentColor : 'transparent',
                                                color: isActive ? '#000' : TEXT_MID,
                                                border: `1px solid ${isActive ? accentColor : BORDER}`,
                                                fontWeight: isActive ? 700 : 400,
                                            }}
                                        >
                                            {t} <span className="ml-1 opacity-70">{count}</span>
                                        </button>
                                    );
                                })}
                            </div>
                            <ResponsiveContainer width="100%" height={340}>
                                <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
                                    <XAxis
                                        dataKey="gsc_impressions"
                                        name="Impressions"
                                        type="number"
                                        tick={{ fill: TEXT_DIM, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
                                        axisLine={{ stroke: BORDER }}
                                        tickLine={{ stroke: BORDER }}
                                        label={{ value: 'GSC Impressions', position: 'bottom', fill: TEXT_DIM, fontSize: 10, offset: 5 }}
                                    />
                                    <YAxis
                                        dataKey="seo_score"
                                        name="SEO Score"
                                        type="number"
                                        domain={[0, 100]}
                                        tick={{ fill: TEXT_DIM, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
                                        axisLine={{ stroke: BORDER }}
                                        tickLine={{ stroke: BORDER }}
                                        label={{ value: 'SEO Score', angle: -90, position: 'insideLeft', fill: TEXT_DIM, fontSize: 10 }}
                                    />
                                    <ZAxis dataKey="revenue" range={[30, 200]} />
                                    <Tooltip content={<V07Tooltip />} />
                                    <Scatter
                                        data={scatterData}
                                        cursor="pointer"
                                        onClick={(data: any, _idx: number, evt: any) => {
                                            if (!data?.id) return;
                                            // Stop the click from immediately closing the popover
                                            evt?.stopPropagation?.();
                                            const native = evt?.nativeEvent;
                                            const x = native?.clientX || 0;
                                            const y = native?.clientY || 0;
                                            setActionPopover({
                                                x,
                                                y,
                                                product: { id: data.id, title: data.title, handle: data.handle || null },
                                            });
                                        }}
                                    >
                                        {scatterData.map((entry, i) => (
                                            <Cell
                                                key={entry.id || `scatter-${i}`}
                                                fill={entry.tier ? TIER_COLORS[entry.tier] : '#374151'}
                                                fillOpacity={entry.tier ? 0.85 : 0.35}
                                            />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                            </ResponsiveContainer>

                            {/* Quadrant labels */}
                            <div className="flex justify-between mt-2 px-4 text-[9px] font-mono" style={{ color: TEXT_DIM }}>
                                <span>Low impressions, weak SEO</span>
                                <span>High impressions, weak SEO → <span style={{ color: TIER_COLORS.gold }}>gold quick wins</span></span>
                            </div>
                        </div>

                        {/* SEO Score Histogram */}
                        <div className="p-6" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                            <div className="mb-5">
                                <h2 className="text-sm font-semibold text-white">Score Distribution</h2>
                                <p className="text-[10px] mt-0.5" style={{ color: TEXT_DIM }}>
                                    Catalog health overview
                                </p>
                            </div>
                            <ResponsiveContainer width="100%" height={340}>
                                <BarChart data={histogramData} margin={{ top: 10, right: 10, bottom: 20, left: -10 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
                                    <XAxis
                                        dataKey="name"
                                        tick={{ fill: TEXT_DIM, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
                                        axisLine={{ stroke: BORDER }}
                                        tickLine={false}
                                    />
                                    <YAxis
                                        tick={{ fill: TEXT_DIM, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
                                        axisLine={{ stroke: BORDER }}
                                        tickLine={false}
                                    />
                                    <Tooltip content={<V07Tooltip />} />
                                    <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                                        {histogramData.map((entry, i) => (
                                            <Cell key={entry.name || `histo-${i}`} fill={entry.fill} fillOpacity={0.85} />
                                        ))}
                                        <LabelList dataKey="count" position="top" fill="#fff" fontSize={11} fontFamily="JetBrains Mono, monospace" />
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* ═══ PENDING VERDICTS (Fix 7) ═══ */}
                    {pendingVerdicts.length > 0 && (
                        <div className="p-5" style={{ background: BG_CARD, border: `1px solid ${BORDER}`, borderLeft: `2px solid ${GOLD}` }}>
                            <div className="flex items-center justify-between mb-3">
                                <div>
                                    <h2 className="text-sm font-semibold text-white">Awaiting Verdict</h2>
                                    <p className="text-[10px] mt-0.5" style={{ color: TEXT_DIM }}>
                                        Optimizations applied recently — verdict computes 7 days after the change
                                    </p>
                                </div>
                                <span className="text-xs font-mono px-2 py-1" style={{ background: GOLD_DIM, color: GOLD }}>
                                    {pendingVerdicts.length} pending
                                </span>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                                {pendingVerdicts.slice(0, 9).map(p => (
                                    <div
                                        key={p.product_id}
                                        role="button"
                                        tabIndex={0}
                                        aria-label={`Open timeline for ${p.title}`}
                                        className="px-3 py-2 cursor-pointer hover:bg-[#1a1a1a] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
                                        style={{ background: BG_SURFACE, border: `1px solid ${BORDER}` }}
                                        onClick={() => setSelectedProduct({ id: p.product_id, title: p.title })}
                                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedProduct({ id: p.product_id, title: p.title }); } }}
                                    >
                                        <p className="text-xs text-white truncate">{p.title}</p>
                                        <div className="flex items-center justify-between mt-1">
                                            <span className="text-[10px] font-mono" style={{ color: TEXT_DIM }}>
                                                optimized {timeSince(p.optimized_at)}
                                            </span>
                                            <span className="text-[10px] font-mono px-1.5 py-0.5" style={{ background: GOLD_DIM, color: GOLD }}>
                                                verdict in {p.days_until_verdict}d
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {pendingVerdicts.length > 9 && (
                                <p className="text-[10px] text-center mt-2" style={{ color: TEXT_DIM }}>
                                    +{pendingVerdicts.length - 9} more pending
                                </p>
                            )}
                        </div>
                    )}

                    {/* ═══ ROW 2: BEFORE/AFTER CARDS ═══ */}
                    <div>
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h2 className="text-sm font-semibold text-white">Before / After</h2>
                                <p className="text-[10px] mt-0.5" style={{ color: TEXT_DIM }}>
                                    {days >= 3650 ? 'All optimizations ever' : `Optimizations from the last ${days} days`} · anchored to each edit's timestamp
                                </p>
                            </div>
                            <span className="text-xs font-mono px-2 py-1 rounded" style={{ background: BG_CARD, border: `1px solid ${BORDER}`, color: TEXT_MID }}>
                                {filteredOptimized.length === optimized.length
                                    ? `${optimized.length} product${optimized.length !== 1 ? 's' : ''}`
                                    : `${filteredOptimized.length} of ${optimized.length}`}
                            </span>
                        </div>

                        {/* ─── Triage filter chips — "what should I do about these?" ─── */}
                        {optimized.length > 0 && (triageCounts.rollback > 0 || triageCounts.recovering > 0 || triageCounts.paradox > 0 || triageCounts.medium > 0) && (
                            <div className="flex items-center gap-2 mb-3 flex-wrap">
                                <span className="text-[10px] uppercase tracking-wider mr-1" style={{ color: TEXT_DIM }}>Triage:</span>
                                {(['all', 'rollback', 'recovering', 'medium', 'paradox', 'too_early'] as const).map(t => {
                                    if (t !== 'all' && triageCounts[t] === 0) return null;
                                    const count = t === 'all' ? optimized.length : triageCounts[t];
                                    const isActive = triageFilter === t;
                                    const cfg = t === 'all'
                                        ? { color: GOLD, label: 'ALL' }
                                        : { color: TRIAGE_CONFIG[t].color, label: TRIAGE_CONFIG[t].label };
                                    return (
                                        <button
                                            key={t}
                                            onClick={() => setTriageFilter(t)}
                                            className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-all"
                                            style={{
                                                background: isActive ? cfg.color : 'transparent',
                                                color: isActive ? '#000' : TEXT_MID,
                                                border: `1px solid ${isActive ? cfg.color : BORDER}`,
                                                fontWeight: isActive ? 700 : 400,
                                            }}
                                        >
                                            {cfg.label} <span className="ml-1 opacity-70">{count}</span>
                                        </button>
                                    );
                                })}
                            </div>
                        )}

                        {/* ─── Verdict filter chips + title search ─── */}
                        {optimized.length > 0 && (
                            <div className="flex items-center gap-3 mb-4 flex-wrap">
                                <div className="flex gap-1 flex-wrap">
                                    {(['all', 'negative', 'inconclusive', 'mixed', 'tracked_only', 'neutral', 'positive', 'pending', 'no_baseline'] as const).map(v => {
                                        const count = v === 'all' ? optimized.length : (verdictSummary?.[v] || 0);
                                        if (v !== 'all' && count === 0) return null;
                                        const isActive = verdictFilter === v;
                                        const colorMap: Record<string, string> = {
                                            all: GOLD,
                                            negative: RED,
                                            inconclusive: '#a855f7',
                                            mixed: AMBER,
                                            tracked_only: '#3b82f6',
                                            neutral: TEXT_MID,
                                            positive: GREEN,
                                            pending: GOLD,
                                            no_baseline: TEXT_DIM,
                                        };
                                        const accent = colorMap[v];
                                        return (
                                            <button
                                                key={v}
                                                onClick={() => setVerdictFilter(v)}
                                                className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-all"
                                                style={{
                                                    background: isActive ? accent : 'transparent',
                                                    color: isActive ? '#000' : TEXT_MID,
                                                    border: `1px solid ${isActive ? accent : BORDER}`,
                                                    fontWeight: isActive ? 700 : 400,
                                                }}
                                            >
                                                {v.replace('_', ' ')} <span className="ml-1 opacity-70">{count}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                                <input
                                    type="text"
                                    value={optimizedSearch}
                                    onChange={(e) => setOptimizedSearch(e.target.value)}
                                    placeholder="Search by title..."
                                    className="flex-1 min-w-[180px] max-w-[320px] px-3 py-1.5 text-xs font-mono outline-none"
                                    style={{ background: BG_CARD, border: `1px solid ${BORDER}`, color: 'white' }}
                                />
                                {(verdictFilter !== 'all' || triageFilter !== 'all' || optimizedSearch) && (
                                    <button
                                        onClick={() => { setVerdictFilter('all'); setTriageFilter('all'); setOptimizedSearch(''); }}
                                        className="text-[10px] font-mono px-2 py-1 hover:text-white transition-colors"
                                        style={{ color: TEXT_DIM }}
                                    >
                                        ✕ clear
                                    </button>
                                )}
                            </div>
                        )}

                        {optimized.length === 0 ? (
                            <div className="p-8 text-center" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                                <p className="text-sm" style={{ color: TEXT_DIM }}>
                                    No products optimized {days >= 3650 ? 'yet' : `in the last ${days} days`}.
                                </p>
                                <p className="text-[10px] mt-1" style={{ color: TEXT_DIM }}>
                                    Generate content for products and run daily snapshots to see before/after comparisons.
                                </p>
                            </div>
                        ) : filteredOptimized.length === 0 ? (
                            <div className="p-8 text-center" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                                <p className="text-sm" style={{ color: TEXT_DIM }}>
                                    No products match your filters.
                                </p>
                                <button
                                    onClick={() => { setVerdictFilter('all'); setOptimizedSearch(''); }}
                                    className="text-[10px] font-mono mt-2 underline" style={{ color: GOLD }}
                                >
                                    Clear filters
                                </button>
                            </div>
                        ) : (
                            <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                                {filteredOptimized.map(p => (
                                    <div
                                        key={p.product_id}
                                        role="button"
                                        tabIndex={0}
                                        aria-label={`Open detail for ${p.title}`}
                                        className="cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
                                        onClick={() => setSelectedProduct({ id: p.product_id, title: p.title, overlaps: p.overlaps })}
                                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedProduct({ id: p.product_id, title: p.title, overlaps: p.overlaps }); } }}
                                    >
                                        <OptimizationCard product={p} />
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* ═══ ROW 3: OPPORTUNITY HEATMAP ═══ */}
                    <div className="p-6" style={{ background: BG_CARD, border: `1px solid ${BORDER}` }}>
                        <div className="flex items-center justify-between mb-5">
                            <div>
                                <h2 className="text-sm font-semibold text-white">Opportunity by Category</h2>
                                <p className="text-[10px] mt-0.5" style={{ color: TEXT_DIM }}>
                                    Revenue vs. avg SEO score — low-score high-revenue categories need attention
                                </p>
                            </div>
                            <div className="flex items-center gap-3 text-[10px]" style={{ color: TEXT_DIM }}>
                                <span className="flex items-center gap-1">
                                    <span className="size-2 rounded-full" style={{ background: RED }} /> SEO &lt; 40
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="size-2 rounded-full" style={{ background: AMBER }} /> 40–65
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="size-2 rounded-full" style={{ background: GREEN }} /> &gt; 65
                                </span>
                            </div>
                        </div>
                        <ResponsiveContainer width="100%" height={320}>
                            <BarChart data={heatmapData} layout="vertical" margin={{ top: 0, right: 30, bottom: 0, left: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" horizontal={false} />
                                <XAxis
                                    type="number"
                                    tick={{ fill: TEXT_DIM, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
                                    axisLine={{ stroke: BORDER }}
                                    tickLine={false}
                                    tickFormatter={(v: number) => `$${fmtNum(v)}`}
                                />
                                <YAxis
                                    dataKey="category"
                                    type="category"
                                    width={160}
                                    tick={{ fill: TEXT_MID, fontSize: 11 }}
                                    axisLine={{ stroke: BORDER }}
                                    tickLine={false}
                                />
                                <Tooltip content={<V07Tooltip />} />
                                <Bar dataKey="revenue" radius={[0, 3, 3, 0]} barSize={24}>
                                    {heatmapData.map((entry, i) => (
                                        <Cell
                                            key={entry.category || `heat-${i}`}
                                            fill={entry.performance < 40 ? RED : entry.performance < 65 ? AMBER : GREEN}
                                            fillOpacity={0.8}
                                        />
                                    ))}
                                    <LabelList
                                        dataKey="performance"
                                        position="right"
                                        formatter={(v: number) => `${v} SEO`}
                                        fill={TEXT_MID}
                                        fontSize={10}
                                        fontFamily="JetBrains Mono, monospace"
                                    />
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* ═══ TIMELINE DRAWER ═══ */}
            {selectedProduct && (
                <TimelineDrawer
                    productId={selectedProduct.id}
                    productTitle={selectedProduct.title}
                    overlaps={selectedProduct.overlaps}
                    onClose={() => setSelectedProduct(null)}
                />
            )}

            {/* ═══ ACTION POPOVER (Fix 5) ═══ */}
            {actionPopover && (
                <div
                    role="dialog"
                    aria-label="Action menu"
                    className="fixed z-50 min-w-[220px] shadow-2xl"
                    style={{
                        top: Math.min(actionPopover.y + 8, window.innerHeight - 220),
                        left: Math.min(actionPopover.x + 8, window.innerWidth - 240),
                        background: BG_CARD,
                        border: `1px solid ${GOLD_DIM}`,
                    }}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                >
                    <div className="px-3 py-2" style={{ borderBottom: `1px solid ${BORDER}` }}>
                        <p className="text-[9px] uppercase tracking-wider" style={{ color: TEXT_DIM }}>Quick Action</p>
                        <p className="text-xs text-white truncate mt-0.5">{actionPopover.product.title}</p>
                    </div>
                    <div className="p-1">
                        <button
                            className="w-full text-left px-3 py-2 text-xs hover:bg-[#1a1a1a] flex items-center gap-2 transition-colors"
                            style={{ color: GOLD }}
                            onClick={() => {
                                setSelectedProduct({ id: actionPopover.product.id, title: actionPopover.product.title });
                                setActionPopover(null);
                            }}
                        >
                            <svg className="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                            </svg>
                            View Timeline
                        </button>
                        <Link
                            href={`/generate/${actionPopover.product.id}`}
                            className="w-full text-left px-3 py-2 text-xs hover:bg-[#1a1a1a] flex items-center gap-2 transition-colors"
                            style={{ color: GREEN }}
                            onClick={() => setActionPopover(null)}
                        >
                            <svg className="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                            Generate Content
                        </Link>
                        {actionPopover.product.handle && (
                            <a
                                href={`https://admin.shopify.com/store/your-store/products?query=${encodeURIComponent(actionPopover.product.handle)}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="w-full text-left px-3 py-2 text-xs hover:bg-[#1a1a1a] flex items-center gap-2 transition-colors"
                                style={{ color: TEXT_MID }}
                                onClick={() => setActionPopover(null)}
                            >
                                <svg className="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                                Open in Shopify
                            </a>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
