import { ReactNode } from 'react';

export interface Theme {
  name: string;
  colors: {
    primary: string;
    secondary: string;
    background: string;
    surface: string;
    text: {
      primary: string;
      secondary: string;
    };
    border: string;
    accent: string;
  };
}

export interface ToastOptions {
  id?: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export interface ModalOptions {
  id: string;
  title: string;
  content: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  closeOnOverlay?: boolean;
  showCloseButton?: boolean;
  actions?: Array<{
    label: string;
    variant: 'primary' | 'secondary' | 'danger';
    onClick: () => void;
  }>;
}

export interface UIState {
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
  activeModals: ModalOptions[];
  toasts: ToastOptions[];
  isLoading: boolean;
  loadingMessage?: string;
}

export interface ButtonVariant {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
}

export interface InputVariant {
  variant?: 'default' | 'outline' | 'filled';
  size?: 'sm' | 'md' | 'lg';
  state?: 'default' | 'error' | 'success';
}