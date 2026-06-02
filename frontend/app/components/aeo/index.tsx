/**
 * AEO Components - Answer Engine Optimization Dashboard
 *
 * Barrel export file for all AEO components.
 * Uses Example Store Design System: #F7B500 brand color, rounded-sm (2px) - industrial aesthetic
 */

'use client';

import React from 'react';
import {
  ChipIcon, GlobeIcon, SparklesIcon, ChartIcon, CarIcon, GearIcon, DatabaseIcon
} from '../ui/Icons';

// Export all components from individual files
export { AEOFocusedOverview } from './AEOFocusedOverview';
export { AEOStatsGrid } from './AEOStatsGrid';
export { AEOChunksGrid } from './AEOChunksGrid';
export { AEOPreviewPanel } from './AEOPreviewPanel';
export { AEOBlogsList } from './AEOBlogsList';
export { AEOKnowledgeGraph } from './AEOKnowledgeGraph';
export { AEOMetricsDashboard } from './AEOMetricsDashboard';
export { AEOConfigPanel } from './AEOConfigPanel';
export { AEOVisibilityPanel } from './AEOVisibilityPanel';
export { AEOProductIntelligence } from './AEOProductIntelligence';
export { AEOVisibilityCorrelation } from './AEOVisibilityCorrelation';
export { EnhancedLLMSalesAttribution } from './EnhancedLLMSalesAttribution';
export { GSCPromptImporter } from './GSCPromptImporter';
export { AEOImpactTimeline } from './AEOImpactTimeline';

// Export shared constants
export { LLM_SOURCE_COLORS, LLM_SOURCE_LABELS, formatCurrency } from './constants';

// ============ AEO Tabs Configuration ============

export const aeoTabs = [
  // Focused overview — real/actionable signals only (AI traffic, earning
  // products, opportunities, schema gaps). This is the default landing.
  { id: 'overview', label: 'Overview', icon: <SparklesIcon size={18} /> },
  { id: 'chunks', label: 'Chunks', icon: <ChipIcon size={18} /> },
  { id: 'preview', label: 'Preview', icon: <GlobeIcon size={18} /> },
  { id: 'visibility', label: 'AI Visibility', icon: <SparklesIcon size={18} /> },
  { id: 'gsc-import', label: 'GSC Import', icon: <DatabaseIcon size={18} /> },
  { id: 'intelligence', label: 'Product Intelligence', icon: <ChartIcon size={18} /> },
  { id: 'correlation', label: 'Correlation ROI', icon: <ChartIcon size={18} /> },
  { id: 'blogs', label: 'Blogs', icon: <ChartIcon size={18} /> },
  { id: 'knowledge', label: 'Knowledge Graph', icon: <CarIcon size={18} /> },
  { id: 'metrics', label: 'Metrics', icon: <ChartIcon size={18} /> },
  { id: 'config', label: 'Config', icon: <GearIcon size={18} /> },
];


