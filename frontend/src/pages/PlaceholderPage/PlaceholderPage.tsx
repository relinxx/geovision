/**
 * PlaceholderPage Component
 * ========================
 * Simple placeholder view for unfinished sections of the application.
 * Displays an icon, title, and description in a centered layout.
 * 
 * @component
 * @example
 * ```tsx
 * <PlaceholderPage
 *   icon={Users}
 *   title="AI Agents View"
 *   description="Configure and monitor AI agents"
 *   color="#3BC7F5"
 * />
 * ```
 */

import { LucideIcon } from 'lucide-react';
import './PlaceholderPage.css';

/** Props for the PlaceholderPage component */
interface PlaceholderPageProps {
  /** Lucide icon component to display */
  icon: LucideIcon;
  /** Page title */
  title: string;
  /** Descriptive text explaining the feature */
  description: string;
  /** Color for the icon and title (hex or CSS color) */
  color: string;
}

/**
 * Placeholder page component.
 * Used for views that are not yet fully implemented.
 */
export function PlaceholderPage({
  icon: Icon,
  title,
  description,
  color,
}: PlaceholderPageProps) {
  return (
    <main className="placeholder-page">
      <div className="placeholder-page__content">
        <Icon className="placeholder-page__icon" style={{ color }} />
        <h1 className="placeholder-page__title" style={{ color }}>
          {title}
        </h1>
        <p className="placeholder-page__description">{description}</p>
      </div>
    </main>
  );
}
