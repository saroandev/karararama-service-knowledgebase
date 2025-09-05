import { BaseEntity } from './common';
import { Source } from './api';

export interface Message extends BaseEntity {
  conversation_id: string;
  type: 'user' | 'bot' | 'system';
  content: string;
  sources?: Source[];
  metadata?: {
    processing_time?: number;
    model_used?: string;
    error?: string;
  };
  status: 'sending' | 'sent' | 'delivered' | 'error';
}

export interface Conversation extends BaseEntity {
  title: string;
  last_message_at?: Date;
  message_count: number;
  metadata?: {
    model_used?: string;
    total_tokens?: number;
  };
}

export interface TypingStatus {
  conversation_id: string;
  is_typing: boolean;
  user_id?: string;
}

export interface MessageResponse {
  message: Message;
  conversation_id: string;
}

export interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Record<string, Message[]>;
  isTyping: boolean;
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting';
  lastError?: string;
}

export interface SendMessageParams {
  content: string;
  conversationId?: string;
  type?: 'user' | 'system';
}