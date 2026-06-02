/**
 * Knowledge Library Page - RAG Knowledge Base
 * 
 * Refactored to use modular Library components
 * Previously: 1,469 lines | Now: ~450 lines
 */

'use client';

import { useState, useEffect } from 'react';
import { formatDate } from '@/app/lib/dates';
import { libraryAPI, documentAPI, promptAPI } from '@/lib/api';
import { Button, Card, Badge, Modal, Input, Tabs } from '@/app/components';
import {
  LibraryStats,
  DocumentList,
  LibraryGrid,
  TemplatesList,
  libraryTabs,
  PromptTemplate,
  Library,
  Document
} from '../components/libraries';
import { PlusIcon, RefreshIcon, DocumentIcon, LibraryIcon, TemplateIcon } from '../components/ui/Icons';

export default function LibrariesPage() {
  // Data State
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('documents');

  // Modal State
  const [showIngestModal, setShowIngestModal] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [selectedLibrary, setSelectedLibrary] = useState<Library | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<PromptTemplate | null>(null);

  // Form State
  const [templateForm, setTemplateForm] = useState({
    name: '',
    template_type: 'brand' as 'brand' | 'product_type' | 'transmission' | 'general',
    system_instructions: '',
    example_output: '',
    priority: 50,
    is_active: true
  });

  const [ingestType, setIngestType] = useState<'url' | 'text' | 'upload'>('url');
  const [ingestUrl, setIngestUrl] = useState('');
  const [ingestTitle, setIngestTitle] = useState('');
  const [ingestContent, setIngestContent] = useState('');
  const [ingestBrands, setIngestBrands] = useState('');
  const [ingestProductTypes, setIngestProductTypes] = useState('');
  const [ingestTransmissions, setIngestTransmissions] = useState('');
  const [ingestFile, setIngestFile] = useState<File | null>(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<string | null>(null);
  // URL scrape modes:
  //   false → sync path, uses httpx+BeautifulSoup fallback on the light API (static HTML only)
  //   true  → async path, dispatched to crawler worker with headless Chromium (JS-rendered OK)
  const [useBrowserCrawler, setUseBrowserCrawler] = useState(false);
  const [ingestProgress, setIngestProgress] = useState<string | null>(null);

  // Basic Info State
  const [basicInfoForm, setBasicInfoForm] = useState({
    title: '',
    content: '',
    sourceUrl: '',
    brands: 'TSS',
    category: 'general' as 'general' | 'transend' | 'stellar' | 'dacco'
  });
  const [basicInfoInputType, setBasicInfoInputType] = useState<'text' | 'pdf'>('text');
  const [basicInfoFile, setBasicInfoFile] = useState<File | null>(null);
  const [savingBasicInfo, setSavingBasicInfo] = useState(false);

  // Document Detail State
  const [fullDocumentContent, setFullDocumentContent] = useState<string | null>(null);
  const [loadingFullContent, setLoadingFullContent] = useState(false);
  const [showFullContent, setShowFullContent] = useState(false);

  // ============ Data Loading ============

  const loadData = async () => {
    try {
      setLoading(true);
      const [libsData, docsData, tempsData] = await Promise.all([
        libraryAPI.getLibraries().catch(() => []),
        documentAPI.getDocuments().catch(() => []),
        promptAPI.getTemplates().catch(() => [])
      ]);
      setLibraries((libsData as any) || []);
      setDocuments((docsData as any) || []);
      setTemplates((tempsData as any) || []);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // ============ Document Actions ============

  const handleIngest = async () => {
    setIsIngesting(true);
    setIngestResult(null);
    setIngestProgress(null);

    try {
      if (ingestType === 'url') {
        if (!ingestUrl.trim()) throw new Error('Enter a URL');
        if (useBrowserCrawler) {
          // Worker-backed async crawl: dispatch, then poll.
          setIngestProgress('Dispatching to crawler worker…');
          const { task_id } = await documentAPI.scrapeUrlAsync(
            ingestUrl,
            ingestBrands || undefined,
            ingestProductTypes || undefined,
            ingestTransmissions || undefined,
          );
          const taskResult = await documentAPI.pollTask<{ status: string; result: { document_id: string; chunk_count: number } }>(
            task_id,
            {
              onProgress: (s) => setIngestProgress(
                s === 'PENDING' ? 'Queued — waiting for a worker…'
                : s === 'STARTED' ? 'Crawler working (headless Chromium)…'
                : `Status: ${s}`
              ),
            }
          );
          const docResult = taskResult.result;
          setIngestResult(`Success! Created ${docResult.chunk_count} chunks.`);
        } else {
          const result = await documentAPI.scrapeUrl(ingestUrl, ingestBrands || undefined, ingestProductTypes || undefined, ingestTransmissions || undefined);
          setIngestResult(`Success! Created ${result.chunk_count} chunks.`);
        }
      } else if (ingestType === 'text') {
        if (!ingestTitle.trim() || !ingestContent.trim()) throw new Error('Enter a title and content');
        const result = await documentAPI.ingestText(ingestTitle, ingestContent, ingestBrands || undefined, ingestProductTypes || undefined, ingestTransmissions || undefined);
        setIngestResult(`Success! Created ${result.chunk_count} chunks.`);
      } else if (ingestType === 'upload') {
        if (!ingestFile) throw new Error('Select a PDF file');
        const formData = new FormData();
        formData.append('file', ingestFile);
        if (ingestBrands) formData.append('brands', ingestBrands);
        if (ingestProductTypes) formData.append('product_types', ingestProductTypes);
        if (ingestTransmissions) formData.append('transmission_codes', ingestTransmissions);
        await documentAPI.uploadDocument(formData);
        setIngestResult('Document uploaded and processed successfully');
      }

      // Reset form
      setIngestUrl('');
      setIngestTitle('');
      setIngestContent('');
      setIngestFile(null);
      loadData();
    } catch (error: any) {
      setIngestResult(`Error: ${error.message || 'Failed to ingest document'}`);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleDeleteDocument = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
      await documentAPI.deleteDocument(id);
      loadData();
      setSelectedDocument(null);
    } catch (error) {
      console.error('Failed to delete document:', error);
    }
  };

  const handleLinkToLibrary = async (docId: string) => {
    const libraryId = prompt('Enter library ID (e.g., brand_tss, brand_sonnax):');
    if (libraryId) {
      try {
        await documentAPI.linkToLibrary(docId, libraryId);
        loadData();
        alert('Document linked successfully');
      } catch (error: any) {
        alert(`Error: ${error.message}`);
      }
    }
  };

  // ============ Template Actions ============

  const handleSaveTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingTemplate) {
        await promptAPI.updateTemplate(editingTemplate.id, templateForm);
      } else {
        const newId = `prompt_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 8)}`;
        await promptAPI.createTemplate({ ...templateForm, id: newId });
      }
      setShowTemplateModal(false);
      setEditingTemplate(null);
      loadData();
    } catch (error) {
      console.error('Failed to save template:', error);
      alert('Error saving template');
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    try {
      await promptAPI.deleteTemplate(id);
      loadData();
    } catch (error) {
      console.error('Failed to delete template:', error);
    }
  };

  const openTemplateModal = (template?: PromptTemplate) => {
    if (template) {
      setEditingTemplate(template);
      setTemplateForm({
        name: template.name,
        template_type: template.template_type,
        system_instructions: template.system_instructions,
        example_output: template.example_output || '',
        priority: template.priority,
        is_active: template.is_active
      });
    } else {
      setEditingTemplate(null);
      setTemplateForm({
        name: '',
        template_type: 'brand',
        system_instructions: '',
        example_output: '',
        priority: 50,
        is_active: true
      });
    }
    setShowTemplateModal(true);
  };

  // ============ Document Detail Actions ============

  const loadFullDocument = async (docId: string) => {
    setLoadingFullContent(true);
    try {
      const fullDoc: any = await documentAPI.getDocument(docId);
      setFullDocumentContent(fullDoc.content || fullDoc.content_preview || 'No content available');
    } catch (error) {
      console.error('Failed to load full document:', error);
      setFullDocumentContent('Error loading content');
    } finally {
      setLoadingFullContent(false);
    }
  };

  // ============ Basic Info Form Handler ============

  const handleSaveBasicInfo = async () => {
    if (!basicInfoForm.title.trim() || (!basicInfoForm.content.trim() && !basicInfoFile)) {
      alert('Please enter a title and content');
      return;
    }
    setSavingBasicInfo(true);
    try {
      const result = await documentAPI.ingestText(
        basicInfoForm.title,
        basicInfoForm.content || 'PDF content',
        basicInfoForm.brands || undefined,
        basicInfoForm.category,
        undefined
      );
      alert(`Success! Created ${result.chunk_count} chunks.`);
      setBasicInfoForm({ title: '', content: '', sourceUrl: '', brands: 'TSS', category: 'general' });
      loadData();
    } catch (error: any) {
      alert(`Error: ${error.message}`);
    } finally {
      setSavingBasicInfo(false);
    }
  };

  // ============ Loading State ============

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-xl text-white">Loading library…</div>
      </div>
    );
  }

  // ============ Render ============

  return (
    <div className="min-h-screen bg-black text-white pt-16">
      {/* Add Document Button - Moved to top */}
      <div className="max-w-7xl mx-auto px-6 pt-6 pb-2 flex justify-end">
        <Button
          variant="primary"
          onClick={() => setShowIngestModal(true)}
          icon={<PlusIcon size={18} />}
        >
          Add Document
        </Button>
      </div>

      {/* Stats */}
      <div className="p-6 max-w-7xl mx-auto">
        <LibraryStats
          documentCount={documents.length}
          libraryCount={libraries.length}
          templateCount={templates.length}
          onRefresh={loadData}
        />

        {/* Tabs */}
        <div className="mb-8">
          <Tabs
            tabs={libraryTabs}
            activeTab={activeTab}
            onChange={setActiveTab}
          />
        </div>

        {/* Tab Content */}
        {activeTab === 'documents' && (
          <DocumentList
            documents={documents}
            onDocumentClick={setSelectedDocument}
            onDeleteDocument={handleDeleteDocument}
            onLinkToLibrary={handleLinkToLibrary}
          />
        )}

        {activeTab === 'libraries' && (
          <LibraryGrid
            libraries={libraries}
            documents={documents}
            onLibraryClick={setSelectedLibrary}
            onAddDocument={() => setShowIngestModal(true)}
          />
        )}

        {activeTab === 'templates' && (
          <TemplatesList
            templates={templates}
            onCreateTemplate={() => openTemplateModal()}
            onEditTemplate={openTemplateModal}
            onDeleteTemplate={handleDeleteTemplate}
          />
        )}
      </div>

      {/* ============ MODALS ============ */}

      {/* Ingest Modal */}
      <Modal
        isOpen={showIngestModal}
        onClose={() => { setShowIngestModal(false); setIngestResult(null); }}
        title="Add Document to Knowledge Base"
        size="lg"
      >
        <div className="space-y-6">
          {/* Type selector */}
          <div className="flex gap-2">
            {(['url', 'text', 'upload'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setIngestType(type)}
                className={`px-4 py-2 font-medium rounded-2xl transition-all ${ingestType === type
                    ? 'bg-[#F7B500] text-black'
                    : 'bg-[#1a1a1a] text-zinc-300 border border-[#3a3a3a] hover:border-[#F7B500]'
                  }`}
              >
                {type === 'url' && '🌐 Extract URL'}
                {type === 'text' && '✍️ Enter Text'}
                {type === 'upload' && '📄 Upload PDF'}
              </button>
            ))}
          </div>

          {/* URL Input */}
          {ingestType === 'url' && (
            <div className="space-y-3">
              <div>
                <label htmlFor="ingest-url" className="block text-sm font-medium text-zinc-300 mb-2">URL to Extract</label>
                <Input
                  id="ingest-url"
                  type="url"
                  value={ingestUrl}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIngestUrl(e.target.value)}
                  placeholder="https://provider.com/product-catalog"
                />
              </div>
              <label
                htmlFor="use-browser-crawler"
                aria-label="Use browser-based crawler"
                className="flex items-start gap-3 cursor-pointer text-sm text-zinc-300"
              >
                <input
                  id="use-browser-crawler"
                  type="checkbox"
                  checked={useBrowserCrawler}
                  onChange={(e) => setUseBrowserCrawler(e.target.checked)}
                  className="mt-0.5 accent-[#F7B500]"
                />
                <span>
                  <span className="font-medium text-white">Use browser-based crawler</span>
                  <span className="block text-xs text-zinc-400 mt-0.5">
                    Dispatches to a worker with headless Chromium — needed for JS-rendered pages (SPAs, React sites).
                    Takes ~20s instead of ~1s. Leave off for static HTML.
                  </span>
                </span>
              </label>
            </div>
          )}

          {/* Text Input */}
          {ingestType === 'text' && (
            <>
              <div>
                <label htmlFor="ingest-title" className="block text-sm font-medium text-zinc-300 mb-2">Document Title</label>
                <Input
                  id="ingest-title"
                  type="text"
                  value={ingestTitle}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIngestTitle(e.target.value)}
                  placeholder="e.g. TSS Valve Body Catalog 2024"
                />
              </div>
              <label className="block">
                <span className="block text-sm font-medium text-zinc-300 mb-2">Content</span>
                <textarea
                  value={ingestContent}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setIngestContent(e.target.value)}
                  placeholder="Paste document content here..."
                  rows={8}
                  className="w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded-2xl px-4 py-3 text-white focus:border-[#F7B500] focus:outline-none"
                />
              </label>
            </>
          )}

          {/* PDF Upload */}
          {ingestType === 'upload' && (
            <div>
              <p className="block text-sm font-medium text-zinc-300 mb-2">Select PDF File</p>
              <div className="border-2 border-dashed border-[#3a3a3a] rounded-2xl p-8 text-center hover:border-[#F7B500] transition-colors">
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIngestFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="pdf-upload"
                />
                <label htmlFor="pdf-upload" className="cursor-pointer">
                  {ingestFile ? (
                    <div>
                      <p className="text-[#F7B500] font-medium text-lg">📄 {ingestFile.name}</p>
                      <p className="text-zinc-500 text-sm mt-1">{(ingestFile.size / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-zinc-400 text-lg mb-2">📤 Click to select PDF</p>
                      <p className="text-xs text-zinc-500">or drag and drop</p>
                    </div>
                  )}
                </label>
              </div>
            </div>
          )}

          {/* Tags */}
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Brands"
              value={ingestBrands}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIngestBrands(e.target.value)}
              placeholder="TSS, Sonnax"
            />
            <Input
              label="Product Types"
              value={ingestProductTypes}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIngestProductTypes(e.target.value)}
              placeholder="valve_body, solenoid"
            />
            <Input
              label="Transmissions"
              value={ingestTransmissions}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setIngestTransmissions(e.target.value)}
              placeholder="4L60E, 4L65E"
            />
          </div>

          {/* Progress (async crawl) */}
          {ingestProgress && !ingestResult && (
            <div className="p-4 rounded-2xl bg-[#F7B500]/10 text-[#F7B500] border border-[#F7B500]/30 flex items-center gap-3">
              <span className="inline-block size-4 rounded-full border-2 border-[#F7B500] border-t-transparent animate-spin" />
              {ingestProgress}
            </div>
          )}

          {/* Result */}
          {ingestResult && (
            <div className={`p-4 rounded-2xl ${ingestResult.startsWith('Success')
                ? 'bg-green-500/20 text-green-300 border border-green-500/30'
                : 'bg-red-500/20 text-red-300 border border-red-500/30'
              }`}>
              {ingestResult}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => { setShowIngestModal(false); setIngestResult(null); setIngestProgress(null); }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleIngest}
              loading={isIngesting}
            >
              {isIngesting ? 'Processing...' : 'Add Document'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Template Modal */}
      <Modal
        isOpen={showTemplateModal}
        onClose={() => { setShowTemplateModal(false); setEditingTemplate(null); }}
        title={editingTemplate ? 'Edit Template' : 'New Template'}
        size="lg"
      >
        <form onSubmit={handleSaveTemplate} className="space-y-4">
          <Input
            label="Name"
            value={templateForm.name}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTemplateForm(prev => ({ ...prev, name: e.target.value }))}
            placeholder="e.g. TSS Template"
            required
          />

          <label className="block">
            <span className="block text-sm font-medium text-zinc-300 mb-2">Type</span>
            <select
              value={templateForm.template_type}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setTemplateForm(prev => ({ ...prev, template_type: e.target.value as 'brand' | 'product_type' | 'transmission' | 'general' }))}
              className="w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded-2xl px-4 py-3 text-white focus:border-[#F7B500] focus:outline-none"
            >
              <option value="brand">Brand</option>
              <option value="product_type">Product Type</option>
              <option value="transmission">Transmission</option>
              <option value="general">General</option>
            </select>
          </label>

          <Input
            label="Example Output (optional)"
            value={templateForm.example_output}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTemplateForm(prev => ({ ...prev, example_output: e.target.value }))}
            placeholder="Example of expected output..."
          />

          <label className="block">
            <span className="block text-sm font-medium text-zinc-300 mb-2">System Instructions</span>
            <textarea
              value={templateForm.system_instructions}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setTemplateForm(prev => ({ ...prev, system_instructions: e.target.value }))}
              placeholder="Write instructions for the AI..."
              rows={10}
              required
              className="w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded-2xl px-4 py-3 text-white font-mono text-sm focus:border-[#F7B500] focus:outline-none"
            />
          </label>

          <div>
            <label htmlFor="template-priority" className="block text-sm font-medium text-zinc-300 mb-2">Priority (0-100)</label>
            <Input
              id="template-priority"
              type="number"
              min="0"
              max="100"
              value={templateForm.priority}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTemplateForm(prev => ({ ...prev, priority: parseInt(e.target.value) || 50 }))}
            />
            <p className="text-xs text-zinc-500 mt-1">Lower = higher priority</p>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="is_active"
              checked={templateForm.is_active}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTemplateForm(prev => ({ ...prev, is_active: e.target.checked }))}
              className="size-5 accent-[#F7B500]"
            />
            <label htmlFor="is_active" className="text-zinc-300">Active template</label>
          </div>

          <div className="flex justify-end gap-4 pt-4 border-t border-[#3a3a3a]">
            <Button
              variant="outline"
              type="button"
              onClick={() => { setShowTemplateModal(false); setEditingTemplate(null); }}
            >
              Cancel
            </Button>
            <Button variant="primary" type="submit">
              {editingTemplate ? 'Save Changes' : 'Create Template'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Library Detail Modal */}
      <Modal
        isOpen={!!selectedLibrary}
        onClose={() => setSelectedLibrary(null)}
        title={selectedLibrary?.name || ''}
        size="lg"
      >
        {selectedLibrary && (
          <div className="space-y-6">
            <p className="text-zinc-400">{selectedLibrary.description}</p>

            <div>
              <h3 className="text-lg font-semibold text-white mb-4">
                Documents ({documents.filter(d =>
                  (selectedLibrary.library_type === 'brand' && d.brands?.includes(selectedLibrary.name)) ||
                  (selectedLibrary.library_type === 'product_type' && d.product_types?.includes(selectedLibrary.name)) ||
                  (selectedLibrary.library_type === 'transmission' && d.transmission_codes?.includes(selectedLibrary.name))
                ).length})
              </h3>

              <div className="text-center py-8 text-zinc-500 border border-[#3a3a3a] border-dashed rounded-2xl">
                Documents in this library will be displayed here
              </div>
            </div>

            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setSelectedLibrary(null)}>
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Document Detail Modal */}
      <Modal
        isOpen={!!selectedDocument}
        onClose={() => { setSelectedDocument(null); setFullDocumentContent(null); setShowFullContent(false); }}
        title={selectedDocument?.title || ''}
        size="xl"
      >
        {selectedDocument && (
          <div className="space-y-6">
            {/* Metadata */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-[#0a0a0a] p-3 rounded-xl border border-[#3a3a3a]">
                <p className="text-xs text-zinc-500 mb-1">Source Type</p>
                <p className="text-white font-medium">{selectedDocument.source_type}</p>
              </div>
              <div className="bg-[#0a0a0a] p-3 rounded-xl border border-[#3a3a3a]">
                <p className="text-xs text-zinc-500 mb-1">Chunks</p>
                <p className="text-white font-medium text-[#F7B500]">{selectedDocument.chunk_count}</p>
              </div>
              <div className="bg-[#0a0a0a] p-3 rounded-xl border border-[#3a3a3a]">
                <p className="text-xs text-zinc-500 mb-1">Verified</p>
                <p className="text-white font-medium">{selectedDocument.verified ? 'Yes' : 'No'}</p>
              </div>
              <div className="bg-[#0a0a0a] p-3 rounded-xl border border-[#3a3a3a]">
                <p className="text-xs text-zinc-500 mb-1">Created</p>
                <p className="text-white text-sm">{selectedDocument.created_at ? formatDate(selectedDocument.created_at) : 'N/A'}</p>
              </div>
            </div>

            {/* Tags */}
            <div>
              <p className="text-xs text-zinc-500 mb-2">Tags</p>
              <div className="flex flex-wrap gap-2">
                {selectedDocument.brands?.map((b) => <Badge key={b} variant="info">{b}</Badge>)}
                {selectedDocument.transmission_codes?.map((c) => <Badge key={c} variant="warning">{c}</Badge>)}
                {selectedDocument.product_types?.map((t) => <Badge key={t} variant="success">{t}</Badge>)}
              </div>
            </div>

            {/* Content */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-zinc-500">
                  {showFullContent ? 'Full Content' : 'Content Preview'}
                </p>
                <button
                  onClick={() => {
                    if (!showFullContent && !fullDocumentContent) {
                      loadFullDocument(selectedDocument.id);
                    }
                    setShowFullContent(!showFullContent);
                  }}
                  className="text-xs text-[#F7B500] hover:underline"
                >
                  {loadingFullContent ? 'Loading...' : (showFullContent ? 'Show Preview' : 'View Full Content')}
                </button>
              </div>
              <div className={`bg-[#0a0a0a] p-4 border border-[#3a3a3a] rounded-2xl ${showFullContent ? 'max-h-[500px]' : 'max-h-64'} overflow-y-auto`}>
                <pre className="text-zinc-400 text-sm whitespace-pre-wrap font-mono">
                  {showFullContent
                    ? (fullDocumentContent || 'Loading...')
                    : (selectedDocument.content_preview || 'No preview available')
                  }
                </pre>
              </div>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => { setSelectedDocument(null); setFullDocumentContent(null); setShowFullContent(false); }}>
                Close
              </Button>
              <Button variant="danger" onClick={() => handleDeleteDocument(selectedDocument.id)}>
                Delete
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
