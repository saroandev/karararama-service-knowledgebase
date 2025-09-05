import { FILE_TYPES, MESSAGE_LIMITS } from './constants';

export const validateFile = (file: File): { valid: boolean; error?: string } => {
  // Check file type
  if (!FILE_TYPES.MIME_TYPES.includes(file.type)) {
    return {
      valid: false,
      error: 'Only PDF files are allowed'
    };
  }
  
  // Check file size
  if (file.size > FILE_TYPES.MAX_SIZE) {
    return {
      valid: false,
      error: `File size must be less than ${Math.round(FILE_TYPES.MAX_SIZE / 1024 / 1024)}MB`
    };
  }
  
  return { valid: true };
};

export const validateMessage = (message: string): { valid: boolean; error?: string } => {
  const trimmed = message.trim();
  
  if (trimmed.length < MESSAGE_LIMITS.MIN_LENGTH) {
    return {
      valid: false,
      error: 'Message cannot be empty'
    };
  }
  
  if (trimmed.length > MESSAGE_LIMITS.MAX_LENGTH) {
    return {
      valid: false,
      error: `Message must be less than ${MESSAGE_LIMITS.MAX_LENGTH} characters`
    };
  }
  
  return { valid: true };
};

export const validateEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

export const validateUrl = (url: string): boolean => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

export const sanitizeFilename = (filename: string): string => {
  return filename.replace(/[^a-zA-Z0-9.-]/g, '_');
};

export const isValidUUID = (uuid: string): boolean => {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(uuid);
};