import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface Product {
  id: string;
  shopify_id: string;
  title: string;
  sku: string;
  handle: string;
  needs_seo: boolean;
  seo_status: string;
  description_length: number;
  image_count: number;
  total_sold?: number;
  total_revenue?: number;
}

interface ProductStore {
  products: Product[];
  total: number;
  selectedProduct: Product | null;
  generatedContent: any | null;
  loading: boolean;
  lastSynced: string | null;  // Track when we last synced
  setProducts: (products: Product[], total: number) => void;
  setSelectedProduct: (product: Product | null) => void;
  setGeneratedContent: (content: any) => void;
  setLoading: (loading: boolean) => void;
  setLastSynced: (date: string) => void;
  clearCache: () => void;
}

const useProductStore = create<ProductStore>()(
  persist(
    (set) => ({
      products: [],
      total: 0,
      selectedProduct: null,
      generatedContent: null,
      loading: false,
      lastSynced: null,
      setProducts: (products, total) => set({ products, total, lastSynced: new Date().toISOString() }),
      setSelectedProduct: (product) => set({ selectedProduct: product }),
      setGeneratedContent: (content) => set({ generatedContent: content }),
      setLoading: (loading) => set({ loading }),
      setLastSynced: (date) => set({ lastSynced: date }),
      clearCache: () => set({ products: [], total: 0, lastSynced: null }),
    }),
    {
      name: 'app-products',  // localStorage key
      partialize: (state) => ({
        products: state.products,
        total: state.total,
        lastSynced: state.lastSynced,
      }),
    }
  )
);

export default useProductStore;
