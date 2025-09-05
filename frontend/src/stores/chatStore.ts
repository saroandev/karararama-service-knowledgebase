import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { ChatState, Message, Conversation, SendMessageParams } from '../types/chat';
import { generateId } from '../utils';

interface ChatActions {
  createConversation: (title?: string) => string;
  deleteConversation: (id: string) => void;
  setActiveConversation: (id: string) => void;
  sendMessage: (params: SendMessageParams) => void;
  addMessage: (message: Message, conversationId: string) => void;
  updateMessage: (messageId: string, updates: Partial<Message>) => void;
  deleteMessage: (messageId: string, conversationId: string) => void;
  clearMessages: (conversationId: string) => void;
  clearAllConversations: () => void;
  setTyping: (isTyping: boolean) => void;
  setConnectionStatus: (status: 'connected' | 'disconnected' | 'reconnecting') => void;
  setError: (error?: string) => void;
}

type ChatStore = ChatState & ChatActions;

const initialState: ChatState = {
  conversations: [],
  activeConversationId: null,
  messages: {},
  isTyping: false,
  connectionStatus: 'disconnected',
  lastError: undefined,
};

export const useChatStore = create<ChatStore>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        createConversation: (title?: string) => {
          const id = generateId();
          const conversation: Conversation = {
            id,
            title: title || 'New Conversation',
            created_at: new Date(),
            updated_at: new Date(),
            last_message_at: undefined,
            message_count: 0,
          };

          set((state) => ({
            conversations: [conversation, ...state.conversations],
            activeConversationId: id,
            messages: { ...state.messages, [id]: [] },
          }));

          return id;
        },

        deleteConversation: (id: string) => {
          set((state) => {
            const newConversations = state.conversations.filter(c => c.id !== id);
            const newMessages = { ...state.messages };
            delete newMessages[id];

            return {
              conversations: newConversations,
              messages: newMessages,
              activeConversationId: state.activeConversationId === id 
                ? (newConversations[0]?.id || null)
                : state.activeConversationId,
            };
          });
        },

        setActiveConversation: (id: string) => {
          set({ activeConversationId: id });
        },

        sendMessage: ({ content, conversationId, type = 'user' }: SendMessageParams) => {
          const targetId = conversationId || get().activeConversationId;
          if (!targetId) return;

          const message: Message = {
            id: generateId(),
            conversation_id: targetId,
            type,
            content,
            timestamp: new Date(),
            status: 'sending',
            created_at: new Date(),
            updated_at: new Date(),
          };

          get().addMessage(message, targetId);
        },

        addMessage: (message: Message, conversationId: string) => {
          set((state) => {
            const currentMessages = state.messages[conversationId] || [];
            const updatedConversations = state.conversations.map(conv => 
              conv.id === conversationId 
                ? { 
                    ...conv, 
                    last_message_at: new Date(), 
                    message_count: currentMessages.length + 1,
                    updated_at: new Date(),
                  }
                : conv
            );

            return {
              conversations: updatedConversations,
              messages: {
                ...state.messages,
                [conversationId]: [...currentMessages, message],
              },
            };
          });
        },

        updateMessage: (messageId: string, updates: Partial<Message>) => {
          set((state) => {
            const newMessages = { ...state.messages };
            
            for (const conversationId in newMessages) {
              const messageIndex = newMessages[conversationId].findIndex(m => m.id === messageId);
              if (messageIndex !== -1) {
                newMessages[conversationId] = [...newMessages[conversationId]];
                newMessages[conversationId][messageIndex] = {
                  ...newMessages[conversationId][messageIndex],
                  ...updates,
                  updated_at: new Date(),
                };
                break;
              }
            }
            
            return { messages: newMessages };
          });
        },

        deleteMessage: (messageId: string, conversationId: string) => {
          set((state) => ({
            messages: {
              ...state.messages,
              [conversationId]: state.messages[conversationId]?.filter(m => m.id !== messageId) || [],
            },
          }));
        },

        clearMessages: (conversationId: string) => {
          set((state) => ({
            messages: {
              ...state.messages,
              [conversationId]: [],
            },
          }));
        },

        clearAllConversations: () => {
          set(initialState);
        },

        setTyping: (isTyping: boolean) => {
          set({ isTyping });
        },

        setConnectionStatus: (connectionStatus: 'connected' | 'disconnected' | 'reconnecting') => {
          set({ connectionStatus });
        },

        setError: (lastError?: string) => {
          set({ lastError });
        },
      }),
      {
        name: 'chat-store',
        partialize: (state) => ({
          conversations: state.conversations,
          messages: state.messages,
          activeConversationId: state.activeConversationId,
        }),
      }
    ),
    { name: 'ChatStore' }
  )
);