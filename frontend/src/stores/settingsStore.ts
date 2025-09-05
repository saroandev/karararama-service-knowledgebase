import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface Settings {
  // Chat settings
  autoScroll: boolean;
  showTimestamps: boolean;
  enableSounds: boolean;
  messagePageSize: number;
  
  // Upload settings
  autoUpload: boolean;
  maxFileSize: number;
  acceptedFileTypes: string[];
  
  // UI settings
  animationsEnabled: boolean;
  compactMode: boolean;
  fontSize: 'small' | 'medium' | 'large';
  
  // API settings
  apiTimeout: number;
  retryAttempts: number;
  
  // Developer settings
  debugMode: boolean;
  enableLogs: boolean;
}

interface SettingsActions {
  updateSettings: (settings: Partial<Settings>) => void;
  resetSettings: () => void;
  exportSettings: () => string;
  importSettings: (settingsJson: string) => boolean;
}

type SettingsStore = Settings & SettingsActions;

const defaultSettings: Settings = {
  // Chat settings
  autoScroll: true,
  showTimestamps: true,
  enableSounds: false,
  messagePageSize: 50,
  
  // Upload settings
  autoUpload: false,
  maxFileSize: 10 * 1024 * 1024, // 10MB
  acceptedFileTypes: ['application/pdf'],
  
  // UI settings
  animationsEnabled: true,
  compactMode: false,
  fontSize: 'medium',
  
  // API settings
  apiTimeout: 30000, // 30 seconds
  retryAttempts: 3,
  
  // Developer settings
  debugMode: false,
  enableLogs: false,
};

export const useSettingsStore = create<SettingsStore>()(
  devtools(
    persist(
      (set, get) => ({
        ...defaultSettings,

        updateSettings: (newSettings: Partial<Settings>) => {
          set((state) => ({ ...state, ...newSettings }));
        },

        resetSettings: () => {
          set(defaultSettings);
        },

        exportSettings: () => {
          const settings = get();
          const exportData = {
            settings: Object.fromEntries(
              Object.entries(settings).filter(([key]) => 
                !['updateSettings', 'resetSettings', 'exportSettings', 'importSettings'].includes(key)
              )
            ),
            version: '1.0',
            timestamp: new Date().toISOString(),
          };
          return JSON.stringify(exportData, null, 2);
        },

        importSettings: (settingsJson: string) => {
          try {
            const importData = JSON.parse(settingsJson);
            
            if (!importData.settings || !importData.version) {
              return false;
            }
            
            // Validate settings structure
            const validKeys = Object.keys(defaultSettings);
            const importedSettings = Object.fromEntries(
              Object.entries(importData.settings).filter(([key]) => 
                validKeys.includes(key)
              )
            );
            
            set((state) => ({ ...state, ...importedSettings }));
            return true;
          } catch {
            return false;
          }
        },
      }),
      {
        name: 'settings-store',
        version: 1,
      }
    ),
    { name: 'SettingsStore' }
  )
);