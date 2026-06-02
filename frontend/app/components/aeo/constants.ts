/**
 * Shared constants for LLM source display
 * Used across AEO components for consistent styling
 */

// LLM Source display names
export const LLM_SOURCE_LABELS: Record<string, string> = {
    chatgpt: 'ChatGPT / OpenAI',
    gemini: 'Google Gemini',
    perplexity: 'Perplexity AI',
    claude: 'Claude / Anthropic',
    copilot: 'Microsoft Copilot',
    grok: 'Grok / X AI',
    other_ai: 'Other AI',
};

// LLM Source brand colors
export const LLM_SOURCE_COLORS: Record<string, string> = {
    chatgpt: '#10A37F',    // OpenAI green
    gemini: '#4285F4',     // Google blue
    perplexity: '#20808D', // Perplexity teal
    claude: '#CC785C',     // Claude coral
    copilot: '#0078D4',    // Microsoft blue
    grok: '#000000',       // X black
    other_ai: '#F7B500',   // Example Store gold
};

// Alert severity colors
export const SEVERITY_COLORS = {
    high: 'bg-red-500',
    medium: 'bg-yellow-500',
    low: 'bg-blue-500',
};

// Alert type icons
export const ALERT_TYPE_ICONS = {
    trend_down: '📉',
    trend_up: '📈',
    anomaly: '⚠️',
    opportunity: '💡',
    insight: 'ℹ️',
};

// Utility: Format currency in MXN
export const formatCurrency = (value: number) =>
    new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(value);

// Utility: Format number with locale
export const formatNumber = (value: number) =>
    new Intl.NumberFormat('es-MX').format(value);

// Utility: Format percent with sign
export const formatPercent = (value: number) =>
    `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
