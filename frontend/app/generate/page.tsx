'use client';

import { useEffect, useState, useCallback } from 'react';
import { productAPI, Product, productsAIAPI } from '@/lib/api';
import useProductStore from '@/store';
import Link from 'next/link';
import { useToast } from '../components/ui/Toast';
import { MultiAgentToggle } from '../components/ui/MultiAgentToggle';
import {
    SyncIcon,
    SpinnerIcon,
    SearchIcon,
    DatabaseIcon,
    ImageIcon,
    FireIcon,
    SparklesIcon
} from '../components/ui/Icons';

export default function GenerateDashboardPage() {
    const { products, lastSynced, setProducts } = useProductStore();
    const [loading, setLoading] = useState(false);
    const [needsSeoOnly, setNeedsSeoOnly] = useState(true); // Default to true for this page
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [darkMode, setDarkMode] = useState(true);
    const [syncing, setSyncing] = useState(false);
    const toast = useToast();
    
    // Multi-Agent State
    const [multiAgentEnabled, setMultiAgentEnabled] = useState(false);
    const [multiAgentStatus, setMultiAgentStatus] = useState<{
        multi_agent_enabled: boolean;
        mode: string;
        agents: string[];
    } | null>(null);
    const [batchAnalyzing, setBatchAnalyzing] = useState(false);
    const [quickScanResults, setQuickScanResults] = useState<Record<string, { score: number; issue: string }>>({});

    useEffect(() => {
        loadProducts();
    }, [needsSeoOnly]);

    useEffect(() => {
        const saved = localStorage.getItem('theme');
        if (saved) setDarkMode(saved === 'dark');
        
        // Load multi-agent status
        loadMultiAgentStatus();
    }, []);

    const loadMultiAgentStatus = async () => {
        try {
            const status = await productsAIAPI.getMultiAgentStatus();
            setMultiAgentStatus(status);
            setMultiAgentEnabled(status.multi_agent_enabled);
        } catch (e) {
            console.log('[Multi-Agent] Status check failed, using defaults');
        }
    };

    // Quick scan for top products
    const runQuickScan = async () => {
        if (products.length === 0) return;
        setBatchAnalyzing(true);
        
        const topProducts = products.slice(0, 5);
        const results: Record<string, { score: number; issue: string }> = {};

        const scanResults = await Promise.allSettled(
            topProducts.map(product => productsAIAPI.quickScan(product.id))
        );

        scanResults.forEach((result, idx) => {
            if (result.status === 'fulfilled') {
                results[topProducts[idx].id] = {
                    score: result.value.quick_score,
                    issue: result.value.top_issue
                };
            }
        });

        setQuickScanResults(results);
        setBatchAnalyzing(false);
    };

    const loadProducts = async () => {
        setLoading(true);
        try {
            const data = await productAPI.getProducts({ needs_seo_only: needsSeoOnly, limit: 5000 });
            setProducts(data.products, data.total);
        } catch (error) {
            console.error('Failed to load products:', error);
        } finally {
            setLoading(false);
        }
    };

    const filteredProducts = products.filter((p) => {
        const searchMatch = searchQuery === '' ||
            p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (p.sku && p.sku.toLowerCase().includes(searchQuery.toLowerCase()));

        if (statusFilter === 'all') return searchMatch;
        if (statusFilter === 'published') return searchMatch && p.seo_status === 'published';
        if (statusFilter === 'draft') return searchMatch && p.seo_status === 'draft';
        if (statusFilter === 'missing') return searchMatch && p.seo_status === 'needs_seo';
        return searchMatch;
    });

    // Theme - Dual mode support
    const theme = darkMode ? {
        // Dark Mode
        bg: 'bg-[#0a0a0a]',
        headerBg: 'bg-[#0a0a0a]',
        cardBg: 'bg-[#1a1a1a]',
        text: 'text-white',
        textSecondary: 'text-zinc-300',
        textMuted: 'text-zinc-400',
        border: 'border-[#3a3a3a]',
        tableBg: 'bg-[#1a1a1a]',
        inputBg: 'bg-[#0a0a0a]',
        tableHeaderBg: 'bg-[#0a0a0a]',
    } : {
        // Light Mode
        bg: 'bg-zinc-50',
        headerBg: 'bg-white',
        cardBg: 'bg-white',
        text: 'text-zinc-900',
        textSecondary: 'text-zinc-600',
        textMuted: 'text-zinc-500',
        border: 'border-zinc-200',
        tableBg: 'bg-white',
        inputBg: 'bg-white',
        tableHeaderBg: 'bg-zinc-100',
    };

    return (
        <div className={`min-h-screen flex flex-col ${theme.bg} pt-16`}>
            <main className="flex-1 max-w-7xl w-full mx-auto px-8 py-10">
                {/* Search Bar - Main Action */}
                <div className="mb-6 flex flex-col md:flex-row md:items-center gap-4">
                    <div className="flex-1 relative">
                        <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500" size={20} />
                        <input
                            type="text"
                            placeholder="Buscar por título o SKU..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className={`w-full pl-12 pr-4 py-3 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-all`}
                        />
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Shopify Sync */}
                        <button
                            onClick={async () => {
                                try {
                                    setSyncing(true);
                                    const response = await productAPI.syncShopify() as any;
                                    toast.success(`Sync: ${response.new_products || 0} new, ${response.updated_products || 0} updated`);
                                    await loadProducts();
                                } catch (error) {
                                    toast.error(`Sync failed: ${error instanceof Error ? error.message : 'Error'}`);
                                } finally { setSyncing(false); }
                            }}
                            disabled={syncing || loading}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0a0a0a] border border-[#3a3a3a] hover:border-[#F7B500] text-[#F7B500] text-xs transition-colors disabled:opacity-50"
                        >
                            {syncing ? <><SpinnerIcon className="animate-spin size-3" /> Syncing…</> : <><SyncIcon className="size-3" /> Shopify</>}
                        </button>

                        {/* Multi-Agent Toggle - Compact */}
                        <MultiAgentToggle
                            enabled={multiAgentEnabled}
                            onChange={setMultiAgentEnabled}
                            variant="compact"
                        />
                        
                        {/* AI Scan - Only when multi-agent enabled */}
                        {multiAgentEnabled && (
                            <button
                                onClick={runQuickScan}
                                disabled={batchAnalyzing || products.length === 0}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs rounded hover:bg-purple-500/20 transition-colors disabled:opacity-50"
                            >
                                {batchAnalyzing ? (
                                    <><SpinnerIcon className="animate-spin size-3" /> Scanning…</>
                                ) : (
                                    <><SparklesIcon size={14} /> AI Scan</>
                                )}
                            </button>
                        )}
                        
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={needsSeoOnly}
                                onChange={(e) => setNeedsSeoOnly(e.target.checked)}
                                className="size-4 accent-[#F7B500]"
                            />
                            <span className={`text-sm ${theme.textSecondary}`}>Solo sin SEO</span>
                        </label>
                        
                        <span className={`text-sm ${theme.textMuted}`}>
                            <span className="text-[#F7B500] font-semibold">{filteredProducts.length}</span> productos
                        </span>
                    </div>
                </div>

                {loading ? (
                    <div className="flex flex-col items-center justify-center py-20">
                        <SpinnerIcon className="animate-spin size-10 text-[#F7B500] mb-4" />
                        <p className={theme.textMuted}>Cargando productos para optimizar…</p>
                    </div>
                ) : filteredProducts.length === 0 ? (
                    <div className={`text-center py-20 ${theme.cardBg} border ${theme.border}`}>
                        <DatabaseIcon size={64} className="mx-auto mb-6 text-zinc-600" />
                        <h3 className={`text-2xl font-semibold ${theme.text} mb-3`}>No hay productos que necesiten SEO</h3>
                        <p className={`${theme.textMuted} mb-8 max-w-md mx-auto`}>
                            ¡Excelente trabajo! Todos tus productos están optimizados.
                        </p>
                    </div>
                ) : (
                    <div className={`${theme.tableBg} border ${theme.border} overflow-hidden`}>
                        <table className="w-full text-left">
                            <thead>
                                {/* Gold border per design system */}
                                <tr className="border-b-2 border-[#F7B500] bg-[#0a0a0a]">
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase">Producto</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase">SKU</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase">Estado</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase">AI Score</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase text-right">Acción</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#333333]">
                                {filteredProducts.map((product) => (
                                    <tr key={product.id} className="hover:bg-[#F7B500]/5 transition-colors">
                                        <td className="px-6 py-4">
                                            <div className={`font-medium ${theme.text} text-sm`}>{product.title}</div>
                                            <div className={`text-xs ${theme.textMuted}`}>{product.handle}</div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <code className="text-xs text-[#F7B500] font-mono">{product.sku || '—'}</code>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center px-2.5 py-0.5 text-xs font-medium ${product.seo_status === 'published' ? 'bg-green-500/20 text-green-400' :
                                                product.seo_status === 'draft' ? 'bg-[#F7B500]/20 text-[#F7B500]' :
                                                    'bg-red-500/20 text-red-400'
                                                }`}>
                                                {product.seo_status === 'published' ? 'Publicado' :

                                                    product.seo_status === 'draft' ? 'Borrador' : 'Sin SEO'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            {quickScanResults[product.id] ? (
                                                <div className="flex flex-col">
                                                    <span className={`text-sm font-bold ${
                                                        quickScanResults[product.id].score >= 80 ? 'text-green-400' :
                                                        quickScanResults[product.id].score >= 60 ? 'text-yellow-400' : 'text-red-400'
                                                    }`}>
                                                        {quickScanResults[product.id].score}%
                                                    </span>
                                                    <span className="text-xs text-zinc-500 truncate max-w-[150px]">
                                                        {quickScanResults[product.id].issue}
                                                    </span>
                                                </div>
                                            ) : (
                                                <span className="text-xs text-zinc-600">—</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <Link
                                                href={`/generate/${product.id}?multi_agent=${multiAgentEnabled}`}
                                                className="inline-flex items-center gap-2 px-4 py-2 bg-[#F7B500] text-black text-sm font-bold hover:bg-[#ffc933] transition-colors"
                                            >
                                                Optimizar →
                                            </Link>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </main>
        </div>
    );
}
