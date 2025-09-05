import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { DocumentState, Document, UploadItem, DocumentFilters } from '../types/document';
import { generateId } from '../utils';

interface DocumentActions {
  fetchDocuments: () => Promise<void>;
  uploadDocument: (file: File, metadata?: any) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  searchDocuments: (query: string) => Document[];
  setDocumentFilter: (filters: Partial<DocumentFilters>) => void;
  selectDocument: (document: Document | null) => void;
  setSortBy: (sortBy: 'date' | 'name' | 'size', order?: 'asc' | 'desc') => void;
  
  // Upload queue management
  addToUploadQueue: (file: File) => void;
  removeFromUploadQueue: (id: string) => void;
  updateUploadProgress: (id: string, progress: number) => void;
  updateUploadStatus: (id: string, status: UploadItem['status'], error?: string) => void;
  clearUploadQueue: () => void;
  
  // Internal state management
  setLoading: (isLoading: boolean) => void;
  setError: (error?: string) => void;
  updateDocument: (id: string, updates: Partial<Document>) => void;
}

type DocumentStore = DocumentState & DocumentActions;

const initialState: DocumentState = {
  documents: [],
  uploadQueue: [],
  selectedDocument: null,
  searchQuery: '',
  sortBy: 'date',
  sortOrder: 'desc',
  filters: {},
  isLoading: false,
  error: undefined,
};

export const useDocumentStore = create<DocumentStore>()(
  devtools(
    (set, get) => ({
      ...initialState,

      fetchDocuments: async () => {
        set({ isLoading: true, error: undefined });
        try {
          // TODO: Implement API call
          // const documents = await documentApi.getDocuments();
          // set({ documents, isLoading: false });
          set({ isLoading: false });
        } catch (error) {
          set({ 
            isLoading: false, 
            error: error instanceof Error ? error.message : 'Failed to fetch documents'
          });
        }
      },

      uploadDocument: async (file: File, metadata?: any) => {
        const uploadId = generateId();
        const uploadItem: UploadItem = {
          id: uploadId,
          file,
          progress: 0,
          status: 'queued',
        };

        get().addToUploadQueue(uploadItem.file);

        try {
          // TODO: Implement API call
          // await documentApi.uploadDocument(file, metadata);
          get().updateUploadStatus(uploadId, 'completed');
        } catch (error) {
          get().updateUploadStatus(uploadId, 'error', 
            error instanceof Error ? error.message : 'Upload failed'
          );
        }
      },

      deleteDocument: async (id: string) => {
        try {
          // TODO: Implement API call
          // await documentApi.deleteDocument(id);
          set((state) => ({
            documents: state.documents.filter(doc => doc.id !== id),
            selectedDocument: state.selectedDocument?.id === id ? null : state.selectedDocument,
          }));
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to delete document'
          });
        }
      },

      searchDocuments: (query: string) => {
        const { documents } = get();
        if (!query.trim()) return documents;

        return documents.filter(doc => 
          doc.filename.toLowerCase().includes(query.toLowerCase()) ||
          doc.original_filename.toLowerCase().includes(query.toLowerCase()) ||
          doc.metadata?.title?.toLowerCase().includes(query.toLowerCase())
        );
      },

      setDocumentFilter: (filters: Partial<DocumentFilters>) => {
        set((state) => ({
          filters: { ...state.filters, ...filters }
        }));
      },

      selectDocument: (document: Document | null) => {
        set({ selectedDocument: document });
      },

      setSortBy: (sortBy: 'date' | 'name' | 'size', order: 'asc' | 'desc' = 'desc') => {
        set({ sortBy, sortOrder: order });
      },

      addToUploadQueue: (file: File) => {
        const uploadItem: UploadItem = {
          id: generateId(),
          file,
          progress: 0,
          status: 'queued',
        };

        set((state) => ({
          uploadQueue: [...state.uploadQueue, uploadItem]
        }));
      },

      removeFromUploadQueue: (id: string) => {
        set((state) => ({
          uploadQueue: state.uploadQueue.filter(item => item.id !== id)
        }));
      },

      updateUploadProgress: (id: string, progress: number) => {
        set((state) => ({
          uploadQueue: state.uploadQueue.map(item =>
            item.id === id ? { ...item, progress } : item
          )
        }));
      },

      updateUploadStatus: (id: string, status: UploadItem['status'], error?: string) => {
        set((state) => ({
          uploadQueue: state.uploadQueue.map(item =>
            item.id === id ? { ...item, status, error } : item
          )
        }));
      },

      clearUploadQueue: () => {
        set({ uploadQueue: [] });
      },

      setLoading: (isLoading: boolean) => {
        set({ isLoading });
      },

      setError: (error?: string) => {
        set({ error });
      },

      updateDocument: (id: string, updates: Partial<Document>) => {
        set((state) => ({
          documents: state.documents.map(doc =>
            doc.id === id ? { ...doc, ...updates, updated_at: new Date() } : doc
          )
        }));
      },
    }),
    { name: 'DocumentStore' }
  )
);