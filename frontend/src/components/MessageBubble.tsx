interface Source {
  document_id: string;
  document_title: string;
  page_number: number;
  score: number;
  text_preview: string;
}

interface Message {
  id: string;
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
  sources?: Source[];
}

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.type === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className="max-w-3/4">
        <div
          className={`inline-block px-4 py-3 rounded-2xl max-w-full break-words ${
            isUser
              ? 'message-bubble-user'
              : 'message-bubble-bot border border-gray-200'
          }`}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>
          
          {/* Sources */}
          {message.sources && message.sources.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <div className="text-xs font-medium text-gray-600 mb-2">Sources:</div>
              <div className="space-y-2">
                {message.sources.map((source, index) => (
                  <div
                    key={index}
                    className="bg-white p-2 rounded-lg border border-gray-200 text-xs"
                  >
                    <div className="font-medium text-gray-800">
                      📄 {source.document_title}
                    </div>
                    <div className="text-gray-600 mt-1">
                      Page {source.page_number} • Score: {(source.score * 100).toFixed(1)}%
                    </div>
                    <div className="text-gray-700 mt-1 text-xs leading-relaxed">
                      {source.text_preview}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        
        <div className={`text-xs text-gray-500 mt-1 ${isUser ? 'text-right' : 'text-left'}`}>
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;