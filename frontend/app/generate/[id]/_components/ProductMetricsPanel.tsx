'use client';

import { useEffect, useState } from 'react';
import { formatDate } from '@/app/lib/dates';
import type { Product, ShopifyProductDetails } from '@/lib/api';
import {
    analyzeSEOContent,
    analyzeImages,
    analyzeAEOContent,
    analyzeGEOContent,
} from '../_helpers/analyze';

export interface ProductMetricsPanelTheme {
    bg: string;
    cardBg: string;
    text: string;
    textSecondary: string;
    textMuted: string;
    border: string;
    inputBg: string;
}

interface ProductMetricsPanelProps {
    product: Product;
    shopifyData: ShopifyProductDetails | null;
    theme: ProductMetricsPanelTheme;
    darkMode: boolean;
}

export function ProductMetricsPanel({ product, shopifyData, theme, darkMode }: ProductMetricsPanelProps) {
    // Client-only "today" stamp so SSR and CSR don't diverge on Date.now().
    const [today, setToday] = useState<string>('');
    useEffect(() => { setToday(formatDate(new Date())); }, []);

    const titleAnalysis = analyzeSEOContent(product.title, 'title');
    const descriptionAnalysis = analyzeSEOContent(shopifyData?.body_html || '', 'description');
    const metaTitleAnalysis = analyzeSEOContent(shopifyData?.meta_title || '', 'meta_title');
    const metaDescAnalysis = analyzeSEOContent(shopifyData?.meta_description || '', 'meta_description');

    const imageAnalysis = analyzeImages(
        shopifyData?.images?.map(img => ({ alt: img.alt, filename: img.filename })) || []
    );

    const aeoAnalysis = analyzeAEOContent(
        product.title,
        shopifyData?.body_html || '',
        shopifyData?.meta_description || '',
        shopifyData?.vehicle_fitments || []
    );

    const geoAnalysis = analyzeGEOContent(
        product.title,
        shopifyData?.body_html || '',
        shopifyData?.meta_title || '',
        shopifyData?.vehicle_fitments || [],
        shopifyData?.vehicle_fitments || []
    );

    const seoMetrics = {
        title: titleAnalysis.score,
        description: descriptionAnalysis.score,
        images: imageAnalysis.score,
        meta: Math.round((metaTitleAnalysis.score + metaDescAnalysis.score) / 2),
    };

    const seoHealthScore = Math.round(
        (seoMetrics.title * 0.25) +
        (seoMetrics.description * 0.35) +
        (seoMetrics.images * 0.20) +
        (seoMetrics.meta * 0.20)
    );

    const allIssues = [
        ...titleAnalysis.issues.map(i => `Título: ${i}`),
        ...descriptionAnalysis.issues.map(i => `Descripción: ${i}`),
        ...imageAnalysis.issues.map(i => `Imágenes: ${i}`),
        ...metaTitleAnalysis.issues.map(i => `Meta Título: ${i}`),
        ...metaDescAnalysis.issues.map(i => `Meta Descripción: ${i}`),
    ];

    const completenessItems = [
        { label: 'Título SEO', completed: titleAnalysis.score >= 60, score: 15, current: `${titleAnalysis.score}%` },
        { label: 'Descripción HTML', completed: descriptionAnalysis.score >= 50, score: 20, current: `${descriptionAnalysis.score}%` },
        { label: 'Imágenes (con alt)', completed: imageAnalysis.score >= 70, score: 15, current: `${imageAnalysis.withAlt}/${imageAnalysis.total}` },
        { label: 'SKU', completed: !!product.sku, score: 10, current: product.sku ? '✓' : '✗' },
        { label: 'Tipo', completed: !!product.product_type, score: 10, current: product.product_type || '—' },
        { label: 'Meta Título', completed: metaTitleAnalysis.score >= 60, score: 15, current: `${metaTitleAnalysis.score}%` },
        { label: 'Meta Desc', completed: metaDescAnalysis.score >= 60, score: 15, current: `${metaDescAnalysis.score}%` },
    ];
    const completenessScore = completenessItems.reduce((acc, item) => acc + (item.completed ? item.score : 0), 0);

    const salesPerformance = product.total_sold > 100 ? 'high' : product.total_sold > 20 ? 'medium' : product.total_sold > 0 ? 'low' : 'none';
    const salesColors = {
        high: 'text-green-400',
        medium: 'text-[#f7b500]',
        low: 'text-orange-400',
        none: 'text-red-400',
    };

    return (
        <div className={`mb-8 ${theme.cardBg} border ${theme.border} rounded-lg overflow-hidden`}>
            {/* Header */}
            <div className={`px-6 py-4 border-b ${theme.border} bg-gradient-to-r from-[#F7B500]/10 to-transparent`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">📊</span>
                        <h2 className={`text-lg font-bold ${theme.text}`}>Métricas del Producto</h2>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className={`text-xs ${theme.textMuted}`}>
                            {today ? `Actualizado: ${today}` : ''}
                        </span>
                    </div>
                </div>
            </div>

            <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {/* Sales Metrics */}
                    <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-zinc-50'} border ${theme.border}`}>
                        <h3 className={`text-xs font-semibold ${theme.textMuted} uppercase mb-3 flex items-center gap-2`}>
                            <span>💰</span> Ventas Shopify
                        </h3>
                        <div className="space-y-3">
                            <div className="flex items-end justify-between">
                                <div>
                                    <p className={`text-2xl font-bold ${salesColors[salesPerformance]}`}>
                                        {product.total_sold?.toLocaleString() || 0}
                                    </p>
                                    <p className={`text-xs ${theme.textMuted}`}>Unidades vendidas</p>
                                </div>
                                <div className="text-right">
                                    <p className={`text-lg font-semibold ${theme.text}`}>
                                        ${product.total_revenue?.toLocaleString() || 0}
                                    </p>
                                    <p className={`text-xs ${theme.textMuted}`}>Ingresos totales</p>
                                </div>
                            </div>
                            <div className={`pt-3 border-t ${theme.border}`}>
                                <div className="flex items-center justify-between text-sm">
                                    <span className={theme.textMuted}>Precio:</span>
                                    <span className={`${theme.text} font-mono`}>${shopifyData?.price || '—'} MXN</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* SEO Health Score */}
                    <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-zinc-50'} border ${theme.border}`}>
                        <h3 className={`text-xs font-semibold ${theme.textMuted} uppercase mb-3 flex items-center gap-2`}>
                            <span>🔍</span> Salud SEO
                            {seoHealthScore < 60 && <span className="text-red-400">⚠️</span>}
                        </h3>
                        <div className="flex items-center gap-4 mb-4">
                            <div className="relative size-16">
                                <svg className="size-full transform -rotate-90">
                                    <circle cx="32" cy="32" r="28" fill="none" stroke={darkMode ? '#333' : '#e5e5e5'} strokeWidth="6" />
                                    <circle
                                        cx="32"
                                        cy="32"
                                        r="28"
                                        fill="none"
                                        stroke={seoHealthScore >= 80 ? '#22c55e' : seoHealthScore >= 60 ? '#f7b500' : '#ef4444'}
                                        strokeWidth="6"
                                        strokeDasharray={`${(seoHealthScore / 100) * 176} 176`}
                                        strokeLinecap="round"
                                    />
                                </svg>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className={`text-lg font-bold ${theme.text}`}>{seoHealthScore}%</span>
                                </div>
                            </div>
                            <div className="flex-1 space-y-1.5">
                                <div className="flex items-center justify-between text-xs">
                                    <span className={theme.textMuted}>Título</span>
                                    <span className={`font-mono ${seoMetrics.title >= 60 ? 'text-green-400' : seoMetrics.title >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                                        {seoMetrics.title}%
                                    </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                    <span className={theme.textMuted}>Descripción</span>
                                    <span className={`font-mono ${seoMetrics.description >= 60 ? 'text-green-400' : seoMetrics.description >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                                        {seoMetrics.description}%
                                    </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                    <span className={theme.textMuted}>Imágenes</span>
                                    <span className={`font-mono ${seoMetrics.images >= 60 ? 'text-green-400' : seoMetrics.images >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                                        {seoMetrics.images}%
                                    </span>
                                </div>
                                <div className="flex items-center justify-between text-xs">
                                    <span className={theme.textMuted}>Meta tags</span>
                                    <span className={`font-mono ${seoMetrics.meta >= 60 ? 'text-green-400' : seoMetrics.meta >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                                        {seoMetrics.meta}%
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Issues List */}
                        {allIssues.length > 0 && (
                            <div className="mt-3 pt-3 border-t border-red-500/20">
                                <p className="text-xs text-red-400 font-medium mb-2">⚠️ Problemas detectados:</p>
                                <ul className="space-y-1">
                                    {allIssues.slice(0, 3).map((issue, idx) => (
                                        <li key={idx} className="text-xs text-red-300 flex items-start gap-1">
                                            <span>•</span>
                                            <span>{issue}</span>
                                        </li>
                                    ))}
                                    {allIssues.length > 3 && (
                                        <li className="text-xs text-zinc-500">+{allIssues.length - 3} más…</li>
                                    )}
                                </ul>
                            </div>
                        )}

                        <p className={`text-xs mt-3 ${seoHealthScore >= 80 ? 'text-green-400' : seoHealthScore >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                            {seoHealthScore >= 80 ? '✓ SEO Optimizado' : seoHealthScore >= 60 ? '⚠ Necesita mejoras' : '❌ Requiere optimización'}
                        </p>
                    </div>

                    {/* Product Completeness */}
                    <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-zinc-50'} border ${theme.border}`}>
                        <h3 className={`text-xs font-semibold ${theme.textMuted} uppercase mb-3 flex items-center gap-2`}>
                            <span>✅</span> Completitud
                        </h3>
                        <div className="flex items-center gap-4 mb-3">
                            <div className="relative size-16">
                                <svg className="size-full transform -rotate-90">
                                    <circle cx="32" cy="32" r="28" fill="none" stroke={darkMode ? '#333' : '#e5e5e5'} strokeWidth="6" />
                                    <circle
                                        cx="32"
                                        cy="32"
                                        r="28"
                                        fill="none"
                                        stroke={completenessScore >= 80 ? '#22c55e' : completenessScore >= 60 ? '#f7b500' : '#ef4444'}
                                        strokeWidth="6"
                                        strokeDasharray={`${(completenessScore / 100) * 176} 176`}
                                        strokeLinecap="round"
                                    />
                                </svg>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className={`text-lg font-bold ${theme.text}`}>{completenessScore}%</span>
                                </div>
                            </div>
                            <div className="flex-1">
                                <p className={`text-sm ${theme.textSecondary}`}>
                                    {completenessItems.filter(i => i.completed).length} de {completenessItems.length} campos
                                </p>
                                <p className={`text-xs ${theme.textMuted} mt-1`}>
                                    {completenessScore >= 80 ? 'Producto completo' : completenessScore >= 50 ? 'Faltan campos importantes' : 'Información incompleta'}
                                </p>
                            </div>
                        </div>
                        <div className="space-y-1.5 max-h-24 overflow-y-auto">
                            {completenessItems.map((item, idx) => (
                                <div key={idx} className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className={item.completed ? 'text-green-500' : 'text-red-400'}>
                                            {item.completed ? '✓' : '×'}
                                        </span>
                                        <span className={item.completed ? theme.textSecondary : theme.textMuted}>
                                            {item.label}
                                        </span>
                                    </div>
                                    <span className={`font-mono text-[10px] ${item.completed ? 'text-green-400' : 'text-red-400'}`}>
                                        {item.current}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* AEO */}
                    <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-zinc-50'} border ${theme.border}`}>
                        <h3 className={`text-xs font-semibold ${theme.textMuted} uppercase mb-3 flex items-center gap-2`}>
                            <span>📢</span> AEO
                            <span className="text-[10px] normal-case opacity-60">(Voice Search)</span>
                            {aeoAnalysis.score < 50 && <span className="text-red-400">⚠️</span>}
                        </h3>
                        <div className="flex items-center gap-4 mb-4">
                            <div className="relative size-16">
                                <svg className="size-full transform -rotate-90">
                                    <circle cx="32" cy="32" r="28" fill="none" stroke={darkMode ? '#333' : '#e5e5e5'} strokeWidth="6" />
                                    <circle
                                        cx="32" cy="32" r="28" fill="none"
                                        stroke={aeoAnalysis.score >= 70 ? '#22c55e' : aeoAnalysis.score >= 50 ? '#f7b500' : '#ef4444'}
                                        strokeWidth="6"
                                        strokeDasharray={`${(aeoAnalysis.score / 100) * 176} 176`}
                                        strokeLinecap="round"
                                    />
                                </svg>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className={`text-lg font-bold ${theme.text}`}>{aeoAnalysis.score}%</span>
                                </div>
                            </div>
                            <div className="flex-1">
                                <p className={`text-xs ${theme.textMuted}`}>
                                    {aeoAnalysis.score >= 70 ? '✓ Optimizado para voz' :
                                        aeoAnalysis.score >= 50 ? '⚠ Mejorable para voz' : '❌ No optimizado'}
                                </p>
                                <p className={`text-[10px] ${theme.textMuted} mt-1`}>
                                    {aeoAnalysis.checks.filter(c => c.passed).length}/{aeoAnalysis.checks.length} checks
                                </p>
                            </div>
                        </div>

                        <div className="space-y-1 max-h-20 overflow-y-auto">
                            {aeoAnalysis.checks.filter(c => c.importance === 'high').map((check, idx) => (
                                <div key={idx} className="flex items-start gap-2 text-xs">
                                    <span className={check.passed ? 'text-green-500' : 'text-yellow-500'}>
                                        {check.passed ? '✓' : '⚠'}
                                    </span>
                                    <span className={check.passed ? theme.textSecondary : 'text-yellow-400'}>
                                        {check.label}
                                    </span>
                                </div>
                            ))}
                        </div>

                        {aeoAnalysis.snippetOpportunities.length > 0 && (
                            <div className="mt-3 pt-3 border-t border-blue-500/20">
                                <p className="text-xs text-blue-400 font-medium mb-1">💡 Oportunidades:</p>
                                <p className="text-[10px] text-blue-300">{aeoAnalysis.snippetOpportunities[0]}</p>
                            </div>
                        )}
                    </div>

                    {/* GEO */}
                    <div className={`p-4 rounded-lg ${darkMode ? 'bg-black/30' : 'bg-zinc-50'} border ${theme.border}`}>
                        <h3 className={`text-xs font-semibold ${theme.textMuted} uppercase mb-3 flex items-center gap-2`}>
                            <span>🤖</span> GEO
                            <span className="text-[10px] normal-case opacity-60">(AI Search)</span>
                            {geoAnalysis.score < 50 && <span className="text-red-400">⚠️</span>}
                        </h3>
                        <div className="flex items-center gap-4 mb-4">
                            <div className="relative size-16">
                                <svg className="size-full transform -rotate-90">
                                    <circle cx="32" cy="32" r="28" fill="none" stroke={darkMode ? '#333' : '#e5e5e5'} strokeWidth="6" />
                                    <circle
                                        cx="32" cy="32" r="28" fill="none"
                                        stroke={geoAnalysis.score >= 70 ? '#22c55e' : geoAnalysis.score >= 50 ? '#f7b500' : '#ef4444'}
                                        strokeWidth="6"
                                        strokeDasharray={`${(geoAnalysis.score / 100) * 176} 176`}
                                        strokeLinecap="round"
                                    />
                                </svg>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className={`text-lg font-bold ${theme.text}`}>{geoAnalysis.score}%</span>
                                </div>
                            </div>
                            <div className="flex-1">
                                <p className={`text-xs ${theme.textMuted}`}>
                                    {geoAnalysis.entityClarity === 'good' ? '✓ Entidades claras' :
                                        geoAnalysis.entityClarity === 'medium' ? '⚠ Entidades mejorables' : '❌ Entidades pobres'}
                                </p>
                                <p className={`text-[10px] ${theme.textMuted} mt-1`}>
                                    {geoAnalysis.checks.filter(c => c.passed).length}/{geoAnalysis.checks.length} checks
                                </p>
                            </div>
                        </div>

                        {geoAnalysis.authoritySignals.length > 0 && (
                            <div className="mb-3">
                                <p className="text-xs text-green-400 font-medium mb-1">✓ Señales de autoridad:</p>
                                <div className="flex flex-wrap gap-1">
                                    {geoAnalysis.authoritySignals.slice(0, 2).map((signal, idx) => (
                                        <span key={idx} className="text-[10px] px-2 py-0.5 bg-green-500/20 text-green-400 rounded">
                                            {signal}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {geoAnalysis.contextGaps.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-red-500/20">
                                <p className="text-xs text-red-400 font-medium mb-1">⚠️ Brechas:</p>
                                <p className="text-[10px] text-red-300">{geoAnalysis.contextGaps[0]}</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
