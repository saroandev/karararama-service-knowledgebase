import { ReactNode } from 'react';
import { useUIStore } from '../../stores';
import { clsx } from 'clsx';

interface MainLayoutProps {
  children: ReactNode;
  sidebar?: ReactNode;
  header?: ReactNode;
}

const MainLayout = ({ children, sidebar, header }: MainLayoutProps) => {
  const { sidebarCollapsed, theme } = useUIStore();

  return (
    <div className={clsx(
      'min-h-screen bg-gray-50 flex',
      theme === 'dark' && 'dark bg-gray-900'
    )}>
      {/* Sidebar */}
      {sidebar && (
        <div className={clsx(
          'bg-white shadow-lg flex flex-col transition-all duration-300',
          sidebarCollapsed ? 'w-16' : 'w-80',
          theme === 'dark' && 'bg-gray-800'
        )}>
          {sidebar}
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        {header && (
          <div className={clsx(
            'bg-white border-b px-6 py-4',
            theme === 'dark' && 'bg-gray-800 border-gray-700'
          )}>
            {header}
          </div>
        )}

        {/* Main Content */}
        <div className="flex-1">
          {children}
        </div>
      </div>
    </div>
  );
};

export default MainLayout;