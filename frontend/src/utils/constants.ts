export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';
export const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8080';

export const API_ENDPOINTS = {
  HEALTH: '/health',
  QUERY: '/query',
  INGEST: '/ingest', 
  DOCUMENTS: '/documents',
  CONVERSATIONS: '/conversations',
} as const;

export const WEBSOCKET_EVENTS = {
  CONNECT: 'connect',
  DISCONNECT: 'disconnect',
  MESSAGE_RESPONSE: 'message_response',
  TYPING_STATUS: 'typing_status',
  UPLOAD_PROGRESS: 'upload_progress',
  DOCUMENT_PROCESSED: 'document_processed',
  ERROR: 'error',
  CONNECTION_STATUS: 'connection_status',
} as const;

export const LOCAL_STORAGE_KEYS = {
  THEME: 'rag-theme',
  CONVERSATIONS: 'rag-conversations',
  USER_PREFERENCES: 'rag-user-preferences',
  LAST_CONVERSATION: 'rag-last-conversation',
} as const;

export const FILE_TYPES = {
  ACCEPTED: ['.pdf'],
  MIME_TYPES: ['application/pdf'],
  MAX_SIZE: 10 * 1024 * 1024, // 10MB
} as const;

export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,
} as const;

export const THEMES = {
  LIGHT: 'light',
  DARK: 'dark',
} as const;

export const MESSAGE_LIMITS = {
  MAX_LENGTH: 2000,
  MIN_LENGTH: 1,
} as const;