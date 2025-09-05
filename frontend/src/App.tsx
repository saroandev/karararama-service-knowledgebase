import { useState, useEffect } from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import SimpleChatInterface from './components/SimpleChatInterface';
import FileUpload from './components/FileUpload';
import MainLayout from './components/Layout/MainLayout';
import Button from './components/UI/Button';
import { useChatStore, useUIStore } from './stores';
import { clsx } from 'clsx';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

function App() {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const { 
    conversations, 
    activeConversationId, 
    createConversation, 
    setActiveConversation,
    deleteConversation 
  } = useChatStore();
  const { theme, sidebarCollapsed, toggleSidebar } = useUIStore();

  // Create initial conversation if none exists
  useEffect(() => {
    if (conversations.length === 0) {
      createConversation('Welcome Chat');
    }
  }, [conversations.length, createConversation]);

  const handleNewConversation = () => {
    const id = createConversation();
    setActiveConversation(id);
  };

  const sidebar = (
    <>
      <div className={clsx(
        'p-6 border-b',
        theme === 'dark' && 'border-gray-700'
      )}>
        {!sidebarCollapsed && (
          <>
            <div className="flex items-center justify-between mb-4">
              <h1 className={clsx(
                'text-xl font-bold',
                theme === 'dark' ? 'text-white' : 'text-gray-800'
              )}>RAG Chat</h1>
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleSidebar}
                className="p-1"
              >
                ←
              </Button>
            </div>
            <p className={clsx(
              'text-sm mt-1',
              theme === 'dark' ? 'text-gray-400' : 'text-gray-600'
            )}>Upload PDFs and ask questions</p>
          </>
        )}
        {sidebarCollapsed && (
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSidebar}
            className="p-1 w-full"
          >
            →
          </Button>
        )}
      </div>
      
      {!sidebarCollapsed && (
        <>
          <div className="p-4">
            <Button
              onClick={handleNewConversation}
              variant="primary"
              size="sm"
              className="w-full mb-4"
            >
              + New Conversation
            </Button>
            
            <div className="space-y-2 mb-6">
              <h3 className={clsx(
                'text-sm font-medium',
                theme === 'dark' ? 'text-white' : 'text-gray-700'
              )}>Conversations</h3>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={clsx(
                      'flex items-center p-2 rounded-lg cursor-pointer text-sm group',
                      activeConversationId === conv.id
                        ? (theme === 'dark' ? 'bg-gray-700 text-white' : 'bg-blue-50 text-blue-700')
                        : (theme === 'dark' ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-600 hover:bg-gray-100')
                    )}
                    onClick={() => setActiveConversation(conv.id)}
                  >
                    <span className="flex-1 truncate">{conv.title}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteConversation(conv.id);
                      }}
                      className="p-1 text-xs opacity-0 group-hover:opacity-100"
                    >
                      ×
                    </Button>
                  </div>
                ))}
              </div>
            </div>
            
            <FileUpload onFileUploaded={(fileName) => setSelectedFile(fileName)} />
          </div>
          
          {selectedFile && (
            <div className={clsx(
              'p-4 border-t',
              theme === 'dark' ? 'border-gray-700 bg-gray-700' : 'border-gray-200 bg-gray-50'
            )}>
              <div className={clsx(
                'text-xs font-medium mb-1',
                theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
              )}>Active Document:</div>
              <div className={clsx(
                'text-sm truncate',
                theme === 'dark' ? 'text-white' : 'text-gray-800'
              )}>{selectedFile}</div>
            </div>
          )}
        </>
      )}
    </>
  );

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <MainLayout sidebar={sidebar}>
          <SimpleChatInterface />
        </MainLayout>
      </Router>
    </QueryClientProvider>
  );
}

export default App;