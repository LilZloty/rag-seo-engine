'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { formatDateTime } from '@/app/lib/dates';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

// ============ Types ============
interface TierMember {
    display_name: string;
    email: string;
    tags: string[];
    has_correct_tag: boolean;
    tier_tags: string[];
}

interface TierInfo {
    tier: string;
    tag: string;
    segment_id: string;
    total_members: number;
    with_correct_tag: number;
    missing_tag: number;
    with_wrong_tier_tag: number;
    members: TierMember[];
    error?: string;
}

interface PreviewData {
    tiers: TierInfo[];
    total_customers: number;
    total_missing_tags: number;
    fetched_at: string;
}

interface SyncChange {
    customer_gid: string;
    display_name: string;
    email: string;
    desired_tier: string;
    current_tier_tags: string[];
    tags_to_add: string[];
    tags_to_remove: string[];
    applied: boolean;
}

interface SyncResult {
    success: boolean;
    dry_run: boolean;
    started_at: string;
    completed_at: string;
    duration_seconds: number;
    segment_counts: Record<string, number>;
    total_customers_checked: number;
    tags_added: number;
    tags_removed: number;
    already_correct: number;
    changes: SyncChange[];
    errors: string[];
}

// ============ Tier Config ============
const TIER_CONFIG: Record<string, { color: string; bg: string; border: string; icon: string; gradient: string }> = {
    'Platino B2B': {
        color: '#E5E4E2',
        bg: 'rgba(229, 228, 226, 0.08)',
        border: 'rgba(229, 228, 226, 0.25)',
        icon: '💎',
        gradient: 'linear-gradient(135deg, #E5E4E2 0%, #B0B0B0 100%)',
    },
    'Oro B2B': {
        color: '#F7B500',
        bg: 'rgba(247, 181, 0, 0.08)',
        border: 'rgba(247, 181, 0, 0.25)',
        icon: '🥇',
        gradient: 'linear-gradient(135deg, #F7B500 0%, #D4A000 100%)',
    },
    'Plata B2B': {
        color: '#C0C0C0',
        bg: 'rgba(192, 192, 192, 0.08)',
        border: 'rgba(192, 192, 192, 0.25)',
        icon: '🥈',
        gradient: 'linear-gradient(135deg, #C0C0C0 0%, #A0A0A0 100%)',
    },
    'Bronce B2B': {
        color: '#CD7F32',
        bg: 'rgba(205, 127, 50, 0.08)',
        border: 'rgba(205, 127, 50, 0.25)',
        icon: '🥉',
        gradient: 'linear-gradient(135deg, #CD7F32 0%, #A0652A 100%)',
    },
};

function getTierStyle(tierName: string) {
    return TIER_CONFIG[tierName] || TIER_CONFIG['Bronce B2B'];
}


// ============ Main Page ============
export default function TierSyncPage() {
    const [preview, setPreview] = useState<PreviewData | null>(null);
    const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [activeTab, setActiveTab] = useState<'overview' | 'members' | 'sync-log'>('overview');
    const [expandedTier, setExpandedTier] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Auto-load preview on mount
    useEffect(() => {
        loadPreview();
    }, []);

    const loadPreview = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/tier-sync/preview`);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setPreview(data);
        } catch (err: any) {
            setError(err.message || 'Failed to load preview');
        } finally {
            setLoading(false);
        }
    }, []);

    const runSync = useCallback(async (dryRun: boolean) => {
        setSyncing(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/tier-sync/sync?dry_run=${dryRun}`, {
                method: 'POST',
            });
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            const data = await res.json();
            setSyncResult(data);
            setActiveTab('sync-log');
            // Reload preview if live sync
            if (!dryRun) {
                setTimeout(() => loadPreview(), 2000);
            }
        } catch (err: any) {
            setError(err.message || 'Sync failed');
        } finally {
            setSyncing(false);
        }
    }, [loadPreview]);

    // Calculate totals from preview
    const totalCustomers = preview?.total_customers || 0;
    const totalMissing = preview?.total_missing_tags || 0;
    const totalCorrect = totalCustomers - totalMissing;
    const healthPercent = totalCustomers > 0 ? Math.round((totalCorrect / totalCustomers) * 100) : 0;

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:p-8">

                {/* Page Header */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <span className="text-2xl">🏷️</span>
                            <h1 className="text-xl font-semibold text-white tracking-wide">
                                B2B Tier Sync
                            </h1>
                            <span className="px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest bg-[#f7b500]/10 text-[#f7b500] border border-[#f7b500]/20">
                                Automático
                            </span>
                        </div>
                        <p className="text-[#888888] text-sm mt-1">
                            Sincronización de tags B2B basada en segmentos de Shopify
                        </p>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={loadPreview}
                            disabled={loading}
                            className="px-4 py-2 text-sm font-medium text-[#999999] hover:text-white border border-[#2a2a2a] hover:border-[#444444] transition-all duration-200 disabled:opacity-50"
                        >
                            {loading ? '⏳' : '↻'} Actualizar
                        </button>
                        <button
                            onClick={() => runSync(true)}
                            disabled={syncing}
                            className="px-4 py-2 text-sm font-medium text-[#f7b500] border border-[#f7b500]/30 hover:bg-[#f7b500]/10 transition-all duration-200 disabled:opacity-50"
                        >
                            {syncing ? '⏳ Procesando...' : '🔍 Vista Previa (Dry Run)'}
                        </button>
                        <button
                            onClick={() => {
                                if (confirm('¿Estás seguro? Esto aplicará los tags de tier a todos los clientes B2B en Shopify.')) {
                                    runSync(false);
                                }
                            }}
                            disabled={syncing}
                            className="px-4 py-2 text-sm font-medium text-[#0a0a0a] bg-[#f7b500] hover:bg-[#ffc933] transition-all duration-200 disabled:opacity-50 font-semibold"
                        >
                            {syncing ? '⏳ Sincronizando...' : '⚡ Sincronizar Ahora'}
                        </button>
                    </div>
                </div>

                {/* Error Banner */}
                {error && (
                    <div className="mb-6 px-4 py-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                        ❌ {error}
                        <button onClick={() => setError(null)} className="ml-3 text-red-300 hover:text-white">✕</button>
                    </div>
                )}

                {/* Stats Row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[#1a1a1a] mb-8">
                    <div className="bg-[#0a0a0a] p-5">
                        <div className="text-[#666666] text-xs uppercase tracking-wider mb-2">Total Clientes</div>
                        <div className="text-2xl font-bold text-white">{totalCustomers}</div>
                        <div className="text-[#555555] text-xs mt-1">En todos los tiers</div>
                    </div>
                    <div className="bg-[#0a0a0a] p-5">
                        <div className="text-[#666666] text-xs uppercase tracking-wider mb-2">Tags Correctos</div>
                        <div className="text-2xl font-bold text-green-400">{totalCorrect}</div>
                        <div className="text-[#555555] text-xs mt-1">{healthPercent}% sincronizado</div>
                    </div>
                    <div className="bg-[#0a0a0a] p-5">
                        <div className="text-[#666666] text-xs uppercase tracking-wider mb-2">Tags Faltantes</div>
                        <div className={`text-2xl font-bold ${totalMissing > 0 ? 'text-[#f7b500]' : 'text-green-400'}`}>
                            {totalMissing}
                        </div>
                        <div className="text-[#555555] text-xs mt-1">{totalMissing > 0 ? 'Necesitan sync' : 'Todo al día'}</div>
                    </div>
                    <div className="bg-[#0a0a0a] p-5">
                        <div className="text-[#666666] text-xs uppercase tracking-wider mb-2">Salud</div>
                        <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 bg-[#2a2a2a] overflow-hidden">
                                <div
                                    className="h-full transition-all duration-700"
                                    style={{
                                        width: `${healthPercent}%`,
                                        background: healthPercent === 100 ? '#22c55e' : healthPercent > 80 ? '#f7b500' : '#ef4444',
                                    }}
                                />
                            </div>
                            <span className="text-sm font-mono text-[#999999]">{healthPercent}%</span>
                        </div>
                        {preview?.fetched_at && (
                            <div className="text-[#444444] text-xs mt-2">
                                {formatDateTime(preview.fetched_at)}
                            </div>
                        )}
                    </div>
                </div>

                {/* Tabs */}
                <div className="flex items-center gap-0 mb-6 border-b border-[#1a1a1a]">
                    {(['overview', 'members', 'sync-log'] as const).map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`px-5 py-3 text-sm font-medium transition-all duration-200 border-b-2 -mb-px
                ${activeTab === tab
                                    ? 'text-[#f7b500] border-[#f7b500]'
                                    : 'text-[#666666] border-transparent hover:text-white hover:border-[#333333]'
                                }`}
                        >
                            {tab === 'overview' && '📊 Vista General'}
                            {tab === 'members' && '👥 Miembros'}
                            {tab === 'sync-log' && `🔄 Log de Sync${syncResult ? ` (${syncResult.changes.length})` : ''}`}
                        </button>
                    ))}
                </div>

                {/* Loading State */}
                {loading && !preview && (
                    <div className="py-20 text-center">
                        <div className="inline-block animate-spin size-8 border-2 border-[#f7b500] border-t-transparent rounded-full mb-4" />
                        <p className="text-[#888888] text-sm">Cargando datos de Shopify…</p>
                    </div>
                )}

                {/* Tab: Overview */}
                {activeTab === 'overview' && preview && (
                    <div className="space-y-4">
                        {preview.tiers.map((tier) => {
                            const style = getTierStyle(tier.tier);
                            const pct = tier.total_members > 0
                                ? Math.round((tier.with_correct_tag / tier.total_members) * 100)
                                : 0;

                            return (
                                <div
                                    key={tier.tier}
                                    className="border transition-all duration-200 hover:border-opacity-50"
                                    style={{
                                        borderColor: style.border,
                                        background: style.bg,
                                    }}
                                >
                                    <div className="p-5">
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="flex items-center gap-3">
                                                <span className="text-2xl">{style.icon}</span>
                                                <div>
                                                    <h3 className="text-base font-semibold" style={{ color: style.color }}>
                                                        {tier.tier}
                                                    </h3>
                                                    <span className="text-xs text-[#666666] font-mono">{tier.tag}</span>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <div className="text-2xl font-bold" style={{ color: style.color }}>
                                                    {tier.total_members}
                                                </div>
                                                <div className="text-xs text-[#666666]">miembros</div>
                                            </div>
                                        </div>

                                        {/* Tag Status Bar */}
                                        <div className="flex items-center gap-3">
                                            <div className="flex-1 h-1.5 bg-[#2a2a2a] overflow-hidden">
                                                <div
                                                    className="h-full transition-all duration-700"
                                                    style={{
                                                        width: `${pct}%`,
                                                        background: style.gradient,
                                                    }}
                                                />
                                            </div>
                                            <span className="text-xs font-mono text-[#888888] w-10 text-right">{pct}%</span>
                                        </div>

                                        {/* Stats Row */}
                                        <div className="flex items-center gap-6 mt-3 text-xs">
                                            <span className="text-green-400">✓ {tier.with_correct_tag} con tag</span>
                                            <span className={tier.missing_tag > 0 ? 'text-[#f7b500]' : 'text-[#555555]'}>
                                                ○ {tier.missing_tag} sin tag
                                            </span>
                                            {tier.with_wrong_tier_tag > 0 && (
                                                <span className="text-red-400">⚠ {tier.with_wrong_tier_tag} tag incorrecto</span>
                                            )}
                                            {tier.error && (
                                                <span className="text-red-400">❌ Error: {tier.error}</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Tab: Members */}
                {activeTab === 'members' && preview && (
                    <div className="space-y-4">
                        {preview.tiers.map((tier) => {
                            const style = getTierStyle(tier.tier);
                            const isExpanded = expandedTier === tier.tier;

                            return (
                                <div key={tier.tier} className="border" style={{ borderColor: style.border }}>
                                    <button
                                        onClick={() => setExpandedTier(isExpanded ? null : tier.tier)}
                                        className="w-full px-5 py-4 flex items-center justify-between text-left"
                                        style={{ background: style.bg }}
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="text-lg">{style.icon}</span>
                                            <span className="font-medium" style={{ color: style.color }}>{tier.tier}</span>
                                            <span className="text-xs text-[#666666]">({tier.total_members} miembros)</span>
                                        </div>
                                        <span className={`text-lg text-[#666666] transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
                                            ▾
                                        </span>
                                    </button>

                                    {isExpanded && (
                                        <div className="border-t" style={{ borderColor: style.border }}>
                                            {/* Table Header */}
                                            <div className="grid grid-cols-12 gap-2 px-5 py-2 text-xs text-[#666666] uppercase tracking-wider bg-[#0d0d0d]">
                                                <div className="col-span-3">Cliente</div>
                                                <div className="col-span-3">Email</div>
                                                <div className="col-span-3">Tags B2B</div>
                                                <div className="col-span-3">Estado</div>
                                            </div>

                                            {/* Members */}
                                            <div className="max-h-96 overflow-y-auto">
                                                {tier.members.length === 0 ? (
                                                    <div className="px-5 py-8 text-center text-[#555555] text-sm">
                                                        Sin miembros en este segmento
                                                    </div>
                                                ) : (
                                                    tier.members.map((member, idx) => (
                                                        <div
                                                            key={member.email || `member-${idx}`}
                                                            className="grid grid-cols-12 gap-2 px-5 py-3 text-sm border-t border-[#1a1a1a] hover:bg-[#111111] transition-colors"
                                                        >
                                                            <div className="col-span-3 text-white truncate">{member.display_name || '—'}</div>
                                                            <div className="col-span-3 text-[#888888] truncate font-mono text-xs pt-0.5">
                                                                {member.email || '—'}
                                                            </div>
                                                            <div className="col-span-3 flex flex-wrap gap-1">
                                                                {member.tier_tags.length > 0 ? (
                                                                    member.tier_tags.map((t) => {
                                                                        const tagStyle = getTierStyle(t);
                                                                        return (
                                                                            <span
                                                                                key={t}
                                                                                className="px-2 py-0.5 text-xs border"
                                                                                style={{
                                                                                    color: tagStyle.color,
                                                                                    borderColor: tagStyle.border,
                                                                                    background: tagStyle.bg,
                                                                                }}
                                                                            >
                                                                                {t}
                                                                            </span>
                                                                        );
                                                                    })
                                                                ) : (
                                                                    <span className="text-xs text-[#555555]">Sin tags B2B</span>
                                                                )}
                                                            </div>
                                                            <div className="col-span-3">
                                                                {member.has_correct_tag ? (
                                                                    <span className="text-green-400 text-xs">✓ Correcto</span>
                                                                ) : (
                                                                    <span className="text-[#f7b500] text-xs">○ Falta tag</span>
                                                                )}
                                                            </div>
                                                        </div>
                                                    ))
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Tab: Sync Log */}
                {activeTab === 'sync-log' && (
                    <div>
                        {syncResult ? (
                            <div className="space-y-6">
                                {/* Sync Summary */}
                                <div className="border border-[#2a2a2a] p-5">
                                    <div className="flex items-center justify-between mb-4">
                                        <div className="flex items-center gap-3">
                                            <span className="text-xl">{syncResult.dry_run ? '🔍' : '✅'}</span>
                                            <div>
                                                <h3 className="text-base font-semibold text-white">
                                                    {syncResult.dry_run ? 'Vista Previa (Dry Run)' : 'Sincronización Completada'}
                                                </h3>
                                                <span className="text-xs text-[#666666]">
                                                    {syncResult.duration_seconds}s · {formatDateTime(syncResult.completed_at)}
                                                </span>
                                            </div>
                                        </div>
                                        <span className={`px-2 py-1 text-xs font-medium ${syncResult.success ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'
                                            }`}>
                                            {syncResult.success ? 'EXITOSO' : 'CON ERRORES'}
                                        </span>
                                    </div>

                                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                                        <div>
                                            <div className="text-lg font-bold text-white">{syncResult.total_customers_checked}</div>
                                            <div className="text-xs text-[#666666]">Revisados</div>
                                        </div>
                                        <div>
                                            <div className="text-lg font-bold text-green-400">{syncResult.already_correct}</div>
                                            <div className="text-xs text-[#666666]">Ya correctos</div>
                                        </div>
                                        <div>
                                            <div className="text-lg font-bold text-[#f7b500]">{syncResult.tags_added}</div>
                                            <div className="text-xs text-[#666666]">Tags {syncResult.dry_run ? 'a agregar' : 'agregados'}</div>
                                        </div>
                                        <div>
                                            <div className="text-lg font-bold text-red-400">{syncResult.tags_removed}</div>
                                            <div className="text-xs text-[#666666]">Tags {syncResult.dry_run ? 'a remover' : 'removidos'}</div>
                                        </div>
                                        <div>
                                            <div className="text-lg font-bold text-red-400">{syncResult.errors.length}</div>
                                            <div className="text-xs text-[#666666]">Errores</div>
                                        </div>
                                    </div>

                                    {/* Segment Breakdown */}
                                    <div className="mt-4 pt-4 border-t border-[#1a1a1a] flex flex-wrap gap-4">
                                        {Object.entries(syncResult.segment_counts).map(([tier, count]) => {
                                            const style = getTierStyle(tier);
                                            return (
                                                <div key={tier} className="flex items-center gap-2">
                                                    <span className="text-sm">{style.icon}</span>
                                                    <span className="text-xs" style={{ color: style.color }}>{tier}:</span>
                                                    <span className="text-xs text-white font-medium">{count}</span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>

                                {/* Errors */}
                                {syncResult.errors.length > 0 && (
                                    <div className="border border-red-500/30 bg-red-500/5 p-4">
                                        <h4 className="text-sm font-medium text-red-400 mb-2">Errores</h4>
                                        {syncResult.errors.map((err, i) => (
                                            <div key={typeof err === 'string' ? err : `err-${i}`} className="text-xs text-red-300 py-1">❌ {err}</div>
                                        ))}
                                    </div>
                                )}

                                {/* Changes List */}
                                {syncResult.changes.length > 0 && (
                                    <div className="border border-[#2a2a2a]">
                                        <div className="px-5 py-3 bg-[#0d0d0d] border-b border-[#1a1a1a]">
                                            <h4 className="text-sm font-medium text-[#888888]">
                                                Cambios {syncResult.dry_run ? 'Planificados' : 'Aplicados'} ({syncResult.changes.length})
                                            </h4>
                                        </div>
                                        <div className="max-h-96 overflow-y-auto">
                                            {syncResult.changes.map((change, idx) => {
                                                const style = getTierStyle(change.desired_tier);
                                                return (
                                                    <div
                                                        key={change.email || `change-${idx}`}
                                                        className="px-5 py-3 border-b border-[#1a1a1a] last:border-0 hover:bg-[#111111] transition-colors"
                                                    >
                                                        <div className="flex items-center justify-between">
                                                            <div className="flex items-center gap-3">
                                                                <span className="text-sm">{style.icon}</span>
                                                                <div>
                                                                    <span className="text-sm text-white font-medium">{change.display_name}</span>
                                                                    <span className="text-xs text-[#666666] ml-2">{change.email}</span>
                                                                </div>
                                                            </div>
                                                            <div className="flex items-center gap-2">
                                                                {change.tags_to_remove.map((t) => (
                                                                    <span key={t} className="px-2 py-0.5 text-xs bg-red-500/10 text-red-400 border border-red-500/20 line-through">
                                                                        {t}
                                                                    </span>
                                                                ))}
                                                                {change.tags_to_add.length > 0 && change.tags_to_remove.length > 0 && (
                                                                    <span className="text-[#555555]">→</span>
                                                                )}
                                                                {change.tags_to_add.map((t) => {
                                                                    const addStyle = getTierStyle(t);
                                                                    return (
                                                                        <span
                                                                            key={t}
                                                                            className="px-2 py-0.5 text-xs border"
                                                                            style={{
                                                                                color: addStyle.color,
                                                                                borderColor: addStyle.border,
                                                                                background: addStyle.bg,
                                                                            }}
                                                                        >
                                                                            + {t}
                                                                        </span>
                                                                    );
                                                                })}
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}

                                {syncResult.changes.length === 0 && (
                                    <div className="py-12 text-center border border-[#2a2a2a]">
                                        <span className="text-4xl mb-4 block">✅</span>
                                        <p className="text-[#888888] text-sm">Todos los clientes ya tienen el tag correcto</p>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="py-20 text-center border border-[#1a1a1a]">
                                <span className="text-4xl mb-4 block">🔄</span>
                                <p className="text-[#888888] text-sm mb-4">No se ha ejecutado ninguna sincronización aún</p>
                                <p className="text-[#555555] text-xs">
                                    Usa &quot;Vista Previa&quot; para ver los cambios planificados, o &quot;Sincronizar Ahora&quot; para aplicarlos
                                </p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
