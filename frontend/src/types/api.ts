import { ApiResponse } from './common';

export interface QueryRequest {
  question: string;
  top_k?: number;
  conversation_id?: string;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
  conversation_id?: string;
  processing_time: number;
}

export interface IngestRequest {
  file: File;
  metadata?: Record<string, any>;
}

export interface IngestResponse {
  document_id: string;
  filename: string;
  pages: number;
  chunks_created: number;
  processing_time: number;
}

export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  services: {
    milvus: boolean;
    minio: boolean;
    etcd: boolean;
  };
  timestamp: string;
}

export interface ConversationRequest {
  title?: string;
}

export interface ConversationResponse {
  conversation_id: string;
  title: string;
  created_at: string;
}

export interface Source {
  document_id: string;
  document_title: string;
  page_number: number;
  score: number;
  text_preview: string;
}

export type ApiEndpoint = 
  | '/query'
  | '/ingest'
  | '/health'
  | '/documents'
  | '/conversations';