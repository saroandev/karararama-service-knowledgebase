import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { UIState, ToastOptions, ModalOptions } from '../types/ui';
import { generateId } from '../utils';

interface UIActions {
  // Theme
  toggleTheme: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
  
  // Sidebar
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  
  // Modals
  openModal: (options: Omit<ModalOptions, 'id'>) => string;
  closeModal: (id: string) => void;
  closeAllModals: () => void;
  
  // Toasts
  showToast: (options: Omit<ToastOptions, 'id'>) => string;
  hideToast: (id: string) => void;
  clearToasts: () => void;
  
  // Loading
  setLoading: (isLoading: boolean, message?: string) => void;
}

type UIStore = UIState & UIActions;

const initialState: UIState = {
  theme: 'light',
  sidebarCollapsed: false,
  activeModals: [],
  toasts: [],
  isLoading: false,
  loadingMessage: undefined,
};

export const useUIStore = create<UIStore>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        toggleTheme: () => {
          set((state) => ({
            theme: state.theme === 'light' ? 'dark' : 'light'
          }));
        },

        setTheme: (theme: 'light' | 'dark') => {
          set({ theme });
        },

        toggleSidebar: () => {
          set((state) => ({
            sidebarCollapsed: !state.sidebarCollapsed
          }));
        },

        setSidebarCollapsed: (sidebarCollapsed: boolean) => {
          set({ sidebarCollapsed });
        },

        openModal: (options: Omit<ModalOptions, 'id'>) => {
          const id = generateId();
          const modal: ModalOptions = { ...options, id };
          
          set((state) => ({
            activeModals: [...state.activeModals, modal]
          }));
          
          return id;
        },

        closeModal: (id: string) => {
          set((state) => ({
            activeModals: state.activeModals.filter(modal => modal.id !== id)
          }));
        },

        closeAllModals: () => {
          set({ activeModals: [] });
        },

        showToast: (options: Omit<ToastOptions, 'id'>) => {
          const id = generateId();
          const toast: ToastOptions = { 
            ...options, 
            id,
            duration: options.duration ?? 5000
          };
          
          set((state) => ({
            toasts: [...state.toasts, toast]
          }));

          // Auto-hide toast after duration
          if (toast.duration && toast.duration > 0) {
            setTimeout(() => {
              get().hideToast(id);
            }, toast.duration);
          }
          
          return id;
        },

        hideToast: (id: string) => {
          set((state) => ({
            toasts: state.toasts.filter(toast => toast.id !== id)
          }));
        },

        clearToasts: () => {
          set({ toasts: [] });
        },

        setLoading: (isLoading: boolean, loadingMessage?: string) => {
          set({ isLoading, loadingMessage });
        },
      }),
      {
        name: 'ui-store',
        partialize: (state) => ({
          theme: state.theme,
          sidebarCollapsed: state.sidebarCollapsed,
        }),
      }
    ),
    { name: 'UIStore' }
  )
);