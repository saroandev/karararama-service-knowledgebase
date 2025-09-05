import { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import { useChatStore } from '../stores';
import { chatApi } from '../services/api';
import Button from './UI/Button';
import { validateMessage } from '../utils/validators';


const ChatInterface = () => {
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { 
    messages, 
    activeConversationId, 
    sendMessage, 
    addMessage, 
    // updateMessage,
    setError 
  } = useChatStore();
  
  const currentMessages = activeConversationId ? messages[activeConversationId] || [] : [];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentMessages]);

  const handleSendMessage = async () => {
    const validation = validateMessage(inputValue);
    if (!validation.valid || isLoading) {
      if (!validation.valid) {
        setError(validation.error);
      }
      return;
    }

    const messageContent = inputValue;
    setInputValue('');
    setIsLoading(true);

    try {
      // Send user message to store
      sendMessage({ content: messageContent, conversationId: activeConversationId });
      
      // Call API
      const response = await chatApi.query({
        question: messageContent,
        top_k: 3,
        conversation_id: activeConversationId,
      });

      if (response.success && response.data) {
        const botMessage = {
          id: `bot_${Date.now()}`,
          conversation_id: activeConversationId!,
          type: 'bot' as const,
          content: response.data.answer,
          timestamp: new Date(),
          created_at: new Date(),
          updated_at: new Date(),
          sources: response.data.sources,
          status: 'sent' as const,
          metadata: {
            processing_time: response.data.processing_time,
          },
        };
        
        addMessage(botMessage, activeConversationId!);
      } else {
        throw new Error(response.error || 'Failed to get response');
      }
    } catch (error) {
      const errorMessage = {
        id: `error_${Date.now()}`,
        conversation_id: activeConversationId!,
        type: 'bot' as const,
        content: 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.',
        timestamp: new Date(),
        created_at: new Date(),
        updated_at: new Date(),
        status: 'error' as const,
      };
      addMessage(errorMessage, activeConversationId!);
      setError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-800">Chat Assistant</h2>
        <p className="text-sm text-gray-600">Ask questions about your uploaded documents</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {currentMessages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <div className="text-4xl mb-4">💬</div>
            <h3 className="text-lg font-medium mb-2">Start a conversation</h3>
            <p>Upload a PDF document and ask questions about it</p>
          </div>
        )}
        
        {currentMessages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        
        {isLoading && (
          <div className="flex items-center space-x-2 text-gray-500">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent"></div>
            <span>Thinking...</span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="bg-white border-t px-6 py-4">
        <div className="flex space-x-3">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question about your documents..."
            className="chat-input resize-none"
            rows={1}
            style={{ minHeight: '40px', maxHeight: '120px' }}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            loading={isLoading}
          >
            Send
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;