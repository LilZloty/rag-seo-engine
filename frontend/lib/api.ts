// API client for RAG SEO Engine Backend

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

// Types
export interface Product {
    id: string;
    shopify_id: string;
    title: string;
    handle: string;
    sku: string | null;
    product_type: string | null;
    vendor: string | null;
    description_length: number;
    seo_score: number;  // 0-100 score indicating SEO optimization level
    seo_status: 'needs_seo' | 'draft' | 'published';
    needs_seo: boolean;
    image_count: number;
    // Sales data (displayed based on selected period)
    total_sold: number;
    total_revenue: number;
    // Time-based sales data
    sold_30d: number;
    revenue_30d: number;
    sold_90d: number;
    revenue_90d: number;
    sold_365d: number;
    revenue_365d: number;
    sold_all_time: number;
    revenue_all_time: number;
    created_at: string | null;  // When added to Shopify (or DB if not synced)
    updated_at?: string;  // When last updated in Shopify (or DB if not synced)
    // Shopify timestamps (from Shopify API)
    shopify_created_at?: string | null;  // When product was created in Shopify
    shopify_updated_at?: string | null;  // When product was last updated in Shopify
    // Additional fields from dashboard
    image_url?: string;
    transmission_code?: string;
    seo_content?: boolean;
    price?: string | null;  // Product price from Shopify
    // GA4 Analytics Fields
    ga4_sessions?: number;
    ga4_engagement_time?: number;
    ga4_bounce_rate?: number;
    ga4_revenue?: number;
    // Search Console Fields
    gsc_impressions?: number;
    gsc_clicks?: number;
    gsc_ctr?: number;
    gsc_position?: number;
    // Calculated Fields
    performance_score?: number;
    opportunity_level?: 'high' | 'medium' | 'low';
    last_analytics_sync?: string | null;
    // Inventory/Stock Fields
    inventory_quantity?: number;
    inventory_status?: 'in_stock' | 'out_of_stock' | 'low_stock';
    last_inventory_sync?: string | null;
}

export interface Library {
    id: string;
    name: string;
    name_es?: string;
    library_type: 'brand' | 'product_type' | 'transmission';
    description: string | null;
    document_count: number;
    is_active: boolean;
}

export interface Document {
    id: string;
    title: string;
    source_type: 'scraped' | 'uploaded_pdf' | 'manual';
    source_url: string | null;
    source_filename: string | null;
    brands: string[];
    product_types: string[];
    transmission_codes: string[];
    chunk_count: number;
    verified: boolean;
}

export interface PromptTemplate {
    id: string;
    name: string;
    template_type: string;
    system_instructions: string;
    is_active: boolean;
    priority: number;
}

export interface ContentDraft {
    id: string;
    product_id: string;
    content: any;
    status: 'draft' | 'approved' | 'published';
    created_at: string;
}

export interface GenerateRequest {
    product_id: string;
    library_ids?: string[];
    template_id?: string;
    image_config?: {
        count: number;
        types: string[];
    };
    provider?: string;
    model_name?: string;
    // Analysis insights for context-aware generation
    analysis_insights?: {
        primary_issue?: {
            type: string;
            severity: string;
            description: string;
            why?: string;
        };
        top_queries?: Array<{
            query: string;
            impressions: number;
            opportunity: string;
        }>;
        recommendations?: Array<{
            priority: string;
            category: string;
            action: string;
            expected_impact: string;
        }>;
        keyword_opportunities?: string[];
        question_targets?: string[];
        generated_content?: {
            suggested_meta_title?: string;
            suggested_meta_description?: string;
            faq_questions?: string[];
        };
        visibility_score?: Record<string, number>;
    };
}

export interface GenerationSource {
    type: 'rag' | 'web';
    file?: string;
    chunks?: number;
    supplier?: string;
    url?: string;
    title?: string;
}

export interface GenerationMeta {
    sources: GenerationSource[];
    rag_chunks: number;
    web_search_used: boolean;
    generation_time_ms: number;
    prompt_hash: string;
    model: string;
}

export interface GenerateResponse {
    content: any;
    _generation_meta?: GenerationMeta;
}

// In-memory request cache with TTL (stale-while-revalidate)
const _requestCache = new Map<string, { data: any; expiry: number; promise?: Promise<any> }>();
// 5 minutes — long enough to survive segment switching + tab revisits without
// re-querying, short enough that nightly sync results show up after one TTL.
const DEFAULT_CACHE_TTL = 300_000;

function getCached<T>(key: string): T | null {
    const entry = _requestCache.get(key);
    if (entry && Date.now() < entry.expiry) return entry.data as T;
    return null;
}

function setCached(key: string, data: any, ttl = DEFAULT_CACHE_TTL) {
    _requestCache.set(key, { data, expiry: Date.now() + ttl });
}

// API Helper
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const method = options?.method?.toUpperCase() || 'GET';

    // Only cache GET requests
    if (method === 'GET') {
        const cached = getCached<T>(url);
        if (cached) return cached;
    }

    console.log(`[API] Fetching: ${url}`);

    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
        ...options,
    });

    if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        console.error(`[API] Error ${response.status}:`, errorText);
        throw new Error(`API Error ${response.status}: ${errorText}`);
    }

    const data = await response.json();

    // Cache successful GET responses
    if (method === 'GET') {
        setCached(url, data);
    }

    return data;
}

// Product API
export const productAPI = {
    getProducts: (params?: {
        needs_seo_only?: boolean;
        opportunity_level?: string;
        min_performance_score?: number;
        min_sessions?: number;
        segment?: string;  // Smart segment filter
        sales_period?: '30d' | '90d' | '365d' | 'all_time';  // Sales time period
        search?: string;  // Search by title, SKU, or handle
        limit?: number;
        offset?: number;
    }) => {
        const searchParams = new URLSearchParams();
        if (params?.needs_seo_only) searchParams.set('needs_seo_only', 'true');
        if (params?.opportunity_level) searchParams.set('opportunity_level', params.opportunity_level);
        if (params?.min_performance_score !== undefined) searchParams.set('min_performance_score', params.min_performance_score.toString());
        if (params?.min_sessions !== undefined) searchParams.set('min_sessions', params.min_sessions.toString());
        if (params?.segment && params.segment !== 'all') searchParams.set('segment', params.segment);
        if (params?.sales_period) searchParams.set('sales_period', params.sales_period);
        if (params?.search) searchParams.set('search', params.search);
        if (params?.limit) searchParams.set('limit', params.limit.toString());
        if (params?.offset) searchParams.set('offset', params.offset.toString());

        return fetchAPI<{ products: Product[]; total: number; sales_period: string }>(`/products?${searchParams}`);
    },

    getProduct: (id: string) => fetchAPI<Product>(`/products/${id}`),

    getProductShopifyDetails: (id: string) => fetchAPI<ShopifyProductDetails>(`/products/${id}/shopify`),

    updateProduct: (id: string, data: any) => fetchAPI<{ success: boolean; message: string }>(`/products/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }),

    generateSchema: (id: string, data?: { description_html?: string; h1_title?: string }) =>
        fetchAPI<{
            product_id: string;
            schema: Record<string, unknown>;
            entities_count: number;
            has_faq: boolean;
            has_howto: boolean;
            has_vehicles: boolean;
        }>(`/products/${id}/generate-schema`, {
            method: 'POST',
            body: JSON.stringify(data || {}),
        }),

    syncShopify: () => fetchAPI<{ message: string }>('/products/sync-shopify', { method: 'POST' }),

    syncSales: () => fetchAPI<{ message: string; products_with_sales: number; products_updated: number }>('/products/sync-sales', { method: 'POST' }),

    checkNewProducts: () => fetchAPI<{ message: string; new_products: number; total_in_database: number; total_in_shopify: number; in_sync: boolean }>('/products/check-new', { method: 'POST' }),

    refreshFitments: (productId: string) => fetchAPI<{ success: boolean; message: string; fitment_count: number; vehicle_fitments: any[] }>(`/products/${productId}/refresh-fitments`, { method: 'POST' }),

    syncAnalytics: () => fetchAPI<{ updated: number; total_products: number; timestamp: string }>('/products/sync-analytics', { method: 'POST' }),

    syncInventory: (productIds?: string[], options?: { max_age_minutes?: number; force?: boolean }) => fetchAPI<{ message: string; products_synced: number; products_updated: number; skipped: number; timestamp: string }>('/products/sync-inventory', {
        method: 'POST',
        body: JSON.stringify({ product_ids: productIds || [], ...(options || {}) })
    }),

    getAnalyticsSummary: () => fetchAPI<{
        total_products: number;
        products_with_ga4: number;
        products_with_gsc: number;
        avg_performance_score: number;
        high_opportunity_count: number;
        medium_opportunity_count: number;
        low_opportunity_count: number;
    }>('/products/analytics/summary'),

    getSegmentCounts: () => fetchAPI<{
        all: number;
        'quick-wins': number;
        'revenue-at-risk': number;
        'new-products': number;
        'zombie-products': number;
        'top-performers': number;
        'high-opportunity': number;
        'needs-seo': number;
    }>('/products/segment-counts'),

    // Content Analysis with Grok
    getProductAnalytics: (productId: string, days?: number) =>
        fetchAPI<{
            product_id: string;
            title: string;
            handle: string;
            sku: string | null;
            price: number;
            product_type: string | null;
            vendor: string | null;
            tags: string[];
            sold_30d: number;
            revenue_30d: number;
            sold_90d: number;
            revenue_90d: number;
            sold_365d: number;
            revenue_365d: number;
            ga4_sessions: number;
            ga4_engagement_time: number;
            ga4_bounce_rate: number;
            ga4_revenue: number;
            gsc_impressions: number;
            gsc_clicks: number;
            gsc_ctr: number;
            gsc_position: number;
            seo_score: number;
            description_length: number;
            image_count: number;
            needs_seo: boolean;
            opportunity_level: string;
            performance_score: number;
        }>(`/analyze/product-analytics/${productId}?days=${days || 30}`),

    analyzeContentWithAI: (data: {
        product_id: string;
        title: string;
        description: string;
        meta_title?: string;
        meta_description?: string;
        price: number;
        product_type?: string;
        sold_30d: number;
        sold_90d?: number;
        sold_365d?: number;
        revenue_30d: number;
        revenue_90d?: number;
        ga4_sessions: number;
        ga4_engagement_time: number;
        gsc_impressions: number;
        gsc_clicks: number;
        gsc_position: number;
        seo_score: number;
        description_length: number;
        image_count: number;
        top_keywords?: string[];
        vehicle_fitments?: string[];
        provider?: string;
        model_name?: string;
    }, forceRefresh: boolean = false) => fetchAPI<{
        seo_analysis: {
            score: number;
            critical_issues: string[];
            improvements: string[];
            keyword_opportunities: string[];
            keyword_opportunities_status?: 'real' | 'no_data';
        };
        aeo_analysis: {
            score: number;
            snippet_opportunities: string[];
            question_targets: string[];
            structured_data_recommendations: string[];
        };
        geo_analysis: {
            score: number;
            entity_clarity: string;
            context_gaps: string[];
            authority_signals: string[];
        };
        recommendations: Array<{
            priority: 'high' | 'medium' | 'low';
            category: 'seo' | 'aeo' | 'geo' | 'conversion';
            action: string;
            expected_impact: string;
            implementation: string;
            why_it_matters?: string;
            auto_generate?: boolean;
            generated_content?: string;
        }>;
        priority_actions: string[];
        expected_impact: {
            traffic_increase: string;
            conversion_increase: string;
            timeline: string;
            revenue_potential?: string;
        };
        cached: boolean;
        cache_age_hours: number;
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
            top_performers?: Array<{
                title: string;
                revenue_30d: number;
                sold_30d: number;
                sessions: number;
            }>;
        };
        ai_visibility_scores?: {
            grok?: number;
            openai?: number;
            perplexity?: number;
            [key: string]: number | undefined;
        } | null;
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
        };
        estimated_revenue_opportunity?: number;
        generated_content?: {
            suggested_meta_title?: string;
            suggested_meta_description?: string;
            faq_questions?: string[];
            comparison_table_html?: string;
        };
    }>(`/analyze/ai-content-review?force_refresh=${forceRefresh}${data.provider ? `&provider=${data.provider}` : ''}${data.model_name ? `&model_name=${data.model_name}` : ''}`, { method: 'POST', body: JSON.stringify(data) }),

    // Lightweight cache-only lookup (never triggers Grok)
    getCachedAnalysis: (productId: string) =>
        fetchAPI<{
            seo_analysis: { score: number; critical_issues?: string[]; improvements?: string[]; keyword_opportunities?: string[]; keyword_opportunities_status?: 'real' | 'no_data' };
            aeo_analysis: { score: number; snippet_opportunities?: string[]; question_targets?: string[]; structured_data_recommendations?: string[] };
            geo_analysis: { score: number; entity_clarity?: string; context_gaps?: string[]; authority_signals?: string[] };
            recommendations: Array<{
                priority: 'high' | 'medium' | 'low';
                category: string;
                action: string;
                expected_impact: string;
                implementation: string;
                why_it_matters?: string;
                auto_generate?: boolean;
                generated_content?: string;
            }>;
            priority_actions: string[];
            expected_impact: { traffic_increase?: string; conversion_increase?: string; timeline?: string; revenue_potential?: string };
            cached: boolean;
            cache_age_hours: number;
            primary_issue?: { type: string; severity?: string; description: string; why?: string; impact_if_fixed?: string };
            performance_vs_benchmark?: any;
            ai_visibility_scores?: { [key: string]: number | undefined } | null;
            ai_visibility_status?: 'fresh' | 'stale' | 'not_measured' | 'unknown' | null;
            ai_visibility_snapshot_date?: string | null;
            ai_visibility_age_days?: number | null;
            top_opportunity_queries?: Array<{ query: string; impressions: number; clicks: number; position: number; opportunity: string }>;
            trend_indicators?: { traffic?: string; position?: string; ai_visibility?: string };
            estimated_revenue_opportunity?: number;
            performance_tier?: string;
        }>(`/analyze/cached/${productId}`),

    // Category Benchmarks (v2)
    getCategoryBenchmarks: (productType: string) =>
        fetchAPI<{
            product_type: string;
            product_count: number;
            avg_conversion_rate: number;
            avg_sessions: number;
            avg_ctr: number;
            avg_position: number;
            avg_price: number;
            avg_description_length: number;
            top_performers: Array<{
                title: string;
                revenue_30d: number;
                sold_30d: number;
                sessions: number;
            }>;
            common_winning_features: string[];
        }>(`/analyze/category-benchmarks/${encodeURIComponent(productType)}`),
};

// Shopify product details (full data from Shopify API)
export interface ShopifyProductDetails {
    local_id: number;
    shopify_id: string;
    title: string;
    handle: string;
    body_html: string;
    vendor: string;
    product_type: string;
    sku: string;
    price: string;
    images: Array<{
        id: number;
        src: string;
        alt: string;
        filename: string;
    }>;
    image_count: number;
    tags: string;
    status: string;
    meta_title: string;
    meta_description: string;
    short_description: string;
    compatible_vehicles: string;
    resumen?: string;
    metafields: Record<string, string>;
    vehicle_fitments?: Array<{
        id: number;
        make: string[];
        modelo: string[];
        year_start: number | null;
        year_end: number | null;
        transmission_type: string;
        transmission_model: string;
        engine: string;
    }>;
}

// Library API
export const libraryAPI = {
    getLibraries: (params?: { library_type?: string; is_active?: boolean }) => {
        const searchParams = new URLSearchParams();
        if (params?.library_type) searchParams.set('library_type', params.library_type);
        if (params?.is_active !== undefined) searchParams.set('is_active', params.is_active.toString());

        return fetchAPI<Library[]>(`/libraries?${searchParams}`);
    },

    getLibrary: (id: string) => fetchAPI<Library>(`/libraries/${id}`),

    createLibrary: (data: Partial<Library>) =>
        fetchAPI<Library>('/libraries', { method: 'POST', body: JSON.stringify(data) }),

    updateLibrary: (id: string, data: Partial<Library>) =>
        fetchAPI<Library>(`/libraries/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

    deleteLibrary: (id: string) =>
        fetchAPI<void>(`/libraries/${id}`, { method: 'DELETE' }),
};

// Document API
export const documentAPI = {
    getDocuments: (params?: { library_id?: string; source_type?: string }) => {
        const searchParams = new URLSearchParams();
        if (params?.library_id) searchParams.set('library_id', params.library_id);
        if (params?.source_type) searchParams.set('source_type', params.source_type);

        return fetchAPI<Document[]>(`/documents?${searchParams}`);
    },

    getDocument: (id: string) => fetchAPI<Document>(`/documents/${id}`),

    uploadDocument: async (formData: FormData) => {
        const response = await fetch(`${API_BASE}/documents/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown upload error' }));
            throw new Error(error.detail || `Upload failed: ${response.status}`);
        }

        return response.json();
    },

    scrapeUrl: (url: string, brands?: string, productTypes?: string, transmissionCodes?: string) => {
        const params = new URLSearchParams({ url });
        if (brands) params.set('brands', brands);
        if (productTypes) params.set('product_types', productTypes);
        if (transmissionCodes) params.set('transmission_codes', transmissionCodes);

        return fetchAPI<{ status: string; document_id: string; chunk_count: number }>(
            `/documents/scrape?${params}`,
            { method: 'POST' }
        );
    },

    // Async URL scrape — dispatches to the crawler worker (full crawl4ai +
    // headless Chromium). Returns a task_id; poll via documentAPI.pollTask.
    scrapeUrlAsync: (url: string, brands?: string, productTypes?: string, transmissionCodes?: string) => {
        const params = new URLSearchParams({ url });
        if (brands) params.set('brands', brands);
        if (productTypes) params.set('product_types', productTypes);
        if (transmissionCodes) params.set('transmission_codes', transmissionCodes);

        return fetchAPI<{ task_id: string; status: string; poll_url: string }>(
            `/documents/scrape/async?${params}`,
            { method: 'POST' }
        );
    },

    // Async bulk scrape — parallel Crawl4AI via SemaphoreDispatcher on a worker.
    scrapeUrlsBulkAsync: (urls: string[], brands?: string, productTypes?: string, transmissionCodes?: string, maxConcurrent: number = 5) => {
        const params = new URLSearchParams();
        if (brands) params.set('brands', brands);
        if (productTypes) params.set('product_types', productTypes);
        if (transmissionCodes) params.set('transmission_codes', transmissionCodes);
        params.set('max_concurrent', String(maxConcurrent));

        return fetchAPI<{ task_id: string; status: string; url_count: number; poll_url: string }>(
            `/documents/scrape/bulk-async?${params}`,
            { method: 'POST', body: JSON.stringify(urls), headers: { 'Content-Type': 'application/json' } }
        );
    },

    // Fetch the current state of a Celery task.
    getTaskStatus: (taskId: string) =>
        fetchAPI<{ task_id: string; status: string; result: unknown; progress: unknown }>(
            `/tasks/${taskId}`
        ),

    // Poll a task until it reaches a terminal state. Returns the unwrapped
    // task result on SUCCESS; throws on FAILURE or timeout. `onProgress` is
    // called with each non-terminal status so the UI can show what's happening.
    pollTask: async <T = unknown>(
        taskId: string,
        opts: { intervalMs?: number; timeoutMs?: number; onProgress?: (status: string) => void } = {}
    ): Promise<T> => {
        const { intervalMs = 2000, timeoutMs = 180_000, onProgress } = opts;
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            const snap = await documentAPI.getTaskStatus(taskId);
            if (snap.status === 'SUCCESS') return snap.result as T;
            if (snap.status === 'FAILURE') {
                const msg = typeof snap.result === 'string' ? snap.result : 'Task failed';
                throw new Error(msg);
            }
            onProgress?.(snap.status);
            await new Promise((r) => setTimeout(r, intervalMs));
        }
        throw new Error(`Task ${taskId} timed out after ${timeoutMs}ms`);
    },

    ingestText: (title: string, content: string, brands?: string, productTypes?: string, transmissionCodes?: string) => {
        const params = new URLSearchParams({ title, content });
        if (brands) params.set('brands', brands);
        if (productTypes) params.set('product_types', productTypes);
        if (transmissionCodes) params.set('transmission_codes', transmissionCodes);

        return fetchAPI<{ status: string; document_id: string; chunk_count: number }>(
            `/documents/text?${params}`,
            { method: 'POST' }
        );
    },

    deleteDocument: (id: string) =>
        fetchAPI<void>(`/documents/${id}`, { method: 'DELETE' }),

    linkToLibrary: (documentId: string, libraryId: string) =>
        fetchAPI<{ status: string }>(`/documents/${documentId}/link/${libraryId}`, { method: 'POST' }),

    unlinkFromLibrary: (documentId: string, libraryId: string) =>
        fetchAPI<{ status: string }>(`/documents/${documentId}/link/${libraryId}`, { method: 'DELETE' }),

    getDocumentLibraries: (documentId: string) =>
        fetchAPI<{ document_id: string; libraries: Array<{ id: string; name: string; library_type: string }> }>(`/documents/${documentId}/libraries`),
};

// Prompt Template API
export const promptAPI = {
    getTemplates: (params?: { template_type?: string; is_active?: boolean }) => {
        const searchParams = new URLSearchParams();
        if (params?.template_type) searchParams.set('template_type', params.template_type);
        if (params?.is_active !== undefined) searchParams.set('is_active', params.is_active.toString());

        return fetchAPI<PromptTemplate[]>(`/prompts?${searchParams}`);
    },

    getTemplate: (id: string) => fetchAPI<PromptTemplate>(`/prompts/${id}`),

    createTemplate: (data: Partial<PromptTemplate>) =>
        fetchAPI<PromptTemplate>('/prompts', { method: 'POST', body: JSON.stringify(data) }),

    updateTemplate: (id: string, data: Partial<PromptTemplate>) =>
        fetchAPI<PromptTemplate>(`/prompts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

    deleteTemplate: (id: string) =>
        fetchAPI<void>(`/prompts/${id}`, { method: 'DELETE' }),
};

// Content Generation API
export const contentAPI = {
    generate: (request: GenerateRequest) =>
        fetchAPI<{ content: any }>('/content/generate', {
            method: 'POST',
            body: JSON.stringify(request),
        }),

    getDrafts: (productId: string) =>
        fetchAPI<ContentDraft[]>(`/content/drafts/${productId}`),

    saveDraft: (productId: string, content: any) =>
        fetchAPI<ContentDraft>('/content/drafts', {
            method: 'POST',
            body: JSON.stringify({ product_id: productId, content }),
        }),

    publishDraft: (draftId: string) =>
        fetchAPI<{ success: boolean }>(`/content/drafts/${draftId}/publish`, { method: 'POST' }),
};

// ============ AEO (Answer Engine Optimization) API ============

export interface ProductChunk {
    product_type: string;
    product_count: number;
    approved: boolean;
    approved_at: string | null;
    approved_by: string | null;
    notes: string | null;
    sample_products: any[];
}

export interface LLMSTxtPreview {
    content: string;
    token_estimate: number;
    byte_size: number;
    approved_chunks: number;
    total_chunks: number;
    last_generated: string | null;
}

export interface BlogArticle {
    id: string;
    title: string;
    handle: string;
    url: string;
    summary: string | null;
    tags: string[];
    published_at: string | null;
    include_in_llms_txt: boolean;
}

export interface AEOConfig {
    llms_txt_version: string;
    include_blogs: boolean;
    include_collections: boolean;
    max_products_per_category: number;
    store_name: string;
    store_description: string;
    include_fault_codes?: boolean;
    authority_statement?: string;
}

export interface SchemaMetrics {
    faq_schemas_deployed: number;
    howto_schemas_deployed: number;
    vehiclepart_schemas_deployed: number;
    total_coverage_pct: number;
    last_updated: string;
}

export interface AITrafficReport {
    status: string;
    summary: {
        total_sessions: number;
        ai_sessions: number;
        llms_txt_sessions: number;
        traditional_sessions: number;
        referrers: Record<string, number>;
    };
    raw_data: {
        llm_traffic: any[];
        ai_referrals: any[];
    };
}

// ============ LLM Sales Attribution Types ============

export interface OrderAttribution {
    first_visit: {
        referrer_url: string;
        landing_page: string;
        source: string;
        utm_source: string;
        utm_medium: string;
        utm_campaign: string;
    };
    last_visit: {
        referrer_url: string;
        landing_page: string;
        source: string;
    };
}

export interface OrderDetail {
    order_id: string;
    order_name: string;
    amount: number;
    currency: string;
    created_at: string;
    date: string;
    time: string;
    attribution: OrderAttribution;
    note: string;
}

export interface LLMSalesBySource {
    source: string;  // chatgpt, gemini, perplexity, claude, copilot, other_ai
    sales: number;
    orders: number;
    aov: number;
    percent_of_total: number;
    top_referrers?: Array<{ url: string; count: number }>;
    orders_detail?: OrderDetail[];
}

export interface MonthlyTrend {
    month: string;
    sales: number;
    orders: number;
}

export interface LLMSalesReport {
    status: 'success' | 'no_data';
    message?: string;
    summary: {
        total_sales: number;
        total_orders: number;
        average_order_value: number;
        sources_detected?: number;
    };
    by_source: LLMSalesBySource[];
    monthly_trend?: MonthlyTrend[];
    all_referrers_sample?: Array<{ url: string; count: number }>;
    comparison: {
        sales_change_pct: number;
        orders_change_pct: number;
        aov_change_pct: number;
    } | null;
    period: {
        start: string;
        end: string;
    } | null;
}

// ============ ENHANCED LLM Analytics Types ============

export interface LLMAttributionAlert {
    type: 'trend_down' | 'trend_up' | 'anomaly' | 'opportunity' | 'insight';
    severity: 'low' | 'medium' | 'high';
    source?: string;
    metric?: string;
    current_value?: number;
    previous_value?: number;
    change_pct?: number;
    message: string;
    recommendation: string;
}

export interface AssistedConversions {
    direct: Record<string, { orders: number; sales: number }>;
    first_touch: Record<string, { orders: number; sales: number }>;
    middle_touch: Record<string, { orders: number; sales: number }>;
    last_touch: Record<string, { orders: number; sales: number }>;
    total_influenced: number;
    multi_source_customers: number;
    attribution_model: {
        last_touch_total: number;
        first_touch_total: number;
        direct_total: number;
        total_assisted: number;
    };
}

export interface TimeToConversion {
    avg_hours: number;
    median_hours: number;
    min_hours: number;
    max_hours: number;
    percentile_25: number;
    percentile_75: number;
    distribution: {
        '0-1h': number;
        '1-24h': number;
        '1-7d': number;
        '1-30d': number;
        '30d+': number;
    };
    sample_size: number;
}

export interface CategoryPerformance {
    category: string;
    llm_sales: number;
    llm_orders: number;
    total_sales: number;
    total_orders: number;
    llm_penetration_pct: number;
    avg_order_value: number;
    top_sources: Array<[string, number]>;
    product_count: number;
}

export interface CohortMetrics {
    cohort_month: string;
    source: string;
    initial_customers: number;
    total_orders: number;
    retention_30d: number;
    avg_orders_per_customer: number;
    total_revenue: number;
    ltv: number;
}

export interface GeoMetrics {
    country: string;
    region: string | null;
    sales: number;
    orders: number;
    customers: number;
    avg_order_value: number;
    sources: Record<string, number>;
}

export interface ConversionFunnel {
    impressions: number;
    traffic: number;
    product_views: number;
    add_to_carts: number;
    checkouts: number;
    purchases: number;
    revenue: number;
    conversion_rates: {
        traffic_to_view: number;
        view_to_cart: number;
        cart_to_checkout: number;
        checkout_to_purchase: number;
        overall: number;
    };
    period_days: number;
}

export interface EnhancedLLMSalesReport {
    status: 'success' | 'no_data';
    message?: string;
    basic: LLMSalesReport;
    enhanced: {
        assisted_conversions?: AssistedConversions;
        time_to_conversion?: Record<string, TimeToConversion>;
        category_performance?: CategoryPerformance[];
        cohort_analysis?: CohortMetrics[];
        geographic?: GeoMetrics[];
    };
    alerts: LLMAttributionAlert[];
}


// ============ AEO Impact Timeline Types ============

export type AEOEventType =
    | 'llms_txt_deployed'
    | 'schema_added'
    | 'content_updated'
    | 'visibility_check'
    | 'keyword_published'
    | 'other';

export interface AEOEvent {
    id: number;
    event_date: string;      // ISO 8601
    event_type: AEOEventType;
    title: string;
    description?: string;
    created_at: string;
}

// ============ Visibility Weekly Trend Types ============

export interface VisibilityWeeklyTrend {
    week: string;                 // "2025-W04"
    week_label: string;           // "Feb W4"
    brand_mention_pct: number;    // % of prompts where brand was mentioned
    citation_pct: number;         // % of prompts where URL was cited
    share_of_voice: number;       // brand / (brand + competitor) * 100
    competitor_mention_pct: number;
    total_checks: number;
}

export interface FaultCode {
    code: string;
    name: string;
    description: string;
    severity: 'low' | 'medium' | 'high';
    monthly_clicks: number;
    monthly_impressions: number;
    current_ctr: number;
    transmissions: string[];
    vehicles: string[];
    blog_url?: string;
    is_priority: boolean;
    has_faq_schema: boolean;
}

export interface Solution {
    fault_code: string;
    title: string;
    description: string;
    recommended_skus: string[];
    collection_url?: string;
}

export const aeoAPI = {
    // llms.txt
    getLLMSTxtPreview: () =>
        fetchAPI<LLMSTxtPreview>('/aeo/llms-txt/preview'),

    downloadLLMSTxt: async (forceRebuild: boolean = false) => {
        const response = await fetch(`${API_BASE}/aeo/llms-txt?force_rebuild=${forceRebuild}`);
        return response.text();
    },

    rebuildLLMSTxt: () =>
        fetchAPI<{ status: string; token_estimate: number; byte_size: number }>('/aeo/rebuild', { method: 'POST' }),

    // Chunks
    getChunks: () =>
        fetchAPI<ProductChunk[]>('/aeo/chunks'),

    approveChunk: (productType: string, approved: boolean, notes?: string) =>
        fetchAPI<{ product_type: string; approved: boolean; message: string }>(
            `/aeo/chunks/${encodeURIComponent(productType)}/approve`,
            { method: 'POST', body: JSON.stringify({ approved, notes, approved_by: 'admin' }) }
        ),

    // Schema.org
    getProductSchema: (productId: string) =>
        fetchAPI<{ product_id: string; json_ld: any; validation_status: string }>(
            `/aeo/schema/product/${productId}`
        ),

    getBulkSchemas: (chunkId?: string) => {
        const params = chunkId ? `?chunk_id=${encodeURIComponent(chunkId)}` : '';
        return fetchAPI<{ count: number; schemas: any[] }>(`/aeo/schema/bulk${params}`);
    },

    // Blogs
    getBlogs: () =>
        fetchAPI<BlogArticle[]>('/aeo/blogs'),

    // Knowledge Graph (GEO)
    getFaultCodes: (priorityOnly: boolean = false) =>
        fetchAPI<{ count: number; fault_codes: FaultCode[] }>(`/aeo/fault-codes?priority_only=${priorityOnly}`),

    syncKnowledgeGraph: () =>
        fetchAPI<{ status: string; fault_codes_seeded: number; solutions_seeded: number }>(
            '/aeo/sync-knowledge-graph',
            { method: 'POST' }
        ),

    getSolutions: (faultCode?: string) => {
        const params = faultCode ? `?fault_code=${faultCode}` : '';
        return fetchAPI<{ count: number; solutions: Solution[] }>(`/aeo/solutions${params}`);
    },

    // Config
    getConfig: () =>
        fetchAPI<AEOConfig>('/aeo/config'),

    updateConfig: (config: Partial<AEOConfig>) =>
        fetchAPI<{ status: string; config: AEOConfig }>('/aeo/config', {
            method: 'PATCH',
            body: JSON.stringify(config)
        }),

    // NEW: Auto-approve top chunks
    autoApproveChunks: (limit: number = 15, minProducts: number = 5) =>
        fetchAPI<{ status: string; approved_count: number; approved_types: string[]; skipped: number; message: string }>
            (`/aeo/chunks/auto-approve?limit=${limit}&min_products=${minProducts}`, { method: 'POST' }),

    // NEW: Get real products for a fault code
    getProductsForFaultCode: (code: string, limit: number = 10) =>
        fetchAPI<{ fault_code: string; count: number; products: RecommendedProduct[] }>
            (`/aeo/fault-codes/${code}/products?limit=${limit}`),

    // NEW: Schema Metrics
    getSchemaMetrics: () =>
        fetchAPI<SchemaMetrics>('/aeo/schema/metrics'),

    // NEW: Product Intelligence
    getProductIntelligence: (days: number = 365) =>
        fetchAPI<ProductIntelligenceResponse>(`/aeo/product-intelligence?days=${days}`),

    // NEW: Product "Why" Analysis — explains why products get LLM recommendations
    getProductWhyAnalysis: (productId?: number, limit: number = 20) =>
        fetchAPI<ProductWhyAnalysis>(`/aeo/product-intelligence/why${productId ? `?product_id=${productId}&limit=${limit}` : `?limit=${limit}`}`),

    // NEW: Visibility-to-Sales Correlation
    getVisibilityCorrelation: (days: number = 30) =>
        fetchAPI<VisibilitySalesCorrelation>(`/aeo/visibility-correlation?days=${days}`),

    // ---- Impact Timeline ----
    getEvents: () =>
        fetchAPI<AEOEvent[]>('/aeo/events'),

    createEvent: (payload: { event_date: string; event_type: AEOEventType; title: string; description?: string }) =>
        fetchAPI<AEOEvent>('/aeo/events', { method: 'POST', body: JSON.stringify(payload) }),

    deleteEvent: (id: number) =>
        fetchAPI<{ status: string; id: number }>(`/aeo/events/${id}`, { method: 'DELETE' }),

    // ---- Visibility Weekly Trend ----
    getVisibilityTrend: (weeks: number = 8) =>
        fetchAPI<VisibilityWeeklyTrend[]>(`/aeo/visibility/trend?weeks=${weeks}`),

    // ---- Article Enrichment (AEO metafields auto-fill) ----
    enrichArticle: (
        articleId: number,
        opts: { blog_id?: number; target_keyword?: string; dry_run?: boolean; write_threshold?: number } = {}
    ) =>
        fetchAPI<ArticleEnrichmentResult>(`/aeo/articles/${articleId}/enrich`, {
            method: 'POST',
            body: JSON.stringify({
                blog_id: opts.blog_id ?? null,
                target_keyword: opts.target_keyword ?? null,
                dry_run: opts.dry_run ?? true,
                write_threshold: opts.write_threshold ?? 0.7,
            }),
        }),

    listArticlesWithMetrics: (opts?: { needs_enrichment_only?: boolean }) =>
        fetchAPI<{ count: number; articles: ArticleMetricsRow[] }>(
            `/aeo/articles/with-metrics?needs_enrichment_only=${opts?.needs_enrichment_only ?? false}`
        ),
};

export interface ArticleMetricsRow {
    article_id: number | string;
    title: string;
    handle: string;
    blog_handle: string;
    url: string;
    tags: string[];
    published_at: string | null;
    enrichment: {
        has_tldr: boolean;
        faqs_count: number;
        last_reviewed_at: string | null;
        fully_enriched: boolean;
    };
    gsc: {
        clicks: number;
        impressions: number;
        ctr: number | null;
        position: number | null;
    };
    ga4: {
        sessions: number;
        active_users: number;
        avg_duration: number | null;
        bounce_rate: number | null;
        conversions: number;
    };
    fault_codes: string[];
    aeo_score: number;
}

export interface ArticleEnrichmentResult {
    status: string;
    article_id: number;
    article_title: string;
    tldr_summary: string;
    faqs: { q: string; a: string }[];
    confidence: number;
    target_keyword: string | null;
    source_signals: {
        paa_count: number;
        gsc_query_count: number;
        fault_code_count?: number;
        fault_codes?: string[];
        article_word_count: number;
    };
    warnings: string[];
    written: boolean;
    dry_run: boolean;
    skip_reason: string | null;
}

// ============================================================================
// SEO ARTICLES — /seo/articles dashboard
// ============================================================================

export interface ArticlePriorityComponents {
    score: number;
    weights: {
        clicks: number;
        enrichment: number;
        engagement: number;
        traffic: number;
        confidence: number;
        effort: number;
    };
    projected_clicks: {
        value: number;
        normalized: number;
        current_position: number;
        target_position: number;
        impressions: number;
    };
    enrichment_gap: {
        value: number;
        aeo_score: number;
        has_tldr: boolean;
        faqs_count: number;
        fully_enriched: boolean;
    };
    engagement_quality: {
        value: number;
        avg_duration_s: number;
        bounce_rate: number | null;
        conversions: number;
        duration_ok: boolean;
        bounce_ok: boolean;
        converts: boolean;
    };
    traffic_potential: {
        value: number;
        ga4_sessions: number;
    };
    confidence: {
        value: number;
        gsc_impressions: number;
        ga4_sessions: number;
        gsc_above_threshold: boolean;
        ga4_above_threshold: boolean;
    };
    effort_estimate: {
        score: number;
        drivers: string[];
    };
}

export interface SEOArticleRow extends ArticleMetricsRow {
    priority_score: number;
    priority_components: ArticlePriorityComponents;
}

export interface SEOArticlesResponse {
    count: number;
    sort: string;
    totals: {
        impressions_30d: number;
        clicks_30d: number;
        sessions_30d: number;
        projected_clicks_potential: number;
        needs_enrichment: number;
        avg_position: number;
    };
    articles: SEOArticleRow[];
}

export interface SEOArticleQuery {
    query: string;
    position: number;
    impressions: number;
    clicks: number;
    ctr: number;
    expected_ctr: number;
    ctr_gap: number | null;
    is_underperforming: boolean;
    potential_extra_clicks: number;
}

export interface SEOArticleQueriesResponse {
    article_id: string;
    article_title: string;
    url: string;
    days: number;
    count: number;
    queries: SEOArticleQuery[];
}

export const seoArticlesAPI = {
    list: (opts?: {
        sort?: 'priority' | 'impressions' | 'sessions' | 'position' | 'aeo_score';
        min_score?: number;
        limit?: number;
    }) => {
        const params = new URLSearchParams();
        if (opts?.sort) params.set('sort', opts.sort);
        if (opts?.min_score) params.set('min_score', String(opts.min_score));
        if (opts?.limit) params.set('limit', String(opts.limit));
        const qs = params.toString();
        return fetchAPI<SEOArticlesResponse>(`/seo/articles${qs ? `?${qs}` : ''}`);
    },

    optimizationQueue: (limit: number = 20, minScore: number = 0) =>
        fetchAPI<{ limit: number; min_score: number; count: number; articles: SEOArticleRow[] }>(
            `/seo/articles/optimization-queue?limit=${limit}&min_score=${minScore}`
        ),

    topQueries: (articleId: string | number, days: number = 90, limit: number = 20) =>
        fetchAPI<SEOArticleQueriesResponse>(
            `/seo/articles/${articleId}/queries?days=${days}&limit=${limit}`
        ),
};

export const analyticsAPI = {
    getAITraffic: (days: number = 30) =>
        fetchAPI<AITrafficReport>(`/analytics/ai-traffic?days=${days}`),

    // LLM Sales Attribution - Basic
    getLLMSales: (days: number = 365, compare: boolean = true) =>
        fetchAPI<LLMSalesReport>(`/analytics/llm-sales?days=${days}&compare=${compare}`),

    // LLM Sales Attribution - Enhanced with all analytics
    getEnhancedLLMSales: (
        days: number = 365,
        options: {
            compare?: boolean;
            includeFunnel?: boolean;
            includeAssisted?: boolean;
            includeGeo?: boolean;
            includeTimeToConversion?: boolean;
            includeCohorts?: boolean;
            includeCategories?: boolean;
            source?: string;
        } = {}
    ) => {
        const params = new URLSearchParams();
        params.set('days', days.toString());
        params.set('compare', (options.compare ?? true).toString());
        params.set('include_funnel', (options.includeFunnel ?? true).toString());
        params.set('include_assisted', (options.includeAssisted ?? true).toString());
        params.set('include_geo', (options.includeGeo ?? true).toString());
        params.set('include_time_to_conversion', (options.includeTimeToConversion ?? true).toString());
        params.set('include_cohorts', (options.includeCohorts ?? true).toString());
        params.set('include_categories', (options.includeCategories ?? true).toString());
        if (options.source) params.set('source', options.source);

        return fetchAPI<EnhancedLLMSalesReport>(`/analytics/llm-sales/enhanced?${params}`);
    },

    // Get conversion funnel for LLM traffic
    getLLMConversionFunnel: (days: number = 30, source?: string) => {
        const params = new URLSearchParams();
        params.set('days', days.toString());
        if (source) params.set('source', source);
        return fetchAPI<{ status: string; funnel: ConversionFunnel }>(`/analytics/llm-sales/funnel?${params}`);
    },

    // Export LLM sales data
    exportLLMSales: (days: number = 365, format: 'csv' | 'json' = 'csv') => {
        return fetch(`${API_BASE}/analytics/llm-sales/export?days=${days}&format=${format}`);
    },
};

// NEW: Type for recommended products from real database
export interface RecommendedProduct {
    id: string;
    sku: string;
    title: string;
    price: number | string | null | undefined;
    vendor: string | null;
    handle: string | null;
    url: string | null;
    transmission_code: string | null;
    total_sold: number;
}

// ============ LLM Product Intelligence Types ============

export interface ProductContentAttributes {
    description_length: number;
    has_aeo_chunks: boolean;
    chunk_count: number;
    in_llms_txt: boolean;
    has_images: boolean;
    image_count: number;
}

export interface LLMReferencedProduct {
    id: string;  // Changed from number to string to match database
    shopify_id: string;
    title: string;
    sku: string;
    handle: string;
    product_type: string;
    orders_from_llm: number;
    revenue_from_llm: number;
    sources: string[];
    content_attributes: ProductContentAttributes;
}

export interface OptimizationOpportunity {
    id: string;  // Changed from number to string to match database
    shopify_id: string;
    title: string;
    sku: string;
    handle: string;
    product_type: string;
    total_sold: number;
    total_revenue: number;
    current_attributes: ProductContentAttributes;
    issues: string[];
    recommendation: string;
}

export interface SuccessPatterns {
    avg_description_length: number;
    products_with_aeo_chunks_pct: number;
    total_products_referenced: number;
    most_common_sources: Array<{ source: string; count: number }>;
}

export interface ProductIntelligenceResponse {
    status: string;
    message?: string;
    products_from_llm: LLMReferencedProduct[];
    optimization_opportunities: OptimizationOpportunity[];
    success_patterns: SuccessPatterns | null;
    sync_needed?: boolean;
    missing_product_count?: number;
}

// ============ Product "Why" Analysis Types ============

export interface ProductWhyEntry {
    product_id: number;
    total_checks: number;
    visibility_score: number;      // % of prompts where mentioned
    citation_rate: number;         // % of mentions with URL citation
    competitor_displacement_pct: number;
    top_prompt_types: Array<{ type: string; total: number; mention_rate: number }>;
    sentiment_breakdown: { positive: number; neutral: number; negative: number; unknown: number };
    recommendation_strength: { strong: number; moderate: number; weak: number; none: number };
    top_competitors: Array<{ name: string; count: number }>;
    llm_breakdown: Array<{ llm: string; total: number; mention_rate: number }>;
    last_checked: string | null;
}

export interface ProductWhyAnalysis {
    status: string;
    message?: string;
    total_products_analyzed: number;
    products: ProductWhyEntry[];
}

// ============ Visibility-to-Sales Correlation Types ============

export interface TopicCorrelation {
    topic: string;
    category: string;
    mentions: number;
    citations: number;
    competitor_mentions: number;
    visibility_score: number;
    orders: number;
    revenue: number;
    revenue_per_mention: number;
    status: 'star' | 'underperformer' | 'potential' | 'neutral';
    original_name: string;
}

export interface VisibilitySalesCorrelation {
    status: string;
    days: number;
    summary: {
        total_mentions: number;
        total_revenue: number;
        avg_revenue_per_mention: number;
        top_performing_topic: string | null;
        most_cited_topic: string | null;
    };
    topics: TopicCorrelation[];
}

// ============ AI Visibility Types ============

export interface VisibilityPrompt {
    id: number;
    prompt_text: string;
    category: string;
    priority: number;
    linked_fault_code: string | null;
    linked_transmission: string | null;
    source: string;
    is_active: boolean;
    last_checked: string | null;
    check_count: number;
    created_at: string | null;
}

export interface VisibilityResult {
    id: number;
    prompt_id: number;
    llm_provider: string;
    llm_model: string | null;
    brand_mentioned: boolean;
    url_cited: boolean;
    product_mentioned: boolean;
    competitor_mentioned: boolean;
    mentioned_brands: string[];
    mentioned_urls: string[];
    mentioned_products: string[];
    sentiment: 'positive' | 'neutral' | 'negative' | null;
    query_time_ms: number | null;
    checked_at: string | null;
    error: string | null;
}

export interface VisibilitySnapshot {
    id: number;
    snapshot_date: string;
    total_prompts_checked: number;
    brand_mentions: number;
    url_citations: number;
    product_mentions: number;
    competitor_mentions: number;
    visibility_score: number;
    citation_score: number;
    share_of_voice: number;
    metrics_by_llm: Record<string, any> | null;
    top_prompts: Array<{ prompt_id: number; mentions: number }> | null;
}

export interface VisibilityDashboard {
    current: {
        visibility_score: number;
        citation_score: number;
        share_of_voice: number;
        last_updated: string | null;
    };
    trends: {
        week_avg_visibility: number;
        week_avg_share: number;
    };
    totals: {
        active_prompts: number;
        total_checks: number;
    };
    by_llm: Record<string, any>;
    top_prompts: Array<{ prompt_id: number; mentions: number; citations: number }>;
}

export interface VisibilityCheckResult {
    prompt_id: number;
    provider: string;
    brand_mentioned: boolean;
    url_cited: boolean;
    competitor_mentioned: boolean;
    mentioned_brands: string[];
    mentioned_urls: string[];
    query_time_ms: number;
    error: string | null;
}

export interface BatchCheckResult {
    total_prompts: number;
    total_checks: number;
    providers_used: string[];
    metrics: {
        brand_mention_rate: number;
        url_citation_rate: number;
        competitor_mention_rate: number;
    };
    results: Array<{
        prompt_id: number;
        prompt_text: string;
        provider: string;
        brand_mentioned: boolean;
        url_cited: boolean;
        competitor_mentioned: boolean;
    }>;
    errors: Array<{ prompt_id: number; provider: string; error: string }>;
}

// ============ AI Visibility API ============

export const visibilityAPI = {
    // Prompts
    getPrompts: (activeOnly: boolean = true, category?: string) => {
        const params = new URLSearchParams({ active_only: activeOnly.toString() });
        if (category) params.set('category', category);
        return fetchAPI<VisibilityPrompt[]>(`/aeo/visibility/prompts?${params}`);
    },

    addPrompt: (data: {
        prompt_text: string;
        category?: string;
        priority?: number;
        linked_fault_code?: string;
        linked_transmission?: string;
        source?: string;
    }) => fetchAPI<VisibilityPrompt>('/aeo/visibility/prompts', {
        method: 'POST',
        body: JSON.stringify(data)
    }),

    removePrompt: (promptId: number) =>
        fetchAPI<{ status: string; prompt_id: number }>(
            `/aeo/visibility/prompts/${promptId}`,
            { method: 'DELETE' }
        ),

    // Visibility Checks
    checkSinglePrompt: (promptId: number, provider: string = 'grok') =>
        fetchAPI<VisibilityCheckResult>(
            `/aeo/visibility/check/${promptId}?provider=${provider}`,
            { method: 'POST' }
        ),

    runBatchCheck: (promptIds?: number[], providers: string[] = ['grok'], limit: number = 20) =>
        fetchAPI<BatchCheckResult>('/aeo/visibility/check', {
            method: 'POST',
            body: JSON.stringify({ prompt_ids: promptIds, providers, limit })
        }),

    // Results
    getResults: (days: number = 7, limit: number = 100) =>
        fetchAPI<VisibilityResult[]>(`/aeo/visibility/results?days=${days}&limit=${limit}`),

    getResultsByPrompt: (promptId: number, limit: number = 50) =>
        fetchAPI<VisibilityResult[]>(`/aeo/visibility/results/prompt/${promptId}?limit=${limit}`),

    // Snapshots
    getSnapshots: (days: number = 30) =>
        fetchAPI<VisibilitySnapshot[]>(`/aeo/visibility/snapshots?days=${days}`),

    createSnapshot: () =>
        fetchAPI<{ status: string; snapshot_date?: string; visibility_score?: number; share_of_voice?: number; total_checks?: number; message?: string }>(
            '/aeo/visibility/snapshots/create',
            { method: 'POST' }
        ),

    // Dashboard
    getDashboard: () =>
        fetchAPI<VisibilityDashboard>('/aeo/visibility/dashboard'),
};

// ============ Collection Optimizer API ============

export interface CollectionOptimizer {
    id: number;
    shopify_id?: string;
    title: string;
    handle: string;
    category: string;
    status: string;
    priority: number;
    has_content: boolean;

    // GSC
    impressions: number;
    clicks: number;
    ctr: number;
    position: number;
    last_analytics_sync?: string | null;

    // GA4
    ga4_sessions?: number;
    ga4_conversions?: number;
    ga4_conversion_rate?: number;
    ga4_revenue?: number;
    ga4_ai_referral_sessions?: number;
    ga4_bounce_rate?: number;
    ga4_avg_engagement_time?: number;
    last_ga4_sync?: string | null;

    // Shopify Attribution
    shopify_attributed_revenue?: number;
    shopify_attributed_orders?: number;
    shopify_llm_revenue?: number;
    shopify_llm_orders?: number;
    last_shopify_sync?: string | null;

    // DataForSEO
    dataforseo_primary_keyword?: string | null;
    dataforseo_volume?: number;
    dataforseo_competition?: string | null;
    dataforseo_cpc?: number;
    dataforseo_top_competitor?: string | null;
    dataforseo_serp_features?: string[];
    dataforseo_people_also_ask?: Array<{ question: string; answer_snippet: string }>;
    dataforseo_organic_results?: any[];
    dataforseo_last_sync?: string | null;

    // Generated Content
    generated_content?: string;
    generated_faq?: Array<{ question: string; answer: string }>;
    generated_schema?: string;
    content_generated_at?: string | null;

    // Timestamps
    created_at?: string;
    updated_at?: string;
}

// ============ UNIFIED SEO/AEO/GEO DASHBOARD TYPES ============

export interface SEOHealth {
    products: {
        total: number;
        needing_seo: number;
        optimized: number;
        avg_score: number;
    };
    collections: {
        total: number;
        analyzed: number;
        optimized: number;
        with_ga4: number;
    };
}

export interface AEOHealth {
    llms_txt_coverage: string;
    faq_schema_coverage: number;
    total_collections: number;
    coverage_percentage: number;
}

export interface GEOHealth {
    ai_referral_sessions: number;
    ai_referral_conversions: number;
    collections_with_ai_traffic: number;
    visibility_score: number;
}

export interface UnifiedOverview {
    seo_health: SEOHealth;
    aeo_health: AEOHealth;
    geo_health: GEOHealth;
}

export interface GA4Summary {
    total_sessions: number;
    total_conversions: number;
    avg_conversion_rate: number;
}

export interface TopProductPerformance {
    id: string;
    title: string;
    sku: string | null;
    seo_score: number;
    total_sold: number;
    total_revenue: number;
}

export interface TopCollectionPerformance {
    id: number;
    title: string;
    sessions: number;
    conversions: number;
    conversion_rate: number;
}

export interface ProductOpportunity {
    id: string;
    title: string;
    sku: string | null;
    seo_score: number;
    total_sold: number;
    total_revenue: number;
    potential_impact: string;
}

export interface CollectionOpportunity {
    id: number;
    title: string;
    sessions: number;
    conversion_rate: number;
    potential_revenue_increase: number;
}

export interface UnifiedOpportunities {
    high_value_products_needing_seo: ProductOpportunity[];
    high_traffic_low_conversion_collections: CollectionOpportunity[];
}

export interface UnifiedRecommendation {
    priority: 'high' | 'medium' | 'low';
    category: 'SEO' | 'AEO' | 'GEO';
    title: string;
    action: string;
    impact: string;
}

export interface UnifiedPerformance {
    ga4_summary: GA4Summary;
    top_products: TopProductPerformance[];
    top_collections: TopCollectionPerformance[];
}

export interface UnifiedDashboard {
    overview: UnifiedOverview;
    performance: UnifiedPerformance;
    opportunities: UnifiedOpportunities;
    recommendations: UnifiedRecommendation[];
}

export interface OptimizerDashboard {
    stats: {
        total_collections: number;
        pending: number;
        analyzed: number;
        ready: number;
        published: number;
        with_ga4_data?: number;
        with_conversions?: number;
    };
    high_priority: CollectionOptimizer[];
    top_opportunities?: CollectionOptimizer[];
}

// ============ GA4 Analytics Dashboard Types ============

export interface GA4DashboardStats {
    collections_with_ga4: number;
    collections_with_conversions: number;
    total_ai_referral_sessions: number;
    collections_with_ai_traffic: number;
    total_sessions: number;
    total_conversions: number;
    avg_conversion_rate: number;
}

export interface TopConverter {
    id: number;
    title: string;
    sessions: number;
    conversions: number;
    conversion_rate: string;
    ai_sessions: number;
}

export interface GA4Dashboard {
    stats: GA4DashboardStats;
    top_converters: TopConverter[];
}

export interface GA4CollectionMetrics {
    collection_id: number;
    collection_title: string;
    ga4_data: {
        sessions: number;
        active_users: number;
        avg_engagement_time: number;
        conversions: number;
        conversion_rate: number;
        ai_referral_sessions: number;
    };
}

export const optimizerAPI = {
    // Dashboard
    getDashboard: () =>
        fetchAPI<OptimizerDashboard>('/optimizer/dashboard'),

    // Sync
    syncCollections: () =>
        fetchAPI<{ status: string; synced: number; updated: number }>(
            '/optimizer/sync',
            { method: 'POST' }
        ),

    // Collections
    getCollections: (params?: { status?: string; category?: string; search?: string; sort_by?: string; limit?: number; offset?: number }) => {
        const queryParams = new URLSearchParams();
        if (params?.status) queryParams.set('status', params.status);
        if (params?.category) queryParams.set('category', params.category);
        if (params?.search) queryParams.set('search', params.search);
        if (params?.sort_by) queryParams.set('sort_by', params.sort_by);
        if (params?.limit) queryParams.set('limit', params.limit.toString());
        if (params?.offset !== undefined) queryParams.set('offset', params.offset.toString());
        const query = queryParams.toString() ? `?${queryParams.toString()}` : '';
        return fetchAPI<{ total: number; offset: number; limit: number; collections: CollectionOptimizer[] }>(`/optimizer/collections${query}`);
    },

    getCollection: (collectionId: number) =>
        fetchAPI<CollectionOptimizer>(`/optimizer/collections/${collectionId}`),

    // Analysis
    analyzeCollection: (collectionId: number) =>
        fetchAPI(`/optimizer/analyze/${collectionId}`, { method: 'POST' }),

    analyzeAll: () =>
        fetchAPI<{ status: string; analyzed: number; results: any[] }>('/optimizer/analyze-all', { method: 'POST' }),

    getCollectionQueries: (collectionId: number, queryType?: string) => {
        const params = new URLSearchParams();
        if (queryType) params.set('query_type', queryType);
        const query = params.toString() ? `?${params.toString()}` : '';
        return fetchAPI(`/optimizer/collections/${collectionId}/queries${query}`);
    },

    // Content Generation
    generateContent: (collectionId: number) =>
        fetchAPI(`/optimizer/generate/${collectionId}`, { method: 'POST' }),

    previewContent: (collectionId: number) =>
        fetchAPI(`/optimizer/collections/${collectionId}/preview`),

    // Deployment
    deployContent: (collectionId: number, dryRun: boolean = false) =>
        fetchAPI(`/optimizer/deploy/${collectionId}?dry_run=${dryRun}`, { method: 'POST' }),

    // Tracking
    trackPerformance: (collectionId: number) =>
        fetchAPI(`/optimizer/track/${collectionId}`, { method: 'POST' }),

    getHistory: (collectionId: number) =>
        fetchAPI(`/optimizer/collections/${collectionId}/history`),

    // Full Workflow
    runWorkflow: (collectionId: number) =>
        fetchAPI(`/optimizer/workflow/${collectionId}`, { method: 'POST' }),

    runBatchWorkflow: (collectionIds: number[]) =>
        fetchAPI('/optimizer/workflow-batch', {
            method: 'POST',
            body: JSON.stringify({ collection_ids: collectionIds })
        }),

    // GA4 Analytics
    getGA4Dashboard: (days?: number) =>
        fetchAPI<GA4Dashboard>(`/optimizer/ga4/dashboard${days ? `?days=${days}` : ''}`),

    getHighOpportunityCollections: (params?: { min_sessions?: number; max_conversion_rate?: number; limit?: number }) => {
        const queryParams = new URLSearchParams();
        if (params?.min_sessions) queryParams.set('min_sessions', params.min_sessions.toString());
        if (params?.max_conversion_rate) queryParams.set('max_conversion_rate', params.max_conversion_rate.toString());
        if (params?.limit) queryParams.set('limit', params.limit.toString());
        const query = queryParams.toString() ? `?${queryParams.toString()}` : '';
        return fetchAPI<{ collections: CollectionOptimizer[]; total_potential_revenue: number }>(`/optimizer/ga4/opportunities${query}`);
    },

    analyzeGA4Collection: (collectionId: number) =>
        fetchAPI<{ status: string; message: string; data: any }>(`/optimizer/ga4/analyze/${collectionId}`, { method: 'POST' }),

    analyzeAllGA4: () =>
        fetchAPI<{ status: string; message: string; data: any }>('/optimizer/ga4/analyze-all', { method: 'POST' }),

    // Shopify Attribution
    syncShopifyAttribution: (days: number = 30) =>
        fetchAPI<{ status: string; message: string; data: any }>(`/optimizer/shopify-sync-all?days=${days}`, { method: 'POST' }),

    // DataForSEO
    runDataForSEOCollection: (collectionId: number) =>
        fetchAPI<{ status: string; message: string; data: any }>(`/optimizer/dataforseo/${collectionId}`, { method: 'POST' }),

    runDataForSEOAll: () =>
        fetchAPI<{ status: string; message: string; data: any }>('/optimizer/dataforseo-all', { method: 'POST' }),

    // Unified SEO/AEO/GEO Dashboard
    getUnifiedDashboard: (days?: number) =>
        fetchAPI<UnifiedDashboard>(`/optimizer/unified-dashboard${days ? `?days=${days}` : ''}`),
};

// ============ COLLECTION INTELLIGENCE TYPES ============

export interface KeywordConflict {
    keyword: string;
    conflicting_url: string;
    conflicting_page_type: 'blog' | 'product' | 'collection';
    conflicting_position: number;
    conflicting_clicks: number;
    conflicting_impressions: number;
    intent: 'informational' | 'transactional' | 'navigational';
    severity: 'blocked' | 'warning' | 'safe';
    recommendation: string;
}

export interface KeywordSafe {
    keyword: string;
    intent: string;
    impressions: number;
    clicks: number;
    position: number;
    opportunity_score: number;
}

export interface CannibalizationCheckResult {
    collection_id: number;
    collection_title: string;
    analyzed_at: string;
    total_keywords_analyzed: number;
    safe_keywords: KeywordSafe[];
    blocked_keywords: KeywordConflict[];
    warning_keywords: KeywordConflict[];
    risk_score: number;
    status: 'safe' | 'warning' | 'blocked';
    can_generate: boolean;
    generation_guidance: string;
}

export interface CollectionRecommendation {
    id: string;
    category: 'seo' | 'aeo' | 'geo' | 'conversion';
    priority: 'high' | 'medium' | 'low';
    title: string;
    action: string;
    expected_impact: string;
    confidence: number;
    auto_applicable: boolean;
    generated_content?: string;
    implementation_steps: string[];
    agent_breakdown?: {
        harper: Record<string, any>;
        benjamin: Record<string, any>;
        lucas: Record<string, any>;
    };
}

export interface CollectionRecommendationsResponse {
    collection_id: number;
    collection_title: string;
    recommendations: CollectionRecommendation[];
    total_opportunities: number;
    estimated_impact: {
        traffic_increase: string;
        conversion_increase: string;
        timeline: string;
        confidence_level?: string;
    };
    cannibalization_status: string;
    cannibalization_risk_score: number;
    safe_keyword_count: number;
    blocked_keyword_count: number;
    _multi_agent?: {
        mode: string;
        agents_used: string[];
        consensus_score: number;
    };
}

export interface CollectionContentDraft {
    id: string;
    collection_id: number;
    version: number;
    draft_status: 'draft' | 'approved' | 'deployed' | 'archived';
    educational_content_preview?: string;
    educational_content?: string;
    faq_content?: Array<{ question: string; answer: string }>;
    faq_count?: number;
    has_schema?: boolean;
    schema_markup?: string;
    meta_title?: string;
    meta_description?: string;
    cannibalization_status?: string;
    risk_score?: number;
    cannibalization_check?: CannibalizationCheckResult;
    safe_keywords_used?: string[];
    blocked_keywords_avoided?: string[];
    generation_provider?: string;
    multi_agent?: boolean;
    created_at?: string;
    updated_at?: string;
}

export interface CollectionTrendSnapshot {
    date: string;
    gsc_impressions: number;
    gsc_clicks: number;
    gsc_ctr: number;
    gsc_position: number;
    ga4_sessions: number;
    ga4_conversions: number;
    ga4_revenue: number;
    ga4_bounce_rate: number;
    shopify_revenue: number;
    shopify_orders: number;
    dataforseo_volume: number;
    has_content: boolean;
    optimization_status: string;
}

export interface CollectionTrendsResponse {
    collection_title: string;
    snapshots: CollectionTrendSnapshot[];
    deltas: Record<string, number> | null;
    optimization_events: Array<{ date: string; event?: string; from_status?: string; to_status?: string }>;
    total_snapshots: number;
}

export interface CollectionOpportunity {
    collection_id: number;
    collection_title: string;
    category: string;
    handle: string;
    // DataForSEO
    dataforseo_volume: number;
    // GSC
    impressions: number;
    position: number;
    ctr: number;
    // GA4
    ga4_sessions: number;
    ga4_conversions: number;
    ga4_conversion_rate: number;
    ga4_bounce_rate: number;
    // Shopify
    shopify_revenue: number;
    shopify_orders: number;
    shopify_llm_revenue: number;
    // Status
    has_content: boolean;
    cannibalization_status: string;
    risk_score: number;
    safe_keywords: number;
    blocked_keywords: number;
    opportunity_score: number;
    // Sync timestamps
    last_gsc_sync?: string | null;
    last_ga4_sync?: string | null;
    last_shopify_sync?: string | null;
    last_dataforseo_sync?: string | null;
}

// ============ COLLECTIONS AI API ============
export const collectionsAIAPI = {
    // Sync All Data Sources
    syncAllDataSources: (collectionId: number) =>
        fetchAPI<{ status: string; collection_id: number; sources: Record<string, any>; summary: { total_sources: number; successful: number; failed: number } }>(
            `/collections-ai/sync-all/${collectionId}`,
            { method: 'POST' }
        ),

    syncAllBatch: (collectionIds: number[]) =>
        fetchAPI<{ status: string; total: number; fully_synced: number; results: Record<string, any> }>(
            '/collections-ai/sync-all-batch',
            { method: 'POST', body: JSON.stringify(collectionIds) }
        ),

    // Cannibalization Check
    checkCannibalization: (collectionId: number) =>
        fetchAPI<{ status: string; data: CannibalizationCheckResult }>(
            `/collections-ai/cannibalization-check/${collectionId}`
        ),

    batchCannibalizationCheck: (collectionIds: number[]) =>
        fetchAPI<{ status: string; total: number; data: Record<string, CannibalizationCheckResult> }>(
            '/collections-ai/cannibalization-check/batch',
            { method: 'POST', body: JSON.stringify({ collection_ids: collectionIds }) }
        ),

    getTransactionalGaps: (collectionId: number) =>
        fetchAPI<{ status: string; collection_id: number; gaps: any[]; total: number }>(
            `/collections-ai/cannibalization-check/${collectionId}/gaps`
        ),

    // Smart Recommendations
    getRecommendations: (collectionId: number, options?: {
        multiAgent?: boolean;
        minConfidence?: number;
        categories?: string;
        maxResults?: number;
        sortBy?: 'impact' | 'confidence' | 'effort';
    }) => {
        const params = new URLSearchParams();
        params.set('multi_agent', String(options?.multiAgent ?? false));
        params.set('min_confidence', String(options?.minConfidence ?? 60));
        if (options?.categories) params.set('categories', options.categories);
        params.set('max_results', String(options?.maxResults ?? 10));
        params.set('sort_by', options?.sortBy ?? 'impact');
        return fetchAPI<{ status: string; data: CollectionRecommendationsResponse }>(
            `/collections-ai/recommendations/${collectionId}?${params}`,
            { method: 'POST' }
        );
    },

    batchRecommendations: (collectionIds: number[], multiAgent: boolean = false) =>
        fetchAPI<{ status: string; total: number; data: Record<string, CollectionRecommendationsResponse> }>(
            '/collections-ai/batch/recommendations',
            { method: 'POST', body: JSON.stringify({ collection_ids: collectionIds, multi_agent: multiAgent }) }
        ),

    // Opportunity Discovery
    discoverOpportunities: (limit: number = 20) =>
        fetchAPI<{ status: string; total: number; data: CollectionOpportunity[] }>(
            `/collections-ai/discover-opportunities?limit=${limit}`
        ),

    // Content Generation with Guard
    generateContent: (collectionId: number, skipCannibalizationCheck: boolean = false) =>
        fetchAPI<any>(
            `/collections-ai/generate-content/${collectionId}?skip_cannibalization_check=${skipCannibalizationCheck}`,
            { method: 'POST' }
        ),

    // Content Drafts
    listDrafts: (collectionId: number, status?: string) => {
        const params = status ? `?status=${status}` : '';
        return fetchAPI<{ status: string; collection_id: number; total: number; data: CollectionContentDraft[] }>(
            `/collections-ai/drafts/${collectionId}${params}`
        );
    },

    getDraft: (collectionId: number, draftId: string) =>
        fetchAPI<{ status: string; data: CollectionContentDraft }>(
            `/collections-ai/drafts/${collectionId}/${draftId}`
        ),

    approveDraft: (draftId: string) =>
        fetchAPI<{ status: string; message: string; collection_status: string }>(
            `/collections-ai/drafts/${draftId}/approve`,
            { method: 'POST' }
        ),

    // Intelligence Reports
    getIntelligence: (collectionId: number) =>
        fetchAPI<{ status: string; data: any }>(
            `/collections-ai/intelligence/${collectionId}`
        ),

    getHealthOverview: () =>
        fetchAPI<{ status: string; data: any }>(
            '/collections-ai/intelligence/overview'
        ),

    // Analytics Snapshots
    createSnapshots: (collectionIds?: number[]) =>
        fetchAPI<{ status: string; created: number; skipped: number }>(
            '/collections-ai/snapshots/create',
            { method: 'POST', body: JSON.stringify(collectionIds || null) }
        ),

    getTrends: (collectionId: number, days: number = 30) =>
        fetchAPI<{ status: string; collection_id: number; days: number } & CollectionTrendsResponse>(
            `/collections-ai/snapshots/${collectionId}?days=${days}`
        ),
};

// ============ PRODUCT AI VISIBILITY API ============
export const productVisibilityAPI = {
    // Get visibility overview for a product
    getVisibility: (productId: string) =>
        fetchAPI<{
            product_id: number;
            product_title: string;
            product_sku: string | null;
            current_score: number | null;
            current_level: string | null;
            last_checked: string | null;
            by_llm: Record<string, number> | null;
            change_7d: number | null;
            top_competitors: Array<{ name: string; mention_count: number }> | null;
        }>(`/product-visibility/${productId}`),

    // Trigger visibility check for a product
    checkVisibility: (productId: string, providers: string[] = ['grok'], maxPrompts: number = 5) =>
        fetchAPI<{
            product_id: number;
            checks_performed: number;
            score: {
                score: number;
                level: string;
                breakdown: {
                    mention_score: number;
                    position_score: number;
                    citation_score: number;
                    competitor_score: number;
                };
                by_llm: Record<string, number>;
                stats: {
                    total_checks: number;
                    mentions: number;
                    first_positions: number;
                    url_citations: number;
                    competitor_appearances: number;
                };
            };
            results: Array<{
                prompt: string;
                provider: string;
                was_mentioned: boolean;
                position: number;
                competitors: string[];
            }>;
        }>(`/product-visibility/${productId}/check`, {
            method: 'POST',
            body: JSON.stringify({ providers, max_prompts: maxPrompts })
        }),

    // Get visibility trend
    getTrend: (productId: string, days: number = 30) =>
        fetchAPI<{
            product_id: number;
            period_days: number;
            trend: Array<{ date: string; score: number; level: string }>;
            current_score: number | null;
            change_7d: number | null;
            change_30d: number | null;
        }>(`/product-visibility/${productId}/trend?days=${days}`),

    // Get competitor gap analysis
    getGapAnalysis: (productId: string, days: number = 30) =>
        fetchAPI<{
            product_id: number;
            competitor_visibility: Array<{ name: string; visibility_rate: number }>;
            gap_vs_product: Array<{ name: string; gap: number }>;
            missed_opportunities: string[];
        }>(`/product-visibility/${productId}/gaps?days=${days}`),
};

// ============ ANALYTICS SNAPSHOT API ============
export const snapshotAPI = {
    // Create daily analytics snapshot
    createSnapshot: (productIds?: string[]) => {
        const params = productIds ? `?product_ids=${productIds.join(',')}` : '';
        return fetchAPI<{
            status: string;
            created: number;
            skipped: number;
            total_products: number;
            timestamp: string;
        }>(`/analytics/snapshots/create${params}`, { method: 'POST' });
    },

    // Cleanup old snapshots
    cleanupSnapshots: (daysToKeep: number = 90) =>
        fetchAPI<{
            status: string;
            deleted: number;
            cutoff_date: string;
        }>(`/analytics/snapshots/cleanup?days_to_keep=${daysToKeep}`, { method: 'DELETE' }),

    // Recalculate SEO scores for all products from their HTML content
    recalculateSeoScores: () =>
        fetchAPI<{
            status: string;
            total_products: number;
            updated: number;
            unchanged: number;
        }>(`/analytics/seo-scores/recalculate`, { method: 'POST' }),

    // Get historical snapshots for a specific product
    getProductSnapshots: (productId: string, days: number = 30) =>
        fetchAPI<{
            product_id: string;
            product_title: string;
            days: number;
            snapshot_count: number;
            snapshots: Array<{
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
                price: string | null;
                inventory_quantity: number | null;
                image_count: number | null;
                description_length: number | null;
            }>;
        }>(`/analytics/snapshots/${productId}?days=${days}`),

    // Get products optimized recently with optimization-anchored before/after deltas
    getOptimizedRecently: (days: number = 30, limit: number = 20) =>
        fetchAPI<{
            days: number;
            verdict_lag_days: number;
            soft_baseline_window_days: number;
            total_optimized: number;
            verdict_summary: {
                positive: number;
                negative: number;
                mixed: number;
                neutral: number;
                pending: number;
                no_baseline: number;
                tracked_only: number;
                inconclusive: number;
            };
            sales_summary: { converting: number; dropping: number };
            products: Array<{
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
                overlaps: Array<{ type: 'price' | 'inventory' | 'images'; before: number | null; after: number | null; pct_change: number | null }>;
                current: { seo_score: number | null; gsc_position: number | null; gsc_impressions: number | null; gsc_clicks: number | null; gsc_ctr: number | null; ga4_sessions: number | null; sold_30d: number | null; revenue_30d: number | null; sold_90d: number | null; revenue_90d: number | null; sold_365d: number | null; revenue_365d: number | null };
                before: { snapshot_date: string | null; seo_score: number | null; gsc_position: number | null; gsc_impressions: number | null; gsc_clicks: number | null; gsc_ctr: number | null; ga4_sessions: number | null; sold_30d: number | null; revenue_30d: number | null; price: string | null; inventory_quantity: number | null; image_count: number | null; description_length: number | null } | null;
                after: { snapshot_date: string | null; seo_score: number | null; gsc_position: number | null; gsc_impressions: number | null; gsc_clicks: number | null; gsc_ctr: number | null; ga4_sessions: number | null; sold_30d: number | null; revenue_30d: number | null; price: string | null; inventory_quantity: number | null; image_count: number | null; description_length: number | null } | null;
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
            }>;
        }>(`/analytics/snapshots/optimized-recently?days=${days}&limit=${limit}`),

    // Refresh GSC + GA4 data AND take a snapshot in one call (returns Celery task id when async)
    refreshAndSnapshot: () =>
        fetchAPI<{
            task_id?: string;
            status?: string;
            steps?: {
                analytics_sync?: any;
                seo_recalc?: any;
                snapshot?: any;
            };
        }>(`/analytics/snapshots/refresh-and-snapshot`, { method: 'POST' }),

    // Data freshness for the dashboard header badge
    getFreshness: () =>
        fetchAPI<{
            last_analytics_sync: string | null;
            last_snapshot_at: string | null;
            last_snapshot_count: number;
            hours_since_sync: number | null;
            hours_since_snapshot: number | null;
            status: 'fresh' | 'stale' | 'very_stale';
        }>(`/analytics/snapshots/freshness`),
};

// ============ SOLUTION ENGINE API ============
// Types for Solution Engine
export interface SolutionEngineProduct {
    rank: number;
    product_id: string;
    sku: string | null;
    title: string;
    handle: string | null;
    price: string | null;
    transmission_code: string | null;
    product_type: string | null;
    total_sold: number;
    url: string | null;
    match_score: number;
    reasoning: string;
    fix_probability: string;
}

export interface SolutionPath {
    query: string;
    fault_code: string | null;
    intent: string;
    steps: Array<{
        step: number;
        type: string;
        title: string;
        content: string;
    }>;
    products: SolutionEngineProduct[];
}

export interface SmartSnippet {
    query: string;
    fault_code: string | null;
    short_answer: string;
    detailed_answer: string;
    authority_quote: string;
    statistic_claims: string[];
    related_products: string[];
}

export interface SolutionEngineStats {
    fault_codes_total: number;
    fault_codes_with_products: number;
    coverage_percentage: number;
    total_product_matches: number;
}

export interface TopFaultCode {
    code: string;
    name: string;
    monthly_clicks: number;
    monthly_impressions: number;
    avg_position: number;
    products_available: number;
}

// ============ SOLUTION ENGINE AI TYPES ============
export interface BlogContentSection {
    heading: string;
    content: string;
    type: string;
}

// ============ ENHANCED SEO CONTENT TYPES ============
export interface FAQItem {
    question: string;
    answer: string;
    category: string;
    priority?: number;
}

export interface FAQExpansion {
    faqs: FAQItem[];
    schema: Record<string, any>;
}

export interface EEATBox {
    html: string;
    statistics: Array<{ label: string; value: string }>;
    trust_signals: string[];
}

export interface InternalLink {
    text: string;
    url: string;
    type: string;
    priority?: number;
}

export interface InternalLinks {
    links: InternalLink[];
    breadcrumb: Array<{ name: string; url: string }>;
    breadcrumb_schema: Record<string, any>;
}

export interface ComparisonTable {
    vs_code: string;
    html: string;
    rows: Array<{ feature: string; value_a: string; value_b: string; winner: string | null }>;
}

export interface ContentQualityScore {
    total_score: number;
    max_score: number;
    rating: 'excellent' | 'good' | 'needs_improvement';
    breakdown: Record<string, number>;
    recommendations: string[];
}

export interface EnhancedContent {
    faq_expansion: FAQExpansion | null;
    eeat_box: EEATBox | null;
    internal_links: InternalLinks | null;
    comparison_tables: ComparisonTable | null;
    related_codes_table: string | null;
    technical_specs: Record<string, any> | null;
}

export interface BlogContentResponse {
    fault_code: string;
    title: string;
    meta_description: string;
    sections: BlogContentSection[];
    product_recommendations: Array<{
        product_id: string;
        sku: string;
        title: string;
        handle: string;
        price: string;
        is_kit: boolean;
        position: number;
    }>;
    faq_schema: Record<string, any>;
    howto_schema: Record<string, any>;
    estimated_read_time: number;
    target_keywords: string[];
    transmissions: string[];
    monthly_clicks: number;
    enhanced_content: EnhancedContent;
    content_quality_score: ContentQualityScore;
}

export interface SchemaGenerationResponse {
    schema_type: string;
    schema_json: Record<string, any>;
    html_script: string;
}

export interface AIFaultCodeAnalysis {
    fault_code: string;
    products: Array<{
        product_id: string;
        sku: string;
        title: string;
        rank: number;
        match_score: number;
        reasoning: string;
        fix_probability: string;
        url: string;
    }>;
    reasoning: string;
    confidence: number;
    alternative_approaches: string[];
    ai_analyzed: boolean;
}

export interface CollectionDataResponse {
    fault_code: string;
    fault_code_name: string;
    title: string;
    handle: string;
    description: string;
    meta_title: string;
    meta_description: string;
    seo_keywords: string[];
    transmissions: string[];
    product_counts: {
        total: number;
        kits: number;
        parts: number;
    };
    top_products: Array<{
        id: string;
        title: string;
        sku: string;
        price: string;
        handle: string;
        type: string;
        transmission_code: string;
    }>;
    revenue_potential: number;
}

export const solutionEngineAPI = {
    // Get product recommendations for a fault code
    getFaultCodeProducts: (faultCode: string, limit: number = 10) =>
        fetchAPI<{ fault_code: string; products: SolutionEngineProduct[] }>(
            `/solution-engine/fault-code/${faultCode}/products?limit=${limit}`
        ),

    // Generate solution path for a query
    getSolutionPath: (query: string) =>
        fetchAPI<SolutionPath>(`/solution-engine/solution-path?query=${encodeURIComponent(query)}`),

    // Generate smart snippet for a query
    getSmartSnippet: (query: string) =>
        fetchAPI<SmartSnippet>(`/solution-engine/smart-snippet?query=${encodeURIComponent(query)}`),

    // Get dashboard stats
    getStats: () =>
        fetchAPI<SolutionEngineStats>('/solution-engine/dashboard/stats'),

    // Get top fault codes
    getTopFaultCodes: (limit: number = 10) =>
        fetchAPI<{ fault_codes: TopFaultCode[] }>(`/solution-engine/top-fault-codes?limit=${limit}`),

    // ============ AI-POWERED ENDPOINTS ============

    // Analyze fault code with Grok AI (supports multi-agent toggle)
    analyzeFaultCodeWithAI: (faultCode: string, multiAgent?: boolean) => {
        const params = multiAgent !== undefined ? `?multi_agent=${multiAgent}` : '';
        return fetchAPI<AIFaultCodeAnalysis>(`/solution-engine/ai/fault-code/${faultCode}/analyze${params}`, { method: 'POST' });
    },

    // Generate GEO-optimized snippet (supports multi-agent toggle)
    generateGEOSnippet: (query: string, multiAgent?: boolean) => {
        const maParam = multiAgent !== undefined ? `&multi_agent=${multiAgent}` : '';
        return fetchAPI<SmartSnippet>(`/solution-engine/ai/smart-snippet/geo?query=${encodeURIComponent(query)}${maParam}`, { method: 'POST' });
    },

    // Get multi-agent status
    getMultiAgentStatus: () =>
        fetchAPI<{
            multi_agent_enabled: boolean;
            mode: string;
            model: string;
            timeout: number;
            provider_registered: boolean;
            provider_status: Record<string, any>;
            agents: string[];
        }>('/solution-engine/ai/multi-agent/status'),

    // Generate blog content for fault code
    generateBlogContent: (faultCode: string, options?: { include_products?: boolean; word_count?: number; tone?: string }) =>
        fetchAPI<BlogContentResponse>('/solution-engine/ai/content/generate-blog', {
            method: 'POST',
            body: JSON.stringify({
                fault_code: faultCode,
                include_products: options?.include_products ?? true,
                word_count: options?.word_count ?? 1000,
                tone: options?.tone ?? 'professional'
            })
        }),

    // Generate Schema.org markup
    generateSchema: (contentType: string, options?: { fault_code?: string; blog_content?: string; products?: string[] }) =>
        fetchAPI<SchemaGenerationResponse>('/solution-engine/ai/content/generate-schema', {
            method: 'POST',
            body: JSON.stringify({
                content_type: contentType,
                fault_code: options?.fault_code,
                blog_content: options?.blog_content,
                products: options?.products
            })
        }),

    // Get collection data for fault code
    getCollectionData: (faultCode: string) =>
        fetchAPI<CollectionDataResponse>(`/solution-engine/ai/collections/fault-code/${faultCode}`),

    // Create collection for fault code
    createCollection: (faultCode: string) =>
        fetchAPI<{ fault_code: string; status: string; collection_data: any }>(
            `/solution-engine/ai/collections/create-for-fault-code/${faultCode}`,
            { method: 'POST' }
        ),

    // Batch generate content for multiple fault codes
    batchGenerateContent: (faultCodes: string[], options?: { generate_blogs?: boolean; generate_schemas?: boolean }) =>
        fetchAPI<{ total_requested: number; completed: number; failed: number; results: any[] }>(
            '/solution-engine/ai/batch/generate-content',
            {
                method: 'POST',
                body: JSON.stringify({
                    fault_codes: faultCodes,
                    generate_blogs: options?.generate_blogs ?? true,
                    generate_schemas: options?.generate_schemas ?? true
                })
            }
        ),

    // Get AI dashboard stats
    getAIStats: () =>
        fetchAPI<{
            ai_analyzed_fault_codes: number;
            smart_snippets_generated: number;
            solution_paths_created: number;
            average_ai_confidence: number;
            fault_codes_ready_for_content: number;
        }>('/solution-engine/ai/dashboard/ai-stats'),
};

// ============ PRODUCTS AI (Multi-Agent) API ============

export interface SEOBreakdown {
    technical: number;
    content: number;
    keywords: number;
}

export interface SEOAnalysisResult {
    score: number;
    breakdown: SEOBreakdown;
    issues: string[];
    opportunities: string[];
}

export interface AEOAnalysisResult {
    score: number;
    voice_search_ready: boolean;
    faq_opportunities: string[];
}

export interface GEOAnalysisResult {
    score: number;
    ai_visibility: {
        grok?: number;
        perplexity?: number;
        chatgpt?: number;
        [key: string]: number | undefined;
    };
}

export interface ProductAnalysisResponse {
    product_id: string;
    product_title: string;
    seo_analysis: SEOAnalysisResult;
    aeo_analysis: AEOAnalysisResult;
    geo_analysis: GEOAnalysisResult;
    recommendations: SmartRecommendation[];
    _multi_agent?: {
        mode: string;
        agents_used: string[];
        consensus_score: number;
        task_type?: string;
    };
}

export interface SmartRecommendation {
    id: string;
    category: 'seo' | 'aeo' | 'geo' | 'conversion';
    priority: 'high' | 'medium' | 'low';
    title: string;
    action: string;
    expected_impact: string;
    confidence: number;
    auto_applicable: boolean;
    generated_content?: string;
    implementation_steps: string[];
    agent_breakdown?: {
        harper: { verified?: boolean; notes?: string };
        benjamin: { logical_valid?: boolean; score?: number };
        lucas: { style_score?: number; suggestions?: string };
    };
}

export interface SmartRecommendationsResponse {
    product_id: string;
    product_title: string;
    recommendations: SmartRecommendation[];
    total_opportunities: number;
    estimated_impact: {
        traffic_increase: string;
        conversion_increase: string;
        timeline: string;
        confidence_level?: string;
    };
    _multi_agent?: {
        mode: string;
        agents_used: string[];
        consensus_score: number;
        task_type?: string;
    };
}

export interface RecommendationFilters {
    min_confidence: number;
    categories: ('seo' | 'aeo' | 'geo' | 'conversion')[];
    max_results: number;
    sort_by: 'impact' | 'confidence' | 'effort';
}

export interface RecommendationContext {
    fault_codes?: string[];
    transmission_codes?: string[];
    customer_segment?: string;
    current_issues?: string[];
}

export const productsAIAPI = {
    // Multi-Agent Product Analysis
    analyzeProduct: (productId: string, multiAgent: boolean = true, depth: 'quick' | 'standard' | 'deep' = 'standard') =>
        fetchAPI<ProductAnalysisResponse>(
            `/products-ai/product/${productId}/analyze?multi_agent=${multiAgent}&analysis_depth=${depth}`,
            { method: 'POST' }
        ),

    // Smart Recommendations
    getSmartRecommendations: (
        productId: string,
        options?: {
            multiAgent?: boolean;
            minConfidence?: number;
            categories?: string;
            maxResults?: number;
            sortBy?: 'impact' | 'confidence' | 'effort';
        }
    ) => {
        const params = new URLSearchParams();
        params.set('multi_agent', String(options?.multiAgent ?? true));
        params.set('min_confidence', String(options?.minConfidence ?? 60));
        if (options?.categories) params.set('categories', options.categories);
        params.set('max_results', String(options?.maxResults ?? 10));
        params.set('sort_by', options?.sortBy ?? 'impact');

        return fetchAPI<SmartRecommendationsResponse>(
            `/products-ai/recommendations/${productId}?${params}`,
            { method: 'POST' }
        );
    },

    // Smart Recommendations with Context
    getSmartRecommendationsWithContext: (
        productId: string,
        context: RecommendationContext,
        filters: Partial<RecommendationFilters>
    ) =>
        fetchAPI<SmartRecommendationsResponse>(
            `/products-ai/recommendations/${productId}?multi_agent=true`,
            {
                method: 'POST',
                body: JSON.stringify(context)
            }
        ),

    // Batch Analysis
    batchAnalyze: (productIds: string[], multiAgent: boolean = true) =>
        fetchAPI<{
            total_requested: number;
            completed: number;
            failed: number;
            results: Record<string, ProductAnalysisResponse | { error: string }>;
        }>('/products-ai/batch/analyze', {
            method: 'POST',
            body: JSON.stringify({
                product_ids: productIds,
                multi_agent: multiAgent,
                include_recommendations: false
            })
        }),

    // Batch Recommendations
    batchRecommendations: (productIds: string[], multiAgent: boolean = true, minConfidence: number = 60) =>
        fetchAPI<{
            total_requested: number;
            results: Record<string, SmartRecommendationsResponse | { error: string }>;
        }>('/products-ai/batch/recommendations', {
            method: 'POST',
            body: JSON.stringify(productIds)
        }),

    // Quick Scan (Single-Agent, Fast)
    quickScan: (productId: string) =>
        fetchAPI<{
            product_id: string;
            quick_score: number;
            top_issue: string;
            quick_win: string;
            analysis_type: string;
        }>(`/products-ai/product/${productId}/quick-scan`),

    // Multi-Agent Status
    getMultiAgentStatus: () =>
        fetchAPI<{
            multi_agent_enabled: boolean;
            mode: string;
            model: string;
            timeout: number;
            available_task_types: string[];
            agents: string[];
        }>('/products-ai/multi-agent/status'),

    // ========== AI-POWERED DISCOVERY ==========

    // Discover Opportunities Across All Products
    discoverOpportunities: (options?: {
        opportunityType?: string;
        minImpact?: number;
        limit?: number;
    }) => {
        const params = new URLSearchParams();
        params.set('opportunity_type', options?.opportunityType ?? 'all');
        params.set('min_impact', String(options?.minImpact ?? 500));
        params.set('limit', String(options?.limit ?? 20));

        return fetchAPI<{
            opportunities: {
                high_revenue_low_seo: Array<{
                    product_id: string;
                    title: string;
                    sku: string;
                    revenue_90d: number;
                    seo_score: number;
                    potential_impact: number;
                    quick_fix: string;
                }>;
                high_traffic_low_conversion: Array<{
                    product_id: string;
                    title: string;
                    sessions: number;
                    bounce_rate: number;
                    potential_impact: number;
                    quick_fix: string;
                }>;
                page_two_opportunities: Array<{
                    product_id: string;
                    title: string;
                    position: number;
                    impressions: number;
                    potential_impact: number;
                    quick_fix: string;
                }>;
                high_impressions_low_ctr: Array<{
                    product_id: string;
                    title: string;
                    impressions: number;
                    ctr: number;
                    potential_impact: number;
                    quick_fix: string;
                }>;
                stale_high_inventory: Array<{
                    product_id: string;
                    title: string;
                    inventory: number;
                    days_since_sale: string;
                    potential_impact: number;
                    quick_fix: string;
                }>;
            };
            summary: {
                total_products_analyzed: number;
                total_opportunities_found: number;
                total_potential_impact: number;
                by_category: Record<string, number>;
            };
            data_sources_used: string[];
            generated_at: string;
        }>(`/products-ai/discover-opportunities?${params}`);
    },

    // Get Smart Filters
    getSmartFilters: () =>
        fetchAPI<{
            smart_filters: Array<{
                id: string;
                name: string;
                description: string;
                filter_config: Record<string, any>;
                estimated_count: number;
                potential_impact: string;
                icon: string;
            }>;
            total_filters: number;
            data_analyzed: number;
            last_updated: string;
        }>('/products-ai/smart-filters'),

    // Batch Discover (Multi-Agent Strategic Analysis)
    batchDiscover: (multiAgent: boolean = true) =>
        fetchAPI<{
            aggregate_data: {
                total_products: number;
                avg_seo_score: number;
                total_revenue_90d: number;
                total_sessions: number;
                products_by_opportunity: Record<string, number>;
                seo_score_distribution: Record<string, number>;
                top_transmission_codes: Record<string, number>;
            };
            strategic_analysis: {
                strategic_recommendations?: Array<{
                    type: string;
                    title: string;
                    description: string;
                    affected_products: number;
                    estimated_impact: string;
                    implementation_effort: string;
                    priority: number;
                }>;
                content_gaps?: string[];
                cross_sell_opportunities?: Array<{
                    product_a: string;
                    product_b: string;
                    reason: string;
                }>;
                technical_improvements?: string[];
                _multi_agent?: {
                    mode: string;
                    consensus_score: number;
                };
                error?: string;
            };
            analysis_type: string;
        }>(`/products-ai/batch-discover?multi_agent=${multiAgent}`, {
            method: 'POST'
        }),
};

// Settings API
export const settingsAPI = {
    // Get active LLM provider
    getActiveLLMProvider: () =>
        fetchAPI<{
            active: string;
            available: string[];
        }>('/settings/llm-providers'),
};

// Task API (Celery task polling)
export interface TaskStatus {
    task_id: string;
    status: 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'RETRY';
    result: unknown;
    progress: { current: number; total: number; [key: string]: unknown } | null;
}

export const taskAPI = {
    getStatus: (taskId: string) =>
        fetchAPI<TaskStatus>(`/tasks/${taskId}`),
    listActive: () =>
        fetchAPI<{ tasks: Array<{ task_id: string; name: string; worker: string; status: string }>; count: number }>('/tasks'),
};

// Creative Intelligence API
export const creativeIntelligenceAPI = {
    getReport: () =>
        fetchAPI<any>('/creative-intelligence'),
    getBrandDetail: (brandName: string) =>
        fetchAPI<any>(`/creative-intelligence/brand/${encodeURIComponent(brandName)}`),
    getTransmissions: () =>
        fetchAPI<any>('/creative-intelligence/transmissions'),
    exportCSV: async () => {
        const url = `${API_BASE}/creative-intelligence/export`;
        const response = await fetch(url);
        return response.text();
    },
};

