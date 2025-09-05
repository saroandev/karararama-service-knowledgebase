export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
}

export interface PaginatedResponse<T> extends ApiResponse<T> {
  meta: PaginationMeta;
}

export type ConnectionStatus = 'connected' | 'disconnected' | 'reconnecting';

export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

export interface BaseEntity {
  id: string;
  created_at: Date;
  updated_at: Date;
}