import { apiClient } from './baseApi';
import { IngestRequest, IngestResponse, HealthResponse } from '../../types/api';
import { Document, DocumentPreview } from '../../types/document';
import { ApiResponse } from '../../types';

export class DocumentApi {
  async uploadDocument(
    file: File, 
    metadata?: Record<string, any>,
    onProgress?: (progress: number) => void
  ): Promise<ApiResponse<IngestResponse>> {
    return apiClient.uploadFile<IngestResponse>('/ingest', file, metadata, onProgress);
  }

  async getDocuments(): Promise<ApiResponse<Document[]>> {
    return apiClient.get<Document[]>('/documents');
  }

  async getDocument(documentId: string): Promise<ApiResponse<Document>> {
    return apiClient.get<Document>(`/documents/${documentId}`);
  }

  async deleteDocument(documentId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/documents/${documentId}`);
  }

  async getDocumentPreview(
    documentId: string, 
    page: number = 1
  ): Promise<ApiResponse<DocumentPreview>> {
    return apiClient.get<DocumentPreview>(`/documents/${documentId}/preview`, { page });
  }

  async searchInDocument(
    documentId: string, 
    query: string
  ): Promise<ApiResponse<any>> {
    return apiClient.post(`/documents/${documentId}/search`, { query });
  }

  async batchUploadDocuments(
    files: File[],
    onProgress?: (fileIndex: number, progress: number) => void
  ): Promise<ApiResponse<IngestResponse[]>> {
    const results: IngestResponse[] = [];
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const result = await this.uploadDocument(file, undefined, (progress) => {
        onProgress?.(i, progress);
      });
      
      if (result.success && result.data) {
        results.push(result.data);
      } else {
        throw new Error(result.error || `Failed to upload ${file.name}`);
      }
    }
    
    return {
      success: true,
      data: results,
    };
  }

  async getHealth(): Promise<ApiResponse<HealthResponse>> {
    return apiClient.get<HealthResponse>('/health');
  }
}

export const documentApi = new DocumentApi();