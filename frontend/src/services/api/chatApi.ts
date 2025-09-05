import { apiClient } from './baseApi';
import { 
  QueryRequest, 
  QueryResponse, 
  ConversationRequest, 
  ConversationResponse 
} from '../../types/api';
import { ApiResponse } from '../../types';

export class ChatApi {
  async query(request: QueryRequest): Promise<ApiResponse<QueryResponse>> {
    return apiClient.post<QueryResponse>('/query', request);
  }

  async createConversation(request: ConversationRequest = {}): Promise<ApiResponse<ConversationResponse>> {
    return apiClient.post<ConversationResponse>('/conversations', request);
  }

  async getConversations(): Promise<ApiResponse<ConversationResponse[]>> {
    return apiClient.get<ConversationResponse[]>('/conversations');
  }

  async deleteConversation(conversationId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/conversations/${conversationId}`);
  }

  async getConversationMessages(conversationId: string): Promise<ApiResponse<any[]>> {
    return apiClient.get(`/conversations/${conversationId}/messages`);
  }

  async queryWithConversation(
    conversationId: string, 
    request: Omit<QueryRequest, 'conversation_id'>
  ): Promise<ApiResponse<QueryResponse>> {
    return apiClient.post<QueryResponse>(`/query/${conversationId}`, request);
  }
}

export const chatApi = new ChatApi();