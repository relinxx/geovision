/**
 * DashboardLayout Component
 * =========================
 * Layout wrapper for all dashboard views.
 * Provides a flexible container for page-specific content.
 * 
 * @component
 * @example
 * ```tsx
 * <DashboardLayout metrics={metrics} simulationTime={time} zones={zones} selectedRegion={region}>
 *   <HomePageContent />
 * </DashboardLayout>
 * ```
 */

import { ReactNode } from 'react';
import './DashboardLayout.css';

/** Props for the DashboardLayout component */
interface DashboardLayoutProps {
  /** Metrics data (kept for API compatibility) */
  metrics: any;
  /** Current simulation time */
  simulationTime: number;
  /** Selected region name */
  selectedRegion: string;
  /** Zone data array */
  zones: any[];
  /** Child components to render */
  children: ReactNode;
}

/**
 * Dashboard layout wrapper for main views.
 * Provides consistent container structure for dashboard pages.
 */
export function DashboardLayout({
  children,
}: DashboardLayoutProps) {
  return (
    <div className="dashboard-layout">
      {children}
    </div>
  );
}
