/**
 * Library Components - Knowledge Library Dashboard
 *
 * Specialized components for Libraries management page
 * Uses Example Store Design System: #F7B500 brand color, rounded-sm (2px) - industrial aesthetic
 */

'use client';

import React from 'react';
import { Button, Card, Badge, Modal, Tabs } from '../';
import { 
  DocumentIcon, LibraryIcon, TemplateIcon, 
  PlusIcon, TrashIcon, EditIcon, LinkIcon,
  RefreshIcon, UploadIcon, ExternalLinkIcon
} from '../ui/Icons';

// ============ Types ============

export interface PromptTemplate {
  id: string;
  name: string;
  template_type: 'brand' | 'product_type' | 'transmission' | 'general';
  system_instructions: string;
  example_output?: string;
  priority: number;
  is_active: boolean;
  created_at?: string;
}

export interface Library {
  id: string;
  name: string;
  name_es?: string;
  library_type: 'brand' | 'product_type' | 'transmission';
  description?: string;
  icon?: string;
  color?: string;
  document_count: number;
  is_active: boolean;
}

export interface Document {
  id: string;
  title: string;
  content_preview?: string;
  source_type: 'scraped' | 'uploaded_pdf' | 'manual';
  source_url?: string;
  source_filename?: string;
  brands: string[];
  product_types: string[];
  transmission_codes: string[];
  chunk_count: number;
  verified: boolean;
  created_at?: string;
}

// ============ Helper Functions ============

const getTypeColor = (type: string) => {
  switch (type) {
    case 'brand': return { border: 'border-blue-500/50', hover: 'hover:border-blue-500', badge: 'bg-blue-500/20 text-blue-300' };
    case 'product_type': return { border: 'border-green-500/50', hover: 'hover:border-green-500', badge: 'bg-green-500/20 text-green-300' };
    case 'transmission': return { border: 'border-purple-500/50', hover: 'hover:border-purple-500', badge: 'bg-purple-500/20 text-purple-300' };
    default: return { border: 'border-zinc-500/50', hover: 'hover:border-zinc-500', badge: 'bg-zinc-500/20 text-zinc-300' };
  }
};

// ============ LibraryColumn Component (extracted to module scope) ============

interface LibraryColumnProps {
  title: string;
  icon: string;
  libraries: Library[];
  type: string;
  onLibraryClick: (library: Library) => void;
}

const LibraryColumn: React.FC<LibraryColumnProps> = ({ title, icon, libraries, type, onLibraryClick }) => (
  <div>
    <div className="flex items-center gap-2 mb-4">
      <span className="text-2xl">{icon}</span>
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <span className="text-sm text-zinc-500">({libraries.length})</span>
    </div>
    <div className="space-y-3">
      {libraries.map((lib) => {
        const colors = getTypeColor(lib.library_type);
        return (
          <div
            key={lib.id}
            role="button"
            tabIndex={0}
            aria-label={`Open library ${lib.name}`}
            onClick={() => onLibraryClick(lib)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onLibraryClick(lib); } }}
            className={`bg-[#1a1a1a] p-4 border border-[#3a3a3a] ${colors.hover} ${colors.border} rounded-sm cursor-pointer transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]`}
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">{lib.icon || ''}</span>
              <div className="flex-1">
                <h3 className="font-semibold text-white">{lib.name}</h3>
                <p className="text-xs text-zinc-500">{lib.document_count} documents</p>
              </div>
              <span className="text-zinc-500">→</span>
            </div>
          </div>
        );
      })}
      {libraries.length === 0 && (
        <div className="text-center py-8 text-zinc-500 border border-[#3a3a3a] border-dashed rounded-sm">
          No {type} libraries
        </div>
      )}
    </div>
  </div>
);

// ============ Library Stats ============

interface LibraryStatsProps {
  documentCount: number;
  libraryCount: number;
  templateCount: number;
  onRefresh: () => void;
}

export const LibraryStats: React.FC<LibraryStatsProps> = ({
  documentCount,
  libraryCount,
  templateCount,
  onRefresh
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-zinc-400">Documents</p>
            <p className="text-3xl font-bold text-white">{documentCount}</p>
          </div>
          <div className="p-3 bg-blue-500/10 rounded-sm">
            <DocumentIcon className="text-blue-400" size={28} />
          </div>
        </div>
      </div>

      <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-zinc-400">Libraries</p>
            <p className="text-3xl font-bold text-white">{libraryCount}</p>
          </div>
          <div className="p-3 bg-green-500/10 rounded-sm">
            <LibraryIcon className="text-green-400" size={28} />
          </div>
        </div>
      </div>

      <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-zinc-400">Templates</p>
            <p className="text-3xl font-bold text-white">{templateCount}</p>
          </div>
          <div className="p-3 bg-purple-500/10 rounded-sm">
            <TemplateIcon className="text-purple-400" size={28} />
          </div>
        </div>
      </div>
    </div>
  );
};

// ============ Document List ============

interface DocumentListProps {
  documents: Document[];
  onDocumentClick: (doc: Document) => void;
  onDeleteDocument: (id: string) => void;
  onLinkToLibrary: (docId: string) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  onDocumentClick,
  onDeleteDocument,
  onLinkToLibrary
}) => {
  const getSourceIcon = (sourceType: string) => {
    switch (sourceType) {
      case 'scraped': return '🌐';
      case 'uploaded_pdf': return '📄';
      case 'manual': return '✍️';
      default: return '📄';
    }
  };

  if (documents.length === 0) {
    return (
      <Card>
        <div className="text-center py-16 text-zinc-400">
          <DocumentIcon size={64} className="mx-auto mb-4 opacity-50" />
          <p className="text-xl mb-2">No documents yet</p>
          <p className="mb-6">Add your first document to build the knowledge base</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {documents.map((doc) => (
        <div
          key={doc.id}
          role="button"
          tabIndex={0}
          aria-label={`Open document ${doc.title}`}
          onClick={() => onDocumentClick(doc)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onDocumentClick(doc); } }}
          className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-5 hover:border-[#F7B500]/50 transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl">{getSourceIcon(doc.source_type)}</span>
                <h3 className="font-semibold text-lg text-white">{doc.title}</h3>
                {doc.verified && (
                  <Badge variant="success">Verified</Badge>
                )}
              </div>

              {doc.content_preview && (
                <p className="text-zinc-400 text-sm mb-3 line-clamp-2">
                  {doc.content_preview}
                </p>
              )}

              <div className="flex flex-wrap gap-2 mb-3">
                {doc.brands?.map((brand) => (
                  <Badge key={brand} variant="info">{brand}</Badge>
                ))}
                {doc.transmission_codes?.map((code) => (
                  <Badge key={code} variant="warning">{code}</Badge>
                ))}
                {doc.product_types?.map((type) => (
                  <Badge key={type} variant="success">{type}</Badge>
                ))}
              </div>

              <div className="text-sm text-zinc-500 flex gap-4">
                <span>{doc.chunk_count} chunks</span>
                {doc.source_url && (
                  <a 
                    href={doc.source_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLinkIcon size={14} /> Source
                  </a>
                )}
                {doc.source_filename && (
                  <span>📎 {doc.source_filename}</span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 ml-4">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onLinkToLibrary(doc.id);
                }}
                className="p-2 text-zinc-400 hover:text-[#F7B500] transition-colors"
                title="Link to library"
              >
                <LinkIcon size={18} />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteDocument(doc.id);
                }}
                className="p-2 text-zinc-400 hover:text-red-400 transition-colors"
                title="Delete document"
              >
                <TrashIcon size={18} />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ============ Library Grid ============

interface LibraryGridProps {
  libraries: Library[];
  documents: Document[];
  onLibraryClick: (library: Library) => void;
  onAddDocument: () => void;
}

export const LibraryGrid: React.FC<LibraryGridProps> = ({
  libraries,
  onLibraryClick,
  onAddDocument
}) => {
  const brands = libraries.filter(l => l.library_type === 'brand');
  const productTypes = libraries.filter(l => l.library_type === 'product_type');
  const transmissions = libraries.filter(l => l.library_type === 'transmission');

  return (
    <div className="space-y-8">
      {libraries.length === 0 ? (
        <Card>
          <div className="text-center py-16 text-zinc-400">
            <LibraryIcon size={64} className="mx-auto mb-4 opacity-50" />
            <p className="text-xl mb-2">No libraries configured</p>
            <p>Libraries organize documents by brand, product type, or transmission</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <LibraryColumn title="Brands" icon="" libraries={brands} type="brand" onLibraryClick={onLibraryClick} />
          <LibraryColumn title="Product Types" icon="" libraries={productTypes} type="product type" onLibraryClick={onLibraryClick} />
          <LibraryColumn title="Transmissions" icon="" libraries={transmissions} type="transmission" onLibraryClick={onLibraryClick} />
        </div>
      )}
    </div>
  );
};

// ============ Templates List ============

interface TemplatesListProps {
  templates: PromptTemplate[];
  onCreateTemplate: () => void;
  onEditTemplate: (template: PromptTemplate) => void;
  onDeleteTemplate: (id: string) => void;
}

export const TemplatesList: React.FC<TemplatesListProps> = ({
  templates,
  onCreateTemplate,
  onEditTemplate,
  onDeleteTemplate
}) => {
  const getTypeBadge = (type: string) => {
    const variants: Record<string, string> = {
      brand: 'bg-blue-500/20 text-blue-300',
      product_type: 'bg-green-500/20 text-green-300',
      transmission: 'bg-purple-500/20 text-purple-300',
      general: 'bg-zinc-500/20 text-zinc-300',
    };
    return variants[type] || variants.general;
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-semibold text-white">Prompt Templates</h2>
          <p className="text-sm text-zinc-400">Configure instructions for SEO content generation</p>
        </div>
        <Button 
          variant="primary" 
          onClick={onCreateTemplate}
          icon={<PlusIcon size={18} />}
        >
          New Template
        </Button>
      </div>

      {templates.length === 0 ? (
        <Card>
          <div className="text-center py-16 text-zinc-400">
            <TemplateIcon size={64} className="mx-auto mb-4 opacity-50" />
            <p className="text-xl mb-2">No templates configured</p>
            <p className="mb-6">Create your first template for SEO content generation</p>
            <Button variant="primary" onClick={onCreateTemplate}>
              + Create Template
            </Button>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {templates.map((template) => (
            <div
              key={template.id}
              className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-5 hover:border-[#F7B500]/50 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-lg text-white">{template.name}</h3>
                    <span className={`text-xs px-2 py-1 font-medium ${getTypeBadge(template.template_type)}`}>
                      {template.template_type}
                    </span>
                    {template.is_active ? (
                      <Badge variant="success">Active</Badge>
                    ) : (
                      <Badge variant="danger">Inactive</Badge>
                    )}
                  </div>

                  {template.example_output && (
                    <p className="text-zinc-400 text-sm mb-3">{template.example_output}</p>
                  )}

                  <div className="bg-[#0a0a0a] p-3 mb-3 rounded-sm">
                    <pre className="text-zinc-400 text-xs font-mono whitespace-pre-wrap line-clamp-4">
                      {template.system_instructions}
                    </pre>
                  </div>

                  <div className="text-xs text-zinc-500">
                    Priority: {template.priority}
                  </div>
                </div>

                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => onEditTemplate(template)}
                    className="p-2 text-zinc-400 hover:text-[#F7B500] transition-colors"
                    title="Edit template"
                  >
                    <EditIcon size={18} />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm('Are you sure you want to delete this template?')) {
                        onDeleteTemplate(template.id);
                      }
                    }}
                    className="p-2 text-zinc-400 hover:text-red-400 transition-colors"
                    title="Delete template"
                  >
                    <TrashIcon size={18} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ============ Library Tabs Configuration ============

export const libraryTabs = [
  { id: 'documents', label: 'Documents', icon: <DocumentIcon size={18} /> },
  { id: 'libraries', label: 'Libraries', icon: <LibraryIcon size={18} /> },
  { id: 'templates', label: 'Templates', icon: <TemplateIcon size={18} /> },
];

// ============ Export ============

export default {
  LibraryStats,
  DocumentList,
  LibraryGrid,
  TemplatesList,
  libraryTabs,
};
