// Global state store using Zustand with localStorage persistence
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Product, Library, Document, PromptTemplate } from '@/lib/api';

interface ProductStore {
    // Products
    products: Product[];
    total: number;
    selectedProduct: Product | null;
    loading: boolean;
    lastSynced: string | null;  // Track when products were last loaded

    // Libraries
    libraries: Library[];
    selectedLibraries: number[];

    // Documents
    documents: Document[];

    // Prompts
    prompts: PromptTemplate[];
    selectedPrompts: number[];

    // Generated Content
    generatedContent: string;
    ragSources: Array<{ document_id: number; chunk_id: number; relevance: number }>;

    // Actions - Products
    setProducts: (products: Product[], total: number) => void;
    setSelectedProduct: (product: Product | null) => void;
    setLoading: (loading: boolean) => void;
    clearProductCache: () => void;

    // Actions - Libraries
    setLibraries: (libraries: Library[]) => void;
    toggleLibrary: (id: number) => void;
    setSelectedLibraries: (ids: number[]) => void;

    // Actions - Documents
    setDocuments: (documents: Document[]) => void;

    // Actions - Prompts
    setPrompts: (prompts: PromptTemplate[]) => void;
    togglePrompt: (id: number) => void;
    setSelectedPrompts: (ids: number[]) => void;

    // Actions - Content
    setGeneratedContent: (content: string, sources: Array<{ document_id: number; chunk_id: number; relevance: number }>) => void;
    clearContent: () => void;
}

const useProductStore = create<ProductStore>()(
    persist(
        (set) => ({
            // Initial state
            products: [],
            total: 0,
            selectedProduct: null,
            loading: false,
            lastSynced: null,
            libraries: [],
            selectedLibraries: [],
            documents: [],
            prompts: [],
            selectedPrompts: [],
            generatedContent: '',
            ragSources: [],

            // Product actions
            setProducts: (products, total) => set({
                products,
                total,
                lastSynced: new Date().toISOString()
            }),
            setSelectedProduct: (product) => set({ selectedProduct: product }),
            setLoading: (loading) => set({ loading }),
            clearProductCache: () => set({ products: [], total: 0, lastSynced: null }),

            // Library actions
            setLibraries: (libraries) => set({ libraries }),
            toggleLibrary: (id) =>
                set((state) => ({
                    selectedLibraries: state.selectedLibraries.includes(id)
                        ? state.selectedLibraries.filter((lib) => lib !== id)
                        : [...state.selectedLibraries, id],
                })),
            setSelectedLibraries: (ids) => set({ selectedLibraries: ids }),

            // Document actions
            setDocuments: (documents) => set({ documents }),

            // Prompt actions
            setPrompts: (prompts) => set({ prompts }),
            togglePrompt: (id) =>
                set((state) => ({
                    selectedPrompts: state.selectedPrompts.includes(id)
                        ? state.selectedPrompts.filter((p) => p !== id)
                        : [...state.selectedPrompts, id],
                })),
            setSelectedPrompts: (ids) => set({ selectedPrompts: ids }),

            // Content actions
            setGeneratedContent: (content, sources) => set({ generatedContent: content, ragSources: sources }),
            clearContent: () => set({ generatedContent: '', ragSources: [] }),
        }),
        {
            name: 'app-store',  // localStorage key
            partialize: (state) => ({
                // Only persist these fields to localStorage
                products: state.products,
                total: state.total,
                lastSynced: state.lastSynced,
            }),
        }
    )
);

export default useProductStore;
