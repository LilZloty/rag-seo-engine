/**
 * Example Store Design System - Shared UI Components
 *
 * Brand Design System:
 * - Primary: #F7B500 (gold/yellow)
 * - Dark background: #0a0a0a
 * - Card background: #1a1a1a
 * - Border: #3a3a3a
 * - Border radius: rounded-sm (2px) - industrial aesthetic per atomic design
 * - Text: white, gray-400
 *
 * Anti-Slop Principles:
 * - No rounded corners exceeding 4px
 * - No generic gradients or soft shadows
 * - High contrast industrial aesthetic
 */

import React from 'react';

// ============ Brand Colors ============
export const BRAND = {
  primary: '#F7B500',
  primaryHover: '#ffc933',
  primaryText: '#000000',
  darkBg: '#0a0a0a',
  cardBg: '#1a1a1a',
  border: '#3a3a3a',
  text: {
    primary: '#FFFFFF',
    secondary: '#D4D4D4',
    muted: '#9CA3AF',
  },
};

// ============ Button Component ============

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0a0a0a]';

  const variants = {
    primary: `bg-[#F7B500] text-black hover:bg-[#ffc933] focus:ring-[#F7B500] rounded-sm`,
    secondary: 'bg-[#1a1a1a] text-white border border-[#3a3a3a] hover:border-[#F7B500] rounded-sm',
    outline: 'border border-[#3a3a3a] text-zinc-300 hover:border-[#F7B500] hover:text-[#F7B500] rounded-sm',
    ghost: 'text-zinc-400 hover:text-[#F7B500] hover:bg-white/5 rounded-sm',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500 rounded-sm',
  };

  const sizes = {
    sm: 'px-4 py-2 text-sm',
    md: 'px-6 py-3 text-base',
    lg: 'px-8 py-4 text-lg',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${disabled || loading ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <svg className="animate-spin -ml-1 mr-2 size-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      ) : icon ? (
        <span className="mr-2">{icon}</span>
      ) : null}
      {children}
    </button>
  );
};

// ============ Card Component ============

interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  accent?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, className = '', title, subtitle, action, accent = false }) => {
  return (
    <div className={`bg-[#1a1a1a] rounded-sm border ${accent ? 'border-[#F7B500]' : 'border-[#3a3a3a]'} ${className}`}>
      {(title || action) && (
        <div className="px-6 py-4 border-b border-[#3a3a3a] flex items-center justify-between">
          <div>
            {title && <h3 className="text-lg font-semibold text-white">{title}</h3>}
            {subtitle && <p className="text-sm text-zinc-400 mt-1">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
};

// ============ Input Component ============

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({ label, error, icon, className = '', ...props }) => {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-zinc-300 mb-2">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-zinc-400">
            {icon}
          </div>
        )}
        <input
          className={`w-full bg-[#1a1a1a] border ${error ? 'border-red-500' : 'border-[#3a3a3a]'} rounded-sm px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:border-[#F7B500] focus:ring-1 focus:ring-[#F7B500]/20 transition-all ${icon ? 'pl-12' : ''} ${className}`}
          {...props}
        />
      </div>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
    </div>
  );
};

// ============ Select Component ============

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
}

export const Select: React.FC<SelectProps> = ({ label, options, className = '', ...props }) => {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-zinc-300 mb-2">
          {label}
        </label>
      )}
      <select
        className={`w-full bg-[#1a1a1a] border border-[#3a3a3a] rounded-sm px-4 py-3 text-white focus:outline-none focus:border-[#F7B500] focus:ring-1 focus:ring-[#F7B500]/20 transition-all appearance-none cursor-pointer ${className}`}
        {...props}
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
};

// ============ Badge Component ============

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'brand';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'default', className = '' }) => {
  const variants = {
    default: 'bg-[#3a3a3a] text-zinc-300',
    success: 'bg-green-500/20 text-green-400 border border-green-500/30',
    warning: 'bg-[#F7B500]/20 text-[#F7B500] border border-[#F7B500]/30',
    danger: 'bg-red-500/20 text-red-400 border border-red-500/30',
    info: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
    brand: 'bg-[#F7B500] text-black font-semibold',
  };

  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-sm text-sm font-medium ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

// ============ Modal Component ============

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children, size = 'md' }) => {
  if (!isOpen) return null;

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-2xl',
    lg: 'max-w-4xl',
    xl: 'max-w-6xl',
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity"
          role="presentation"
          onClick={onClose}
          onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
        />
        <div className={`relative w-full ${sizes[size]} bg-[#1a1a1a] rounded-sm shadow-2xl border border-[#3a3a3a] transform transition-all`}>
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#3a3a3a]">
            <h3 className="text-xl font-semibold text-white">{title}</h3>
            <button
              onClick={onClose}
              className="text-zinc-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-sm"
            >
              <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="px-6 py-4">{children}</div>
        </div>
      </div>
    </div>
  );
};

// ============ Table Component ============

interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (item: T) => void;
  emptyMessage?: string;
}

export function Table<T extends { id: string | number }>({ columns, data, onRowClick, emptyMessage = 'No hay datos disponibles' }: TableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="text-center py-16 text-zinc-400">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-hidden border border-[#3a3a3a]">
      <table className="w-full">
        <thead>
          <tr className="bg-[#0a0a0a]">
            {columns.map(col => (
              <th key={col.key} className={`px-6 py-4 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider ${col.className || ''}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[#3a3a3a]">
          {data.map(item => (
            <tr
              key={item.id}
              onClick={() => onRowClick?.(item)}
              className={onRowClick ? 'cursor-pointer hover:bg-[#3a3a3a]/30 transition-all' : 'transition-all'}
            >
              {columns.map(col => (
                <td key={col.key} className={`px-6 py-4 text-sm text-zinc-300 ${col.className || ''}`}>
                  {col.render ? col.render(item) : (item as any)[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ============ Pagination Component ============

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({ currentPage, totalPages, onPageChange, className = '' }) => {
  if (totalPages <= 1) return null;

  return (
    <div className={`flex items-center justify-center space-x-3 ${className}`}>
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-4 py-2 rounded-sm bg-[#1a1a1a] text-zinc-300 border border-[#3a3a3a] hover:border-[#F7B500] hover:text-[#F7B500] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        Anterior
      </button>
      <span className="text-sm text-zinc-400 px-4">
        {currentPage} / {totalPages}
      </span>
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-4 py-2 rounded-sm bg-[#1a1a1a] text-zinc-300 border border-[#3a3a3a] hover:border-[#F7B500] hover:text-[#F7B500] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        Siguiente
      </button>
    </div>
  );
};

// ============ Progress Bar Component ============

interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  showPercentage?: boolean;
  color?: 'brand' | 'green' | 'yellow' | 'red';
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ value, max = 100, label, showPercentage = true, color = 'brand' }) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  const colors = {
    brand: 'bg-[#F7B500]',
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  };

  return (
    <div>
      {(label || showPercentage) && (
        <div className="flex justify-between mb-2">
          {label && <span className="text-sm text-zinc-300">{label}</span>}
          {showPercentage && <span className="text-sm text-zinc-400">{Math.round(percentage)}%</span>}
        </div>
      )}
      <div className="w-full bg-[#3a3a3a] rounded-sm h-2">
        <div className={`${colors[color]} h-2 rounded-sm transition-all duration-500`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
};

// ============ Empty State Component ============

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, action }) => {
  return (
    <div className="text-center py-16">
      {icon && <div className="mx-auto size-16 text-zinc-500 mb-4">{icon}</div>}
      <h3 className="text-xl font-medium text-white mb-2">{title}</h3>
      {description && <p className="text-zinc-400 mb-6">{description}</p>}
      {action}
    </div>
  );
};

// ============ Tabs Component ============

interface Tab {
  id: string;
  label: string;
  icon?: React.ReactNode;
  count?: number;
}

interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onChange: (tabId: string) => void;
}

export const Tabs: React.FC<TabsProps> = ({ tabs, activeTab, onChange }) => {
  return (
    <div className="border-b border-[#3a3a3a]">
      <nav className="-mb-px flex space-x-8 px-2">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`p-4 border-b-2 font-medium text-base transition-all ${
              activeTab === tab.id
                ? 'border-[#F7B500] text-[#F7B500]'
                : 'border-transparent text-zinc-400 hover:text-zinc-300 hover:border-zinc-500'
            }`}
          >
            <div className="flex items-center gap-2">
              {tab.icon}
              {tab.label}
              {tab.count !== undefined && (
                <span className={`ml-2 py-1 px-3 rounded-sm text-sm ${
                  activeTab === tab.id ? 'bg-[#F7B500]/20 text-[#F7B500]' : 'bg-[#3a3a3a] text-zinc-400'
                }`}>
                  {tab.count}
                </span>
              )}
            </div>
          </button>
        ))}
      </nav>
    </div>
  );
}
