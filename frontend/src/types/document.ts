import { BaseEntity } from './common';

export interface Document extends BaseEntity {
  filename: string;
  original_filename: string;
  mime_type: string;
  size: number;
  pages?: number;
  chunks_count?: number;
  status: 'uploading' | 'processing' | 'completed' | 'error';
  metadata?: {
    title?: string;
    author?: string;
    subject?: string;
    keywords?: string;
    creator?: string;
    producer?: string;
    creation_date?: string;
    modification_date?: string;
  };
  preview_url?: string;
  download_url?: string;
}

export interface UploadItem {
  id: string;
  file: File;
  progress: number;
  status: 'queued' | 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
  document_id?: string;
}

export interface DocumentFilters {
  search?: string;
  status?: Document['status'];
  date_from?: Date;
  date_to?: Date;
  size_min?: number;
  size_max?: number;
}

export interface DocumentState {
  documents: Document[];
  uploadQueue: UploadItem[];
  selectedDocument: Document | null;
  searchQuery: string;
  sortBy: 'date' | 'name' | 'size';
  sortOrder: 'asc' | 'desc';
  filters: DocumentFilters;
  isLoading: boolean;
  error?: string;
}

export interface DocumentPreview {
  document_id: string;
  page_number: number;
  page_count: number;
  content: string;
  image_url?: string;
}

export interface DocumentSearchResult {
  document_id: string;
  filename: string;
  matches: Array<{
    page_number: number;
    text: string;
    score: number;
  }>;
}