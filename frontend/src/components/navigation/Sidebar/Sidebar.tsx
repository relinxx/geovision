/**
 * Sidebar Navigation Component
 * ============================
 * Vertical navigation sidebar with icon buttons for main views.
 * Allows users to switch between dashboard workspaces.
 * 
 * @component
 * @example
 * ```tsx
 * <Sidebar activeView="workbench" onViewChange={handleViewChange} />
 * ```
 */

import {
  Home,
  TreePine,
  Map,
  Grid3x3,
  Settings,
  LogOut,
  MessageCircleQuestion,
} from 'lucide-react';
import { ViewType } from '../../../types';
import { useAuth } from '../../../context/AuthContext';
import './Sidebar.css';

/** Navigation item configuration */
interface NavItem {
  /** View identifier */
  id: ViewType;
  /** Lucide icon component */
  icon: typeof Home;
  /** Accessibility label */
  label: string;
}

/** Props for the Sidebar component */
interface SidebarProps {
  /** Currently active view */
  activeView: ViewType;
  /** Callback when a view is selected */
  onViewChange: (view: ViewType) => void;
}

/** Navigation items configuration with meaningful icons */
const NAV_ITEMS: NavItem[] = [
  { id: 'workbench', icon: Home, label: 'Home' },
  { id: 'environmental', icon: TreePine, label: 'Environmental Agent' },
  { id: 'layers', icon: Map, label: 'Layers' },
  { id: 'plans', icon: Grid3x3, label: 'Plans' },
  { id: 'copilot', icon: MessageCircleQuestion, label: 'Copilot' },
  { id: 'settings', icon: Settings, label: 'Settings' },
];

/**
 * Sidebar navigation component.
 * Renders vertical navigation with icons for main app views.
 */
export function Sidebar({ activeView, onViewChange }: SidebarProps) {
  const { logout } = useAuth();

  return (
    <nav className="sidebar" aria-label="Main navigation">
      <div className="sidebar-nav-items">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`sidebar-nav-btn ${isActive ? 'sidebar-nav-btn--active' : ''}`}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
              title={item.label}
            >
              <Icon
                className={`sidebar-nav-btn__icon ${
                  isActive ? 'sidebar-nav-btn__icon--active' : 'sidebar-nav-btn__icon--inactive'
                }`}
              />
              {isActive && <span className="sidebar-nav-btn__indicator" aria-hidden="true" />}
            </button>
          );
        })}
      </div>
      
      <button
        onClick={logout}
        className="sidebar-nav-btn sidebar-nav-btn--logout"
        aria-label="Logout"
        title="Logout"
      >
        <LogOut className="sidebar-nav-btn__icon sidebar-nav-btn__icon--inactive" />
      </button>
    </nav>
  );
}
