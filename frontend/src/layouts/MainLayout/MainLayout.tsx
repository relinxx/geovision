/**
 * MainLayout Component
 * ====================
 * Root application layout that wraps all views.
 * Provides the main container with sidebar navigation.
 * 
 * @component
 * @example
 * ```tsx
 * <MainLayout activeView="workbench" onViewChange={handleViewChange}>
 *   <HomePage {...props} />
 * </MainLayout>
 * ```
 */

import { ReactNode } from 'react';
import { Sidebar } from '../../components/navigation/Sidebar/Sidebar';
import { ViewType } from '../../types';
import './MainLayout.css';

/** Props for the MainLayout component */
interface MainLayoutProps {
  /** Child components to render in the main content area */
  children: ReactNode;
  /** Currently active view identifier */
  activeView: ViewType;
  /** Callback when user selects a different view */
  onViewChange: (view: ViewType) => void;
}

/**
 * Main application layout wrapper.
 * Renders the sidebar navigation and main content area.
 */
export function MainLayout({
  children,
  activeView,
  onViewChange,
}: MainLayoutProps) {
  return (
    <div className="main-layout">
      <Sidebar activeView={activeView} onViewChange={onViewChange} />
      {children}
    </div>
  );
}
