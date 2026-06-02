'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { formatDate } from '@/app/lib/dates';
import { productAPI, libraryAPI, promptAPI, contentAPI, productVisibilityAPI, snapshotAPI, productsAIAPI, Product, ShopifyProductDetails, Library, PromptTemplate, GenerationMeta } from '../../../lib/api';
import { parseVehicleFitments, VehicleFitment } from '../../../lib/parsers/vehicleFitmentParser';
import { MultiAgentToggle } from '../../components/ui/MultiAgentToggle';
import { ConsensusDisplay } from '../../components/ui/ConsensusDisplay';
import Link from 'next/link';
import Image from 'next/image';

// SaveButton component - extracted to module scope to prevent re-creation on every render
interface SaveButtonProps {
    section: string;
    data: any;
    label?: string;
    savingSection: string | null;
    onSave: (section: string, data: any) => void;
}

const SaveButton = ({ section, data, label, savingSection, onSave }: SaveButtonProps) => (
    <button
        onClick={() => onSave(section, data)}
        disabled={savingSection === section}
        className={`px-3 py-1.5 text-xs ${savingSection === section
            ? 'bg-zinc-600 text-zinc-400 cursor-wait'
            : 'bg-[#F7B500] text-black hover:bg-[#e5a800]'} transition-colors`}
    >
        {savingSection === section ? '💾 Guardando...' : (label || '💾 Guardar')}
    </button>
);

// CharCounter component - extracted to module scope to prevent re-creation on every render
interface CharCounterProps {
    value: string;
    min: number;
    max: number;
    softMax?: number;
}

const CharCounter = ({ value, min, max, softMax }: CharCounterProps) => {
    const len = value.length;
    let color = 'text-green-400';
    let display = `${len}/${max}`;

    if (len < min) {
        color = 'text-red-400';
    } else if (softMax && len > softMax && len <= max) {
        // Between soft limit (60) and hard limit (100) - show warning
        color = 'text-yellow-400';
        display = `${len}/${softMax} (max: ${max})`;
    } else if (len > max) {
        color = 'text-red-400';
    }

    return <span className={`text-xs ${color}`}>{display} caracteres</span>;
};


export interface SmartRecommendation {
    priority: 'high' | 'medium' | 'low';
    category: string;
    action: string;
    expected_impact: string;
    implementation: string;
    why_it_matters?: string;
    auto_generate?: boolean;
    generated_content?: string;
    title?: string;
}

interface SEOContent {
    h1_title: string;
    description_html: string;
    alt_tags: string;
    compatible_vehicles: string;
    short_description: string;
    meta_title: string;
    meta_description: string;
    url_handle: string;
    resumen: string;
}

export default function ProductEditorPage() {
    const params = useParams();
    const router = useRouter();
    const [product, setProduct] = useState<Product | null>(null);
    const [shopifyData, setShopifyData] = useState<ShopifyProductDetails | null>(null);
    const [loadingShopify, setLoadingShopify] = useState(false);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [darkMode, setDarkMode] = useState(true);
    const [showCurrentData, setShowCurrentData] = useState(true);
    const [descriptionView, setDescriptionView] = useState<'preview' | 'html'>('preview');
    const [showFitmentModal, setShowFitmentModal] = useState(false);
    const [refreshingFitments, setRefreshingFitments] = useState(false);
    const [savingSection, setSavingSection] = useState<string | null>(null); // Track which section is saving
    const [imageAlts, setImageAlts] = useState<Array<{ id: number; src: string; filename: string; newFilename: string; alt: string }>>([]);
    const [vehicleFitments, setVehicleFitments] = useState<Array<{
        id: number;
        make: string[];
        modelo: string[];
        year_start: number | null;
        year_end: number | null;
        transmission_type: string;
        transmission_model: string;
        engine: string;
    }>>([]);
    const [generationMeta, setGenerationMeta] = useState<GenerationMeta | null>(null); // Sources & generation info
    const [previewMode, setPreviewMode] = useState<'edit' | 'preview'>('edit'); // Toggle between edit and preview

    const [libraries, setLibraries] = useState<Library[]>([]);
    const [templates, setTemplates] = useState<PromptTemplate[]>([]);
    const [selectedLibraries, setSelectedLibraries] = useState<string[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<string>('');
    const [selectedModel, setSelectedModel] = useState<string>('grok-4.3');
    const [selectedProvider, setSelectedProvider] = useState<string>('grok');  // factory_provider name
    const [reasoning, setReasoning] = useState<string>('');  // AI reasoning/thinking
    const [useAnalysisInsights, setUseAnalysisInsights] = useState(true); // Include Grok analysis in generation
    const [applyingRecommendation, setApplyingRecommendation] = useState<string | null>(null); // Track which recommendation is being applied

    // Multi-Agent State — defaults to false so the user's provider selection is respected
    const [multiAgentEnabled, setMultiAgentEnabled] = useState(false);
    const [multiAgentMeta, setMultiAgentMeta] = useState<{
        mode: string;
        agents_used: string[];
        consensus_score: number;
        task_type?: string;
    } | null>(null);

    const [content, setContent] = useState<SEOContent>({
        h1_title: '',
        description_html: '',
        alt_tags: '',
        compatible_vehicles: '',
        short_description: '',
        meta_title: '',
        meta_description: '',
        url_handle: '',
        resumen: '',
    });

    // AI Analysis State (v2 Enhanced)
    const [aiAnalysis, setAiAnalysis] = useState<{
        seo_analysis: { score: number; critical_issues: string[]; improvements: string[]; keyword_opportunities: string[]; keyword_opportunities_status?: 'real' | 'no_data' };
        aeo_analysis: { score: number; snippet_opportunities: string[]; question_targets: string[]; structured_data_recommendations: string[] };
        geo_analysis: { score: number; entity_clarity: string; context_gaps: string[]; authority_signals: string[] };
        recommendations: Array<SmartRecommendation>;
        priority_actions: string[];
        expected_impact: { traffic_increase: string; conversion_increase: string; timeline: string; revenue_potential?: string };
        cached?: boolean;
        cache_age_hours?: number;
        // v2 Enhanced Fields
        primary_issue?: {
            type: 'VISIBILITY' | 'RELEVANCE' | 'CONVERSION' | 'STALLED' | 'OPTIMIZATION';
            severity: 'high' | 'medium' | 'low';
            description: string;
            why?: string;
            impact_if_fixed?: string;
            estimated_revenue_impact?: number;
        };
        performance_vs_benchmark?: {
            category: string;
            product_count: number;
            metrics: {
                sessions: { product: number; category_avg: number };
                conversion: { product: number; category_avg: number };
                ctr: { product: number; category_avg: number };
                position: { product: number; category_avg: number };
            };
            top_performers?: Array<{ title: string; revenue_30d: number; }>;
        };
        ai_visibility_scores?: { grok?: number; openai?: number; perplexity?: number;[key: string]: number | undefined } | null;
        ai_visibility_status?: 'fresh' | 'stale' | 'not_measured' | 'unknown' | null;
        ai_visibility_snapshot_date?: string | null;
        ai_visibility_age_days?: number | null;
        top_opportunity_queries?: Array<{
            query: string;
            impressions: number;
            clicks: number;
            position: number;
            opportunity: string;
        }>;
        trend_indicators?: {
            traffic?: string;
            position?: string;
            ai_visibility?: string;
            sales?: string;
            impressions?: string;
        };
        estimated_revenue_opportunity?: number;
        generated_content?: {
            suggested_meta_title?: string;
            suggested_meta_description?: string;
            faq_questions?: string[];
        };
    } | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const [analysisCacheStatus, setAnalysisCacheStatus] = useState<{ cached: boolean; age: number } | null>(null);

    // JSON-LD Schema State
    const [productSchema, setProductSchema] = useState<Record<string, unknown> | null>(null);
    const [generatingSchema, setGeneratingSchema] = useState(false);
    const [showSchemaSection, setShowSchemaSection] = useState(false);
    const [refreshingData, setRefreshingData] = useState(false); // Loading state for visibility/snapshot buttons
    const [isRunningVisibilityCheck, setIsRunningVisibilityCheck] = useState(false); // Inline "Medir ahora" button in Análisis card

    // Get URL search params for multi_agent setting
    const searchParams = useSearchParams();

    // Sync LLM selection with global header selector
    useEffect(() => {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
        fetch(`${API_BASE}/settings/llm-providers`)
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (!data?.active) return;
                const activeEntry = data.providers?.find((p: any) => p.active);
                if (!activeEntry) return;
                // Use factory_provider from backend — maps UI name to provider class
                setSelectedProvider(activeEntry.factory_provider || data.active);
                setSelectedModel(activeEntry.model);
                // Auto-enable multi-agent toggle when grok420 is selected
                if (activeEntry.factory_provider === 'grok420') {
                    setMultiAgentEnabled(true);
                }
            })
            .catch(() => {});

        // Listen for real-time changes from the header LLM selector
        const handleProviderChange = (e: Event) => {
            const { factory_provider, model } = (e as CustomEvent).detail;
            setSelectedProvider(factory_provider);
            if (model) setSelectedModel(model);
            // Auto-enable multi-agent toggle when grok420 is selected
            setMultiAgentEnabled(factory_provider === 'grok420');
        };
        window.addEventListener('llm-provider-changed', handleProviderChange);
        return () => window.removeEventListener('llm-provider-changed', handleProviderChange);
    }, []);

    useEffect(() => {
        const saved = localStorage.getItem('theme');
        if (saved) setDarkMode(saved === 'dark');

        // Read multi_agent from URL params
        const multiAgentParam = searchParams.get('multi_agent');
        if (multiAgentParam !== null) {
            setMultiAgentEnabled(multiAgentParam === 'true');
        }

        loadProduct();
        // Load libraries and templates for RAG configuration
        loadRagConfig();
    }, [params.id]);



    // Handle applying a recommendation
    const handleApplyRecommendation = (rec: SmartRecommendation) => {
        if (rec.generated_content) {
            // Apply based on category
            switch (rec.category) {
                case 'seo':
                    if (rec.title.toLowerCase().includes('meta title')) {
                        setContent(c => ({ ...c, meta_title: rec.generated_content! }));
                    } else if (rec.title.toLowerCase().includes('meta description')) {
                        setContent(c => ({ ...c, meta_description: rec.generated_content! }));
                    }
                    break;
                case 'aeo':
                    // Could add FAQ items
                    break;
                case 'conversion':
                    // Could add to description
                    break;
            }
        }
    };

    const loadRagConfig = async () => {
        try {
            // Load active libraries
            const libs = await libraryAPI.getLibraries({ is_active: true });
            setLibraries(libs);
            // Load prompt templates
            const temps = await promptAPI.getTemplates();
            setTemplates(temps);
        } catch (error) {
            console.error('Error loading RAG config:', error);
        }
    };

    const loadProduct = async () => {
        let loadedShopify: ShopifyProductDetails | null = null;
        try {
            const productId = params.id as string;
            const data = await productAPI.getProduct(productId);
            setProduct(data);

            // Now fetch full Shopify data
            setLoadingShopify(true);
            try {
                loadedShopify = await productAPI.getProductShopifyDetails(productId);
                setShopifyData(loadedShopify);

                // Pre-fill with current Shopify content
                const altTagsFromImages = loadedShopify.images
                    .map(img => `${img.filename} | ${img.alt || 'Sin texto alternativo'}`)
                    .join('\n');

                // Set image alts for individual editing
                setImageAlts(loadedShopify.images.map(img => ({
                    id: img.id,
                    src: img.src,
                    filename: img.filename,
                    newFilename: img.filename, // Initialize with current filename
                    alt: img.alt || ''
                })));

                setContent({
                    h1_title: loadedShopify.title || '',
                    description_html: loadedShopify.body_html || '',
                    alt_tags: altTagsFromImages,
                    compatible_vehicles: loadedShopify.compatible_vehicles || '',
                    short_description: loadedShopify.short_description || '',
                    meta_title: loadedShopify.meta_title || `${loadedShopify.title} | Example Store`,
                    meta_description: loadedShopify.meta_description || '',
                    url_handle: loadedShopify.handle || '',
                    resumen: loadedShopify.resumen || '',
                });

                // Load vehicle fitments from Shopify metaobjects
                if (loadedShopify.vehicle_fitments && loadedShopify.vehicle_fitments.length > 0) {
                    console.log('[Frontend] Loaded vehicle fitments from Shopify:', loadedShopify.vehicle_fitments);
                    setVehicleFitments(loadedShopify.vehicle_fitments);
                }

                // Load existing JSON-LD schema from metafield if available
                const existingSchema = loadedShopify.metafields?.['custom.product_schema_json'];
                if (existingSchema) {
                    try {
                        const parsedSchema = typeof existingSchema === 'string'
                            ? JSON.parse(existingSchema)
                            : existingSchema;
                        setProductSchema(parsedSchema);
                        console.log('[Frontend] Loaded existing product schema from metafield');
                    } catch (e) {
                        console.log('[Frontend] Could not parse existing schema:', e);
                    }
                }
            } catch (e) {
                console.error('Error loading Shopify data:', e);
                // Fallback to basic data
                setContent({
                    h1_title: data.title || '',
                    description_html: '',
                    alt_tags: '',
                    compatible_vehicles: '',
                    short_description: '',
                    meta_title: `${data.title} | Example Store`,
                    meta_description: '',
                    url_handle: data.handle || '',
                    resumen: '',
                });
            } finally {
                setLoadingShopify(false);

                // Load cached AI analysis (lightweight GET, never triggers Grok)
                loadCachedAnalysis(productId);
            }
        } catch (error) {
            console.error('Error loading product:', error);
        } finally {
            setLoading(false);
        }
    };

    // Load cached AI analysis from database (lightweight, never triggers Grok)
    const loadCachedAnalysis = async (productId: string) => {
        try {
            const cachedAnalysis = await productAPI.getCachedAnalysis(productId);
            console.log('[Analysis] Loaded cached analysis from DB');
            setAiAnalysis(cachedAnalysis);
            setAnalysisCacheStatus({
                cached: true,
                age: cachedAnalysis.cache_age_hours || 0
            });
        } catch (e) {
            console.log('[Analysis] No cached analysis available');
        }
    };

    // Inline visibility probe trigger for the Análisis Grok card. Fires when the user
    // hits "Medir ahora" on a product that has no ProductVisibilitySnapshot yet — the
    // backend now reports status="not_measured" instead of a fake 0%, so we surface a
    // real CTA next to that state. Probes Grok only (matches the existing "Visibilidad AI"
    // button to keep cost predictable); the multi-LLM probe lives on /aeo for now.
    const runProductVisibilityCheck = async () => {
        if (!product || isRunningVisibilityCheck) return;
        setIsRunningVisibilityCheck(true);
        try {
            const result = await productVisibilityAPI.checkVisibility(product.id, ['grok'], 5);
            console.log('[Visibility] Inline check complete:', result.score?.score);
            // Re-pull the cached analysis so the card flips from "Not measured" to the new scores.
            await runAIAnalysis(true);
        } catch (e: any) {
            alert(`No se pudo medir la visibilidad: ${e?.message || 'error desconocido'}`);
        } finally {
            setIsRunningVisibilityCheck(false);
        }
    };

    // Parse vehicle fitment from H4 sections in description
    const parseVehicleFitmentFromDescription = () => {
        const html = content.description_html;
        const title = product?.title || '';
        const vendor = shopifyData?.vendor || '';

        if (!html && !title) {
            alert('No hay descripción para analizar');
            return;
        }

        // Use the extracted parser module
        const result = parseVehicleFitments(html, { title, vendor });

        if (result.fitments.length > 0) {
            // Convert to local format (parser uses same interface)
            setVehicleFitments(result.fitments);
            alert(` Se detectaron ${result.fitments.length} fitment(s) únicos`);
        } else {
            alert('️ No se encontró información de vehículos en la descripción. Revisa la consola para más detalles.');
        }
    };

    const generateContent = async () => {
        if (!product) return;
        setGenerating(true);
        setMultiAgentMeta(null); // Reset multi-agent meta
        try {
            // Prepare analysis insights if available and enabled
            const analysisInsights = useAnalysisInsights && aiAnalysis ? {
                primary_issue: aiAnalysis.primary_issue,
                seo_score: aiAnalysis.seo_analysis?.score,
                aeo_score: aiAnalysis.aeo_analysis?.score,
                geo_score: aiAnalysis.geo_analysis?.score,
                top_queries: aiAnalysis.top_opportunity_queries?.slice(0, 5),
                recommendations: aiAnalysis.recommendations?.slice(0, 5),
                suggestions: aiAnalysis.recommendations?.slice(0, 5),       // backend alias
                keyword_opportunities: aiAnalysis.seo_analysis?.keyword_opportunities,
                aeo_questions: aiAnalysis.aeo_analysis?.question_targets,   // backend alias
                question_targets: aiAnalysis.aeo_analysis?.question_targets,
                competitor_analysis: aiAnalysis.geo_analysis?.context_gaps ? {
                    gap_summary: aiAnalysis.geo_analysis.context_gaps.join('; '),
                    top_competitors: aiAnalysis.top_opportunity_queries?.slice(0, 3)?.map((q: any) => ({ domain: q.query, position: q.opportunity })) ?? []
                } : undefined,
                generated_content: aiAnalysis.generated_content,
                visibility_score: aiAnalysis.ai_visibility_scores,
            } : null;

            // Use the selected provider — multiAgentEnabled syncs with grok420 selection
            const provider = selectedProvider;

            const result = await contentAPI.generate({
                product_id: product.id,
                library_ids: selectedLibraries,
                template_id: selectedTemplate,
                provider: provider,
                model_name: selectedModel,
                analysis_insights: analysisInsights, // NEW: Pass analysis data
            });

            if (result.content) {
                const newContent = result.content;
                console.log('=== Generated Content Debug ===');
                console.log('h1_title:', newContent.h1_title);
                console.log('description_html length:', newContent.description_html?.length);
                console.log('alt_tags:', newContent.alt_tags);
                console.log('url_handle:', newContent.url_handle);
                console.log('meta_title:', newContent.meta_title);
                console.log('meta_description:', newContent.meta_description);
                console.log('=== End Debug ===');

                // Capture generation metadata (sources, timing, etc.)
                if (newContent._generation_meta) {
                    setGenerationMeta(newContent._generation_meta);
                    console.log('=== Generation Sources ===');
                    console.log('Sources:', newContent._generation_meta.sources);
                    console.log('RAG chunks:', newContent._generation_meta.rag_chunks);
                    console.log('Web search used:', newContent._generation_meta.web_search_used);
                    console.log('Time:', newContent._generation_meta.generation_time_ms, 'ms');
                }

                // Capture multi-agent metadata if present
                if (newContent._multi_agent) {
                    setMultiAgentMeta(newContent._multi_agent);
                    console.log('=== Multi-Agent Consensus ===');
                    console.log('Mode:', newContent._multi_agent.mode);
                    console.log('Agents:', newContent._multi_agent.agents_used);
                    console.log('Consensus:', newContent._multi_agent.consensus_score + '%');
                }

                setContent({
                    h1_title: newContent.h1_title || '',
                    description_html: newContent.description_html || '',
                    alt_tags: Array.isArray(newContent.alt_tags) ? newContent.alt_tags.join('\n') : (newContent.alt_tags || ''),
                    compatible_vehicles: newContent.compatible_vehicles || '',
                    short_description: newContent.short_description || '',
                    meta_title: newContent.meta_title || '',
                    meta_description: newContent.meta_description || '',
                    url_handle: newContent.url_handle || '',
                    resumen: newContent.resumen || '',
                });
                alert(' Contenido generado con éxito!');

                // Store reasoning if available
                if (newContent.reasoning) {
                    setReasoning(newContent.reasoning);
                    console.log('=== AI Reasoning ===');
                    console.log(newContent.reasoning);
                }

                // Update imageAlts with generated alt_tags
                if (newContent.alt_tags && Array.isArray(newContent.alt_tags) && imageAlts.length > 0) {
                    const updatedAlts = [...imageAlts];
                    newContent.alt_tags.forEach((altTag: string, idx: number) => {
                        if (idx < updatedAlts.length) {
                            // Parse alt tag format: "filename.jpg | Alt text description"
                            const parts = altTag.split('|');
                            if (parts.length >= 2) {
                                const newAlt = parts.slice(1).join('|').trim();
                                updatedAlts[idx] = { ...updatedAlts[idx], alt: newAlt };
                            } else {
                                // Just use the whole string as alt if no | separator
                                updatedAlts[idx] = { ...updatedAlts[idx], alt: altTag.trim() };
                            }
                        }
                    });
                    setImageAlts(updatedAlts);
                    console.log('Updated imageAlts with generated alt tags');
                }
            }
        } catch (error: any) {
            console.error('Error generating content:', error);
            alert(`❌ Error al generar: ${error.message}`);
        } finally {
            setGenerating(false);
        }
    };

    const runAIAnalysis = async (forceRefresh: boolean = false) => {
        if (!product) return;
        setAnalyzing(true);
        try {
            // Step 1: Get aggregated analytics data
            console.log(`[Grok Analysis] Fetching product analytics... (forceRefresh: ${forceRefresh})`);
            const analytics = await productAPI.getProductAnalytics(product.id, 30);
            console.log('[Grok Analysis] Analytics:', analytics);

            // Warn if analytics data is stale
            if ((analytics as any).data_stale) {
                const hours = (analytics as any).last_sync_hours_ago;
                console.warn(`[Grok Analysis] Analytics data is stale (${hours}h old). Run sync for fresh data.`);
            }

            // Step 2: Send to AI for comprehensive analysis (with caching)
            console.log('[Grok Analysis] Checking cache or calling Grok AI...');
            const analysis = await productAPI.analyzeContentWithAI({
                product_id: product.id,
                title: analytics.title,
                description: content.description_html || shopifyData?.body_html || '',
                meta_title: content.meta_title || shopifyData?.meta_title || '',
                meta_description: content.meta_description || shopifyData?.meta_description || '',
                price: analytics.price,
                product_type: analytics.product_type || '',
                sold_30d: analytics.sold_30d,
                sold_90d: analytics.sold_90d,
                sold_365d: analytics.sold_365d,
                revenue_30d: analytics.revenue_30d,
                revenue_90d: analytics.revenue_90d,
                ga4_sessions: analytics.ga4_sessions,
                ga4_engagement_time: analytics.ga4_engagement_time,
                gsc_impressions: analytics.gsc_impressions,
                gsc_clicks: analytics.gsc_clicks,
                gsc_position: analytics.gsc_position,
                seo_score: analytics.seo_score,
                description_length: analytics.description_length,
                image_count: analytics.image_count,
                top_keywords: [],  // Could be populated from Search Console data
                vehicle_fitments: vehicleFitments.map(v => `${v.make?.[0]} ${v.modelo?.[0]} ${v.year_start}-${v.year_end}`),
                provider: selectedProvider,
                model_name: selectedModel,
            }, forceRefresh);

            console.log('[Grok Analysis] AI Response:', analysis);
            setAiAnalysis(analysis);
            setAnalysisCacheStatus({
                cached: analysis.cached,
                age: analysis.cache_age_hours || 0
            });

            // Show notification if served from cache
            if (analysis.cached && !forceRefresh) {
                console.log(`[Grok Analysis] Served from cache (${analysis.cache_age_hours?.toFixed(1)} hours old)`);
            }

            setShowAnalysisModal(true);

        } catch (error: any) {
            console.error('[Grok Analysis] Error:', error);
            alert(`❌ Error en análisis: ${error.message}`);
        } finally {
            setAnalyzing(false);
        }
    };

    const saveContent = async () => {
        if (!product) return;
        setSaving(true);
        try {
            // Transform image alts to dict for backend
            const imageAltsDict: Record<string, string> = {};
            imageAlts.forEach(img => {
                imageAltsDict[img.id.toString()] = img.alt;
            });

            await productAPI.updateProduct(product.id, {
                ...content,
                vehicle_fitments: vehicleFitments,
                image_alts: imageAltsDict,
                product_schema: productSchema
            });
            alert(' Producto guardado correctamente en Shopify y base de datos local');
        } catch (error) {
            console.error('Error saving product:', error);
            alert('❌ Error al guardar el producto: ' + (error instanceof Error ? error.message : String(error)));
        } finally {
            setSaving(false);
        }
    };

    // Save individual section
    const saveSection = async (sectionName: string, data: Partial<typeof content & { image_alts?: Record<string, string> }>) => {
        if (!product) return;
        setSavingSection(sectionName);
        try {
            await productAPI.updateProduct(product.id, data);
            // Brief success feedback
            console.log(` ${sectionName} saved`);
        } catch (error) {
            console.error(`Error saving ${sectionName}:`, error);
            alert(`❌ Error al guardar ${sectionName}: ` + (error instanceof Error ? error.message : String(error)));
        } finally {
            setSavingSection(null);
        }
    };

    // Theme classes
    const theme = {
        bg: darkMode ? 'bg-black' : 'bg-zinc-100',
        headerBg: darkMode ? 'bg-[#1a1a1a]' : 'bg-white',
        cardBg: darkMode ? 'bg-[#111]' : 'bg-white',
        text: darkMode ? 'text-white' : 'text-zinc-900',
        textSecondary: darkMode ? 'text-zinc-400' : 'text-zinc-600',
        textMuted: darkMode ? 'text-zinc-500' : 'text-zinc-400',
        border: darkMode ? 'border-zinc-800' : 'border-zinc-200',
        inputBg: darkMode ? 'bg-black' : 'bg-white',
    };

    if (loading) {
        return (
            <div className={`min-h-screen ${theme.bg} flex items-center justify-center`}>
                <div className="text-center">
                    <svg className="animate-spin size-10 text-[#F7B500] mx-auto mb-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <p className={theme.textMuted}>Cargando producto…</p>
                </div>
            </div>
        );
    }

    if (!product) {
        return (
            <div className={`min-h-screen ${theme.bg} flex items-center justify-center`}>
                <div className="text-center">
                    <p className={theme.text}>Producto no encontrado</p>
                    <Link href="/" className="text-[#F7B500] hover:underline mt-4 inline-block">← Volver</Link>
                </div>
            </div>
        );
    }

    return (
        <div className={`min-h-screen ${theme.bg} pt-16`}>
            {/* Back Link, Multi-Agent Toggle & Save Button */}
            <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link
                        href="/generate"
                        className="text-[#666666] hover:text-white transition-colors text-sm flex items-center gap-2"
                    >
                        ← Volver
                    </Link>
                    <MultiAgentToggle
                        enabled={multiAgentEnabled}
                        onChange={setMultiAgentEnabled}
                        variant="compact"
                    />
                </div>
                <button
                    onClick={saveContent}
                    disabled={saving}
                    className="flex items-center gap-2 px-6 py-2 bg-[#F7B500] text-black font-semibold hover:bg-[#ffc933] transition-all disabled:opacity-50 text-sm"
                >
                    {saving ? 'Guardando...' : 'Guardar'}
                </button>
            </div>

            <main className="max-w-7xl mx-auto px-6 py-8">
                {/* ========== PRODUCT METRICS DASHBOARD ========== */}
                {product && (
                    <ProductMetricsPanel
                        product={product}
                        shopifyData={shopifyData}
                        theme={theme}
                        darkMode={darkMode}
                    />
                )}

                {/* AI Deep Analysis Button */}
                {product && (
                    <div className="mb-6 bg-[#1a1a1a] border border-[#333333] rounded-lg p-4">
                        {/* Main Analysis Row */}
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-4">
                                <button
                                    onClick={() => aiAnalysis ? setShowAnalysisModal(true) : runAIAnalysis(false)}
                                    disabled={analyzing || !product}
                                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <span>{analyzing ? '⏳' : aiAnalysis ? '👁️ Ver Análisis' : '🧠 Análisis Profundo con Grok'}</span>
                                </button>

                                {/* Cache status indicator */}
                                {analysisCacheStatus && (
                                    <span className={`text-xs px-2 py-1 rounded ${analysisCacheStatus.cached ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'}`}>
                                        {analysisCacheStatus.cached
                                            ? `💾 Cache (${analysisCacheStatus.age.toFixed(1)}h)`
                                            : '⚡ Nuevo'}
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center gap-3">
                                {aiAnalysis && (
                                    <button
                                        onClick={() => runAIAnalysis(true)}
                                        disabled={analyzing}
                                        className="px-3 py-1.5 bg-[#F7B500]/20 text-[#F7B500] text-xs rounded hover:bg-[#F7B500]/30 transition-colors disabled:opacity-50"
                                        title="Forzar nuevo análisis (usa créditos API)"
                                    >
                                        {analyzing ? '⏳' : '🔄 Refrescar'}
                                    </button>
                                )}
                                <span className={`text-xs ${theme.textMuted}`}>
                                    SEO: {product?.seo_score || 0}% | Opportunity: {product?.opportunity_level || 'low'}
                                </span>
                            </div>
                        </div>

                        {/* Data Population Buttons Row */}
                        <div className="flex items-center gap-3 pt-3 border-t border-[#333333]">
                            <span className="text-xs text-zinc-500">📊 Poblar datos:</span>

                            <button
                                onClick={async () => {
                                    if (!product) return;
                                    setRefreshingData(true);
                                    try {
                                        // 1. Run visibility check
                                        const result = await productVisibilityAPI.checkVisibility(product.id, ['grok'], 5);
                                        console.log('[Visibility] Score:', result.score.score);

                                        // 2. Refresh the analysis to get updated data
                                        await runAIAnalysis(true);

                                        // 3. Show success
                                        alert(`✅ Datos actualizados!\n\nVisibilidad AI: ${result.score.score}/100 (${result.score.level})\nChecks realizados: ${result.checks_performed}\n\nEl análisis se ha refrescado con los nuevos datos.`);
                                    } catch (e: any) {
                                        alert(`❌ Error: ${e.message}`);
                                    } finally {
                                        setRefreshingData(false);
                                    }
                                }}
                                disabled={refreshingData || analyzing}
                                className="px-3 py-1.5 bg-emerald-500/20 text-emerald-400 text-xs rounded hover:bg-emerald-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                title="Verifica visibilidad AI y refresca el análisis completo"
                            >
                                {refreshingData ? '⏳ Actualizando...' : '🤖 Visibilidad AI'}
                            </button>

                            <button
                                onClick={async () => {
                                    setRefreshingData(true);
                                    try {
                                        // 1. Create snapshot
                                        const result = await snapshotAPI.createSnapshot();
                                        console.log('[Snapshot] Created:', result.created);

                                        // 2. Refresh the analysis to get updated trends
                                        await runAIAnalysis(true);

                                        // 3. Show success
                                        alert(`✅ Snapshot creado y análisis refrescado!\n\nProductos: ${result.total_products}\nCreados: ${result.created}\nSaltados: ${result.skipped}`);
                                    } catch (e: any) {
                                        alert(`❌ Error: ${e.message}`);
                                    } finally {
                                        setRefreshingData(false);
                                    }
                                }}
                                disabled={refreshingData || analyzing}
                                className="px-3 py-1.5 bg-blue-500/20 text-blue-400 text-xs rounded hover:bg-blue-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                title="Crea snapshot y refresca el análisis para ver trends"
                            >
                                {refreshingData ? '⏳ Actualizando...' : '📈 Crear Snapshot'}
                            </button>

                            <span className="text-xs text-zinc-600">
                                (Refresca automáticamente el análisis)
                            </span>
                        </div>
                    </div>
                )}

                {/* Persistent Grok Analysis Results Panel (v2 Enhanced) */}
                {aiAnalysis && (
                    <div className="mb-6 bg-gradient-to-r from-purple-900/20 to-blue-900/20 border border-purple-500/30 rounded-lg overflow-hidden">
                        {/* Header with Primary Issue */}
                        <div
                            className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-purple-500/10 transition-colors"
                            onClick={() => setShowAnalysisModal(true)}
                        >
                            <div className="flex items-center gap-3">
                                <span className="text-xl">🧠</span>
                                <div>
                                    <h3 className="text-white font-semibold text-sm">Análisis Grok v2</h3>
                                    {aiAnalysis.primary_issue && (
                                        <p className="text-xs text-yellow-400 mt-0.5">
                                            ⚠️ {aiAnalysis.primary_issue.type}: {aiAnalysis.primary_issue.description}
                                        </p>
                                    )}
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                {/* Mini score badges with v2 fields */}
                                <div className="flex gap-2">
                                    <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded">
                                        SEO: {aiAnalysis.seo_analysis?.score ?? 0}
                                    </span>
                                    <span className="px-2 py-1 bg-blue-500/20 text-blue-400 text-xs rounded">
                                        AEO: {aiAnalysis.aeo_analysis?.score ?? 0}
                                    </span>
                                    <span className="px-2 py-1 bg-purple-500/20 text-purple-400 text-xs rounded">
                                        GEO: {aiAnalysis.geo_analysis?.score ?? 0}
                                    </span>
                                </div>
                                {aiAnalysis.estimated_revenue_opportunity && (
                                    <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 text-xs rounded font-medium">
                                        +${aiAnalysis.estimated_revenue_opportunity.toLocaleString()}/mes
                                    </span>
                                )}
                                <button
                                    className="text-purple-400 hover:text-purple-300 text-sm"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setShowAnalysisModal(true);
                                    }}
                                >
                                    Ver Análisis →
                                </button>
                            </div>
                        </div>

                        {/* v2: AI Visibility — distinguishes "not measured yet" from a real 0% reading.
                            Previously this card always rendered 0/0/0 placeholders for any product without
                            a ProductVisibilitySnapshot row, which looked like a real measurement and biased
                            Grok's recommendations toward generic AEO additions. */}
                        <div className="px-4 py-2 border-t border-purple-500/20 bg-black/10">
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-xs text-zinc-400">🤖 Visibilidad en IA:</p>
                                {aiAnalysis.ai_visibility_status === 'fresh' && aiAnalysis.ai_visibility_age_days !== null && aiAnalysis.ai_visibility_age_days !== undefined && (
                                    <span className="text-[10px] text-zinc-500">
                                        Medido hace {aiAnalysis.ai_visibility_age_days}d
                                    </span>
                                )}
                                {aiAnalysis.ai_visibility_status === 'stale' && (
                                    <span className="text-[10px] text-yellow-500">
                                        ⚠️ Stale ({aiAnalysis.ai_visibility_age_days}d) — refresh recomendado
                                    </span>
                                )}
                            </div>
                            {aiAnalysis.ai_visibility_scores && (aiAnalysis.ai_visibility_status === 'fresh' || aiAnalysis.ai_visibility_status === 'stale') ? (
                                <div className="flex gap-3">
                                    {Object.entries(aiAnalysis.ai_visibility_scores).map(([llm, score]) => (
                                        <div key={llm} className="flex items-center gap-1.5">
                                            <span className="text-xs text-zinc-500 capitalize">{llm}:</span>
                                            <span className={`text-xs font-medium ${(score ?? 0) >= 70 ? 'text-green-400' : (score ?? 0) >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                                                {score ?? 0}%
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="flex items-center justify-between gap-3">
                                    <span className="text-xs text-zinc-500 italic">
                                        {aiAnalysis.ai_visibility_status === 'unknown'
                                            ? 'Error al leer la visibilidad'
                                            : 'Aún no se ha medido la visibilidad de este producto'}
                                    </span>
                                    <button
                                        onClick={runProductVisibilityCheck}
                                        disabled={isRunningVisibilityCheck}
                                        className="text-[11px] font-medium px-2 py-1 bg-purple-600/30 text-purple-300 border border-purple-500/40 hover:bg-purple-600/50 transition-all disabled:opacity-50"
                                    >
                                        {isRunningVisibilityCheck ? 'Midiendo…' : 'Medir ahora'}
                                    </button>
                                </div>
                            )}
                        </div>
                        {aiAnalysis.ai_visibility_status === 'not_measured' && (
                            <div className="px-4 py-1 text-[10px] text-zinc-600 italic bg-black/20">
                                Nota: Grok generó las recomendaciones SIN datos de visibilidad — no asume 0% por defecto.
                            </div>
                        )}

                        {/* v2: Benchmark Comparison Summary */}
                        {aiAnalysis.performance_vs_benchmark && aiAnalysis.performance_vs_benchmark.metrics && (
                            <div className="px-4 py-2 border-t border-purple-500/20 bg-black/10">
                                <p className="text-xs text-zinc-400 mb-2">📊 vs Categoría ({aiAnalysis.performance_vs_benchmark.category}):</p>
                                <div className="grid grid-cols-4 gap-2 text-xs">
                                    {Object.entries(aiAnalysis.performance_vs_benchmark.metrics).map(([metric, data]) => {
                                        const isBetter = metric === 'position'
                                            ? data.product < data.category_avg
                                            : data.product > data.category_avg;
                                        const diff = metric === 'position'
                                            ? ((data.category_avg - data.product) / data.category_avg * 100).toFixed(0)
                                            : ((data.product - data.category_avg) / data.category_avg * 100).toFixed(0);
                                        return (
                                            <div key={metric} className="flex flex-col">
                                                <span className="text-zinc-500 capitalize">{metric}</span>
                                                <span className={isBetter ? 'text-green-400' : 'text-red-400'}>
                                                    {data.product.toFixed(1)} ({isBetter ? '+' : ''}{diff}%)
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}

                        {/* v2.1: Historical Trend Indicators */}
                        {aiAnalysis.trend_indicators && (
                            <div className="px-4 py-2 border-t border-purple-500/20 bg-black/10">
                                <p className="text-xs text-zinc-400 mb-2">📈 Tendencias (7d vs 30d):</p>
                                <div className="flex gap-4 text-xs">
                                    {Object.entries(aiAnalysis.trend_indicators).map(([key, value]) => (
                                        <div key={key} className="flex items-center gap-1.5">
                                            <span className="text-zinc-500 capitalize">{key}:</span>
                                            <span className={`font-medium ${String(value).includes('↗') ? 'text-green-400' :
                                                String(value).includes('↘') ? 'text-red-400' :
                                                    'text-zinc-400'
                                                }`}>
                                                {String(value)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* v2.1: Top GSC Opportunity Queries */}
                        {aiAnalysis.top_opportunity_queries && aiAnalysis.top_opportunity_queries.length > 0 && (
                            <div className="px-4 py-2 border-t border-purple-500/20 bg-black/10">
                                <p className="text-xs text-zinc-400 mb-2">🔍 Queries con Oportunidad:</p>
                                <div className="space-y-1 max-h-24 overflow-y-auto">
                                    {aiAnalysis.top_opportunity_queries.slice(0, 4).map((q, idx) => (
                                        <div key={idx} className="flex items-center justify-between text-xs">
                                            <span className="text-zinc-300 truncate max-w-[140px]">{q.query}</span>
                                            <div className="flex items-center gap-2">
                                                <span className="text-zinc-500">{q.impressions.toLocaleString()} imp</span>
                                                <span className={`px-1.5 py-0.5 rounded text-[10px] ${q.opportunity === 'HIGH' ? 'bg-red-500/20 text-red-400' :
                                                    q.opportunity === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                                                        'bg-zinc-500/20 text-zinc-400'
                                                    }`}>
                                                    {q.opportunity}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Quick priority actions preview with revenue context */}
                        {(aiAnalysis.priority_actions ?? []).length > 0 && (
                            <div className="px-4 py-3 border-t border-purple-500/20 bg-black/20">
                                <p className="text-xs text-purple-400 mb-2 font-medium">⚡ Acciones Prioritarias:</p>
                                <ul className="space-y-1">
                                    {(aiAnalysis.priority_actions ?? []).slice(0, 3).map((action, idx) => (
                                        <li key={idx} className="text-sm text-zinc-300 flex items-start gap-2">
                                            <span className="text-purple-400">{idx + 1}.</span>
                                            {action}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}


                {/* Multi-Agent Consensus Display */}
                {multiAgentMeta && (
                    <div className="mb-6">
                        <ConsensusDisplay metadata={multiAgentMeta} variant="full" />
                    </div>
                )}

                {/* ========== UNIFIED AI GENERATION CONTAINER ========== */}
                <div className={`mb-8 border-2 border-[#F7B500] ${theme.cardBg} overflow-hidden shadow-lg shadow-[#F7B500]/10`}>
                    {/* Header */}
                    <div className="px-6 py-4 bg-gradient-to-r from-[#F7B500]/20 to-transparent border-b border-[#F7B500]/30">
                        <h2 className="text-lg font-semibold text-[#F7B500] flex items-center gap-2">
                            Generador de Contenido IA
                            {generating && <span className="text-sm font-normal text-zinc-400 animate-pulse">Generando…</span>}
                        </h2>
                    </div>

                    <div className="p-6">
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div className="lg:col-span-1 space-y-4">
                                {/* Template Selection */}
                                <label className="block">
                                    <span className={`block text-xs font-medium ${theme.textMuted} uppercase mb-2`}>
                                        Plantilla de Prompt
                                    </span>
                                    <select
                                        value={selectedTemplate}
                                        onChange={(e) => setSelectedTemplate(e.target.value)}
                                        className={`w-full px-3 py-2 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] outline-none text-sm transition-all`}
                                    >
                                        <option value="">Seleccionar plantilla…</option>
                                        {templates.map(t => (
                                            <option key={t.id} value={t.id}>{t.name}</option>
                                        ))}
                                    </select>
                                </label>

                                {/* Model Selection */}
                                <label className="block">
                                    <span className={`block text-xs font-medium ${theme.textMuted} uppercase mb-2`}>
                                        Modelo de IA
                                    </span>
                                    <select
                                        value={`${selectedProvider}:${selectedModel}`}
                                        onChange={(e) => {
                                            const [p, m] = e.target.value.split(':');
                                            setSelectedProvider(p);
                                            setSelectedModel(m);
                                        }}
                                        className={`w-full px-3 py-2 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] outline-none text-sm transition-all`}
                                    >
                                        <optgroup label="X.AI (Grok)">
                                            <option value="grok:grok-4.3">Grok 4.3 (1M context)</option>
                                            <option value="grok:grok-4.20-0309-reasoning">Grok 4.20 (Reasoning, 2M)</option>
                                            <option value="grok:grok-4.20-0309-non-reasoning">Grok 4.20 (Non-Reasoning, 2M)</option>
                                            <option value="grok:grok-4-1-fast-reasoning">Grok 4.1 Fast (Reasoning)</option>
                                            <option value="grok:grok-4-1-fast-non-reasoning">Grok 4.1 Fast (General)</option>
                                            <option value="grok:grok-code-fast-1">Grok Code Fast 1</option>
                                            <option value="grok:grok-3">Grok 3 (Standard)</option>
                                        </optgroup>
                                        <optgroup label="OpenAI (GPT)">
                                            <option value="openai:gpt-5">GPT-5 (Flagship)</option>
                                            <option value="openai:gpt-4.5-turbo">GPT-4.5 Turbo (SOTA)</option>
                                            <option value="openai:gpt-5-mini">GPT-5 Mini (Fast)</option>
                                        </optgroup>
                                        <optgroup label="Anthropic (Claude)">
                                            <option value="anthropic:claude-sonnet-4-5-20250929">Claude 4.5 Sonnet</option>
                                            <option value="anthropic:claude-opus-4-5-20251101">Claude 4.5 Opus</option>
                                            <option value="anthropic:claude-haiku-4-5-20251001">Claude 4.5 Haiku</option>
                                        </optgroup>
                                        <optgroup label="Mistral AI">
                                            <option value="mistral:mistral-large-latest">Mistral Large (Flagship)</option>
                                            <option value="mistral:mistral-small-latest">Mistral Small (Fast)</option>
                                            <option value="mistral:codestral-latest">Codestral (Técnico)</option>
                                        </optgroup>
                                        <optgroup label="MiniMax (Reasoning)">
                                            <option value="minimax:minimax-text-01">MiniMax-Text-01 (Deep Think)</option>
                                        </optgroup>
                                        <optgroup label="Ollama (Local)">
                                            <option value="ollama:llama3.2:latest">Llama 3.2</option>
                                            <option value="ollama:mistral:latest">Mistral (Local)</option>
                                        </optgroup>
                                    </select>
                                    <p className="mt-1 text-[10px] text-zinc-500">
                                        {selectedProvider === 'minimax' ? '💡 MiniMax usa razonamiento profundo (tarda más).' :
                                            selectedProvider === 'grok' && selectedModel === 'grok-4.3' ? '✨ Grok 4.3 — 1M contexto, último modelo X.AI ($1.25/$2.50 por M tokens).' :
                                            selectedProvider === 'grok' && selectedModel.includes('4.20') ? '🧪 Grok 4.20 — 2M contexto, razonamiento avanzado.' :
                                            selectedProvider === 'grok' ? '🚀 Grok 4.1 tiene razonamiento rápido y 2M de contexto.' :
                                                selectedProvider === 'mistral' ? '🇪🇺 Mistral es el líder europeo en eficiencia.' :
                                                    selectedProvider === 'openai' ? '🌟 GPT-5 es el modelo de inteligencia máxima de OpenAI.' :
                                                        selectedProvider === 'anthropic' ? '🎭 Claude 4.5 ofrece una escritura excepcional y precisión.' : ''}
                                    </p>
                                </label>

                                {/* Library Selection */}
                                <div>
                                    <label className={`block text-xs font-medium ${theme.textMuted} uppercase mb-2 flex justify-between`}>
                                        Librerías RAG
                                        <span className="text-[#F7B500] normal-case">{selectedLibraries.length} seleccionadas</span>
                                    </label>
                                    <div className={`max-h-[180px] overflow-y-auto space-y-1 pr-1 ${theme.inputBg} p-2 border ${theme.border}`}>
                                        {libraries.length > 0 ? (
                                            libraries.map(lib => (
                                                <label
                                                    key={lib.id}
                                                    className={`flex items-center gap-2 p-2  cursor-pointer transition-colors text-sm ${selectedLibraries.includes(lib.id)
                                                        ? 'bg-[#F7B500]/20 border-[#F7B500]/50'
                                                        : `hover:bg-white/5`
                                                        }`}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={selectedLibraries.includes(lib.id)}
                                                        onChange={(e) => {
                                                            if (e.target.checked) {
                                                                setSelectedLibraries([...selectedLibraries, lib.id]);
                                                            } else {
                                                                setSelectedLibraries(selectedLibraries.filter(id => id !== lib.id));
                                                            }
                                                        }}
                                                        className="size-4 border-zinc-600 bg-zinc-800 text-[#F7B500] focus:ring-[#F7B500]"
                                                    />
                                                    <span className={theme.text}>{lib.name_es || lib.name}</span>
                                                    <span className={`text-[10px] ${theme.textMuted}`}>({lib.document_count})</span>
                                                </label>
                                            ))
                                        ) : (
                                            <p className={`text-xs ${theme.textMuted} py-2 text-center italic`}>No hay librerías activas</p>
                                        )}
                                    </div>
                                    {selectedLibraries.length > 0 && (
                                        <button
                                            onClick={() => setSelectedLibraries([])}
                                            className={`mt-2 text-[10px] ${theme.textMuted} hover:text-[#F7B500] transition-colors`}
                                        >
                                            Limpiar selección
                                        </button>
                                    )}
                                </div>
                            </div>


                            {/* RIGHT: Generation Output */}
                            <div className="lg:col-span-2">
                                <p className={`block text-xs font-medium ${theme.textMuted} uppercase mb-2`}>
                                    Salida de la IA
                                </p>
                                <div className={`${theme.inputBg} border ${theme.border} p-4 min-h-[220px] max-h-[300px] overflow-y-auto`}>
                                    {generating ? (
                                        <div className="space-y-3">
                                            <div className="flex items-center gap-2 text-[#F7B500]">
                                                <svg className="animate-spin size-4" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                                </svg>
                                                <span className="text-sm font-medium">Generando contenido…</span>
                                            </div>
                                            {reasoning && (
                                                <div className="mt-2">
                                                    <p className="text-xs text-purple-400 mb-1"> Razonamiento:</p>
                                                    <pre className="text-xs text-zinc-400 whitespace-pre-wrap font-mono bg-black/20 p-2 max-h-32 overflow-y-auto">
                                                        {reasoning.substring(0, 500)}{reasoning.length > 500 ? '...' : ''}
                                                    </pre>
                                                </div>
                                            )}
                                        </div>
                                    ) : reasoning ? (
                                        <div className="space-y-3">
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                {/* Reasoning */}
                                                <div>
                                                    <p className="text-xs text-purple-400 font-medium mb-1"> Razonamiento</p>
                                                    <pre className="text-[11px] text-zinc-400 whitespace-pre-wrap font-mono bg-black/20 p-2 max-h-40 overflow-y-auto">
                                                        {reasoning.substring(0, 800)}{reasoning.length > 800 ? '...' : ''}
                                                    </pre>
                                                </div>
                                                {/* Results */}
                                                <div>
                                                    <p className="text-xs text-green-400 font-medium mb-1"> Resultado</p>
                                                    <div className="text-[11px] text-zinc-300 space-y-1 bg-black/20 p-2 max-h-40 overflow-y-auto">
                                                        <p><span className="text-yellow-400">H1:</span> {content.h1_title || 'N/A'}</p>
                                                        <p><span className="text-yellow-400">Meta:</span> {content.meta_title?.substring(0, 50) || 'N/A'}...</p>
                                                        <p><span className="text-yellow-400">URL:</span> {content.url_handle || 'N/A'}</p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className={`flex flex-col items-center justify-center h-full py-8 ${theme.textMuted}`}>
                                            <span className="text-4xl mb-3"></span>
                                            <p className="text-sm">Configura las opciones y genera contenido</p>
                                            <p className="text-xs mt-1">Selecciona librerías RAG para mejorar la calidad</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Sources Panel - Shows what resources were used */}
                        {
                            generationMeta && generationMeta.sources.length > 0 && (
                                <div className={`${theme.cardBg} border ${theme.border} p-4 mt-4`}>
                                    <div className="flex items-center justify-between mb-3">
                                        <h4 className={`font-semibold ${theme.text} text-sm flex items-center gap-2`}>
                                            <span className="text-lg">📚</span>
                                            FUENTES UTILIZADAS
                                        </h4>
                                        <div className={`text-xs ${theme.textMuted} flex items-center gap-4`}>
                                            <span>⏱️ {(generationMeta.generation_time_ms / 1000).toFixed(1)}s</span>
                                            <span>🤖 {generationMeta.model}</span>
                                            {generationMeta.web_search_used && (
                                                <span className="text-green-400">🌐 Web Search</span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="space-y-2 max-h-40 overflow-y-auto">
                                        {generationMeta.sources.map((source, idx) => (
                                            <div
                                                key={idx}
                                                className={`flex items-center gap-2 text-xs ${theme.textMuted} py-1 px-2 ${theme.inputBg} border ${theme.border}`}
                                            >
                                                {source.type === 'rag' ? (
                                                    <>
                                                        <span className="text-yellow-400">📄</span>
                                                        <span className="flex-1 truncate">{source.file}</span>
                                                        <span className="text-yellow-400 font-mono">({source.chunks} chunks)</span>
                                                        {source.supplier && (
                                                            <span className={`px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-[10px]`}>
                                                                {source.supplier}
                                                            </span>
                                                        )}
                                                    </>
                                                ) : (
                                                    <>
                                                        <span className="text-green-400">🌐</span>
                                                        <a
                                                            href={source.url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="flex-1 truncate text-green-400 hover:underline"
                                                        >
                                                            {source.url}
                                                        </a>
                                                    </>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                    <div className={`mt-2 pt-2 border-t ${theme.border} flex justify-between text-xs ${theme.textMuted}`}>
                                        <span>📊 {generationMeta.rag_chunks} chunks RAG</span>
                                        <span className="font-mono text-[10px]">#{generationMeta.prompt_hash}</span>
                                    </div>
                                </div>
                            )
                        }

                        {/* Generate Button - Full Width */}
                        {/* Analysis Insights Toggle */}
                        {aiAnalysis && (
                            <div className="mt-4 p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                                <label className="flex items-center gap-3 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={useAnalysisInsights}
                                        onChange={(e) => setUseAnalysisInsights(e.target.checked)}
                                        className="size-5 rounded border-purple-500 text-purple-500 focus:ring-purple-500 focus:ring-offset-0 bg-transparent"
                                    />
                                    <div>
                                        <span className="text-sm font-medium text-purple-300">
                                            🧠 Usar insights del Análisis Grok
                                        </span>
                                        <p className="text-xs text-purple-400/70 mt-0.5">
                                            Incluye recomendaciones, keywords objetivo y contenido sugerido en la generación
                                        </p>
                                    </div>
                                </label>
                                {useAnalysisInsights && aiAnalysis.primary_issue && (
                                    <div className="mt-2 pt-2 border-t border-purple-500/20 text-xs text-purple-300">
                                        <span className="text-purple-400">Issue detectado:</span> {aiAnalysis.primary_issue.type} - {aiAnalysis.primary_issue.description}
                                    </div>
                                )}
                            </div>
                        )}

                        <button
                            onClick={generateContent}
                            disabled={generating}
                            className="w-full mt-6 py-4 bg-gradient-to-r from-[#F7B500] to-[#ffc933] text-black font-bold text-lg hover:from-[#ffc933] hover:to-[#F7B500] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-[#F7B500]/20 flex items-center justify-center gap-3"
                        >
                            {generating ? (
                                <>
                                    <svg className="animate-spin size-5" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                    Generando Contenido SEO...
                                </>
                            ) : (
                                <>
                                    Generar Contenido con IA
                                </>
                            )}
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left Column - Main Content */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* 1. H1 Title */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-3">
                                <p className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-2 py-1">1</span>
                                    H1 TÍTULO
                                </p>
                                <div className="flex items-center gap-3">
                                    <CharCounter value={content.h1_title} min={50} max={100} softMax={60} />
                                    <SaveButton section="title" data={{ h1_title: content.h1_title }} savingSection={savingSection} onSave={saveSection} />
                                </div>
                            </div>
                            <input
                                type="text"
                                value={content.h1_title}
                                onChange={(e) => setContent({ ...content, h1_title: e.target.value })}
                                placeholder="Título principal del producto (ideal: 50-60 caracteres, máx: 100)"
                                maxLength={100}
                                className={`w-full px-4 py-3 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-colors`}
                            />
                            <p className={`text-xs ${theme.textMuted} mt-2`}>
                                💡 <strong>Recomendado:</strong> 50-60 caracteres para mejor SEO (consistente con Meta Title).
                                <span className="text-yellow-500"> Máximo {content.h1_title?.length > 60 ? '100' : '100'} caracteres permitido por sistema.</span>
                            </p>
                        </div>

                        {/* 2. Description HTML */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-3">
                                <p className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-2 py-1">2</span>
                                    DESCRIPCIÓN HTML
                                </p>
                                <div className="flex items-center gap-2">
                                    <span className={`text-xs ${theme.textMuted}`}>{content.description_html.length} chars</span>
                                    <div className={`flex border ${theme.border} overflow-hidden`}>
                                        <button
                                            onClick={() => setDescriptionView('preview')}
                                            className={`px-3 py-1 text-xs font-medium transition-colors ${descriptionView === 'preview' ? 'bg-[#F7B500] text-black' : `${theme.textSecondary} hover:${theme.text}`}`}
                                        >
                                            👁 Vista previa
                                        </button>
                                        <button
                                            onClick={() => setDescriptionView('html')}
                                            className={`px-3 py-1 text-xs font-medium transition-colors ${descriptionView === 'html' ? 'bg-[#F7B500] text-black' : `${theme.textSecondary} hover:${theme.text}`}`}
                                        >
                                            &lt;/&gt; HTML
                                        </button>
                                    </div>
                                    <SaveButton section="description" data={{ description_html: content.description_html }} savingSection={savingSection} onSave={saveSection} />
                                </div>
                            </div>

                            {descriptionView === 'html' ? (
                                <textarea
                                    value={content.description_html}
                                    onChange={(e) => setContent({ ...content, description_html: e.target.value })}
                                    placeholder="<h2>¿Título gancho?</h2>&#10;<p>Descripción del producto...</p>&#10;<ul><li>Característica 1</li></ul>"
                                    rows={15}
                                    className={`w-full px-4 py-3 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-colors font-mono text-sm`}
                                />
                            ) : (
                                <div
                                    className={`w-full px-4 py-3 ${theme.inputBg} border ${theme.border} ${theme.text} min-h-[300px] max-h-[500px] overflow-auto prose prose-sm ${darkMode ? 'prose-invert' : ''}`}
                                    dangerouslySetInnerHTML={{ __html: content.description_html || '<p class="text-zinc-500 italic">Sin descripción...</p>' }}
                                />
                            )}
                            <p className={`text-xs ${theme.textMuted} mt-2`}>
                                {descriptionView === 'html' ? 'Edita el código HTML directamente' : 'Vista previa del contenido renderizado'}
                            </p>
                        </div>

                        {/* 3. Alt Tags - Image by Image Editor */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-4">
                                <p className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-2 py-1">3</span>
                                    ALT TAGS DE IMÁGENES
                                </p>
                                <div className="flex items-center gap-3">
                                    <span className={`text-xs ${theme.textMuted}`}>
                                        {imageAlts.filter(img => img.alt.trim()).length}/{imageAlts.length} con alt
                                    </span>
                                    <SaveButton
                                        section="image_alts"
                                        data={{ image_alts: Object.fromEntries(imageAlts.map(img => [img.id.toString(), img.alt])) }}
                                        savingSection={savingSection}
                                        onSave={saveSection}
                                    />
                                </div>
                            </div>

                            {imageAlts.length > 0 ? (
                                <div className="space-y-3">
                                    {imageAlts.map((img, idx) => (
                                        <div key={img.id} className={`flex gap-3 p-3 ${darkMode ? 'bg-black/30' : 'bg-zinc-50'}`}>
                                            <div className="relative flex-shrink-0">
                                                <img
                                                    src={img.src}
                                                    alt={img.alt || img.filename}
                                                    className="size-20 object-cover border border-zinc-600"
                                                />
                                                <span className="absolute -top-1 -left-1 bg-[#F7B500] text-black text-[10px] font-bold size-5 flex items-center justify-center">
                                                    {idx + 1}
                                                </span>
                                            </div>
                                            <div className="flex-1 min-w-0 space-y-2">
                                                {/* Filename */}
                                                <label className="block">
                                                    <span className={`text-[10px] ${theme.textMuted} uppercase`}>Nombre archivo</span>
                                                    <input
                                                        type="text"
                                                        value={img.newFilename}
                                                        onChange={(e) => {
                                                            const newAlts = [...imageAlts];
                                                            newAlts[idx] = { ...img, newFilename: e.target.value };
                                                            setImageAlts(newAlts);
                                                        }}
                                                        placeholder={img.filename}
                                                        className={`w-full px-2 py-1 text-xs ${theme.inputBg} border ${img.newFilename !== img.filename ? 'border-yellow-500/50' : theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none font-mono`}
                                                    />
                                                </label>
                                                {/* Alt Text */}
                                                <label className="block">
                                                    <span className={`text-[10px] ${theme.textMuted} uppercase`}>Texto alternativo</span>
                                                    <input
                                                        type="text"
                                                        value={img.alt}
                                                        onChange={(e) => {
                                                            const newAlts = [...imageAlts];
                                                            newAlts[idx] = { ...img, alt: e.target.value };
                                                            setImageAlts(newAlts);
                                                        }}
                                                        placeholder="Descripción SEO de la imagen..."
                                                        className={`w-full px-2 py-1 text-xs ${theme.inputBg} border ${img.alt.trim() ? 'border-green-500/50' : 'border-red-500/50'} ${theme.text} focus:border-[#F7B500] focus:outline-none`}
                                                    />
                                                </label>
                                            </div>
                                            <div className="flex flex-col items-center justify-center gap-1">
                                                {img.alt.trim() ? (
                                                    <span className="text-green-500 text-sm" title="Alt OK"></span>
                                                ) : (
                                                    <span className="text-red-400 text-sm" title="Falta alt"></span>
                                                )}
                                                {img.newFilename !== img.filename && (
                                                    <span className="text-yellow-500 text-sm" title="Nombre modificado">✎</span>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className={`text-center py-8 ${theme.textMuted}`}>
                                    <p> Cargando imágenes…</p>
                                </div>
                            )}

                            <p className={`text-xs ${theme.textMuted} mt-3`}>
                                Edita el texto alternativo de cada imagen para SEO. Las imágenes sin alt afectan el posicionamiento.
                            </p>
                        </div>

                        {/* ========== COMPLETE PRODUCT PAGE PREVIEW ========== */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-4">
                                <p className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-2 py-1">PREVIEW</span>
                                    VISTA PREVIA DE PÁGINA COMPLETA
                                </p>
                                <div className="flex items-center gap-3">
                                    <button
                                        onClick={() => setPreviewMode(previewMode === 'edit' ? 'preview' : 'edit')}
                                        className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${previewMode === 'preview'
                                            ? 'bg-[#F7B500] text-black'
                                            : 'bg-[#1a1a1a] text-zinc-300 border border-[#3a3a3a] hover:border-[#F7B500]'
                                            }`}
                                    >
                                        {previewMode === 'edit' ? '👁 Ver Preview' : '✏️ Volver a Editar'}
                                    </button>
                                </div>
                            </div>

                            {previewMode === 'preview' ? (
                                <div className="space-y-6">
                                    {/* Product Title Preview */}
                                    <div className="border-b border-[#3a3a3a] pb-4">
                                        <h1 className="text-2xl font-semibold text-white leading-tight">
                                            {content.h1_title || 'Sin título H1'}
                                        </h1>
                                        {shopifyData && (
                                            <p className="text-zinc-400 mt-1 text-sm">
                                                SKU: <span className="text-[#F7B500]">{shopifyData.sku}</span>
                                                {shopifyData.price && (
                                                    <> | <span className="text-white font-semibold">${shopifyData.price} MXN</span></>
                                                )}
                                            </p>
                                        )}
                                    </div>

                                    {/* Product Images Grid Preview */}
                                    <div className="grid grid-cols-4 gap-2">
                                        {imageAlts.slice(0, 4).map((img, idx) => (
                                            <div key={img.id} className="relative aspect-square bg-[#0a0a0a] border border-[#3a3a3a]">
                                                <img
                                                    src={img.src}
                                                    alt={img.alt || img.filename}
                                                    className="size-full object-cover"
                                                />
                                                <span className="absolute bottom-1 left-1 bg-black/70 text-white text-[10px] px-1">
                                                    {idx + 1}
                                                </span>
                                            </div>
                                        ))}
                                        {imageAlts.length === 0 && (
                                            <div className="col-span-4 text-center py-8 text-zinc-500 border border-dashed border-[#3a3a3a]">
                                                No hay imágenes cargadas
                                            </div>
                                        )}
                                    </div>

                                    {/* Short Description Preview */}
                                    {content.short_description && (
                                        <div className="bg-[#0a0a0a] p-4 border-l-2 border-[#F7B500]">
                                            <p className="text-zinc-300 text-sm leading-relaxed">
                                                {content.short_description}
                                            </p>
                                        </div>
                                    )}

                                    {/* Full Description Preview */}
                                    <div className="prose prose-invert prose-sm max-w-none">
                                        <div dangerouslySetInnerHTML={{
                                            __html: content.description_html ||
                                                '<p class="text-zinc-500 italic">Sin descripción generada...</p>'
                                        }} />
                                    </div>

                                    {/* Vehicle Fitment Preview */}
                                    {vehicleFitments.length > 0 && (
                                        <div className="bg-[#0a0a0a] p-4 border border-[#3a3a3a]">
                                            <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                                                <span className="text-[#F7B500]">🚗</span>
                                                Compatibilidad Vehicular
                                            </h3>
                                            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                                                {vehicleFitments.slice(0, 6).map((f, idx) => (
                                                    <div key={idx} className="bg-[#1a1a1a] p-2 text-xs border border-[#3a3a3a]">
                                                        <span className="text-white font-medium">{f.make.join(', ')}</span>
                                                        <span className="text-zinc-400"> {f.modelo.join('/')}</span>
                                                        <div className="text-zinc-500 mt-1">
                                                            {f.year_start}-{f.year_end}
                                                            {f.transmission_model && ` | ${f.transmission_model}`}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                            {vehicleFitments.length > 6 && (
                                                <p className="text-zinc-500 text-xs mt-2 text-center">
                                                    +{vehicleFitments.length - 6} vehículos más…
                                                </p>
                                            )}
                                        </div>
                                    )}

                                    {/* Compatible Vehicles Text */}
                                    {content.compatible_vehicles && (
                                        <div className="text-zinc-400 text-sm">
                                            <strong className="text-white">Vehículos compatibles:</strong> {content.compatible_vehicles}
                                        </div>
                                    )}

                                    {/* Resumen / Ficha Técnica Preview */}
                                    {content.resumen && (
                                        <div className="bg-[#0a0a0a] p-4 border border-[#3a3a3a]">
                                            <div
                                                className="text-sm [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-[#3a3a3a] [&_th]:border [&_th]:border-[#3a3a3a] [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_h4]:text-[#F7B500] [&_h4]:font-bold [&_h4]:mb-2 [&_tr:nth-child(odd)]:bg-[#1a1a1a]"
                                                dangerouslySetInnerHTML={{ __html: content.resumen }}
                                            />
                                        </div>
                                    )}

                                    {/* SEO Meta Preview */}
                                    <div className="bg-[#0a0a0a] p-4 border border-[#3a3a3a] text-sm">
                                        <h4 className="text-zinc-400 mb-2 text-xs uppercase tracking-wide">Vista previa en motores de búsqueda</h4>
                                        <div className="space-y-1">
                                            <div className="text-blue-400 hover:underline cursor-pointer">
                                                {content.meta_title || content.h1_title || 'Título SEO'}
                                            </div>
                                            <div className="text-green-600 text-xs">
                                                example-store.com/products/{content.url_handle || 'producto'}
                                            </div>
                                            <div className="text-zinc-400 text-xs">
                                                {content.meta_description || 'Descripción meta para motores de búsqueda...'}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Generation Sources Preview */}
                                    {generationMeta && generationMeta.sources.length > 0 && (
                                        <div className="bg-[#1a1a1a] p-4 border border-[#3a3a3a]">
                                            <h4 className="text-[#F7B500] text-xs uppercase tracking-wide mb-2 flex items-center gap-2">
                                                <span>📚</span> Fuentes utilizadas
                                            </h4>
                                            <div className="space-y-1 max-h-32 overflow-y-auto">
                                                {generationMeta.sources.map((source, idx) => (
                                                    <div key={idx} className="text-xs text-zinc-400 flex items-center gap-2">
                                                        {source.type === 'rag' ? (
                                                            <>
                                                                <span className="text-yellow-500">📄</span>
                                                                <span className="truncate">{source.file}</span>
                                                                <span className="text-yellow-500">({source.chunks} chunks)</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <span className="text-green-500">🌐</span>
                                                                <span className="truncate">{source.url}</span>
                                                            </>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                            <div className="text-xs text-zinc-500 mt-2 flex items-center gap-4">
                                                <span>⏱️ {(generationMeta.generation_time_ms / 1000).toFixed(1)}s</span>
                                                <span>🤖 {generationMeta.model}</span>
                                                {generationMeta.web_search_used && <span className="text-green-400">Web Search</span>}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className={`text-center py-12 border border-dashed ${theme.border} ${theme.textMuted}`}>
                                    <span className="text-4xl mb-4 block">👁</span>
                                    <p className="text-sm">Haz clic en "Ver Preview" para ver la página completa del producto</p>
                                    <p className="text-xs mt-2">Podrás ver cómo quedó el título, descripción, imágenes y SEO</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right Column - Sidebar */}
                    <div className="space-y-6">
                        {/* Product Info */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <h3 className={`font-semibold ${theme.text} mb-4`}>Información del Producto</h3>

                            {loadingShopify && (
                                <div className="flex items-center gap-2 mb-4 text-[#F7B500]">
                                    <svg className="animate-spin size-4" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                    <span className="text-sm">Cargando datos de Shopify…</span>
                                </div>
                            )}

                            <div className="space-y-3">
                                <div className={`flex justify-between text-sm`}>
                                    <span className={theme.textMuted}>Shopify ID</span>
                                    <span className={`${theme.textSecondary} font-mono`}>{product.shopify_id}</span>
                                </div>
                                <div className={`flex justify-between text-sm`}>
                                    <span className={theme.textMuted}>SKU</span>
                                    <span className={`text-[#F7B500] font-mono`}>{product.sku || '—'}</span>
                                </div>
                                {shopifyData && (
                                    <>
                                        <div className={`flex justify-between text-sm`}>
                                            <span className={theme.textMuted}>Precio</span>
                                            <span className={theme.text}>${shopifyData.price} MXN</span>
                                        </div>
                                        <div className={`flex justify-between text-sm`}>
                                            <span className={theme.textMuted}>Tipo</span>
                                            <span className={theme.textSecondary}>{shopifyData.product_type || '—'}</span>
                                        </div>
                                        <div className={`flex justify-between text-sm`}>
                                            <span className={theme.textMuted}>Vendor</span>
                                            <span className={theme.textSecondary}>{shopifyData.vendor || '—'}</span>
                                        </div>
                                        <div className={`flex justify-between text-sm`}>
                                            <span className={theme.textMuted}>Estado</span>
                                            <span className={`px-2 py-0.5 text-xs ${shopifyData.status === 'active' ? 'bg-green-500/20 text-green-500' : 'bg-zinc-500/20 text-zinc-400'}`}>
                                                {shopifyData.status}
                                            </span>
                                        </div>
                                    </>
                                )}
                                <div className={`flex justify-between text-sm`}>
                                    <span className={theme.textMuted}>Imágenes</span>
                                    <span className={theme.text}> {shopifyData?.image_count || product.image_count}</span>
                                </div>
                                <div className={`pt-3 border-t ${theme.border}`}>
                                    <a
                                        href={`https://admin.shopify.com/store/your-store/products/${product.shopify_id}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-[#F7B500] hover:underline text-sm"
                                    >
                                        Ver en Shopify ↗
                                    </a>
                                </div>
                            </div>
                        </div>

                        {/* 4. Vehicle Fitment - Summary Card */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-3">
                                <p className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-2 py-1">4</span>
                                    VEHICLE FITMENT
                                </p>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={async () => {
                                            if (!product) return;
                                            setRefreshingFitments(true);
                                            try {
                                                const result = await productAPI.refreshFitments(product.id.toString());
                                                setVehicleFitments(result.vehicle_fitments);
                                                alert(` ${result.message}`);
                                            } catch (error) {
                                                console.error('Failed to refresh fitments:', error);
                                                alert('Error al refrescar fitments de Shopify');
                                            } finally {
                                                setRefreshingFitments(false);
                                            }
                                        }}
                                        disabled={refreshingFitments}
                                        className={`text-xs px-2 py-1.5 border ${theme.border} hover:border-[#F7B500] transition-colors ${theme.text} disabled:opacity-50`}
                                        title="Refrescar desde Shopify"
                                    >
                                        {refreshingFitments ? '' : ''}
                                    </button>
                                    <button
                                        onClick={() => setShowFitmentModal(true)}
                                        className="text-xs px-3 py-1.5 bg-[#F7B500] text-black hover:bg-[#F7B500]/80 transition-colors font-medium"
                                    >
                                        {vehicleFitments.length > 0 ? `Editar (${vehicleFitments.length})` : '+ Agregar'}
                                    </button>
                                </div>
                            </div>

                            {vehicleFitments.length > 0 ? (
                                <div className={`border ${theme.border} overflow-hidden`}>
                                    <div className="max-h-[120px] overflow-y-auto">
                                        {vehicleFitments.slice(0, 5).map((f, idx) => (
                                            <div key={f.id} className={`px-3 py-2 text-xs flex justify-between items-center ${idx > 0 ? `border-t ${theme.border}` : ''} ${darkMode ? 'hover:bg-white/5' : 'hover:bg-zinc-50'}`}>
                                                <span className={theme.text}>{f.make.join(', ')} {f.modelo.join('/')}</span>
                                                <span className={theme.textMuted}>{f.year_start}-{f.year_end}</span>
                                            </div>
                                        ))}
                                    </div>
                                    {vehicleFitments.length > 5 && (
                                        <div className={`px-3 py-1.5 text-xs ${theme.textMuted} border-t ${theme.border} text-center`}>
                                            +{vehicleFitments.length - 5} más…
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className={`text-center py-4 ${theme.textMuted} border border-dashed ${theme.border}`}>
                                    <p className="text-sm"> Sin fitment definido</p>
                                    <p className="text-xs mt-1">Click para agregar</p>
                                </div>
                            )}
                        </div>

                        {/* 4.5 Compatible Vehicles (Plain Text) */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-3">
                                <p className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-2 py-1">4.5</span>
                                    VEHÍCULOS COMPATIBLES (TEXTO)
                                </p>
                                <div className="flex items-center gap-3">
                                    <CharCounter value={content.compatible_vehicles} min={20} max={500} />
                                    <SaveButton section="compatible_vehicles" data={{ compatible_vehicles: content.compatible_vehicles }} savingSection={savingSection} onSave={saveSection} />
                                </div>
                            </div>
                            <textarea
                                value={content.compatible_vehicles}
                                onChange={(e) => setContent({ ...content, compatible_vehicles: e.target.value })}
                                placeholder="Lista de vehículos compatibles en texto plano..."
                                rows={4}
                                className={`w-full px-4 py-3 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-colors text-sm`}
                            />
                            <p className={`text-xs ${theme.textMuted} mt-2`}>
                                Información de compatibilidad en texto para motores de búsqueda y la sección de especificaciones.
                            </p>
                        </div>

                        {/* 5. Short Description */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-3">
                                <p className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-2 py-1">5</span>
                                    SHORT DESC
                                </p>
                                <div className="flex items-center gap-3">
                                    <CharCounter value={content.short_description} min={100} max={160} />
                                    <SaveButton section="short_desc" data={{ short_description: content.short_description }} savingSection={savingSection} onSave={saveSection} />
                                </div>
                            </div>
                            <textarea
                                value={content.short_description}
                                onChange={(e) => setContent({ ...content, short_description: e.target.value })}
                                placeholder="Descripción corta para listados (máx 160 chars)"
                                rows={3}
                                className={`w-full px-4 py-3 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-colors text-sm`}
                            />
                        </div>

                        {/* 5.5 Resumen / Ficha Técnica */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-3">
                                <p className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-2 py-1">5.5</span>
                                    FICHA TÉCNICA (RESUMEN)
                                </p>
                                <SaveButton section="resumen" data={{ resumen: content.resumen }} savingSection={savingSection} onSave={saveSection} />
                            </div>
                            <textarea
                                value={content.resumen}
                                onChange={(e) => setContent({ ...content, resumen: e.target.value })}
                                placeholder="Tabla HTML de ficha técnica (SKU, transmisiones, años, códigos alternos)..."
                                rows={5}
                                className={`w-full px-4 py-3 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-colors text-sm font-mono`}
                            />
                            {content.resumen && (
                                <div className="mt-3 border border-[#3a3a3a] p-3">
                                    <p className={`text-xs ${theme.textMuted} mb-2`}>Vista previa:</p>
                                    <div
                                        className="text-sm [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-[#3a3a3a] [&_th]:border [&_th]:border-[#3a3a3a] [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_h4]:text-[#F7B500] [&_h4]:font-bold [&_h4]:mb-2"
                                        dangerouslySetInnerHTML={{ __html: content.resumen }}
                                    />
                                </div>
                            )}
                            <p className={`text-xs ${theme.textMuted} mt-2`}>
                                HTML generado por el LLM. Se guarda en el metafield <code>custom.resumen</code> de Shopify.
                            </p>
                        </div>

                        {/* AEO Structured Data Section — reads from the consolidated Phase 2.10 blob with legacy fallback */}
                        {(() => {
                            // Parse the Phase 2.10 consolidated blob (custom.product_schema_json) — primary source
                            let blob: { '@graph'?: Array<{ '@type'?: string; mainEntity?: Array<{ name?: string; acceptedAnswer?: { text?: string } }> }>; store_aeo?: Record<string, unknown> } | null = null;
                            const blobRaw = shopifyData?.metafields?.['custom.product_schema_json'];
                            if (blobRaw) {
                                try {
                                    blob = typeof blobRaw === 'string' ? JSON.parse(blobRaw) : (blobRaw as typeof blob);
                                } catch { blob = null; }
                            }
                            const aeo = (blob?.store_aeo || {}) as Record<string, unknown>;

                            // Helper: parse a legacy list metafield (JSON-encoded string)
                            const parseListField = (key: string): string[] | null => {
                                const raw = shopifyData?.metafields?.[`custom.${key}`];
                                if (!raw) return null;
                                try {
                                    const arr = typeof raw === 'string' ? JSON.parse(raw) : raw;
                                    return Array.isArray(arr) ? arr.map(String) : null;
                                } catch { return null; }
                            };

                            // Each field: prefer blob, fall back to legacy individual metafield
                            const rebuildTier = (aeo.rebuild_tier as string) || shopifyData?.metafields?.['custom.rebuild_tier'] || null;
                            const transmissionCodes = (aeo.transmission_codes as string[]) || parseListField('transmission_codes');
                            const oemNumbers = (aeo.oem_numbers as string[]) || parseListField('oem_numbers');
                            const relatedGids = (aeo.related_product_gids as string[]) || parseListField('related_products');
                            const tldrSummary = (aeo.tldr_summary as string) || shopifyData?.metafields?.['custom.product_tldr_summary'] || null;
                            const fixesFaultCodes = (aeo.fixes_fault_codes as Array<{ code: string; name: string; monthly_clicks?: number; source?: string }>) || null;
                            const paaQuestionsAdded = (aeo.paa_questions_added as number) || 0;
                            const topSearchQueries = (aeo.top_search_queries as Array<{ query: string; clicks: number; impressions: number; position: number }>) || null;

                            // Phase 3.3 — Organization entity from @graph (Example Store seller authority).
                            const orgEntity = blob?.['@graph']?.find?.((e) => e?.['@type'] === 'Organization') as
                                | { name?: string; areaServed?: { name?: string }; knowsAbout?: string[]; additionalProperty?: Array<{ name?: string; value?: string }> }
                                | undefined;

                            // Phase 3.5b — repair_intent categories (derived from tier + product_type).
                            const repairIntent = (aeo.repair_intent as string[]) || null;

                            // Phase 3.5c — professional notes (Grok-generated, persisted in blob).
                            const professionalNotes = (aeo.professional_notes as {
                                common_failures?: string[];
                                companion_parts?: string[];
                                installation_tips?: string[];
                                confidence?: number;
                            }) || null;

                            // FAQs: from blob's @graph FAQPage mainEntity, or from legacy product_faqs
                            let faqs: Array<{ q: string; a: string }> = [];
                            const blobFaqPage = blob?.['@graph']?.find?.((e) => e?.['@type'] === 'FAQPage');
                            if (blobFaqPage?.mainEntity && Array.isArray(blobFaqPage.mainEntity)) {
                                faqs = blobFaqPage.mainEntity.map((q) => ({
                                    q: q?.name || '',
                                    a: q?.acceptedAnswer?.text || '',
                                })).filter(f => f.q && f.a);
                            }
                            if (faqs.length === 0) {
                                const rawFaqs = shopifyData?.metafields?.['custom.product_faqs'];
                                if (rawFaqs) {
                                    try {
                                        const arr = typeof rawFaqs === 'string' ? JSON.parse(rawFaqs) : rawFaqs;
                                        if (Array.isArray(arr)) {
                                            faqs = arr.map((f: { q?: string; a?: string; question?: string; answer?: string }) => ({
                                                q: f.q || f.question || '',
                                                a: f.a || f.answer || '',
                                            })).filter(f => f.q && f.a);
                                        }
                                    } catch { /* ignore */ }
                                }
                            }

                            const sourceLabel = blob ? 'consolidated blob' : 'legacy metafields (Phase 2.10 not yet pushed for this product)';

                            return (
                                <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                            <span className="text-purple-400">🤖</span>
                                            AEO Structured Data
                                            <span className={`text-xs ${theme.textMuted} font-normal`}>(read-only — what LLMs / Google AI Shopping see)</span>
                                        </h3>
                                        <span className={`text-xs ${theme.textMuted}`}>source: {sourceLabel}</span>
                                    </div>

                                    {/* rebuild_tier */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>Rebuild Tier (→ additionalProperty)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.rebuild_tier</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm`}>
                                            {rebuildTier || <span className={theme.textMuted}>(not set)</span>}
                                        </div>
                                    </div>

                                    {/* transmission_codes */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>Transmission Codes (cross-reference list → multi additionalProperty)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.transmission_codes</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm font-mono`}>
                                            {transmissionCodes && transmissionCodes.length > 0
                                                ? transmissionCodes.join(', ')
                                                : <span className={theme.textMuted}>(not set)</span>}
                                        </div>
                                    </div>

                                    {/* oem_numbers */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>OEM Cross-References (→ multi additionalProperty)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.oem_numbers</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm font-mono`}>
                                            {oemNumbers && oemNumbers.length > 0
                                                ? oemNumbers.join(', ')
                                                : <span className={theme.textMuted}>(not set)</span>}
                                        </div>
                                    </div>

                                    {/* related_products */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>Related Products (co-purchase → isRelatedTo)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.related_product_gids</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm font-mono`}>
                                            {relatedGids && relatedGids.length > 0
                                                ? `${relatedGids.length} product references`
                                                : <span className={theme.textMuted}>(not set)</span>}
                                        </div>
                                    </div>

                                    {/* tldr_summary */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>TL;DR Summary (→ disambiguatingDescription)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.tldr_summary</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm`}>
                                            {tldrSummary || <span className={theme.textMuted}>(not set)</span>}
                                        </div>
                                    </div>

                                    {/* repair_intent (Phase 3.5b — derived from tier + product_type) */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>Repair Intent Categories (AEO framework match)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.repair_intent</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm`}>
                                            {repairIntent && repairIntent.length > 0
                                                ? (
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {repairIntent.map((intent, i) => (
                                                            <span key={i} className="px-2 py-1 bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs">
                                                                {intent}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )
                                                : <span className={theme.textMuted}>(not derivable — vendor or product_type missing)</span>}
                                        </div>
                                    </div>

                                    {/* fixes_fault_codes (Phase 3.1 — KG bridge) */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>Fault Codes Fixed (→ HowTo per code in @graph)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.fixes_fault_codes</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm`}>
                                            {fixesFaultCodes && fixesFaultCodes.length > 0
                                                ? (
                                                    <div className="flex flex-wrap gap-2">
                                                        {fixesFaultCodes.map((fc, i) => {
                                                            const isGrok = fc.source === 'grok';
                                                            const chipStyle = isGrok
                                                                ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                                                                : 'bg-purple-500/10 border-purple-500/30 text-purple-300';
                                                            return (
                                                                <span key={i} className={`font-mono text-xs px-2 py-1 border inline-flex items-center gap-1 ${chipStyle}`} title={`${fc.name}${fc.monthly_clicks ? ` — ${fc.monthly_clicks} clicks/mo` : ''} — source: ${fc.source || 'kg'}`}>
                                                                    {fc.code}
                                                                    {isGrok && <span className="text-[10px] uppercase opacity-70">grok</span>}
                                                                </span>
                                                            );
                                                        })}
                                                    </div>
                                                )
                                                : <span className={theme.textMuted}>(none — KG had no match and Grok found no genuine fix-relation for this product)</span>}
                                        </div>
                                    </div>

                                    {/* FAQs from @graph (includes Grok + PAA after Phase 3.2 merge) */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>
                                                FAQs (→ FAQPage JSON-LD)
                                                {paaQuestionsAdded > 0 && (
                                                    <span className="ml-2 text-[10px] uppercase px-1.5 py-0.5 bg-blue-500/15 border border-blue-500/30 text-blue-300">
                                                        +{paaQuestionsAdded} PAA
                                                    </span>
                                                )}
                                            </span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>@graph[FAQPage].mainEntity</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm`}>
                                            {faqs.length > 0
                                                ? (
                                                    <div className="space-y-2">
                                                        {faqs.map((faq, i) => (
                                                            <details key={i} className="border-l-2 border-purple-500 pl-2">
                                                                <summary className="text-sm cursor-pointer font-medium">{faq.q}</summary>
                                                                <p className={`text-xs ${theme.textSecondary} mt-1 pl-2`}>{faq.a}</p>
                                                            </details>
                                                        ))}
                                                    </div>
                                                )
                                                : <span className={theme.textMuted}>(not set)</span>}
                                        </div>
                                    </div>

                                    {/* Top Search Queries (Phase 3.2 — GSC top queries for this product URL) */}
                                    <div className="mb-2">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>Top Search Queries (real GSC demand, last 30d)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.top_search_queries</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm`}>
                                            {topSearchQueries && topSearchQueries.length > 0
                                                ? (
                                                    <div className="space-y-1">
                                                        {topSearchQueries.map((q, i) => (
                                                            <div key={i} className="flex items-center justify-between gap-2 text-xs">
                                                                <span className="font-mono truncate" title={q.query}>{q.query}</span>
                                                                <span className={`${theme.textMuted} whitespace-nowrap`}>
                                                                    {q.clicks > 0 && <span className="text-emerald-400">{q.clicks} clicks</span>}
                                                                    {q.clicks > 0 && q.impressions > 0 && <span> · </span>}
                                                                    {q.impressions > 0 && <span>{q.impressions.toLocaleString()} imp</span>}
                                                                    {q.position > 0 && <span> · pos {q.position}</span>}
                                                                </span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )
                                                : <span className={theme.textMuted}>(no GSC data — product may be new or GSC unavailable)</span>}
                                        </div>
                                    </div>

                                    {/* Phase 3.5c: Professional Notes (Grok-generated, persisted) */}
                                    <div className="mb-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>
                                                Professional Notes (mechanic-grade context for AI engines)
                                                {professionalNotes?.confidence !== undefined && (
                                                    <span className="ml-2 text-[10px] uppercase px-1.5 py-0.5 bg-amber-500/15 border border-amber-500/30 text-amber-300">
                                                        grok · conf {(professionalNotes.confidence * 100).toFixed(0)}%
                                                    </span>
                                                )}
                                            </span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>store_aeo.professional_notes</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm`}>
                                            {professionalNotes
                                                ? (
                                                    <div className="space-y-2 text-xs">
                                                        {professionalNotes.common_failures && professionalNotes.common_failures.length > 0 && (
                                                            <div>
                                                                <div className={`${theme.textSecondary} font-semibold mb-1`}>Common failures</div>
                                                                <ul className={`${theme.textMuted} pl-4 space-y-0.5`}>
                                                                    {professionalNotes.common_failures.map((f, i) => <li key={i}>• {f}</li>)}
                                                                </ul>
                                                            </div>
                                                        )}
                                                        {professionalNotes.companion_parts && professionalNotes.companion_parts.length > 0 && (
                                                            <div>
                                                                <div className={`${theme.textSecondary} font-semibold mb-1`}>Companion parts</div>
                                                                <ul className={`${theme.textMuted} pl-4 space-y-0.5`}>
                                                                    {professionalNotes.companion_parts.map((p, i) => <li key={i}>• {p}</li>)}
                                                                </ul>
                                                            </div>
                                                        )}
                                                        {professionalNotes.installation_tips && professionalNotes.installation_tips.length > 0 && (
                                                            <div>
                                                                <div className={`${theme.textSecondary} font-semibold mb-1`}>Installation tips</div>
                                                                <ul className={`${theme.textMuted} pl-4 space-y-0.5`}>
                                                                    {professionalNotes.installation_tips.map((t, i) => <li key={i}>• {t}</li>)}
                                                                </ul>
                                                            </div>
                                                        )}
                                                    </div>
                                                )
                                                : <span className={theme.textMuted}>(not set — will Grok-generate on next Generar Schema, smart-merge preserves once written)</span>}
                                        </div>
                                    </div>

                                    {/* Phase 3.3: Organization (Example Store seller authority) */}
                                    <div className="mb-2">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className={`text-xs ${theme.textSecondary}`}>Organization (Example Store seller authority → schema.org Organization)</span>
                                            <span className={`text-xs ${theme.textMuted} font-mono`}>@graph[Organization]</span>
                                        </div>
                                        <div className={`px-3 py-2 ${theme.inputBg} border ${theme.border} text-sm`}>
                                            {orgEntity
                                                ? (
                                                    <div className="space-y-1 text-xs">
                                                        <div><span className={theme.textMuted}>name:</span> {orgEntity.name}</div>
                                                        <div><span className={theme.textMuted}>areaServed:</span> {orgEntity.areaServed?.name || '—'}</div>
                                                        {orgEntity.additionalProperty && orgEntity.additionalProperty.length > 0 && (
                                                            <div className="flex flex-wrap gap-1.5 mt-1">
                                                                {orgEntity.additionalProperty.map((p, i) => (
                                                                    <span key={i} className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-mono text-[11px]">
                                                                        {p.name}: {p.value}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                        {orgEntity.knowsAbout && orgEntity.knowsAbout.length > 0 && (
                                                            <div className={`${theme.textMuted} mt-1`}>
                                                                knowsAbout: {orgEntity.knowsAbout.slice(0, 3).join(', ')}{orgEntity.knowsAbout.length > 3 ? ` (+${orgEntity.knowsAbout.length - 3} more)` : ''}
                                                            </div>
                                                        )}
                                                    </div>
                                                )
                                                : <span className={theme.textMuted}>(not set — will appear after next Generar Schema)</span>}
                                        </div>
                                    </div>

                                    <div className={`mt-4 pt-3 border-t ${theme.border} text-xs ${theme.textMuted}`}>
                                        Phase 2.10 + 3.x: single consolidated <code>custom.product_schema_json</code> metafield contains the @graph (Organization + FAQs + HowTo entities) and the <code>store_aeo</code> extension (rebuild_tier, transmission codes, OEMs, related products, TL;DR, fault codes, top search queries).
                                        Theme emits each in the right JSON-LD location. This card reads from the blob with fallback to the legacy individual metafields if the blob isn&apos;t set yet.
                                        Click <strong>Generar Schema</strong> in Section 9 to (re)compose + push the blob.
                                    </div>
                                </div>
                            );
                        })()}

                        {/* SEO Section */}
                        <div className={`${theme.cardBg} border ${theme.border} p-6`}>
                            <div className="flex items-center justify-between mb-4">
                                <h3 className={`font-semibold ${theme.text} flex items-center gap-2`}>
                                    SEO
                                </h3>
                                <SaveButton section="seo" data={{ meta_title: content.meta_title, meta_description: content.meta_description, url_handle: content.url_handle }} label="💾 Guardar SEO" savingSection={savingSection} onSave={saveSection} />
                            </div>

                            {/* 6. Meta Title */}
                            <label className="mb-4 block">
                                <div className="flex items-center justify-between mb-2">
                                    <span className={`text-sm ${theme.textSecondary} flex items-center gap-2`}>
                                        <span className="bg-[#F7B500] text-black text-xs font-bold px-1.5 py-0.5">6</span>
                                        Meta Título
                                    </span>
                                    <CharCounter value={content.meta_title} min={50} max={60} />
                                </div>
                                <input
                                    type="text"
                                    value={content.meta_title}
                                    onChange={(e) => setContent({ ...content, meta_title: e.target.value })}
                                    placeholder="Meta título (50-60 chars) - Google trunca después de 60"
                                    className={`w-full px-3 py-2 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-colors text-sm`}
                                />
                            </label>

                            {/* 7. Meta Description */}
                            <label className="mb-4 block">
                                <div className="flex items-center justify-between mb-2">
                                    <span className={`text-sm ${theme.textSecondary} flex items-center gap-2`}>
                                        <span className="bg-[#F7B500] text-black text-xs font-bold px-1.5 py-0.5">7</span>
                                        Meta Descripción
                                    </span>
                                    <CharCounter value={content.meta_description} min={150} max={160} />
                                </div>
                                <textarea
                                    value={content.meta_description}
                                    onChange={(e) => setContent({ ...content, meta_description: e.target.value })}
                                    placeholder="Meta descripción para Google (150-160 chars)"
                                    rows={3}
                                    className={`w-full px-3 py-2 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-colors text-sm`}
                                />
                            </label>

                            {/* 8. URL Handle */}
                            <label className="block">
                                <span className={`text-sm ${theme.textSecondary} flex items-center gap-2 mb-2`}>
                                    <span className="bg-[#F7B500] text-black text-xs font-bold px-1.5 py-0.5">8</span>
                                    URL Handle
                                </span>
                                <span className="flex items-center gap-2">
                                    <span className={`text-xs ${theme.textMuted}`}>/products/</span>
                                    <input
                                        type="text"
                                        value={content.url_handle}
                                        onChange={(e) => setContent({ ...content, url_handle: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') })}
                                        placeholder="url-handle"
                                        className={`flex-1 px-3 py-2 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] focus:outline-none transition-colors text-sm font-mono`}
                                    />
                                </span>
                            </label>

                            {/* Google Preview */}
                            <div className="mt-6 pt-4 border-t border-zinc-800">
                                <p className={`text-xs ${theme.textMuted} mb-2`}>Vista previa en Google:</p>
                                <div className={`p-3 ${darkMode ? 'bg-black/30' : 'bg-zinc-50'}`}>
                                    <div className="text-blue-500 text-sm hover:underline cursor-pointer">
                                        {content.meta_title || 'Titulo del producto | Example Store'}
                                    </div>
                                    <div className="text-green-600 text-xs">
                                        example-store.com/products/{content.url_handle || 'producto'}
                                    </div>
                                    <div className={`text-xs ${theme.textSecondary} mt-1`}>
                                        {content.meta_description || 'Meta descripcion del producto...'}
                                    </div>
                                </div>
                            </div>

                            {/* 9. JSON-LD Structured Data Schema */}
                            <div className="mt-6 pt-4 border-t border-zinc-800">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <span className="bg-purple-600 text-white text-xs font-bold px-1.5 py-0.5">9</span>
                                        <h4 className={`text-sm font-medium ${theme.text}`}>JSON-LD Schema</h4>
                                        {productSchema && (
                                            <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded">
                                                {(productSchema as any)?.['@graph']?.length || 0} entidades
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={async () => {
                                                if (!product) return;
                                                setGeneratingSchema(true);
                                                try {
                                                    const result = await productAPI.generateSchema(product.id, {
                                                        description_html: content.description_html,
                                                        h1_title: content.h1_title
                                                    });
                                                    setProductSchema(result.schema);
                                                    setShowSchemaSection(true);
                                                    console.log(`[Schema] Generated: ${result.entities_count} entities, FAQ=${result.has_faq}, HowTo=${result.has_howto}, Vehicles=${result.has_vehicles}`);
                                                } catch (error) {
                                                    console.error('Error generating schema:', error);
                                                    alert('Error generando schema: ' + (error instanceof Error ? error.message : String(error)));
                                                } finally {
                                                    setGeneratingSchema(false);
                                                }
                                            }}
                                            disabled={generatingSchema}
                                            className="px-3 py-1 bg-purple-600/20 text-purple-400 text-xs rounded hover:bg-purple-600/30 transition-colors disabled:opacity-50"
                                        >
                                            {generatingSchema ? 'Generando...' : productSchema ? 'Re-generar' : 'Generar Schema'}
                                        </button>
                                        {productSchema && (
                                            <SaveButton
                                                section="schema"
                                                data={{ product_schema: productSchema }}
                                                label="💾 Guardar Schema"
                                                savingSection={savingSection}
                                                onSave={saveSection}
                                            />
                                        )}
                                    </div>
                                </div>

                                {productSchema && showSchemaSection && (
                                    <div className="space-y-3">
                                        {/* Schema Entity Summary */}
                                        <div className="flex flex-wrap gap-2">
                                            {((productSchema as any)?.['@graph'] || []).map((entity: any, idx: number) => {
                                                const type = entity?.['@type'] || '?';
                                                const colors: Record<string, string> = {
                                                    'Product': 'bg-blue-500/20 text-blue-400',
                                                    'FAQPage': 'bg-green-500/20 text-green-400',
                                                    'HowTo': 'bg-yellow-500/20 text-yellow-400',
                                                    'VehiclePart': 'bg-purple-500/20 text-purple-400'
                                                };
                                                const details: Record<string, string> = {
                                                    'Product': `${entity?.isAccessoryOrSparePartFor?.length || 0} vehiculos`,
                                                    'FAQPage': `${entity?.mainEntity?.length || 0} preguntas`,
                                                    'HowTo': `${entity?.step?.length || 0} pasos`,
                                                    'VehiclePart': `${entity?.isAccessoryOrSparePartFor?.length || 0} vehiculos`
                                                };
                                                return (
                                                    <span key={idx} className={`text-xs px-2 py-1 rounded ${colors[type] || 'bg-zinc-500/20 text-zinc-400'}`}>
                                                        {type}: {details[type] || ''}
                                                    </span>
                                                );
                                            })}
                                        </div>

                                        {/* Schema JSON Preview */}
                                        <div className="relative">
                                            <button
                                                onClick={() => {
                                                    navigator.clipboard.writeText(JSON.stringify(productSchema, null, 2));
                                                    alert('Schema JSON copiado al portapapeles');
                                                }}
                                                className="absolute top-2 right-2 px-2 py-1 bg-zinc-700 text-zinc-300 text-xs rounded hover:bg-zinc-600 z-10"
                                            >
                                                Copiar
                                            </button>
                                            <pre className={`p-3 ${darkMode ? 'bg-black/50' : 'bg-zinc-100'} ${theme.text} text-xs overflow-auto max-h-64 rounded border ${theme.border}`}>
                                                {JSON.stringify(productSchema, null, 2)}
                                            </pre>
                                        </div>

                                        {/* Validation Link */}
                                        <div className="flex items-center gap-3 text-xs">
                                            <a
                                                href="https://search.google.com/test/rich-results"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-blue-400 hover:text-blue-300 underline"
                                            >
                                                Validar en Google Rich Results Test
                                            </a>
                                            <a
                                                href="https://validator.schema.org/"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-blue-400 hover:text-blue-300 underline"
                                            >
                                                Schema.org Validator
                                            </a>
                                        </div>
                                    </div>
                                )}

                                {!productSchema && (
                                    <p className={`text-xs ${theme.textMuted}`}>
                                        Genera y guarda <strong>todos los metafields AEO</strong> en una sola llamada:
                                        HowTo en <code>custom.product_schema_json</code>, FAQs en <code>custom.product_faqs</code> (deduplicado del @graph para que no se emitan dos FAQPage),
                                        OEMs en <code>custom.oem_numbers</code>, codigos de transmision en <code>custom.transmission_codes</code>,
                                        productos relacionados (co-purchase) en <code>custom.related_products</code>,
                                        y tier de reconstruccion en <code>custom.rebuild_tier</code>.
                                        BreadcrumbList y Product los maneja el tema. Sin llamadas a Grok — todo deterministico desde la descripcion + DB.
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </main>

            {/* Vehicle Fitment Modal */}
            {
                showFitmentModal && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                        <div className={`${theme.cardBg} w-full max-w-7xl max-h-[90vh] border ${theme.border} shadow-2xl flex flex-col overflow-hidden`}>
                            {/* Modal Header */}
                            <div className={`px-6 py-4 border-b ${theme.border} flex items-center justify-between bg-[#1a1a1a]`}>
                                <div>
                                    <h2 className={`text-xl font-bold ${theme.text} flex items-center gap-2`}>
                                        Vehicle Fitment
                                        <span className="text-xs font-normal px-2 py-0.5 bg-zinc-800 text-zinc-400">
                                            Metaobjeto: custom.vehiculo_fitment
                                        </span>
                                    </h2>
                                    <p className={`text-sm ${theme.textMuted}`}>Configura la compatibilidad detallada del producto</p>
                                </div>
                                <div className="flex items-center gap-3">
                                    <button
                                        onClick={parseVehicleFitmentFromDescription}
                                        className="flex items-center gap-2 px-4 py-2 bg-blue-600/20 text-blue-400 font-semibold hover:bg-blue-600/30 transition-all border border-blue-600/30"
                                    >
                                        Auto-Detectar
                                    </button>
                                    <button
                                        onClick={() => setVehicleFitments([...vehicleFitments, {
                                            id: vehicleFitments.length ? Math.max(...vehicleFitments.map(f => f.id)) + 1 : 1,
                                            make: [],
                                            modelo: [],
                                            year_start: null,
                                            year_end: null,
                                            transmission_type: '',
                                            transmission_model: '',
                                            engine: ''
                                        }])}
                                        className="flex items-center gap-2 px-4 py-2 bg-[#F7B500]/20 text-[#F7B500] font-semibold hover:bg-[#F7B500]/30 transition-all border border-[#F7B500]/30"
                                    >
                                        + Agregar Nuevo
                                    </button>
                                    <button
                                        onClick={() => setShowFitmentModal(false)}
                                        className={`p-2 hover:${darkMode ? 'bg-white/10' : 'bg-black/5'} transition-colors`}
                                    >
                                        <svg className={`size-6 ${theme.textSecondary}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </div>
                            </div>

                            {/* Modal Content - Table */}
                            <div className="flex-1 overflow-auto p-6">
                                {vehicleFitments.length > 0 ? (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm border-collapse" style={{ minWidth: '900px' }}>
                                            <thead>
                                                <tr className={`${darkMode ? 'bg-black/40' : 'bg-zinc-50'} border-b ${theme.border}`}>
                                                    <th className={`p-3 text-left ${theme.textMuted} font-semibold text-xs uppercase tracking-wide whitespace-nowrap`} style={{ width: '160px' }}>Años</th>
                                                    <th className={`p-3 text-left ${theme.textMuted} font-semibold text-xs uppercase tracking-wide whitespace-nowrap`} style={{ width: '150px' }}>Marca</th>
                                                    <th className={`p-3 text-left ${theme.textMuted} font-semibold text-xs uppercase tracking-wide whitespace-nowrap`}>Modelo(s)</th>
                                                    <th className={`p-3 text-left ${theme.textMuted} font-semibold text-xs uppercase tracking-wide whitespace-nowrap`} style={{ width: '120px' }}>Transmisión</th>
                                                    <th className={`p-3 text-left ${theme.textMuted} font-semibold text-xs uppercase tracking-wide whitespace-nowrap`} style={{ width: '150px' }}>Motor</th>
                                                    <th className="px-2 py-3" style={{ width: '50px' }}></th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-zinc-800">
                                                {vehicleFitments.map((fitment, idx) => (
                                                    <tr key={fitment.id} className={`${darkMode ? 'hover:bg-white/5' : 'hover:bg-zinc-50'} transition-colors group`}>
                                                        <td className="p-2">
                                                            <div className="flex items-center gap-1">
                                                                <input
                                                                    type="number"
                                                                    value={fitment.year_start || ''}
                                                                    onChange={(e) => {
                                                                        const newFitments = [...vehicleFitments];
                                                                        newFitments[idx] = { ...fitment, year_start: e.target.value ? parseInt(e.target.value) : null };
                                                                        setVehicleFitments(newFitments);
                                                                    }}
                                                                    placeholder="2003"
                                                                    min="1980"
                                                                    max="2030"
                                                                    className={`w-16 px-2 py-1.5 text-center ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] outline-none transition-all placeholder:text-zinc-600 text-sm font-mono`}
                                                                />
                                                                <span className={`${theme.textMuted} text-xs`}>-</span>
                                                                <input
                                                                    type="number"
                                                                    value={fitment.year_end || ''}
                                                                    onChange={(e) => {
                                                                        const newFitments = [...vehicleFitments];
                                                                        newFitments[idx] = { ...fitment, year_end: e.target.value ? parseInt(e.target.value) : null };
                                                                        setVehicleFitments(newFitments);
                                                                    }}
                                                                    placeholder="2012"
                                                                    min="1980"
                                                                    max="2030"
                                                                    className={`w-16 px-2 py-1.5 text-center ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] outline-none transition-all placeholder:text-zinc-600 text-sm font-mono`}
                                                                />
                                                            </div>
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                type="text"
                                                                value={fitment.make.join(', ')}
                                                                onChange={(e) => {
                                                                    const newFitments = [...vehicleFitments];
                                                                    newFitments[idx] = { ...fitment, make: e.target.value.split(',').map(s => s.trim()).filter(s => s) };
                                                                    setVehicleFitments(newFitments);
                                                                }}
                                                                placeholder="AUDI"
                                                                className={`w-full px-2 py-1.5 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] outline-none transition-all placeholder:text-zinc-600 font-semibold text-sm uppercase`}
                                                            />
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                type="text"
                                                                value={fitment.modelo.join(', ')}
                                                                onChange={(e) => {
                                                                    const newFitments = [...vehicleFitments];
                                                                    newFitments[idx] = { ...fitment, modelo: e.target.value.split(',').map(s => s.trim()).filter(s => s) };
                                                                    setVehicleFitments(newFitments);
                                                                }}
                                                                placeholder="A3, Q3, TT..."
                                                                className={`w-full px-2 py-1.5 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] outline-none transition-all placeholder:text-zinc-600 text-sm`}
                                                            />
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                type="text"
                                                                value={fitment.transmission_model}
                                                                onChange={(e) => {
                                                                    const newFitments = [...vehicleFitments];
                                                                    newFitments[idx] = { ...fitment, transmission_model: e.target.value };
                                                                    setVehicleFitments(newFitments);
                                                                }}
                                                                placeholder="09G"
                                                                className={`w-full px-2 py-1.5 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] outline-none transition-all placeholder:text-zinc-600 font-mono text-sm`}
                                                            />
                                                        </td>
                                                        <td className="p-2">
                                                            <input
                                                                type="text"
                                                                value={fitment.engine}
                                                                onChange={(e) => {
                                                                    const newFitments = [...vehicleFitments];
                                                                    newFitments[idx] = { ...fitment, engine: e.target.value };
                                                                    setVehicleFitments(newFitments);
                                                                }}
                                                                placeholder="6 SP FWD"
                                                                className={`w-full px-2 py-1.5 ${theme.inputBg} border ${theme.border} ${theme.text} focus:border-[#F7B500] outline-none transition-all placeholder:text-zinc-600 font-mono text-sm`}
                                                            />
                                                        </td>
                                                        <td className="p-2 text-center">
                                                            <button
                                                                onClick={() => setVehicleFitments(vehicleFitments.filter(f => f.id !== fitment.id))}
                                                                className="p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all"
                                                                title="Eliminar fila"
                                                            >
                                                                <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                                </svg>
                                                            </button>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
                                        <div className="size-20 bg-zinc-900 flex items-center justify-center mb-6 border border-zinc-800">
                                            <svg className="size-10 text-zinc-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                        </div>
                                        <h3 className={`text-xl font-semibold ${theme.text} mb-2`}>No se ha detectado fitment</h3>
                                        <p className={`${theme.textMuted} max-w-md mx-auto mb-8`}>
                                            Puedes intentar detectarlo automáticamente desde la descripción del producto o agregarlo manualmente usando los botones de arriba.
                                        </p>
                                        <div className="flex gap-4">
                                            <button
                                                onClick={parseVehicleFitmentFromDescription}
                                                className="px-6 py-2 bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-all shadow-lg shadow-blue-900/20"
                                            >
                                                Auto-Detectar Ahora
                                            </button>
                                            <button
                                                onClick={() => setVehicleFitments([{
                                                    id: 1,
                                                    make: [],
                                                    modelo: [],
                                                    year_start: null,
                                                    year_end: null,
                                                    transmission_type: '',
                                                    transmission_model: '',
                                                    engine: ''
                                                }])}
                                                className="px-6 py-2 bg-[#F7B500] text-black font-semibold hover:bg-[#ffc933] transition-all shadow-lg shadow-yellow-900/20"
                                            >
                                                + Agregar Manualmente
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Modal Footer */}
                            <div className={`px-6 py-4 border-t ${theme.border} flex items-center justify-between bg-[#1a1a1a]`}>
                                <div className={`text-sm ${theme.textMuted}`}>
                                    Total: <span className="text-[#F7B500] font-bold">{vehicleFitments.length}</span> entradas de fitment
                                </div>
                                <div className="flex gap-3">
                                    <button
                                        onClick={() => setShowFitmentModal(false)}
                                        className={`px-8 py-2.5 bg-[#F7B500] text-black font-bold hover:bg-[#ffc933] transition-all shadow-lg shadow-yellow-900/20`}
                                    >
                                        Cerrar y Revisar
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

            {/* AI Analysis Results Modal */}
            {showAnalysisModal && aiAnalysis && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className={`${theme.cardBg} w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col rounded-lg shadow-2xl`}>
                        {/* Modal Header */}
                        <div className={`px-6 py-4 border-b ${theme.border} flex items-center justify-between bg-gradient-to-r from-purple-600/20 to-blue-600/20`}>
                            <div className="flex items-center gap-3">
                                <span className="text-2xl">🧠</span>
                                <div>
                                    <h2 className={`text-lg font-bold ${theme.text}`}>Análisis Profundo con Grok</h2>
                                    <p className={`text-xs ${theme.textMuted}`}>SEO + AEO + GEO Optimization</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setShowAnalysisModal(false)}
                                className={`p-2 rounded-lg ${theme.textMuted} hover:text-white transition-colors`}
                            >
                                ✕
                            </button>
                        </div>

                        {/* Modal Content */}
                        <div className="flex-1 overflow-y-auto p-6 space-y-6">
                            {/* Scores Overview */}
                            <div className="grid grid-cols-3 gap-4">
                                <div className={`p-4 rounded-lg ${theme.inputBg} border ${theme.border}`}>
                                    <div className="text-xs text-zinc-400 mb-1">SEO Score</div>
                                    <div className="text-2xl font-bold text-green-400">{aiAnalysis.seo_analysis?.score ?? 0}/100</div>
                                </div>
                                <div className={`p-4 rounded-lg ${theme.inputBg} border ${theme.border}`}>
                                    <div className="text-xs text-zinc-400 mb-1">AEO Score</div>
                                    <div className="text-2xl font-bold text-blue-400">{aiAnalysis.aeo_analysis?.score ?? 0}/100</div>
                                </div>
                                <div className={`p-4 rounded-lg ${theme.inputBg} border ${theme.border}`}>
                                    <div className="text-xs text-zinc-400 mb-1">GEO Score</div>
                                    <div className="text-2xl font-bold text-purple-400">{aiAnalysis.geo_analysis?.score ?? 0}/100</div>
                                </div>
                            </div>

                            {/* Priority Actions */}
                            <div className={`p-4 rounded-lg ${theme.inputBg} border border-[#F7B500]/30`}>
                                <h3 className="text-[#F7B500] font-semibold mb-3 flex items-center gap-2">
                                    ⚡ Acciones Prioritarias
                                </h3>
                                <ul className="space-y-2">
                                    {(aiAnalysis.priority_actions ?? []).map((action, idx) => (
                                        <li key={idx} className={`${theme.textSecondary} text-sm flex items-start gap-2`}>
                                            <span className="text-[#F7B500]">{idx + 1}.</span>
                                            {action}
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            {/* Recommendations */}
                            <div className="space-y-3">
                                <h3 className={`font-semibold ${theme.text}`}>💡 Recomendaciones Detalladas</h3>
                                {(aiAnalysis.recommendations ?? []).map((rec, idx) => (
                                    <div key={idx} className={`p-4 rounded-lg ${theme.inputBg} border ${theme.border}`}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className={`px-2 py-0.5 text-xs rounded ${rec.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                                                rec.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                                    'bg-green-500/20 text-green-400'
                                                }`}>
                                                {rec.priority?.toUpperCase()}
                                            </span>
                                            <span className="text-xs text-zinc-400">{rec.category?.toUpperCase()}</span>
                                        </div>
                                        <p className={`${theme.text} font-medium mb-1`}>{rec.action}</p>
                                        <p className={`${theme.textSecondary} text-sm mb-2`}>{rec.expected_impact}</p>
                                        <p className={`text-xs ${theme.textMuted}`}>🛠 {rec.implementation}</p>
                                    </div>
                                ))}
                            </div>

                            {/* Expected Impact */}
                            <div className={`p-4 rounded-lg ${theme.inputBg} border ${theme.border}`}>
                                <h3 className={`font-semibold ${theme.text} mb-3`}>📈 Impacto Esperado</h3>
                                <div className="grid grid-cols-3 gap-4 text-center">
                                    <div>
                                        <div className="text-2xl font-bold text-green-400">{aiAnalysis.expected_impact?.traffic_increase ?? 'N/A'}</div>
                                        <div className={`text-xs ${theme.textMuted}`}>Aumento Tráfico</div>
                                    </div>
                                    <div>
                                        <div className="text-2xl font-bold text-blue-400">{aiAnalysis.expected_impact?.conversion_increase ?? 'N/A'}</div>
                                        <div className={`text-xs ${theme.textMuted}`}>Aumento Conversión</div>
                                    </div>
                                    <div>
                                        <div className="text-2xl font-bold text-purple-400">{aiAnalysis.expected_impact?.timeline ?? 'N/A'}</div>
                                        <div className={`text-xs ${theme.textMuted}`}>Timeline</div>
                                    </div>
                                </div>
                            </div>

                            {/* SEO Issues */}
                            {(aiAnalysis.seo_analysis?.critical_issues ?? []).length > 0 && (
                                <div className={`p-4 rounded-lg bg-red-500/10 border border-red-500/30`}>
                                    <h3 className="text-red-400 font-semibold mb-2">⚠️ Problemas SEO Críticos</h3>
                                    <ul className="space-y-1">
                                        {(aiAnalysis.seo_analysis?.critical_issues ?? []).map((issue, idx) => (
                                            <li key={idx} className="text-red-300 text-sm">• {issue}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Keyword Opportunities */}
                            <div className={`p-4 rounded-lg ${theme.inputBg} border ${theme.border}`}>
                                <h3 className={`font-semibold ${theme.text} mb-2`}>🎯 Oportunidades de Keywords</h3>
                                {(aiAnalysis.seo_analysis?.keyword_opportunities ?? []).length > 0 ? (
                                    <div className="flex flex-wrap gap-2">
                                        {(aiAnalysis.seo_analysis?.keyword_opportunities ?? []).map((kw, idx) => (
                                            <span key={idx} className="px-3 py-1 bg-[#F7B500]/20 text-[#F7B500] rounded-full text-sm">
                                                {kw}
                                            </span>
                                        ))}
                                    </div>
                                ) : aiAnalysis.seo_analysis?.keyword_opportunities_status === 'no_data' ? (
                                    <p className={`text-sm ${theme.textMuted} leading-relaxed`}>
                                        Sin datos de keywords todavía. Este producto no tiene consultas con impresiones en Search Console
                                        ni búsquedas relacionadas de DataForSEO. Cuando acumule impresiones (~10+ por consulta) o
                                        actives DataForSEO, las oportunidades reales aparecerán aquí.
                                    </p>
                                ) : (
                                    <p className={`text-sm ${theme.textMuted}`}>
                                        No se encontraron oportunidades adicionales en los datos disponibles.
                                    </p>
                                )}
                            </div>

                            {/* AEO Questions */}
                            {(aiAnalysis.aeo_analysis?.question_targets ?? []).length > 0 && (
                                <div className={`p-4 rounded-lg ${theme.inputBg} border ${theme.border}`}>
                                    <h3 className={`font-semibold ${theme.text} mb-2`}>❓ Preguntas para AEO (Voice Search)</h3>
                                    <ul className="space-y-1">
                                        {(aiAnalysis.aeo_analysis?.question_targets ?? []).map((q, idx) => (
                                            <li key={idx} className={`${theme.textSecondary} text-sm`}>• {q}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* GEO Entity Clarity */}
                            <div className={`p-4 rounded-lg ${theme.inputBg} border ${theme.border}`}>
                                <h3 className={`font-semibold ${theme.text} mb-2`}>🤖 Claridad de Entidades (GEO)</h3>
                                <div className="flex items-center gap-2 mb-2">
                                    <span className={`px-2 py-0.5 text-xs rounded ${aiAnalysis.geo_analysis?.entity_clarity === 'good' ? 'bg-green-500/20 text-green-400' :
                                        aiAnalysis.geo_analysis?.entity_clarity === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                            'bg-red-500/20 text-red-400'
                                        }`}>
                                        {(aiAnalysis.geo_analysis?.entity_clarity ?? 'unknown').toUpperCase()}
                                    </span>
                                </div>
                                {(aiAnalysis.geo_analysis?.context_gaps ?? []).length > 0 && (
                                    <div className="mt-2">
                                        <p className={`text-xs ${theme.textMuted} mb-1`}>Brechas de contexto:</p>
                                        <ul className="space-y-1">
                                            {(aiAnalysis.geo_analysis?.context_gaps ?? []).map((gap, idx) => (
                                                <li key={idx} className={`${theme.textSecondary} text-sm`}>• {gap}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Modal Footer */}
                        <div className={`px-6 py-4 border-t ${theme.border} flex items-center justify-between bg-[#1a1a1a]`}>
                            <div className={`text-xs ${theme.textMuted}`}>
                                Análisis powered by <span className="text-purple-400 font-semibold">Grok AI</span>
                            </div>
                            <div className="flex gap-3">
                                <button
                                    onClick={() => setShowAnalysisModal(false)}
                                    className="px-6 py-2 bg-zinc-700 text-white rounded hover:bg-zinc-600 transition-colors"
                                >
                                    Cerrar
                                </button>
                                <button
                                    onClick={() => {
                                        setShowAnalysisModal(false);
                                        // Scroll to content editor
                                        window.scrollTo({ top: 0, behavior: 'smooth' });
                                    }}
                                    className="px-6 py-2 bg-[#F7B500] text-black font-semibold rounded hover:bg-[#ffc933] transition-colors"
                                >
                                    Aplicar Recomendaciones
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ============================================
// PRODUCT METRICS PANEL COMPONENT
// ============================================

interface ProductMetricsPanelProps {
    product: Product;
    shopifyData: ShopifyProductDetails | null;
    theme: {
        bg: string;
        cardBg: string;
        text: string;
        textSecondary: string;
        textMuted: string;
        border: string;
        inputBg: string;
    };
    darkMode: boolean;
}

// ============================================
// AEO (Answer Engine Optimization) ANALYZER
// For Voice Search & Featured Snippets
// ============================================

function analyzeAEOContent(
    title: string,
    description: string,
    metaDescription: string,
    fitments: Array<any>
): {
    score: number;
    checks: Array<{ label: string; passed: boolean; importance: 'high' | 'medium' | 'low'; tip: string }>;
    snippetOpportunities: string[];
    recommendedQuestions: string[];
} {
    const checks: Array<{ label: string; passed: boolean; importance: 'high' | 'medium' | 'low'; tip: string }> = [];
    const snippetOpportunities: string[] = [];
    const recommendedQuestions: string[] = [];
    let score = 0;

    const lowerDesc = description.toLowerCase();
    const lowerTitle = title.toLowerCase();

    // 1. Direct Answer in First Paragraph
    const firstParagraph = description.split(/<\/p>/i)[0] || '';
    const hasDirectAnswer = firstParagraph.length > 100 && firstParagraph.length < 400;
    checks.push({
        label: 'Respuesta directa en primer párrafo',
        passed: hasDirectAnswer,
        importance: 'high',
        tip: 'El primer párrafo debe responder qué es el producto en 2-3 oraciones'
    });
    if (hasDirectAnswer) score += 20;
    else snippetOpportunities.push('Agregar definición clara en el primer párrafo');

    // 2. Question-Answer Format
    const hasQuestions = description.includes('?');
    checks.push({
        label: 'Formato pregunta-respuesta',
        passed: hasQuestions,
        importance: 'high',
        tip: 'Incluir FAQ o preguntas comunes que los clientes hacen'
    });
    if (hasQuestions) {
        score += 20;
        // Extract questions
        const questions = description.match(/[^.!?]*\?/g) || [];
        questions.slice(0, 3).forEach(q => {
            if (q.length > 20) recommendedQuestions.push(q.trim());
        });
    } else {
        snippetOpportunities.push('Agregar sección de Preguntas Frecuentes');
        recommendedQuestions.push(`¿Qué es ${title}?`);
        recommendedQuestions.push(`¿Para qué vehículos sirve ${title}?`);
    }

    // 3. List Structure (for featured snippets)
    const hasLists = description.includes('<ul>') || description.includes('<ol>') || description.includes('<li>');
    checks.push({
        label: 'Estructura de listas (pasos, beneficios)',
        passed: hasLists,
        importance: 'medium',
        tip: 'Usar listas para características, compatibilidades, pasos de instalación'
    });
    if (hasLists) score += 15;
    else snippetOpportunities.push('Convertir características a formato de lista');

    // 4. Concise Definitions (30-60 words)
    const sentences = description.match(/[^.!?]+[.!?]+/g) || [];
    const conciseDefinitions = sentences.filter(s => {
        const wordCount = s.trim().split(/\s+/).length;
        return wordCount >= 30 && wordCount <= 60;
    });
    const hasConciseDefinitions = conciseDefinitions.length > 0;
    checks.push({
        label: 'Definiciones concisas (30-60 palabras)',
        passed: hasConciseDefinitions,
        importance: 'high',
        tip: 'Google prefiere respuestas directas de 40-60 palabras para snippets'
    });
    if (hasConciseDefinitions) score += 20;

    // 5. Table Data (comparisons, specs)
    const hasTables = description.includes('<table>');
    checks.push({
        label: 'Datos en tabla (especificaciones)',
        passed: hasTables,
        importance: 'medium',
        tip: 'Tablas de especificaciones técnicas aparecen en snippets destacados'
    });
    if (hasTables) score += 10;

    // 6. Structured Data Markup Mention
    const hasStructuredIntent = lowerDesc.includes('compatible con') ||
        lowerDesc.includes('aplicaciones') ||
        fitments.length > 0;
    checks.push({
        label: 'Datos estructurados de compatibilidad',
        passed: hasStructuredIntent,
        importance: 'high',
        tip: 'Marcar claramente años, marcas y modelos compatibles'
    });
    if (hasStructuredIntent) score += 15;

    // 7. Voice Search Keywords
    const voiceKeywords = ['cómo', 'qué es', 'para qué', 'cuándo', 'dónde', 'por qué'];
    const hasVoiceKeywords = voiceKeywords.some(kw => lowerDesc.includes(kw));
    checks.push({
        label: 'Keywords de búsqueda por voz',
        passed: hasVoiceKeywords,
        importance: 'medium',
        tip: 'Incluir frases como "Cómo instalar...", "Qué es..."'
    });
    if (hasVoiceKeywords) score += 10;

    // Generate recommended questions based on content
    if (fitments.length > 0) {
        recommendedQuestions.push(`¿Con qué transmisiones es compatible ${title}?`);
        const makes = [...new Set(fitments.flatMap(f => f.make))].slice(0, 2);
        if (makes.length > 0) {
            recommendedQuestions.push(`¿Sirve para ${makes.join(', ')}?`);
        }
    }

    return { score: Math.min(100, score), checks, snippetOpportunities, recommendedQuestions };
}

// ============================================
// GEO (Generative Engine Optimization) ANALYZER
// For AI Search (ChatGPT, Perplexity, Bing AI)
// ============================================

function analyzeGEOContent(
    title: string,
    description: string,
    metaTitle: string,
    fitments: Array<any>,
    vehicleFitments: Array<any>
): {
    score: number;
    checks: Array<{ label: string; passed: boolean; importance: 'high' | 'medium' | 'low'; tip: string }>;
    entityClarity: 'good' | 'medium' | 'poor';
    contextGaps: string[];
    authoritySignals: string[];
} {
    const checks: Array<{ label: string; passed: boolean; importance: 'high' | 'medium' | 'low'; tip: string }> = [];
    const contextGaps: string[] = [];
    const authoritySignals: string[] = [];
    let score = 0;

    const lowerDesc = description.toLowerCase();
    const lowerTitle = title.toLowerCase();

    // 1. Clear Entity Definition (What IS this product)
    const entityPatterns = [
        /es (un|una) [a-z\s]+ (transmisión|convertidor|kit|solenoides?)/i,
        /(transmisión|convertidor|solenoides?) (automática|de transmisión)/i,
    ];
    const hasEntityDefinition = entityPatterns.some(p => p.test(description)) ||
        description.match(/\b(transmisión|transmission|convertidor|converter|solenoid)\b/i);
    checks.push({
        label: 'Definición clara de entidad (qué ES)',
        passed: !!hasEntityDefinition,
        importance: 'high',
        tip: 'La IA debe entender inmediatamente qué tipo de producto es'
    });
    if (hasEntityDefinition) {
        score += 20;
        authoritySignals.push('Entidad claramente definida');
    } else {
        contextGaps.push('Definición de producto ambigua');
    }

    // 2. Technical Specifications
    const techSpecs = ['número de parte', 'part number', 'oem', 'sku', 'especificaciones'];
    const hasTechSpecs = techSpecs.some(spec => lowerDesc.includes(spec));
    checks.push({
        label: 'Especificaciones técnicas detalladas',
        passed: hasTechSpecs,
        importance: 'high',
        tip: 'Números de parte OEM, especificaciones técnicas ayudan a la IA'
    });
    if (hasTechSpecs) {
        score += 15;
        authoritySignals.push('Especificaciones técnicas presentes');
    } else {
        contextGaps.push('Faltan especificaciones técnicas');
    }

    // 3. Vehicle Compatibility Context
    const hasCompatibilityContext = lowerDesc.includes('compatible') ||
        lowerDesc.includes('aplicaciones') ||
        lowerDesc.includes('vehículos') ||
        vehicleFitments.length > 0;
    checks.push({
        label: 'Contexto de compatibilidad vehicular',
        passed: hasCompatibilityContext,
        importance: 'high',
        tip: 'Las IA usan datos de compatibilidad para responder "sirve para mi carro?"'
    });
    if (hasCompatibilityContext) {
        score += 20;
        authoritySignals.push('Datos de compatibilidad claros');
        if (vehicleFitments.length > 0) {
            authoritySignals.push(`${vehicleFitments.length} vehículos documentados`);
        }
    } else {
        contextGaps.push('Falta contexto de compatibilidad');
    }

    // 4. Relationship Mapping (connects to other concepts)
    const relationshipTerms = ['funciona con', 'compatible con', 'se usa en', 'para transmisiones'];
    const hasRelationships = relationshipTerms.some(term => lowerDesc.includes(term));
    checks.push({
        label: 'Mapeo de relaciones (con qué conecta)',
        passed: hasRelationships,
        importance: 'high',
        tip: 'Las IA construyen grafos de conocimiento con relaciones explícitas'
    });
    if (hasRelationships) {
        score += 15;
        authoritySignals.push('Relaciones de compatibilidad mapeadas');
    } else {
        contextGaps.push('Relaciones del producto no claras');
    }

    // 5. Unique Value Proposition
    const valueProps = ['garantía', 'calidad', 'original', 'oem', 'mejor', 'único'];
    const hasValueProp = valueProps.some(vp => lowerDesc.includes(vp));
    checks.push({
        label: 'Propuesta de valor única',
        passed: hasValueProp,
        importance: 'medium',
        tip: 'La IA debe entender por qué elegir este producto sobre otros'
    });
    if (hasValueProp) {
        score += 10;
        authoritySignals.push('Diferenciadores claros');
    }

    // 6. Trust Indicators
    const trustSignals = ['garantía', 'años de experiencia', 'certificado', 'iso', 'garantía de por vida'];
    const hasTrust = trustSignals.some(ts => lowerDesc.includes(ts));
    checks.push({
        label: 'Indicadores de confianza',
        passed: hasTrust,
        importance: 'medium',
        tip: 'Menciones de garantía, certificaciones aumentan credibilidad'
    });
    if (hasTrust) {
        score += 10;
        authoritySignals.push('Señales de confianza presentes');
    }

    // 7. Content Freshness & Depth
    const wordCount = description.replace(/<[^>]*>/g, '').split(/\s+/).length;
    const hasDepth = wordCount > 200;
    checks.push({
        label: 'Contenido profundo (>200 palabras)',
        passed: hasDepth,
        importance: 'medium',
        tip: 'Las IA prefieren contenido completo para generar respuestas'
    });
    if (hasDepth) {
        score += 10;
        authoritySignals.push('Contenido profundo');
    } else {
        contextGaps.push('Contenido superficial');
    }

    // Determine entity clarity
    let entityClarity: 'good' | 'medium' | 'poor' = 'poor';
    if (hasEntityDefinition && hasCompatibilityContext && hasRelationships) {
        entityClarity = 'good';
    } else if (hasEntityDefinition || hasCompatibilityContext) {
        entityClarity = 'medium';
    }

    return { score: Math.min(100, score), checks, entityClarity, contextGaps, authoritySignals };
}

function analyzeSEOContent(content: string, type: 'title' | 'description' | 'meta_title' | 'meta_description'): {
    score: number;
    maxScore: number;
    issues: string[];
    suggestions: string[];
} {
    const issues: string[] = [];
    const suggestions: string[] = [];
    let score = 0;
    let maxScore = 100;

    if (!content || content.trim().length === 0) {
        return { score: 0, maxScore, issues: ['Contenido vacío'], suggestions: ['Agregar contenido'] };
    }

    const lowerContent = content.toLowerCase();

    switch (type) {
        case 'title':
            // Length check (50-60 chars ideal for Meta Title - Google truncates after ~60)
            if (content.length < 30) {
                issues.push('Título muy corto (< 30 caracteres)');
                suggestions.push('Expandir el título con keywords relevantes');
            } else if (content.length > 60) {
                issues.push('Título muy largo (> 60 caracteres) - Google truncará');
                suggestions.push('Acortar el título a 50-60 caracteres para mejor SEO');
                score += 10;
            } else {
                score += 25;
            }

            // Keyword presence (basic check)
            const genericWords = ['producto', 'item', 'nuevo', 'nueva'];
            const hasGenericOnly = genericWords.every(w => lowerContent.includes(w)) && content.length < 40;
            if (hasGenericOnly) {
                issues.push('Título demasiado genérico');
                suggestions.push('Incluir palabras clave específicas del producto');
            } else {
                score += 25;
            }

            // Brand mention
            if (!lowerContent.includes('example store') && !lowerContent.includes('example-store')) {
                suggestions.push('Considerar agregar la marca al título');
            } else {
                score += 15;
            }

            // Numbers/specifics (good for CTR)
            if (/\d/.test(content)) {
                score += 15;
            } else {
                suggestions.push('Agregar números o especificaciones técnicas para mejor CTR');
            }

            // Capitalization check
            if (content === content.toUpperCase()) {
                issues.push('Título en MAYÚSCULAS');
                suggestions.push('Usar capitalización apropiada');
                score -= 10;
            } else {
                score += 10;
            }

            break;

        case 'description':
        case 'meta_description':
            // Length check
            if (content.length < 100) {
                issues.push('Descripción muy corta');
                suggestions.push('Expandir a 150-300 palabras con información valiosa');
            } else if (content.length > 500 && type === 'meta_description') {
                issues.push('Meta descripción demasiado larga (> 160 caracteres recomendado)');
                suggestions.push('Acortar meta descripción a 150-160 caracteres');
                score += 10;
            } else {
                score += 20;
            }

            // HTML structure check
            const hasHTML = /<[a-z][\s\S]*>/i.test(content);
            if (!hasHTML && content.length > 200) {
                suggestions.push('Agregar formato HTML (h2, p, ul) para mejor estructura');
            } else if (hasHTML) {
                score += 15;
            }

            // Keyword density (simple check)
            const wordCount = content.split(/\s+/).length;
            if (wordCount < 50 && content.length > 200) {
                suggestions.push('Aumentar densidad de palabras clave');
            } else {
                score += 20;
            }

            // Duplicate content check (basic)
            const sentences = content.split(/[.!?]+/).filter(s => s.trim().length > 10);
            const uniqueSentences = new Set(sentences.map(s => s.trim().toLowerCase()));
            if (uniqueSentences.size < sentences.length * 0.8) {
                issues.push('Posible contenido repetitivo');
                suggestions.push('Revisar y eliminar frases repetidas');
            } else {
                score += 15;
            }

            // Call to action
            const ctaWords = ['comprar', 'adquirir', 'ordenar', 'llamar', 'contactar', 'ahora', 'hoy'];
            const hasCTA = ctaWords.some(w => lowerContent.includes(w));
            if (!hasCTA) {
                suggestions.push('Agregar llamado a la acción (CTA)');
            } else {
                score += 15;
            }

            // Vehicle fitment mention
            if (type === 'description' && !lowerContent.includes('compatible') && !lowerContent.includes('vehículo')) {
                suggestions.push('Mencionar compatibilidad con vehículos');
            } else if (type === 'description') {
                score += 15;
            }

            break;

        case 'meta_title':
            if (content.length < 50) {
                issues.push('Meta título muy corto');
                suggestions.push('Expandir a 50-60 caracteres');
            } else if (content.length > 70) {
                issues.push('Meta título muy largo');
                suggestions.push('Reducir a máximo 60 caracteres');
                score += 15;
            } else {
                score += 40;
            }

            if (content.includes('|')) {
                score += 20;
            } else {
                suggestions.push('Usar formato: "Título | Example Store"');
            }

            if (/\d/.test(content)) {
                score += 20;
            }

            break;
    }

    return { score: Math.max(0, Math.min(100, score)), maxScore, issues, suggestions };
}

function analyzeImages(images: Array<{ alt: string; filename: string }>): {
    score: number;
    total: number;
    withAlt: number;
    withGoodAlt: number;
    issues: string[];
} {
    const issues: string[] = [];
    let score = 0;

    if (images.length === 0) {
        return { score: 0, total: 0, withAlt: 0, withGoodAlt: 0, issues: ['Sin imágenes'] };
    }

    const withAlt = images.filter(img => img.alt && img.alt.trim().length > 0).length;
    const withGoodAlt = images.filter(img =>
        img.alt &&
        img.alt.trim().length > 10 &&
        !img.alt.toLowerCase().includes('image') &&
        !img.alt.toLowerCase().includes('img') &&
        !img.alt.toLowerCase().includes('foto')
    ).length;

    // Base score for having images
    score += Math.min(30, images.length * 10);

    // Alt tag coverage
    const altCoverage = withAlt / images.length;
    score += Math.round(altCoverage * 40);

    // Quality alt tags
    const qualityCoverage = withGoodAlt / images.length;
    score += Math.round(qualityCoverage * 30);

    if (withAlt === 0) {
        issues.push('Ninguna imagen tiene texto alternativo');
    } else if (withAlt < images.length) {
        issues.push(`${images.length - withAlt} imágenes sin alt text`);
    }

    if (withGoodAlt < withAlt) {
        issues.push(`${withAlt - withGoodAlt} imágenes con alt text genérico`);
    }

    return { score: Math.min(100, score), total: images.length, withAlt, withGoodAlt, issues };
}

function ProductMetricsPanel({ product, shopifyData, theme, darkMode }: ProductMetricsPanelProps) {
    // Client-only "today" stamp so SSR and CSR don't diverge on Date.now().
    const [today, setToday] = useState<string>('');
    useEffect(() => { setToday(formatDate(new Date())); }, []);

    // Analyze actual SEO content quality
    const titleAnalysis = analyzeSEOContent(product.title, 'title');
    const descriptionAnalysis = analyzeSEOContent(shopifyData?.body_html || '', 'description');
    const metaTitleAnalysis = analyzeSEOContent(shopifyData?.meta_title || '', 'meta_title');
    const metaDescAnalysis = analyzeSEOContent(shopifyData?.meta_description || '', 'meta_description');

    // Analyze images
    const imageAnalysis = analyzeImages(shopifyData?.images?.map(img => ({ alt: img.alt, filename: img.filename })) || []);

    // NEW: Analyze AEO (Answer Engine Optimization)
    const aeoAnalysis = analyzeAEOContent(
        product.title,
        shopifyData?.body_html || '',
        shopifyData?.meta_description || '',
        shopifyData?.vehicle_fitments || []
    );

    // NEW: Analyze GEO (Generative Engine Optimization)
    const geoAnalysis = analyzeGEOContent(
        product.title,
        shopifyData?.body_html || '',
        shopifyData?.meta_title || '',
        shopifyData?.vehicle_fitments || [],
        shopifyData?.vehicle_fitments || []
    );

    // Calculate weighted SEO score
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

    // Collect all issues and suggestions
    const allIssues = [
        ...titleAnalysis.issues.map(i => `Título: ${i}`),
        ...descriptionAnalysis.issues.map(i => `Descripción: ${i}`),
        ...imageAnalysis.issues.map(i => `Imágenes: ${i}`),
        ...metaTitleAnalysis.issues.map(i => `Meta Título: ${i}`),
        ...metaDescAnalysis.issues.map(i => `Meta Descripción: ${i}`),
    ];

    const allSuggestions = [
        ...titleAnalysis.suggestions.map(s => `Título: ${s}`),
        ...descriptionAnalysis.suggestions.map(s => `Descripción: ${s}`),
        ...aeoAnalysis.snippetOpportunities.map(s => `AEO: ${s}`),
        ...geoAnalysis.contextGaps.map(g => `GEO: ${g}`),
    ];

    // Calculate product completeness (more strict)
    const completenessItems = [
        {
            label: 'Título SEO',
            completed: titleAnalysis.score >= 60,
            score: 15,
            current: `${titleAnalysis.score}%`
        },
        {
            label: 'Descripción HTML',
            completed: descriptionAnalysis.score >= 50,
            score: 20,
            current: `${descriptionAnalysis.score}%`
        },
        {
            label: 'Imágenes (con alt)',
            completed: imageAnalysis.score >= 70,
            score: 15,
            current: `${imageAnalysis.withAlt}/${imageAnalysis.total}`
        },
        {
            label: 'SKU',
            completed: !!product.sku,
            score: 10,
            current: product.sku ? '✓' : '✗'
        },
        {
            label: 'Tipo',
            completed: !!product.product_type,
            score: 10,
            current: product.product_type || '—'
        },
        {
            label: 'Meta Título',
            completed: metaTitleAnalysis.score >= 60,
            score: 15,
            current: `${metaTitleAnalysis.score}%`
        },
        {
            label: 'Meta Desc',
            completed: metaDescAnalysis.score >= 60,
            score: 15,
            current: `${metaDescAnalysis.score}%`
        },
    ];
    const completenessScore = completenessItems.reduce((acc, item) => acc + (item.completed ? item.score : 0), 0);

    // Sales performance indicator
    const salesPerformance = product.total_sold > 100 ? 'high' : product.total_sold > 20 ? 'medium' : product.total_sold > 0 ? 'low' : 'none';
    const salesColors = {
        high: 'text-green-400',
        medium: 'text-[#f7b500]',
        low: 'text-orange-400',
        none: 'text-red-400'
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
                                <div className={`text-right`}>
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
                        <div className={`space-y-1.5 max-h-24 overflow-y-auto`}>
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

                    {/* AEO - Answer Engine Optimization */}
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

                        {/* AEO Checks */}
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

                        {/* Snippet Opportunities */}
                        {aeoAnalysis.snippetOpportunities.length > 0 && (
                            <div className="mt-3 pt-3 border-t border-blue-500/20">
                                <p className="text-xs text-blue-400 font-medium mb-1">💡 Oportunidades:</p>
                                <p className="text-[10px] text-blue-300">{aeoAnalysis.snippetOpportunities[0]}</p>
                            </div>
                        )}
                    </div>

                    {/* GEO - Generative Engine Optimization */}
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

                        {/* Authority Signals */}
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

                        {/* Context Gaps */}
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
