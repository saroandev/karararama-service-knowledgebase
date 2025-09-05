import { format, formatDistanceToNow, isToday, isYesterday, isThisWeek } from 'date-fns';

export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export const formatDate = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  
  if (isToday(d)) {
    return format(d, 'HH:mm');
  }
  
  if (isYesterday(d)) {
    return 'Yesterday';
  }
  
  if (isThisWeek(d)) {
    return format(d, 'EEEE');
  }
  
  return format(d, 'MMM d, yyyy');
};

export const formatRelativeTime = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return formatDistanceToNow(d, { addSuffix: true });
};

export const formatProcessingTime = (timeMs: number): string => {
  if (timeMs < 1000) {
    return `${Math.round(timeMs)}ms`;
  }
  
  return `${(timeMs / 1000).toFixed(1)}s`;
};

export const formatScore = (score: number): string => {
  return `${Math.round(score * 100)}%`;
};

export const truncateText = (text: string, maxLength: number = 100): string => {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
};

export const highlightText = (text: string, searchTerm: string): string => {
  if (!searchTerm) return text;
  
  const regex = new RegExp(`(${searchTerm})`, 'gi');
  return text.replace(regex, '<mark>$1</mark>');
};

export const formatConversationTitle = (firstMessage: string): string => {
  const title = truncateText(firstMessage, 50);
  return title || 'New Conversation';
};