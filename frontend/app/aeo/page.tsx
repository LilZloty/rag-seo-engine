/**
 * AEO Dashboard Page - Answer Engine Optimization
 * 
 * Refactored to use modular AEO components
 * Previously: 669 lines | Now: ~250 lines
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { aeoAPI, visibilityAPI, analyticsAPI, settingsAPI, ProductChunk, LLMSTxtPreview, BlogArticle, AEOConfig, FaultCode, Solution, RecommendedProduct, SchemaMetrics, AITrafficReport, VisibilityPrompt, VisibilityDashboard, LLMSalesReport, EnhancedLLMSalesReport, ProductIntelligenceResponse, VisibilitySalesCorrelation, AEOEvent, AEOEventType, VisibilityWeeklyTrend, ProductWhyAnalysis } from '@/lib/api';
import { Tabs } from '@/app/components';
import {
  AEOFocusedOverview,
  AEOStatsGrid,
  AEOChunksGrid,
  AEOPreviewPanel,
  AEOBlogsList,
  AEOKnowledgeGraph,
  AEOMetricsDashboard,
  AEOVisibilityPanel,
  AEOConfigPanel,
  AEOProductIntelligence,
  AEOVisibilityCorrelation,
  EnhancedLLMSalesAttribution,
  GSCPromptImporter,
  AEOImpactTimeline,
  aeoTabs
} from '@/app/components/aeo';

export default function AEOPage() {
  // Data State
  const [chunks, setChunks] = useState<ProductChunk[]>([]);
  const [preview, setPreview] = useState<LLMSTxtPreview | null>(null);
  const [blogs, setBlogs] = useState<BlogArticle[]>([]);
  const [faultCodes, setFaultCodes] = useState<FaultCode[]>([]);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [config, setConfig] = useState<AEOConfig | null>(null);
  const [productsByFaultCode, setProductsByFaultCode] = useState<Record<string, RecommendedProduct[]>>({});
  const [metrics, setMetrics] = useState<SchemaMetrics | null>(null);
  const [aiTraffic, setAiTraffic] = useState<AITrafficReport | null>(null);
  const [llmSales, setLLMSales] = useState<LLMSalesReport | null>(null);
  const [enhancedLLMSales, setEnhancedLLMSales] = useState<EnhancedLLMSalesReport | null>(null);
  const [llmSalesLoading, setLLMSalesLoading] = useState(false);
  const [llmSalesError, setLLMSalesError] = useState<string | null>(null);
  const [llmSalesDays, setLLMSalesDays] = useState(365);

  // Visibility State
  const [visibilityPrompts, setVisibilityPrompts] = useState<VisibilityPrompt[]>([]);
  const [visibilityDashboard, setVisibilityDashboard] = useState<VisibilityDashboard | null>(null);
  const [checking, setChecking] = useState(false);

  // Product Intelligence State
  const [productIntelligence, setProductIntelligence] = useState<ProductIntelligenceResponse | null>(null);
  const [intelligenceLoading, setIntelligenceLoading] = useState(false);
  const [productWhyAnalysis, setProductWhyAnalysis] = useState<ProductWhyAnalysis | null>(null);

  // Correlation State
  const [correlationData, setCorrelationData] = useState<VisibilitySalesCorrelation | null>(null);
  const [correlationLoading, setCorrelationLoading] = useState(false);

  // Impact Timeline + Visibility Trend State
  const [aeoEvents, setAeoEvents] = useState<AEOEvent[]>([]);
  const [visibilityTrend, setVisibilityTrend] = useState<VisibilityWeeklyTrend[] | null>(null);

  // UI State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [copied, setCopied] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // LLM Provider State - defaults to 'grok', updates from header selector
  const [activeLLMProvider, setActiveLLMProvider] = useState<string>('grok');

  // Fetch active LLM provider on mount
  useEffect(() => {
    const fetchActiveProvider = async () => {
      try {
        const data = await settingsAPI.getActiveLLMProvider();
        if (data.active) {
          setActiveLLMProvider(data.active);
        }
      } catch (err) {
        console.error('Failed to fetch active LLM provider, using default grok:', err);
      }
    };
    fetchActiveProvider();
  }, []);

  // ============ Data Loading Functions ============

  const loadCoreData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [chunksData, previewData, configData, metricsData] = await Promise.all([
        aeoAPI.getChunks(),
        aeoAPI.getLLMSTxtPreview(),
        aeoAPI.getConfig(),
        aeoAPI.getSchemaMetrics().catch(() => null)
      ]);
      setChunks(chunksData);
      setPreview(previewData);
      setConfig(configData);
      if (metricsData) setMetrics(metricsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load AEO data');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMetricsData = useCallback(async () => {
    try {
      setLoading(true);
      setLLMSalesLoading(true);

      const [metricsData, trafficData, salesData, correlationRes] = await Promise.all([
        aeoAPI.getSchemaMetrics(),
        analyticsAPI.getAITraffic(),
        analyticsAPI.getEnhancedLLMSales(llmSalesDays, {
          compare: true,
          includeFunnel: true,
          includeAssisted: true,
          includeGeo: true,
          includeTimeToConversion: true,
          includeCohorts: true,
          includeCategories: true
        }).catch(err => {
          setLLMSalesError(err.message || 'Failed to load LLM sales');
          return null;
        }),
        aeoAPI.getVisibilityCorrelation(30).catch(() => null)
      ]);
      setMetrics(metricsData);
      setAiTraffic(trafficData);
      if (salesData) {
        setEnhancedLLMSales(salesData);
        setLLMSalesError(null);
      }
      if (correlationRes) {
        setCorrelationData(correlationRes);
      }
    } catch (err) {
      console.error('Failed to load metrics:', err);
      setError('Failed to load tracking metrics. Check Google API credentials.');
    } finally {
      setLoading(false);
      setLLMSalesLoading(false);
    }
  }, [llmSalesDays]);

  const handleExportLLMSales = async (format: 'csv' | 'json') => {
    try {
      const response = await analyticsAPI.exportLLMSales(llmSalesDays, format);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `llm_sales_${llmSalesDays}d.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Export failed:', err);
      setError('Failed to export LLM sales data');
    }
  };

  const loadBlogs = useCallback(async () => {
    try {
      const blogsData = await aeoAPI.getBlogs();
      setBlogs(blogsData);
    } catch (err) {
      console.error('Failed to load blogs:', err);
    }
  }, []);

  const loadKnowledgeGraph = useCallback(async () => {
    try {
      setLoading(true);
      const [fcData, solData] = await Promise.all([
        aeoAPI.getFaultCodes(),
        aeoAPI.getSolutions()
      ]);
      setFaultCodes(fcData.fault_codes);
      setSolutions(solData.solutions);

      // Fetch real products for each fault code (limit to 10 for performance)
      const productsMap: Record<string, RecommendedProduct[]> = {};
      for (const fc of fcData.fault_codes.slice(0, 10)) {
        try {
          const result = await aeoAPI.getProductsForFaultCode(fc.code, 5);
          productsMap[fc.code] = result.products as RecommendedProduct[];
        } catch {
          productsMap[fc.code] = [];
        }
      }
      setProductsByFaultCode(productsMap);
    } catch (err) {
      console.error('Failed to load knowledge graph:', err);
      setError('Failed to load knowledge graph data');
    } finally {
      setLoading(false);
    }
  }, []);

  // ============ Action Handlers ============

  const handleSyncKnowledge = async () => {
    try {
      setSyncing(true);
      await aeoAPI.syncKnowledgeGraph();
      await loadKnowledgeGraph();
    } catch (err) {
      setError('Failed to sync knowledge graph');
    } finally {
      setSyncing(false);
    }
  };

  const handleApproveChunk = async (productType: string, approved: boolean) => {
    try {
      await aeoAPI.approveChunk(productType, approved);
      await loadCoreData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update chunk');
    }
  };

  const handleDownload = async () => {
    try {
      const content = await aeoAPI.downloadLLMSTxt();
      const blob = new Blob([content], { type: 'text/markdown' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'llms.txt';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download llms.txt');
    }
  };

  const handleCopy = async () => {
    if (preview?.content) {
      await navigator.clipboard.writeText(preview.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRebuild = async () => {
    try {
      setLoading(true);
      await aeoAPI.rebuildLLMSTxt();
      await loadCoreData();
    } catch (err) {
      setError('Failed to rebuild llms.txt');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoApprove = async () => {
    try {
      setLoading(true);
      const result = await aeoAPI.autoApproveChunks(15, 5);
      if (result.approved_count > 0) {
        await aeoAPI.rebuildLLMSTxt();
      }
      await loadCoreData();
      alert(`✅ ${result.message}`);
    } catch (err) {
      setError('Failed to auto-approve chunks');
    } finally {
      setLoading(false);
    }
  };

  // ============ Effects ============

  useEffect(() => {
    loadCoreData();
  }, [loadCoreData]);

  // Visibility Data Loading
  const loadVisibilityData = useCallback(async () => {
    try {
      const [promptsData, dashboardData] = await Promise.all([
        visibilityAPI.getPrompts(),
        visibilityAPI.getDashboard()
      ]);
      setVisibilityPrompts(promptsData);
      setVisibilityDashboard(dashboardData);
    } catch (err) {
      console.error('Failed to load visibility data:', err);
    }
  }, []);

  const handleRunVisibilityCheck = async (promptIds?: number[]) => {
    try {
      setChecking(true);
      if (promptIds) {
        for (const id of promptIds) {
          await visibilityAPI.checkSinglePrompt(id).catch(console.error);
        }
      } else {
        await visibilityAPI.runBatchCheck(undefined, [activeLLMProvider], 10);
      }
      await loadVisibilityData();
    } catch (err) {
      setError('Failed to run visibility check');
    } finally {
      setChecking(false);
    }
  };

  const handleAddVisibilityPrompt = async (promptText: string, category: string) => {
    try {
      await visibilityAPI.addPrompt({ prompt_text: promptText, category });
      await loadVisibilityData();
    } catch (err) {
      setError('Failed to add prompt');
    }
  };

  const handleRemoveVisibilityPrompt = async (promptId: number) => {
    try {
      await visibilityAPI.removePrompt(promptId);
      await loadVisibilityData();
    } catch (err) {
      setError('Failed to remove prompt');
    }
  };

  // Product Intelligence Data Loading
  const loadProductIntelligence = useCallback(async () => {
    try {
      setIntelligenceLoading(true);
      const [data, whyData] = await Promise.all([
        aeoAPI.getProductIntelligence(365),
        aeoAPI.getProductWhyAnalysis(undefined, 20).catch(() => null),
      ]);
      setProductIntelligence(data);
      if (whyData) setProductWhyAnalysis(whyData);
    } catch (err) {
      console.error('[Product Intelligence] Failed to load:', err);
      setError('Failed to load product intelligence: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIntelligenceLoading(false);
    }
  }, []);
  // Correlation Data Loading
  const loadCorrelationData = useCallback(async () => {
    try {
      setCorrelationLoading(true);
      const data = await aeoAPI.getVisibilityCorrelation(30);
      setCorrelationData(data);
    } catch (err) {
      console.error('Failed to load correlation data:', err);
      setError('Failed to load visibility correlation data');
    } finally {
      setCorrelationLoading(false);
    }
  }, []);

  const loadAeoEvents = useCallback(async () => {
    try {
      const data = await aeoAPI.getEvents();
      setAeoEvents(data);
    } catch (err) {
      console.error('Failed to load AEO events:', err);
    }
  }, []);

  const loadVisibilityTrend = useCallback(async () => {
    try {
      const data = await aeoAPI.getVisibilityTrend(8);
      setVisibilityTrend(data);
    } catch (err) {
      console.error('Failed to load visibility trend:', err);
    }
  }, []);

  const handleAddEvent = async (payload: { event_date: string; event_type: AEOEventType; title: string; description?: string }) => {
    await aeoAPI.createEvent(payload);
    await loadAeoEvents();
  };

  const handleDeleteEvent = async (id: number) => {
    await aeoAPI.deleteEvent(id);
    await loadAeoEvents();
  };

  useEffect(() => {
    if (activeTab === 'overview') {
      // Overview needs: aiTraffic (from loadMetricsData), productIntelligence
      // (from loadProductIntelligence), and schema metrics (already loaded
      // on mount via loadCoreData). Only trigger what's missing.
      if (!aiTraffic) loadMetricsData();
      if (!productIntelligence) loadProductIntelligence();
    } else if (activeTab === 'blogs' && blogs.length === 0) {
      loadBlogs();
    } else if (activeTab === 'knowledge' && faultCodes.length === 0) {
      loadKnowledgeGraph();
    } else if (activeTab === 'metrics' && !aiTraffic) {
      loadMetricsData();
      if (aeoEvents.length === 0) loadAeoEvents();
    } else if (activeTab === 'metrics' && aeoEvents.length === 0) {
      loadAeoEvents();
    } else if (activeTab === 'visibility' && visibilityPrompts.length === 0) {
      loadVisibilityData();
      if (!visibilityTrend) loadVisibilityTrend();
    } else if (activeTab === 'visibility' && !visibilityTrend) {
      loadVisibilityTrend();
    } else if (activeTab === 'intelligence' && !productIntelligence) {
      loadProductIntelligence();
    } else if (activeTab === 'correlation' && !correlationData) {
      loadCorrelationData();
    }
  }, [activeTab, blogs.length, faultCodes.length, aiTraffic, visibilityPrompts.length, productIntelligence, correlationData, aeoEvents.length, visibilityTrend, loadBlogs, loadKnowledgeGraph, loadMetricsData, loadVisibilityData, loadProductIntelligence, loadCorrelationData, loadAeoEvents, loadVisibilityTrend]);

  // ============ Loading State ============

  if (loading && chunks.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-black">
        <div className="animate-spin rounded-full size-12 border-b-2 border-[#F7B500]" />
      </div>
    );
  }

  // ============ Render ============

  return (
    <div className="min-h-screen bg-black text-white pt-16">
      <div className="p-6 relative z-0 isolate">
        {/* Error Display */}
        {error && (
          <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-2xl mb-6 flex justify-between items-center">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-200 hover:text-white">
              <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Stats Grid */}
        <AEOStatsGrid
          totalChunks={preview?.total_chunks || 0}
          approvedChunks={preview?.approved_chunks || 0}
          tokenEstimate={preview?.token_estimate || 0}
          fileSizeKB={(preview?.byte_size || 0) / 1024}
        />

        {/* Tabs */}
        <div className="mb-8">
          <Tabs
            tabs={aeoTabs}
            activeTab={activeTab}
            onChange={setActiveTab}
          />
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <AEOFocusedOverview
            aiTraffic={aiTraffic}
            intelligence={productIntelligence}
            schemaMetrics={metrics}
            loading={loading || intelligenceLoading || llmSalesLoading}
          />
        )}

        {activeTab === 'chunks' && (
          <AEOChunksGrid
            chunks={chunks}
            onApprove={handleApproveChunk}
            onAutoApprove={handleAutoApprove}
            onRefresh={loadCoreData}
            loading={loading}
          />
        )}

        {activeTab === 'preview' && (
          <AEOPreviewPanel
            preview={preview}
            onCopy={handleCopy}
            onRebuild={handleRebuild}
            onDownload={handleDownload}
            copied={copied}
            loading={loading}
          />
        )}

        {activeTab === 'blogs' && (
          <AEOBlogsList
            blogs={blogs}
            onRefresh={loadBlogs}
          />
        )}

        {activeTab === 'knowledge' && (
          <AEOKnowledgeGraph
            faultCodes={faultCodes}
            solutions={solutions}
            productsByFaultCode={productsByFaultCode}
            onSync={handleSyncKnowledge}
            onRefresh={loadKnowledgeGraph}
            syncing={syncing}
          />
        )}

        {activeTab === 'visibility' && (
          <AEOVisibilityPanel
            prompts={visibilityPrompts}
            dashboard={visibilityDashboard}
            visibilityTrend={visibilityTrend}
            onRunCheck={handleRunVisibilityCheck}
            onRefresh={loadVisibilityData}
            onAddPrompt={handleAddVisibilityPrompt}
            onRemovePrompt={handleRemoveVisibilityPrompt}
            loading={loading}
            checking={checking}
          />
        )}

        {activeTab === 'metrics' && (
          <div className="space-y-6">
            {/* Enhanced LLM Sales Attribution with full analytics */}
            <EnhancedLLMSalesAttribution
              data={enhancedLLMSales}
              loading={llmSalesLoading}
              error={llmSalesError}
              days={llmSalesDays}
              onDaysChange={setLLMSalesDays}
              onRefresh={loadMetricsData}
              onExport={handleExportLLMSales}
            />

            {/* AEO Impact Timeline — overlay improvement events on the monthly trend */}
            <AEOImpactTimeline
              monthlyTrend={enhancedLLMSales?.basic?.monthly_trend}
              events={aeoEvents}
              onAddEvent={handleAddEvent}
              onDeleteEvent={handleDeleteEvent}
            />

            {/* Traffic / Schema metrics dashboard */}
            <AEOMetricsDashboard
              metrics={metrics}
              aiTraffic={aiTraffic}
              correlation={correlationData}
              onLoadData={loadMetricsData}
            />
          </div>
        )}

        {activeTab === 'intelligence' && (
          <AEOProductIntelligence
            productsFromLLM={productIntelligence?.products_from_llm || []}
            optimizationOpportunities={productIntelligence?.optimization_opportunities || []}
            successPatterns={productIntelligence?.success_patterns || null}
            whyAnalysis={productWhyAnalysis}
            onRefresh={loadProductIntelligence}
            loading={intelligenceLoading}
          />
        )}

        {activeTab === 'correlation' && (
          <AEOVisibilityCorrelation
            data={correlationData}
            onRefresh={loadCorrelationData}
            loading={correlationLoading}
          />
        )}

        {activeTab === 'config' && (
          <AEOConfigPanel config={config} />
        )}

        {activeTab === 'gsc-import' && (
          <GSCPromptImporter
            onImportComplete={() => {
              // Refresh visibility prompts after import
              loadVisibilityData();
            }}
          />
        )}
      </div>
    </div>
  );
}
