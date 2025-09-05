import { useState, useRef } from 'react';

interface FileUploadProps {
  onFileUploaded: (fileName: string) => void;
}

const SimpleFileUpload = ({ onFileUploaded }: FileUploadProps) => {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (file: File) => {
    // Basic file validation
    if (file.type !== 'application/pdf') {
      alert('Please upload PDF files only');
      return;
    }

    if (file.size > 10 * 1024 * 1024) { // 10MB
      alert('File size must be less than 10MB');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8080/ingest', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const result = await response.json();
      
      if (result.success) {
        setUploadedFiles(prev => [...prev, file.name]);
        onFileUploaded(file.name);
      } else {
        alert('Upload failed: ' + (result.message || 'Unknown error'));
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    const pdfFiles = files.filter(file => file.type === 'application/pdf');
    
    if (pdfFiles.length === 0) {
      alert('Please upload PDF files only');
      return;
    }

    if (pdfFiles.length > 0) {
      handleFileUpload(pdfFiles[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      handleFileUpload(files[0]);
    }
  };

  return (
    <div className="space-y-4">
      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        Upload Documents
      </div>
      
      {/* Upload Zone */}
      <div
        className="upload-zone"
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
        />
        
        {isUploading ? (
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent mx-auto mb-2"></div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Uploading...</div>
            <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2 mt-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
          </div>
        ) : (
          <div className="text-center">
            <div className="text-3xl mb-2">📄</div>
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Drop PDF files here or click to browse
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              PDF files only • Max 10MB
            </div>
          </div>
        )}
      </div>

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Uploaded Documents ({uploadedFiles.length})
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {uploadedFiles.map((fileName, index) => (
              <div
                key={index}
                className="flex items-center space-x-2 p-2 bg-green-50 dark:bg-green-900 border border-green-200 dark:border-green-800 rounded-lg"
              >
                <div className="text-green-600 dark:text-green-400">✓</div>
                <div className="text-sm text-gray-800 dark:text-gray-200 truncate flex-1">
                  {fileName}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SimpleFileUpload;