import { useState, useRef } from 'react';
import { useDocumentStore } from '../stores';
import { documentApi } from '../services/api';
import Button from './UI/Button';
import { validateFile } from '../utils/validators';
import { formatFileSize } from '../utils/formatters';

interface FileUploadProps {
  onFileUploaded: (fileName: string) => void;
}

const FileUpload = ({ onFileUploaded }: FileUploadProps) => {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { addToUploadQueue, updateUploadProgress, updateUploadStatus } = useDocumentStore();

  const handleFileUpload = async (file: File) => {
    const validation = validateFile(file);
    if (!validation.valid) {
      alert(validation.error);
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    addToUploadQueue(file);

    try {
      const response = await documentApi.uploadDocument(
        file,
        {},
        (progress) => {
          setUploadProgress(progress);
          updateUploadProgress(file.name, progress);
        }
      );

      if (response.success && response.data) {
        setUploadedFiles(prev => [...prev, file.name]);
        onFileUploaded(file.name);
        updateUploadStatus(file.name, 'completed');
      } else {
        throw new Error(response.error || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Upload failed. Please try again.';
      alert(errorMessage);
      updateUploadStatus(file.name, 'error', errorMessage);
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

    // Handle multiple files
    pdfFiles.forEach(file => handleFileUpload(file));
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      handleFileUpload(files[0]);
    }
  };

  return (
    <div className="space-y-4">
      <div className="text-sm font-medium text-gray-700 mb-2">
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
            <div className="text-sm text-gray-600">Uploading...</div>
            <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
          </div>
        ) : (
          <div className="text-center">
            <div className="text-3xl mb-2">📄</div>
            <div className="text-sm font-medium text-gray-700">
              Drop PDF files here or click to browse
            </div>
            <div className="text-xs text-gray-500 mt-1">
              PDF files only • Max {formatFileSize(10 * 1024 * 1024)}
            </div>
          </div>
        )}
      </div>

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-medium text-gray-700">
            Uploaded Documents ({uploadedFiles.length})
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {uploadedFiles.map((fileName, index) => (
              <div
                key={index}
                className="flex items-center space-x-2 p-2 bg-green-50 border border-green-200 rounded-lg"
              >
                <div className="text-green-600">✓</div>
                <div className="text-sm text-gray-800 truncate flex-1">
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

export default FileUpload;