import React from 'react';
import type { ReactNode } from 'react';
import { APP_CONSTANTS } from '../../constants/app.constants';

interface AppLayoutProps {
  readonly children: ReactNode;
}

const NAV_SECTIONS = [
  { href: '#emission-chart-section', label: 'Charts' },
  { href: '#trend-chart-section', label: 'Trends' },
  { href: '#log-activity-section', label: 'Log Activity' },
  { href: '#activity-history-section', label: 'History' },
  { href: '#insight-coach', label: 'AI Coach' },
  { href: '#chat-coach', label: 'Chat' },
] as const;

function AppHeader(): React.JSX.Element {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <nav aria-label="Main navigation">
          <a href="/" className="app-logo" aria-label={`${APP_CONSTANTS.APP_NAME} home`}>
            {APP_CONSTANTS.APP_NAME}
          </a>
        </nav>
        <nav aria-label="Section navigation" className="app-nav-links">
          {NAV_SECTIONS.map((section) => (
            <a
              key={section.href}
              href={section.href}
              className="app-nav-link"
            >
              {section.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}

function AppFooter(): React.JSX.Element {
  return (
    <footer className="app-footer">
      <p>&copy; {new Date().getFullYear()} {APP_CONSTANTS.APP_NAME}</p>
    </footer>
  );
}

export function AppLayout({ children }: AppLayoutProps): React.JSX.Element {
  return (
    <div className="app-container">
      <a className="skip-link" href="#app-main">Skip to content</a>
      <AppHeader />
      <main id="app-main" className="app-main" tabIndex={-1}>
        {children}
      </main>
      <AppFooter />
    </div>
  );
}
