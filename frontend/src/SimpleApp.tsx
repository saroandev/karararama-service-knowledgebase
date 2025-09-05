import { useState } from 'react';
import SimpleChatInterface from './components/SimpleChatInterface';
import SimpleFileUpload from './components/SimpleFileUpload';

function SimpleApp() {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex">
      {/* Sidebar */}
      <div className="w-80 bg-white dark:bg-gray-800 shadow-lg flex flex-col">
        <div className="p-6 border-b dark:border-gray-700">
          <h1 className="text-xl font-bold text-gray-800 dark:text-white">RAG Chat</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Upload PDFs and ask questions</p>
        </div>
        
        <div className="flex-1 p-4">
          <SimpleFileUpload onFileUploaded={(fileName) => setSelectedFile(fileName)} />
        </div>
        
        {selectedFile && (
          <div className="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Active Document:</div>
            <div className="text-sm text-gray-800 dark:text-white truncate">{selectedFile}</div>
          </div>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1">
        <SimpleChatInterface />
      </div>
    </div>
  );
}

export default SimpleApp;