/**
 * Dashboard Components - Example Store Design System
 *
 * Uses brand colors and design patterns:
 * - Primary: #F7B500 (gold/yellow)
 * - Dark background: #0a0a0a
 * - Card background: #1a1a1a
 * - Border: #3a3a3a
 * - Border radius: rounded-sm (2px) - industrial aesthetic per atomic design
 */

'use client';

import React from 'react';
import { Product } from '@/lib/api';
import { formatDate } from '@/app/lib/dates';
import { Button, Badge, Card, Input, Select } from '../';
import {
  SyncIcon,
  SearchIcon,
  ArrowRightIcon,
  EditIcon,
  CheckIcon,
  ClockIcon,
  ChartIcon,
  FireIcon,
  DatabaseIcon,
  UploadIcon,
  DownloadIcon,
  ExternalLinkIcon,
  PlusIcon,
  TrashIcon,
  LinkIcon,
} from '../ui/Icons';

// ============ Stats Card ============

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: { value: number; label: string };
  color?: 'brand' | 'green' | 'yellow' | 'red' | 'blue';
}

export const StatsCard: React.FC<StatsCardProps> = ({ title, value, subtitle, icon, trend, color = 'brand' }) => {
  const colors = {
    brand: 'border-l-[#F7B500]',
    green: 'border-l-green-500',
    yellow: 'border-l-yellow-500',
    red: 'border-l-red-500',
    blue: 'border-l-blue-500',
  };

  const valueColors = {
    brand: 'text-[#F7B500]',
    green: 'text-green-400',
    yellow: 'text-yellow-400',
    red: 'text-red-400',
    blue: 'text-blue-400',
  };

  const iconBgColors = {
    brand: 'bg-[#F7B500]/10 text-[#F7B500]',
    green: 'bg-green-500/10 text-green-400',
    yellow: 'bg-yellow-500/10 text-yellow-400',
    red: 'bg-red-500/10 text-red-400',
    blue: 'bg-blue-500/10 text-blue-400',
  };

  return (
    <Card className={`${colors[color]} border-l-4 hover:border-[#F7B500]/50 transition-all`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-zinc-400 uppercase tracking-wider">{title}</p>
          <p className={`text-3xl font-bold mt-2 font-mono ${valueColors[color]}`}>{value}</p>
          {subtitle && <p className="text-sm text-zinc-500 mt-1">{subtitle}</p>}
          {trend && (
            <p className={`text-sm mt-2 ${trend.value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {trend.value >= 0 ? '↑' : '↓'} {Math.abs(trend.value)}% {trend.label}
            </p>
          )}
        </div>
        {icon && (
          <div className={`size-12 rounded-sm flex items-center justify-center ${iconBgColors[color]}`}>
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
};

// ============ Sync Panel ============

interface SyncPanelProps {
  syncing: boolean;
  syncStats: {
    message: string;
    new_products: number;
    updated_products: number;
    skipped_products: number;
    total_in_database: number;
    needs_seo: number;
  } | null;
  onSync: () => void;
}

export const SyncPanel: React.FC<SyncPanelProps> = ({ syncing, syncStats, onSync }) => {
  return (
    <Card 
      title={
        <div className="flex items-center gap-3">
          <DatabaseIcon size={24} className="text-[#F7B500]" />
          <span>Sincronización Shopify</span>
        </div>
      } 
      subtitle="Gestiona la sincronización de productos desde Shopify" 
      accent
    >
      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="relative p-5 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a] overflow-hidden group hover:border-zinc-600 transition-colors">
          <div className="relative z-10">
            <p className="text-2xl font-bold text-white font-mono">{syncStats?.total_in_database || 0}</p>
            <p className="text-xs text-zinc-500 uppercase tracking-wider mt-1">En Base de Datos</p>
          </div>
          <DatabaseIcon size={32} className="absolute right-3 top-3 text-zinc-700 opacity-30" />
        </div>
        
        <div className="relative p-5 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a] overflow-hidden group hover:border-[#F7B500]/50 transition-colors">
          <div className="relative z-10">
            <p className="text-2xl font-bold text-[#F7B500] font-mono">{syncStats?.needs_seo || 0}</p>
            <p className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Necesitan SEO</p>
          </div>
          <EditIcon size={32} className="absolute right-3 top-3 text-[#F7B500] opacity-20" />
        </div>
        
        <div className="relative p-5 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a] overflow-hidden group hover:border-green-500/50 transition-colors">
          <div className="relative z-10">
            <p className="text-2xl font-bold text-green-400 font-mono">{syncStats?.new_products || 0}</p>
            <p className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Nuevos</p>
          </div>
          <PlusIcon size={32} className="absolute right-3 top-3 text-green-500 opacity-20" />
        </div>
        
        <div className="relative p-5 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a] overflow-hidden group hover:border-blue-500/50 transition-colors">
          <div className="relative z-10">
            <p className="text-2xl font-bold text-blue-400 font-mono">{syncStats?.updated_products || 0}</p>
            <p className="text-xs text-zinc-500 uppercase tracking-wider mt-1">Actualizados</p>
          </div>
          <SyncIcon size={32} className="absolute right-3 top-3 text-blue-500 opacity-20" />
        </div>
      </div>

      {/* Action Button - Single Primary Action */}
      <div className="flex flex-col sm:flex-row gap-3 p-4 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a]">
        <div className="flex-1">
          <p className="text-sm font-medium text-white mb-1">Sincronización</p>
          <p className="text-xs text-zinc-500">Verifica nuevos productos y actualiza la base de datos</p>
        </div>
        <Button 
          onClick={onSync} 
          loading={syncing} 
          size="sm"
          icon={<SyncIcon size={16} />}
          className="whitespace-nowrap"
        >
          Sincronizar
        </Button>
      </div>

      {syncStats && (
        <div className="mt-4 flex items-center gap-2 text-sm text-zinc-400 bg-[#0a0a0a] p-3 rounded-sm border border-[#2a2a2a]">
          <CheckIcon size={16} className="text-green-400" />
          {syncStats.message}
        </div>
      )}
    </Card>
  );
};

// ============ Filter Bar ============

interface FilterBarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusChange: (value: string) => void;
  sortBy: string;
  onSortChange: (value: string) => void;
  needsSeoOnly: boolean;
  onNeedsSeoToggle: () => void;
  totalProducts: number;
  filteredCount: number;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusChange,
  sortBy,
  onSortChange,
  needsSeoOnly,
  onNeedsSeoToggle,
  totalProducts,
  filteredCount
}) => {
  return (
    <div className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] p-5 mb-6">
      {/* Top Row - Search and Primary Filters */}
      <div className="flex flex-col lg:flex-row gap-4">
        {/* Search - Takes more space */}
        <div className="flex-1 min-w-[280px]">
          <label htmlFor="dashboard-search" className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">Búsqueda</label>
          <Input
            id="dashboard-search"
            placeholder="Buscar por título o SKU..."
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onSearchChange(e.target.value)}
            icon={<SearchIcon size={18} />}
          />
        </div>

        {/* Status Filter */}
        <div className="w-full lg:w-44">
          <label htmlFor="dashboard-status" className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">Estado</label>
          <Select
            id="dashboard-status"
            value={statusFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onStatusChange(e.target.value)}
            options={[
              { value: 'all', label: 'Todos' },
              { value: 'needs_seo', label: 'Necesita SEO' },
              { value: 'published', label: 'Publicados' },
              { value: 'draft', label: 'Borradores' }
            ]}
          />
        </div>

        {/* Sort */}
        <div className="w-full lg:w-44">
          <label htmlFor="dashboard-sort" className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">Ordenar por</label>
          <Select
            id="dashboard-sort"
            value={sortBy}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onSortChange(e.target.value)}
            options={[
              { value: 'title', label: 'Por Título' },
              { value: 'sales', label: 'Por Ventas' },
              { value: 'description', label: 'Por Descripción' },
              { value: 'newest', label: 'Más Recientes' }
            ]}
          />
        </div>

        {/* SEO Toggle - Aligned as a button-like control */}
        <div className="w-full lg:w-auto">
          <span className="block text-xs text-zinc-500 uppercase tracking-wider mb-1.5">Filtro rápido</span>
          <button
            onClick={onNeedsSeoToggle}
            className={`
              flex items-center gap-2.5 px-4 py-2.5 rounded-sm border transition-all w-full lg:w-auto justify-center lg:justify-start
              ${needsSeoOnly 
                ? 'bg-[#F7B500]/10 border-[#F7B500] text-[#F7B500]' 
                : 'bg-[#0a0a0a] border-[#3a3a3a] text-zinc-400 hover:border-zinc-500'
              }
            `}
          >
            <div className={`
              size-5 rounded-sm border flex items-center justify-center transition-colors
              ${needsSeoOnly 
                ? 'bg-[#F7B500] border-[#F7B500]' 
                : 'border-[#3a3a3a] bg-[#0a0a0a]'
              }
            `}>
              {needsSeoOnly && <CheckIcon size={14} className="text-black" />}
            </div>
            <span className="text-sm font-medium whitespace-nowrap">Solo necesita SEO</span>
          </button>
        </div>
      </div>

      {/* Results Count - Separated at bottom */}
      <div className="mt-4 pt-4 border-t border-[#2a2a2a] flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-zinc-500">Mostrando</span>
          <span className="text-white font-medium font-mono bg-[#0a0a0a] px-2 py-0.5 rounded-sm">{filteredCount}</span>
          <span className="text-zinc-500">de</span>
          <span className="text-white font-medium font-mono bg-[#0a0a0a] px-2 py-0.5 rounded-sm">{totalProducts}</span>
          <span className="text-zinc-500">productos</span>
        </div>
        
        {filteredCount !== totalProducts && (
          <button 
            onClick={() => {
              onSearchChange('');
              onStatusChange('all');
              if (needsSeoOnly) onNeedsSeoToggle();
            }}
            className="text-xs text-[#F7B500] hover:text-[#ffc933] transition-colors"
          >
            Limpiar filtros
          </button>
        )}
      </div>
    </div>
  );
};

// ============ Product Table ============

interface ProductTableProps {
  products: Product[];
  loading: boolean;
  onProductClick: (product: Product) => void;
  onGenerateContent: (product: Product) => void;
  currentPage: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
}

export const ProductTable: React.FC<ProductTableProps> = ({
  products,
  loading,
  onProductClick,
  onGenerateContent,
  currentPage,
  itemsPerPage,
  onPageChange
}) => {
  const paginatedProducts = products.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const totalPages = Math.ceil(products.length / itemsPerPage);

  if (loading) {
    return (
      <Card>
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full size-10 border-b-2 border-[#F7B500]" />
        </div>
      </Card>
    );
  }

  if (products.length === 0) {
    return (
      <Card>
        <div className="text-center py-16 text-zinc-400">
          No se encontraron productos
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="overflow-hidden border border-[#3a3a3a]">
        <table className="w-full">
          <thead>
            <tr className="bg-[#0a0a0a]">
              <th className="px-6 py-4 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Producto</th>
              <th className="px-6 py-4 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">SKU</th>
              <th className="px-6 py-4 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Estado</th>
              <th className="px-6 py-4 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Ventas</th>
              <th className="px-6 py-4 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Última Modificación</th>
              <th className="px-6 py-4 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#3a3a3a]">
            {paginatedProducts.map(product => (
              <tr
                key={product.id}
                className="hover:bg-[#3a3a3a]/20 cursor-pointer transition-all"
                onClick={() => {
                  console.log('Row clicked, product:', product.id);
                  onProductClick(product);
                }}
              >
                <td className="px-6 py-5">
                  <div className="flex items-center gap-4">
                    {product.image_url && (
                      <img
                        src={product.image_url}
                        alt={product.title}
                        className="size-12 rounded-sm object-cover"
                      />
                    )}
                    <div>
                      <p className="text-sm font-medium text-white max-w-[300px] truncate">
                        {product.title}
                      </p>
                      {product.transmission_code && (
                        <Badge variant="brand" className="mt-2">{product.transmission_code}</Badge>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-6 py-5 text-sm text-zinc-300 font-mono">
                  {product.sku || 'N/A'}
                </td>
                <td className="px-6 py-5">
                  <Badge variant={product.seo_content ? 'success' : 'warning'}>
                    {product.seo_content ? 'Con SEO' : 'Sin SEO'}
                  </Badge>
                </td>
                <td className="px-6 py-5 text-sm text-zinc-300">
                  {product.total_sold || 0}
                </td>
                <td className="px-6 py-5 text-sm text-zinc-400">
                  {product.updated_at
                    ? formatDate(product.updated_at)
                    : 'Nunca'
                  }
                </td>
                <td className="px-6 py-5 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onGenerateContent(product);
                    }}
                    className="px-4 py-2 bg-[#F7B500] text-black rounded-sm text-sm font-medium hover:bg-[#ffc933] transition-colors"
                  >
                    Generar SEO
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex justify-center">
          <TablePagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={onPageChange}
          />
        </div>
      )}
    </Card>
  );
};

// ============ Product Card (Grid View) ============

interface ProductCardProps {
  product: Product;
  onClick: () => void;
  onGenerate: () => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({ product, onClick, onGenerate }) => {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Open product ${product.title}`}
      className="bg-[#1a1a1a] rounded-sm border border-[#3a3a3a] overflow-hidden hover:border-[#F7B500] transition-all cursor-pointer group focus:outline-none focus-visible:ring-2 focus-visible:ring-[#F7B500]"
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.(); } }}
    >
      <div className="aspect-square bg-[#0a0a0a] relative overflow-hidden">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.title}
            className="size-full object-cover group-hover:scale-105 transition-transform duration-500"
          />
        ) : (
          <div className="flex items-center justify-center h-full text-zinc-500">
            <span className="text-5xl">📷</span>
          </div>
        )}
        <div className="absolute top-4 right-4">
          <Badge variant={product.seo_content ? 'success' : 'warning'}>
            {product.seo_content ? 'SEO' : 'Sin SEO'}
          </Badge>
        </div>
      </div>

      <div className="p-6">
        <h3 className="text-base font-medium text-white truncate" title={product.title}>
          {product.title}
        </h3>

        <div className="flex items-center gap-2 mt-3">
          <span className="text-xs text-zinc-400 font-mono bg-[#0a0a0a] px-3 py-1 rounded-sm">{product.sku || 'N/A'}</span>
          {product.transmission_code && (
            <Badge variant="brand" className="text-xs">{product.transmission_code}</Badge>
          )}
        </div>

        <div className="flex items-center justify-between mt-5">
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <ChartIcon size={18} />
            <span>{product.total_sold || 0} ventas</span>
          </div>

          <button
            onClick={(e) => {
              e.stopPropagation();
              onGenerate();
            }}
            className="px-5 py-2.5 bg-[#F7B500] text-black rounded-sm text-sm font-medium hover:bg-[#ffc933] transition-colors flex items-center gap-2"
          >
            Generar
            <ArrowRightIcon size={16} />
          </button>
        </div>
      </div>
    </div>
  );
};

// ============ Quick Actions Panel ============

interface QuickActionsProps {
  onGenerateAll: () => void;
  onBulkUpdate: () => void;
  onExport: () => void;
  pendingCount: number;
}

export const QuickActions: React.FC<QuickActionsProps> = ({
  onGenerateAll,
  onBulkUpdate,
  onExport,
  pendingCount
}) => {
  return (
    <Card title="Acciones Rápidas" subtitle="Operaciones en lote">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <button
          onClick={onGenerateAll}
          disabled={pendingCount === 0}
          className="p-6 bg-gradient-to-br from-[#F7B500] to-[#ffc933] rounded-sm text-black hover:from-[#ffc933] hover:to-[#F7B500] disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium text-left group"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-black/10 rounded-sm">
              <FireIcon size={28} />
            </div>
            <div>
              <p className="text-lg font-bold">Generar SEO</p>
              <p className="text-sm text-black/70">{pendingCount} pendientes</p>
            </div>
          </div>
        </button>

        <button
          onClick={onBulkUpdate}
          className="p-6 bg-[#1a1a1a] border-2 border-[#3a3a3a] rounded-sm text-white hover:border-[#F7B500] hover:text-[#F7B500] transition-all font-medium text-left group"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-[#0a0a0a] rounded-sm group-hover:bg-[#F7B500]/10 transition-colors">
              <SyncIcon size={28} />
            </div>
            <div>
              <p className="text-lg font-bold">Actualizar Datos</p>
              <p className="text-sm text-zinc-400 group-hover:text-[#F7B500] transition-colors">Sincronizar ventas</p>
            </div>
          </div>
        </button>

        <button
          onClick={onExport}
          className="p-6 bg-[#1a1a1a] border-2 border-[#3a3a3a] rounded-sm text-white hover:border-[#F7B500] hover:text-[#F7B500] transition-all font-medium text-left group"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-[#0a0a0a] rounded-sm group-hover:bg-[#F7B500]/10 transition-colors">
              <DownloadIcon size={28} />
            </div>
            <div>
              <p className="text-lg font-bold">Exportar</p>
              <p className="text-sm text-zinc-400 group-hover:text-[#F7B500] transition-colors">Descargar CSV</p>
            </div>
          </div>
        </button>
      </div>
    </Card>
  );
};

// ============ Activity Feed ============

interface Activity {
  id: string;
  type: 'generate' | 'sync' | 'update';
  message: string;
  timestamp: Date;
}

interface ActivityFeedProps {
  activities: Activity[];
}

export const ActivityFeed: React.FC<ActivityFeedProps> = ({ activities }) => {
  const icons = {
    generate: <EditIcon size={18} className="text-[#F7B500]" />,
    sync: <SyncIcon size={18} className="text-green-400" />,
    update: <ClockIcon size={18} className="text-yellow-400" />
  };

  return (
    <Card title="Actividad Reciente">
      <div className="space-y-4">
        {activities.length === 0 ? (
          <p className="text-center text-zinc-400 py-8">Sin actividad reciente</p>
          ) : (
            activities.map(activity => (
              <div key={activity.id} className="flex items-start gap-4 p-4 bg-[#0a0a0a] rounded-sm border border-[#3a3a3a]">
                <div className="p-3 bg-[#1a1a1a] rounded-sm">
                  {icons[activity.type]}
                </div>
              <div className="flex-1">
                <p className="text-sm text-white">{activity.message}</p>
                <p className="text-xs text-zinc-500 mt-2">
                  {activity.timestamp.toLocaleTimeString('es-MX')}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
};

// ============ Pagination Component ============

interface TablePaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export const TablePagination: React.FC<TablePaginationProps> = ({ currentPage, totalPages, onPageChange, className = '' }) => {
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
        {currentPage} de {totalPages}
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

export default {
  StatsCard,
  FilterBar,
  ProductTable,
  ProductCard,
  ActivityFeed,
  TablePagination,
};
