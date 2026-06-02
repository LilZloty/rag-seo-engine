'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { collectionsAIAPI, CollectionContentDraft } from '@/lib/api';
import { formatDate } from '@/app/lib/dates';

interface CollectionContentDraftsProps {
  collectionId: number;
  onDraftApproved?: () => void;
}

export function CollectionContentDrafts({
  collectionId,
  onDraftApproved,
}: CollectionContentDraftsProps) {
  const [drafts, setDrafts] = useState<CollectionContentDraft[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDraft, setSelectedDraft] = useState<CollectionContentDraft | null>(null);
  const [approving, setApproving] = useState(false);

  const loadDrafts = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await collectionsAIAPI.listDrafts(collectionId);
      setDrafts(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to load drafts');
    } finally {
      setLoading(false);
    }
  }, [collectionId]);

  const loadDraftDetail = useCallback(async (draftId: string) => {
    try {
      const response = await collectionsAIAPI.getDraft(collectionId, draftId);
      setSelectedDraft(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to load draft detail');
    }
  }, [collectionId]);

  const approveDraft = useCallback(async (draftId: string) => {
    try {
      setApproving(true);
      await collectionsAIAPI.approveDraft(draftId);
      await loadDrafts();
      setSelectedDraft(null);
      onDraftApproved?.();
    } catch (err: any) {
      setError(err.message || 'Failed to approve draft');
    } finally {
      setApproving(false);
    }
  }, [loadDrafts, onDraftApproved]);

  useEffect(() => {
    loadDrafts();
  }, [collectionId]);

  if (loading && drafts.length === 0) {
    return (
      <div className="border border-zinc-700 rounded-lg p-4 bg-zinc-800/50">
        <div className="flex items-center gap-2">
          <div className="size-4 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-zinc-400">Loading drafts…</span>
        </div>
      </div>
    );
  }

  if (drafts.length === 0 && !error) {
    return (
      <div className="border border-zinc-700 rounded-lg p-6 bg-zinc-800/30 text-center">
        <p className="text-sm text-zinc-500">No content drafts yet</p>
        <p className="text-xs text-zinc-600 mt-1">Generate content to create the first draft</p>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    draft: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    approved: 'bg-green-500/10 text-green-400 border-green-500/20',
    deployed: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    archived: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20',
  };

  return (
    <div className="space-y-3">
      {error && (
        <div className="text-xs text-red-400 bg-red-500/10 rounded px-3 py-2">{error}</div>
      )}

      {/* Draft List */}
      <div className="space-y-2">
        {drafts.map((draft) => (
          <div
            key={draft.id}
            role="button"
            tabIndex={0}
            aria-label={`Open draft ${draft.id}`}
            className={`border border-zinc-700 rounded-lg p-3 bg-zinc-800/30 cursor-pointer hover:bg-zinc-800/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500] ${
              selectedDraft?.id === draft.id ? 'ring-1 ring-[#f7b500]' : ''
            }`}
            onClick={() => loadDraftDetail(draft.id)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadDraftDetail(draft.id); } }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-zinc-500">v{draft.version}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded border ${statusColors[draft.draft_status] || statusColors.draft}`}>
                  {draft.draft_status}
                </span>
                {draft.cannibalization_status && draft.cannibalization_status !== 'unknown' && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    draft.cannibalization_status === 'safe' ? 'bg-green-500/10 text-green-400' :
                    draft.cannibalization_status === 'warning' ? 'bg-[#f7b500]/10 text-[#f7b500]' :
                    'bg-red-500/10 text-red-400'
                  }`}>
                    {draft.cannibalization_status}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {draft.faq_count !== undefined && (
                  <span className="text-[10px] text-zinc-500">{draft.faq_count} FAQs</span>
                )}
                <span className="text-[10px] text-zinc-600">
                  {draft.created_at ? formatDate(draft.created_at) : ''}
                </span>
              </div>
            </div>
            {draft.educational_content_preview && (
              <p className="text-xs text-zinc-400 mt-2 line-clamp-2">
                {draft.educational_content_preview}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Draft Detail Panel */}
      {selectedDraft && (
        <div className="border border-zinc-600 rounded-lg bg-zinc-900/50">
          <div className="px-4 py-3 border-b border-zinc-700 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-white">
              Draft v{selectedDraft.version}
              <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded border ${statusColors[selectedDraft.draft_status] || ''}`}>
                {selectedDraft.draft_status}
              </span>
            </h4>
            <div className="flex gap-2">
              {selectedDraft.draft_status === 'draft' && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    approveDraft(selectedDraft.id);
                  }}
                  disabled={approving}
                  className="px-3 py-1 bg-green-600 hover:bg-green-500 text-white text-xs rounded transition-colors disabled:opacity-50"
                >
                  {approving ? 'Approving...' : 'Approve Draft'}
                </button>
              )}
              <button
                onClick={() => setSelectedDraft(null)}
                className="text-xs text-zinc-400 hover:text-white px-2"
              >
                Close
              </button>
            </div>
          </div>

          <div className="p-4 space-y-4 max-h-[500px] overflow-y-auto">
            {/* Educational Content */}
            {selectedDraft.educational_content && (
              <div>
                <h5 className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
                  Educational Content
                </h5>
                <div
                  className="prose prose-invert prose-sm max-w-none bg-zinc-800 rounded-lg p-3 text-xs"
                  dangerouslySetInnerHTML={{ __html: selectedDraft.educational_content }}
                />
              </div>
            )}

            {/* FAQ Content */}
            {selectedDraft.faq_content && selectedDraft.faq_content.length > 0 && (
              <div>
                <h5 className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
                  FAQ ({selectedDraft.faq_content.length} items)
                </h5>
                <div className="space-y-2">
                  {selectedDraft.faq_content.map((faq, i) => (
                    <div key={faq.question || `faq-${i}`} className="bg-zinc-800 rounded-lg p-3">
                      <p className="text-xs font-medium text-white mb-1">Q: {faq.question}</p>
                      <p className="text-xs text-zinc-400">A: {faq.answer}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Cannibalization Context */}
            {selectedDraft.safe_keywords_used && (
              <div>
                <h5 className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
                  Keywords Used
                </h5>
                <div className="flex flex-wrap gap-1">
                  {selectedDraft.safe_keywords_used.map((kw) => (
                    <span key={kw} className="px-2 py-0.5 bg-green-500/10 border border-green-500/20 rounded text-[10px] text-green-300">
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {selectedDraft.blocked_keywords_avoided && selectedDraft.blocked_keywords_avoided.length > 0 && (
              <div>
                <h5 className="text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wider">
                  Keywords Avoided (cannibalization)
                </h5>
                <div className="flex flex-wrap gap-1">
                  {selectedDraft.blocked_keywords_avoided.map((kw) => (
                    <span key={kw} className="px-2 py-0.5 bg-red-500/10 border border-red-500/20 rounded text-[10px] text-red-300 line-through">
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Metadata */}
            <div className="flex gap-4 text-[10px] text-zinc-600 pt-2 border-t border-zinc-700">
              {selectedDraft.generation_provider && (
                <span>Provider: {selectedDraft.generation_provider}</span>
              )}
              {selectedDraft.multi_agent && <span>Multi-agent: Yes</span>}
              {selectedDraft.risk_score !== undefined && (
                <span>Risk score: {selectedDraft.risk_score}%</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CollectionContentDrafts;
