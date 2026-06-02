/**
 * Solution Engine Dashboard
 * 
 * Integrates fault code analysis, product recommendations, solution paths,
 * and smart snippets for AEO/GEO optimization.
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  solutionEngineAPI,
  aeoAPI,
  SolutionEngineProduct,
  SolutionPath,
  SmartSnippet,
  SolutionEngineStats,
  TopFaultCode,
  BlogContentResponse,
  AIFaultCodeAnalysis,
  CollectionDataResponse
} from '@/lib/api';
import { Card, Button, Badge, Tabs, ProgressBar, Input } from '@/app/components/ui';
import Link from 'next/link';
import {
  SearchIcon,
  DocumentIcon,
  LibraryIcon,
  TrendingUpIcon,
  CheckIcon,
  AlertIcon,
  RefreshIcon,
  DownloadIcon,
  CopyIcon,
  ArrowRightIcon,
  SparklesIcon,
  TargetIcon,
  ChartIcon,
  DatabaseIcon,
  GlobeIcon,
  PlusIcon,
  ShoppingCartIcon,
  CarIcon
} from '@/app/components/ui/Icons';

// Types
interface FaultCodeWithProducts {
  code: string;
  name: string;
  description?: string;
  monthly_clicks?: number;
  monthly_impressions?: number;
  products: SolutionEngineProduct[];
  loading?: boolean;
}

export default function SolutionEngineDashboard() {
  // State
  const [stats, setStats] = useState<SolutionEngineStats | null>(null);
  const [topFaultCodes, setTopFaultCodes] = useState<TopFaultCode[]>([]);
  const [selectedFaultCode, setSelectedFaultCode] = useState<FaultCodeWithProducts | null>(null);
  const [faultCodes, setFaultCodes] = useState<FaultCodeWithProducts[]>([]);
  const [solutionPath, setSolutionPath] = useState<SolutionPath | null>(null);
  const [smartSnippet, setSmartSnippet] = useState<SmartSnippet | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [llmsPreview, setLlmsPreview] = useState<string>('');

  // AI-Powered State
  const [aiAnalysis, setAiAnalysis] = useState<AIFaultCodeAnalysis | null>(null);
  const [blogContent, setBlogContent] = useState<BlogContentResponse | null>(null);
  const [collectionData, setCollectionData] = useState<CollectionDataResponse | null>(null);
  const [aiStats, setAiStats] = useState<{
    ai_analyzed_fault_codes: number;
    smart_snippets_generated: number;
    solution_paths_created: number;
    average_ai_confidence: number;
    fault_codes_ready_for_content: number;
  } | null>(null);

  // Multi-Agent State
  const [multiAgentEnabled, setMultiAgentEnabled] = useState<boolean>(false);
  const [multiAgentMeta, setMultiAgentMeta] = useState<{
    mode: string;
    agents_used: string[];
    consensus_score: number;
    task_type?: string;
  } | null>(null);

  // Load initial data
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, topCodesData] = await Promise.all([
        solutionEngineAPI.getStats(),
        solutionEngineAPI.getTopFaultCodes(10)
      ]);
      setStats(statsData);
      setTopFaultCodes(topCodesData.fault_codes);
    } catch (err) {
      console.error('Failed to load Solution Engine data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    // Load multi-agent status on mount
    solutionEngineAPI.getMultiAgentStatus()
      .then(status => setMultiAgentEnabled(status.multi_agent_enabled))
      .catch(() => {}); // Silently default to true
  }, [loadData]);

  // Load fault code details
  const loadFaultCodeDetails = async (code: string) => {
    try {
      const result = await solutionEngineAPI.getFaultCodeProducts(code, 5);
      setSelectedFaultCode({
        code: result.fault_code,
        name: result.fault_code,
        products: result.products,
        loading: false
      });
    } catch (err) {
      console.error('Failed to load fault code details:', err);
    }
  };

  // Search for solution path
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setGenerating(true);
    try {
      const [pathResult, snippetResult] = await Promise.all([
        solutionEngineAPI.getSolutionPath(searchQuery),
        solutionEngineAPI.getSmartSnippet(searchQuery)
      ]);
      setSolutionPath(pathResult);
      setSmartSnippet(snippetResult);
    } catch (err) {
      console.error('Failed to generate solution:', err);
    } finally {
      setGenerating(false);
    }
  };

  // Generate enhanced llms.txt preview
  const generateLlmsPreview = async () => {
    try {
      const content = await aeoAPI.downloadLLMSTxt();
      setLlmsPreview(content.slice(0, 2000) + '...');
    } catch (err) {
      console.error('Failed to load llms.txt preview:', err);
    }
  };

  // Load AI stats
  const loadAIStats = useCallback(async () => {
    try {
      const stats = await solutionEngineAPI.getAIStats();
      setAiStats(stats);
    } catch (err) {
      console.error('Failed to load AI stats:', err);
    }
  }, []);

  // Analyze fault code with AI
  const handleAnalyzeFaultCode = async () => {
    if (!selectedFaultCode?.code) return;

    setGenerating(true);
    setMultiAgentMeta(null);
    try {
      const result = await solutionEngineAPI.analyzeFaultCodeWithAI(selectedFaultCode.code, multiAgentEnabled);
      setAiAnalysis(result);
      // Capture multi-agent metadata if present
      if ((result as any)?._multi_agent) {
        setMultiAgentMeta((result as any)._multi_agent);
      }
    } catch (err) {
      console.error('AI analysis failed:', err);
    } finally {
      setGenerating(false);
    }
  };

  // Generate blog content
  const handleGenerateBlog = async () => {
    if (!selectedFaultCode?.code) return;

    setGenerating(true);
    try {
      const result = await solutionEngineAPI.generateBlogContent(selectedFaultCode.code, {
        include_products: true,
        word_count: 1000,
        tone: 'professional'
      });
      setBlogContent(result);
    } catch (err) {
      console.error('Blog generation failed:', err);
    } finally {
      setGenerating(false);
    }
  };

  // Get collection data
  const handleGetCollectionData = async () => {
    if (!selectedFaultCode?.code) return;

    setGenerating(true);
    try {
      const result = await solutionEngineAPI.getCollectionData(selectedFaultCode.code);
      setCollectionData(result);
    } catch (err) {
      console.error('Collection data fetch failed:', err);
    } finally {
      setGenerating(false);
    }
  };

  // Tabs configuration
  const tabs = [
    { id: 'overview', label: 'Overview', icon: <ChartIcon size={16} /> },
    { id: 'content-gen', label: 'Content Generator', icon: <DocumentIcon size={16} /> },
    { id: 'comparison', label: 'Comparison Tool', icon: <TargetIcon size={16} /> },
    { id: 'collections', label: 'Collections', icon: <ShoppingCartIcon size={16} /> },
    { id: 'fault-codes', label: 'Fault Codes', icon: <CarIcon size={16} />, count: stats?.fault_codes_total },
    { id: 'llms-txt', label: 'LLMs.txt', icon: <LibraryIcon size={16} /> },
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white pt-16">
        <div className="p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-[#2a2a2a] rounded w-1/4" />
            <div className="grid grid-cols-4 gap-4">
              {[1, 2, 3, 4].map(n => (
                <div key={`skel-${n}`} className="h-32 bg-[#2a2a2a] rounded" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white pt-16">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="space-y-3">
          {/* Row 1: Title + Multi-Agent Toggle */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-semibold">Solution Engine</h1>
              <p className="text-zinc-400 text-sm mt-1">
                AI-powered fault code analysis and product recommendations
              </p>
            </div>

            {/* Multi-Agent Toggle - Prominent position */}
            <label className="flex items-center gap-3 bg-[#1a1a1a] border border-[#3a3a3a] px-4 py-2.5 cursor-pointer hover:border-[#F7B500] transition-colors flex-shrink-0">
              <input
                type="checkbox"
                className="size-5 accent-[#F7B500]"
                checked={multiAgentEnabled}
                onChange={(e) => setMultiAgentEnabled(e.target.checked)}
              />
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold whitespace-nowrap">
                  Multi-Agent
                </span>
                {multiAgentEnabled ? (
                  <span className="text-xs bg-[#F7B500] text-black px-1.5 py-0.5 font-bold">
                    4 AGENTS
                  </span>
                ) : (
                  <span className="text-xs bg-[#3a3a3a] text-zinc-400 px-1.5 py-0.5 font-medium">
                    OFF
                  </span>
                )}
              </div>
            </label>
          </div>

          {/* Row 2: Action buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            <Button variant="outline" onClick={loadData} icon={<RefreshIcon size={16} />}>
              Refresh
            </Button>
            <Button variant="outline" onClick={loadAIStats} icon={<SparklesIcon size={16} />}>
              AI Stats
            </Button>
            <Link href="/aeo">
              <Button icon={<ArrowRightIcon size={16} />}>
                AEO/GEO
              </Button>
            </Link>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card accent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-400">Fault Codes</p>
                <p className="text-3xl font-bold">{stats?.fault_codes_total || 0}</p>
              </div>
              <CarIcon size={32} className="text-[#F7B500]" />
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-400">With Products</p>
                <p className="text-3xl font-bold text-green-400">
                  {stats?.fault_codes_with_products || 0}
                </p>
              </div>
              <CheckIcon size={32} className="text-green-400" />
            </div>
            <ProgressBar 
              value={stats?.coverage_percentage || 0} 
              className="mt-3"
              color="green"
            />
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-400">Coverage</p>
                <p className="text-3xl font-bold">
                  {Math.round(stats?.coverage_percentage || 0)}%
                </p>
              </div>
              <TargetIcon size={32} className="text-blue-400" />
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-400">Product Matches</p>
                <p className="text-3xl font-bold">{stats?.total_product_matches || 0}</p>
              </div>
              <DatabaseIcon size={32} className="text-yellow-400" />
            </div>
          </Card>
        </div>

        {/* Quick Search */}
        <Card accent>
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <label htmlFor="solution-path-query" className="block text-sm text-zinc-400 mb-2">
                Test Solution Path Generator
              </label>
              <div className="flex gap-2">
                <Input
                  id="solution-path-query"
                  placeholder="Enter query (e.g., 'p0700 chevrolet', 'codigo p0706')..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  icon={<SearchIcon size={18} />}
                  className="flex-1"
                />
                <Button 
                  onClick={handleSearch} 
                  loading={generating}
                  icon={<SparklesIcon size={18} />}
                >
                  Generate
                </Button>
              </div>
            </div>
          </div>

          {/* Search Results */}
          {(solutionPath || smartSnippet) && (
            <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
              {solutionPath && (
                <div>
                  <h3 className="font-semibold mb-3">Solution Path</h3>
                  <div className="space-y-2">
                    {solutionPath.steps.map((step, idx) => (
                      <div key={step.step || `step-${idx}`} className="flex items-start gap-3 p-3 bg-[#2a2a2a] rounded">
                        <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[#F7B500] text-black text-xs font-bold">
                          {step.step}
                        </div>
                        <div>
                          <p className="font-medium">{step.title}</p>
                          <p className="text-sm text-zinc-400">{step.content}</p>
                          <Badge variant="default" className="mt-1">{step.type}</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {smartSnippet && (
                <div>
                  <h3 className="font-semibold mb-3">Smart Snippet (GEO)</h3>
                  <div className="space-y-3">
                    <div className="p-3 bg-[#2a2a2a] rounded border-l-4 border-[#F7B500]">
                      <p className="text-sm text-zinc-400 mb-1">Short Answer</p>
                      <p className="text-sm">{smartSnippet.short_answer}</p>
                    </div>
                    <div className="p-3 bg-[#2a2a2a] rounded">
                      <p className="text-sm text-zinc-400 mb-1">Authority Quote</p>
                      <p className="text-sm italic">{smartSnippet.authority_quote}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {smartSnippet.statistic_claims.map((claim, idx) => (
                        <Badge key={typeof claim === 'string' ? claim : `claim-${idx}`} variant="success">{claim}</Badge>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Tabs */}
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

        {/* Tab Content */}
        <div className="space-y-6">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Top Fault Codes */}
              <Card title="Top Fault Codes by Traffic" icon={<TrendingUpIcon size={20} className="text-[#F7B500]" />}>
                <div className="space-y-3">
                  {topFaultCodes.slice(0, 5).map((fc) => (
                    <div
                      key={fc.code}
                      role="button"
                      tabIndex={0}
                      aria-label={`Open detail for fault code ${fc.code}`}
                      className="flex items-center justify-between p-3 bg-[#2a2a2a] rounded hover:bg-[#3a3a3a] cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
                      onClick={() => loadFaultCodeDetails(fc.code)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadFaultCodeDetails(fc.code); } }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="size-10 rounded bg-[#F7B500]/20 flex items-center justify-center">
                          <CarIcon size={20} className="text-[#F7B500]" />
                        </div>
                        <div>
                          <p className="font-semibold">{fc.code}</p>
                          <p className="text-sm text-zinc-400">{fc.name}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-[#F7B500]">{fc.monthly_clicks.toLocaleString()}</p>
                        <p className="text-xs text-zinc-400">clicks/mo</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="space-y-3">
                  {topFaultCodes.slice(0, 5).map((fc) => (
                    <div
                      key={fc.code}
                      role="button"
                      tabIndex={0}
                      aria-label={`Open detail for fault code ${fc.code}`}
                      className="flex items-center justify-between p-3 bg-[#2a2a2a] rounded hover:bg-[#3a3a3a] cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
                      onClick={() => loadFaultCodeDetails(fc.code)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadFaultCodeDetails(fc.code); } }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="size-10 rounded bg-[#F7B500]/20 flex items-center justify-center">
                          <CarIcon size={20} className="text-[#F7B500]" />
                        </div>
                        <div>
                          <p className="font-semibold">{fc.code}</p>
                          <p className="text-sm text-zinc-400">{fc.name}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-[#F7B500]">{fc.monthly_clicks.toLocaleString()}</p>
                        <p className="text-xs text-zinc-400">clicks/mo</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-4 border-t border-[#3a3a3a]">
                  <p className="text-sm text-zinc-400">
                    Click on a fault code to see product recommendations
                  </p>
                </div>
              </Card>

              {/* Selected Fault Code Details */}
              {selectedFaultCode && (
                <Card 
                  title={`${selectedFaultCode.code} - Product Recommendations`}
                  icon={<DatabaseIcon size={20} className="text-[#F7B500]" />}
                >
                  <div className="space-y-3">
                    {selectedFaultCode.products.map((product) => (
                      <div key={product.product_id} className="p-3 bg-[#2a2a2a] rounded">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-lg font-bold text-[#F7B500]">#{product.rank}</span>
                              <p className="font-medium">{product.title}</p>
                            </div>
                            <p className="text-sm text-zinc-400 mt-1">{product.reasoning}</p>
                            <div className="flex items-center gap-3 mt-2">
                              <Badge variant={product.fix_probability === 'high' ? 'success' : product.fix_probability === 'medium' ? 'warning' : 'default'}>
                                {product.fix_probability} probability
                              </Badge>
                              <span className="text-sm text-zinc-400">
                                Score: {product.match_score}/100
                              </span>
                              {product.total_sold > 0 && (
                                <span className="text-sm text-green-400">
                                  {product.total_sold} sold
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="text-right">
                            {product.price && (
                              <p className="font-semibold">${product.price}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {!selectedFaultCode && (
                <Card className="flex items-center justify-center min-h-[300px]">
                  <div className="text-center">
                    <CarIcon size={48} className="text-zinc-600 mx-auto mb-4" />
                    <p className="text-zinc-400">Select a fault code to see recommendations</p>
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* AI Analyzer Tab */}
          {activeTab === 'ai-analyzer' && (
            <div className="space-y-6">
              <Card accent>
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="flex-1">
                    <label htmlFor="ai-analyzer-fault-code" className="block text-sm text-zinc-400 mb-2">
                      Select Fault Code for AI Analysis
                    </label>
                    <select
                      id="ai-analyzer-fault-code"
                      value={selectedFaultCode?.code || ''}
                      onChange={(e) => {
                        const code = e.target.value;
                        if (code) loadFaultCodeDetails(code);
                      }}
                      className="w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded px-4 py-2 text-white"
                    >
                      <option value="">Select a fault code…</option>
                      {topFaultCodes.map((fc) => (
                        <option key={fc.code} value={fc.code}>
                          {fc.code} - {fc.name} ({fc.monthly_clicks} clicks/mo)
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <Button
                      onClick={handleAnalyzeFaultCode}
                      loading={generating}
                      disabled={!selectedFaultCode}
                      icon={<SparklesIcon size={18} />}
                    >
                      Analyze with Grok AI
                    </Button>
                  </div>
                </div>
              </Card>

              {aiAnalysis && (
                <Card title={`AI Analysis: ${aiAnalysis.fault_code}`}>
                  <div className="space-y-4">
                    <div className="flex items-center gap-4 flex-wrap">
                      <Badge variant={aiAnalysis.confidence >= 80 ? 'success' : 'warning'}>
                        Confidence: {aiAnalysis.confidence}%
                      </Badge>
                      {aiAnalysis.ai_analyzed && (
                        <Badge variant="success">AI Analyzed</Badge>
                      )}
                      {multiAgentMeta && (
                        <>
                          <Badge variant="default">
                            Mode: {multiAgentMeta.mode}
                          </Badge>
                          <Badge variant={multiAgentMeta.consensus_score >= 70 ? 'success' : 'warning'}>
                            Consensus: {multiAgentMeta.consensus_score}%
                          </Badge>
                          <span className="text-xs text-zinc-400">
                            Agents: {multiAgentMeta.agents_used.join(', ')}
                          </span>
                        </>
                      )}
                    </div>

                    <div>
                      <p className="text-sm text-zinc-400 mb-2">AI Reasoning:</p>
                      <p className="text-zinc-300 bg-[#2a2a2a] p-3 rounded">
                        {aiAnalysis.reasoning}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-zinc-400 mb-2">Recommended Products:</p>
                      <div className="space-y-2">
                        {aiAnalysis.products.map((product, idx) => (
                          <div
                            key={product.product_id}
                            className="flex items-center justify-between p-3 bg-[#2a2a2a] rounded"
                          >
                            <div className="flex items-center gap-3">
                              <span className="text-[#F7B500] font-bold">#{idx + 1}</span>
                              <div>
                                <p className="font-medium">{product.title}</p>
                                <p className="text-sm text-zinc-400">{product.reasoning}</p>
                              </div>
                            </div>
                            <div className="text-right">
                              <Badge variant={product.fix_probability === 'high' ? 'success' : 'warning'}>
                                {product.fix_probability}
                              </Badge>
                              <p className="text-sm text-zinc-400 mt-1">
                                Score: {product.match_score}/100
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {aiAnalysis.alternative_approaches.length > 0 && (
                      <div>
                        <p className="text-sm text-zinc-400 mb-2">Alternative Approaches:</p>
                        <ul className="list-disc list-inside text-zinc-300">
                          {aiAnalysis.alternative_approaches.map((approach, idx) => (
                            <li key={typeof approach === 'string' ? approach : `approach-${idx}`}>{approach}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* Content Generator Tab */}
          {activeTab === 'content-gen' && (
            <div className="space-y-6">
              <Card accent>
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="flex-1">
                    <label htmlFor="content-gen-fault-code" className="block text-sm text-zinc-400 mb-2">
                      Generate Blog Article
                    </label>
                    <select
                      id="content-gen-fault-code"
                      value={selectedFaultCode?.code || ''}
                      onChange={(e) => {
                        const code = e.target.value;
                        if (code) loadFaultCodeDetails(code);
                      }}
                      className="w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded px-4 py-2 text-white"
                    >
                      <option value="">Select a fault code…</option>
                      {topFaultCodes.map((fc) => (
                        <option key={fc.code} value={fc.code}>
                          {fc.code} - {fc.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end gap-2">
                    <Button
                      onClick={handleGenerateBlog}
                      loading={generating}
                      disabled={!selectedFaultCode}
                      icon={<DocumentIcon size={18} />}
                    >
                      Generate Blog Article
                    </Button>
                  </div>
                </div>
              </Card>

              {blogContent && (
                <>
                  {/* Main Article Card */}
                  <Card title={blogContent.title}>
                    <div className="space-y-4">
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="success">
                          <CheckIcon size={12} className="mr-1" />
                          {blogContent.estimated_read_time} min read
                        </Badge>
                        <Badge variant="default">
                          {blogContent.product_recommendations.length} products
                        </Badge>
                      </div>

                      <div>
                        <p className="text-sm text-zinc-400 mb-1">Meta Description:</p>
                        <p className="text-sm text-zinc-300 bg-[#2a2a2a] p-2 rounded">
                          {blogContent.meta_description}
                        </p>
                      </div>

                      <div>
                        <p className="text-sm text-zinc-400 mb-1">Target Keywords:</p>
                        <div className="flex flex-wrap gap-1">
                          {blogContent.target_keywords.map((kw, idx) => (
                            <Badge key={typeof kw === 'string' ? kw : `kw-${idx}`} variant="default" >{kw}</Badge>
                          ))}
                        </div>
                      </div>

                      <div>
                        <p className="text-sm text-zinc-400 mb-2">Content Sections:</p>
                        <div className="space-y-2">
                          {blogContent.sections.map((section, idx) => (
                            <div key={section.heading || `section-${idx}`} className="border border-[#3a3a3a] rounded overflow-hidden">
                              <div className="bg-[#2a2a2a] px-3 py-2 flex items-center justify-between">
                                <span className="font-medium">{section.heading}</span>
                                <Badge variant="default" >{section.type}</Badge>
                              </div>
                              <div className="p-3 text-sm text-zinc-300 max-h-32 overflow-y-auto">
                                <div dangerouslySetInnerHTML={{ __html: section.content }} />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </Card>

                  {/* Trust Signals Box */}
                  {blogContent.enhanced_content?.eeat_box && (
                    <Card title="Trust Signals" icon={<CheckIcon size={20} className="text-green-400" />}>
                      <div className="bg-[#1a1a1a] border border-[#F7B500]/30 rounded p-4">
                        <h4 className="text-[#F7B500] font-semibold mb-3">Expertos en Transmisiones</h4>
                        <div className="grid grid-cols-2 gap-3">
                          {blogContent.enhanced_content.eeat_box.statistics.map((stat, idx) => (
                            <div key={stat.label || `stat-${idx}`} className="text-center">
                              <p className="text-xl font-bold text-[#F7B500]">{stat.value}</p>
                              <p className="text-xs text-zinc-400">{stat.label}</p>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 pt-3 border-t border-[#3a3a3a]">
                          {blogContent.enhanced_content.eeat_box.trust_signals.slice(0, 3).map((signal, idx) => (
                            <p key={typeof signal === 'string' ? signal : `signal-${idx}`} className="text-sm text-zinc-300 flex items-center gap-2">
                              <span className="text-green-400">✓</span> {signal}
                            </p>
                          ))}
                        </div>
                      </div>
                    </Card>
                  )}

                  {/* FAQ Schema (Compact) */}
                  {blogContent.faq_schema && (
                    <Card title="FAQ Schema" icon={<DocumentIcon size={20} className="text-[#F7B500]" />}>
                      <p className="text-sm text-zinc-400 mb-2">
                        {blogContent.faq_schema.mainEntity?.length || 0} FAQs ready for Google
                      </p>
                      <Button
                        variant="outline"
                        onClick={() => navigator.clipboard.writeText(JSON.stringify(blogContent.faq_schema, null, 2))}
                        icon={<CopyIcon size={14} />}
                      >
                        Copy Schema
                      </Button>
                    </Card>
                  )}

                  {/* Comparison Tables */}
                  {blogContent.enhanced_content?.comparison_tables && (
                    <Card title={`Comparison: ${blogContent.fault_code} vs ${blogContent.enhanced_content.comparison_tables.vs_code}`} icon={<ChartIcon size={20} className="text-[#F7B500]" />}>
                      <div 
                        className="overflow-x-auto"
                        dangerouslySetInnerHTML={{ __html: blogContent.enhanced_content.comparison_tables.html }} 
                      />
                    </Card>
                  )}
                </>
              )}
            </div>
          )}

          {/* Comparison Tool Tab */}
          {activeTab === 'comparison' && (
            <div className="space-y-6">
              <Card accent>
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="flex-1">
                    <label htmlFor="comparison-first-code" className="block text-sm text-zinc-400 mb-2">
                      First Fault Code
                    </label>
                    <select
                      id="comparison-first-code"
                      value={selectedFaultCode?.code || ''}
                      onChange={(e) => {
                        const code = e.target.value;
                        if (code) loadFaultCodeDetails(code);
                      }}
                      className="w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded px-4 py-2 text-white"
                    >
                      <option value="">Select first code…</option>
                      {topFaultCodes.map((fc) => (
                        <option key={fc.code} value={fc.code}>
                          {fc.code} - {fc.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center justify-center">
                    <span className="text-zinc-400">vs</span>
                  </div>
                  <div className="flex-1">
                    <label htmlFor="comparison-second-code" className="block text-sm text-zinc-400 mb-2">
                      Second Fault Code
                    </label>
                    <select
                      id="comparison-second-code"
                      className="w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded px-4 py-2 text-white"
                    >
                      <option value="">Select second code…</option>
                      {topFaultCodes.filter(fc => fc.code !== selectedFaultCode?.code).map((fc) => (
                        <option key={fc.code} value={fc.code}>
                          {fc.code} - {fc.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <Button
                      icon={<ChartIcon size={18} />}
                    >
                      Generate Comparison
                    </Button>
                  </div>
                </div>
              </Card>

              <Card title="Why Comparison Content Matters">
                <div className="space-y-4 text-zinc-300">
                  <p>
                    Mechanics often search for comparisons like <strong>"P0700 vs P0706"</strong> to understand 
                    differences between codes. Creating this content helps you:
                  </p>
                  <ul className="list-disc list-inside space-y-2">
                    <li>Capture <strong>1,900+ monthly searches</strong> for "vs" queries</li>
                    <li>Position as the expert who explains differences</li>
                    <li>Rank for long-tail keywords competitors miss</li>
                    <li>Increase time on site (mechanics read both guides)</li>
                  </ul>
                  <div className="bg-[#2a2a2a] p-4 rounded mt-4">
                    <p className="text-sm text-zinc-400">Example comparison table:</p>
                    <table className="w-full mt-2 text-sm">
                      <thead>
                        <tr className="border-b border-[#3a3a3a]">
                          <th className="text-left py-2">Feature</th>
                          <th className="text-left py-2">P0700</th>
                          <th className="text-left py-2">P0706</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b border-[#3a3a3a]/50">
                          <td className="py-2">Severity</td>
                          <td className="py-2">Moderate</td>
                          <td className="py-2 text-[#F7B500]">High ✓</td>
                        </tr>
                        <tr className="border-b border-[#3a3a3a]/50">
                          <td className="py-2">Main Symptom</td>
                          <td className="py-2">Check engine light</td>
                          <td className="py-2">Won't shift</td>
                        </tr>
                        <tr>
                          <td className="py-2">Repair Cost</td>
                          <td className="py-2">$2,000-4,000</td>
                          <td className="py-2">$1,500-3,000</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* Collections Tab */}
          {activeTab === 'collections' && (
            <div className="space-y-6">
              <Card accent>
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="flex-1">
                    <label htmlFor="collections-fault-code" className="block text-sm text-zinc-400 mb-2">
                      View Collection Data
                    </label>
                    <select
                      id="collections-fault-code"
                      value={selectedFaultCode?.code || ''}
                      onChange={(e) => {
                        const code = e.target.value;
                        if (code) loadFaultCodeDetails(code);
                      }}
                      className="w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded px-4 py-2 text-white"
                    >
                      <option value="">Select a fault code…</option>
                      {topFaultCodes.map((fc) => (
                        <option key={fc.code} value={fc.code}>
                          {fc.code} - {fc.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <Button
                      onClick={handleGetCollectionData}
                      loading={generating}
                      disabled={!selectedFaultCode}
                      icon={<ShoppingCartIcon size={18} />}
                    >
                      Get Collection Data
                    </Button>
                  </div>
                </div>
              </Card>

              {collectionData && (
                <Card title={`Collection: ${collectionData.title}`}>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-[#2a2a2a] p-3 rounded text-center">
                        <p className="text-2xl font-bold text-[#F7B500]">{collectionData.product_counts.total}</p>
                        <p className="text-xs text-zinc-400">Total Products</p>
                      </div>
                      <div className="bg-[#2a2a2a] p-3 rounded text-center">
                        <p className="text-2xl font-bold text-green-400">{collectionData.product_counts.kits}</p>
                        <p className="text-xs text-zinc-400">Kits</p>
                      </div>
                      <div className="bg-[#2a2a2a] p-3 rounded text-center">
                        <p className="text-2xl font-bold text-blue-400">{collectionData.product_counts.parts}</p>
                        <p className="text-xs text-zinc-400">Parts</p>
                      </div>
                      <div className="bg-[#2a2a2a] p-3 rounded text-center">
                        <p className="text-2xl font-bold text-purple-400">
                          ${collectionData.revenue_potential.toLocaleString()}
                        </p>
                        <p className="text-xs text-zinc-400">Est. Revenue/mo</p>
                      </div>
                    </div>

                    <div>
                      <p className="text-sm text-zinc-400 mb-1">Handle:</p>
                      <code className="text-sm bg-[#2a2a2a] px-2 py-1 rounded">
                        /collections/{collectionData.handle}
                      </code>
                    </div>

                    <div>
                      <p className="text-sm text-zinc-400 mb-1">Transmissions:</p>
                      <div className="flex flex-wrap gap-1">
                        {collectionData.transmissions.map((t, idx) => (
                          <Badge key={typeof t === 'string' ? t : `trans-${idx}`} variant="default" >{t}</Badge>
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="text-sm text-zinc-400 mb-2">Top Products:</p>
                      <div className="space-y-2">
                        {collectionData.top_products.map((product) => (
                          <div
                            key={product.id}
                            className="flex items-center justify-between p-2 bg-[#2a2a2a] rounded"
                          >
                            <div className="flex items-center gap-2">
                              <ShoppingCartIcon size={16} className="text-zinc-400" />
                              <span>{product.title}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge variant={product.type === 'kit' ? 'success' : 'default'} >
                                {product.type}
                              </Badge>
                              <span className="text-[#F7B500]">${product.price}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* Fault Codes Tab */}
          {activeTab === 'fault-codes' && (
            <Card title="All Fault Codes" icon={<CarIcon size={20} className="text-[#F7B500]" />}>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {topFaultCodes.map((fc) => (
                  <div key={fc.code} className="p-4 bg-[#2a2a2a] rounded border border-[#3a3a3a] hover:border-[#F7B500] transition-colors">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold text-lg">{fc.code}</h3>
                      <Badge variant={fc.products_available > 0 ? 'success' : 'warning'}>
                        {fc.products_available} products
                      </Badge>
                    </div>
                    <p className="text-sm text-zinc-400 mb-3">{fc.name}</p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="bg-[#1a1a1a] p-2 rounded">
                        <p className="text-zinc-500">Clicks</p>
                        <p className="font-semibold">{fc.monthly_clicks.toLocaleString()}</p>
                      </div>
                      <div className="bg-[#1a1a1a] p-2 rounded">
                        <p className="text-zinc-500">Position</p>
                        <p className="font-semibold">{fc.avg_position.toFixed(1)}</p>
                      </div>
                    </div>
                    <Button 
                      variant="outline" 
                       
                      className="w-full mt-3"
                      onClick={() => loadFaultCodeDetails(fc.code)}
                    >
                      View Products
                    </Button>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Solution Paths Tab */}
          {activeTab === 'solution-paths' && (
            <Card 
              title="Solution Path Generator" 
              icon={<GlobeIcon size={20} className="text-[#F7B500]" />}
            >
              <div className="space-y-4">
                <p className="text-zinc-400">
                  Solution paths create step-by-step journeys from search query to purchase.
                  Enter a query above to generate a custom path.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {['p0700', 'p0706', 'p0715', 'p0730', 'p0743', 'p0841'].map((code) => (
                    <Button
                      key={code}
                      variant="outline"
                      onClick={() => {
                        setSearchQuery(code);
                        handleSearch();
                      }}
                    >
                      Test: {code.toUpperCase()}
                    </Button>
                  ))}
                </div>

                {solutionPath && (
                  <div className="mt-6 p-4 bg-[#2a2a2a] rounded">
                    <h4 className="font-semibold mb-3">Generated Path for: "{solutionPath.query}"</h4>
                    <div className="space-y-2">
                      {solutionPath.steps.map((step) => (
                        <div key={step.step} className="flex items-center gap-3">
                          <div className="size-8 rounded-full bg-[#F7B500] text-black flex items-center justify-center font-bold text-sm">
                            {step.step}
                          </div>
                          <div className="flex-1 p-3 bg-[#1a1a1a] rounded">
                            <p className="font-medium">{step.title}</p>
                            <p className="text-sm text-zinc-400">{step.content}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Smart Snippets Tab */}
          {activeTab === 'snippets' && (
            <Card 
              title="Smart Snippet Generator (GEO)" 
              icon={<DocumentIcon size={20} className="text-[#F7B500]" />}
            >
              <div className="space-y-4">
                <p className="text-zinc-400">
                  Smart snippets are AI-optimized answers designed for AI engine citations (Grok, Perplexity, ChatGPT).
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {['codigo p0700', 'que es p0706', 'p0715 solucion', 'p0730 reparar'].map((query) => (
                    <Button
                      key={query}
                      variant="outline"
                      onClick={() => {
                        setSearchQuery(query);
                        handleSearch();
                      }}
                    >
                      Generate: "{query}"
                    </Button>
                  ))}
                </div>

                {smartSnippet && (
                  <div className="mt-6 space-y-4">
                    <div className="p-4 bg-[#2a2a2a] rounded border-l-4 border-[#F7B500]">
                      <p className="text-xs text-zinc-400 uppercase tracking-wider mb-2">Short Answer (Featured Snippet)</p>
                      <p className="text-lg">{smartSnippet.short_answer}</p>
                    </div>

                    <div className="p-4 bg-[#2a2a2a] rounded">
                      <p className="text-xs text-zinc-400 uppercase tracking-wider mb-2">Detailed Answer</p>
                      <p className="text-sm text-zinc-300 whitespace-pre-wrap">{smartSnippet.detailed_answer}</p>
                    </div>

                    <div className="p-4 bg-[#2a2a2a] rounded border-l-4 border-green-500">
                      <p className="text-xs text-zinc-400 uppercase tracking-wider mb-2">Authority Quote (E-E-A-T)</p>
                      <p className="text-sm italic">"{smartSnippet.authority_quote}"</p>
                    </div>

                    <div>
                      <p className="text-xs text-zinc-400 uppercase tracking-wider mb-2">Statistic Claims</p>
                      <div className="flex flex-wrap gap-2">
                        {smartSnippet.statistic_claims.map((claim, idx) => (
                          <Badge key={typeof claim === 'string' ? claim : `claim-${idx}`} variant="success">{claim}</Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* LLMs.txt Tab */}
          {activeTab === 'llms-txt' && (
            <Card 
              title="Enhanced LLMs.txt" 
              icon={<LibraryIcon size={20} className="text-[#F7B500]" />}
            >
              <div className="space-y-4">
                <p className="text-zinc-400">
                  The enhanced llms.txt includes solution paths, product recommendations, and GEO-optimized content.
                </p>

                <div className="flex gap-2">
                  <Button onClick={generateLlmsPreview} icon={<RefreshIcon size={16} />}>
                    Load Preview
                  </Button>
                  <Link href="/aeo">
                    <Button variant="outline" icon={<ArrowRightIcon size={16} />}>
                      Full AEO Dashboard
                    </Button>
                  </Link>
                </div>

                {llmsPreview && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm text-zinc-400">Preview (first 2000 chars)</p>
                      <div className="flex gap-2">
                        <Button variant="ghost"  icon={<CopyIcon size={14} />}>
                          Copy
                        </Button>
                        <Button variant="ghost"  icon={<DownloadIcon size={14} />}>
                          Download
                        </Button>
                      </div>
                    </div>
                    <pre className="p-4 bg-[#2a2a2a] rounded text-sm text-zinc-300 overflow-auto max-h-[500px]">
                      {llmsPreview}
                    </pre>
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
