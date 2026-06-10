import React from 'react';
import type { ReactNode } from 'react';
import { APP_CONSTANTS } from '../../constants/app.constants';

interface AppLayoutProps {
  readonly children: ReactNode;
}

function AppHeader(): React.JSX.Element {
  return (
    <header role="banner" className="app-header">
      <nav role="navigation" aria-label="Main navigation">
        <a href="/" className="app-logo" aria-label={`${APP_CONSTANTS.APP_NAME} home`}>
          {APP_CONSTANTS.APP_NAME}
        </a>
      </nav>
    </header>
  );
}

function AppFooter(): React.JSX.Element {
  return (
    <footer role="contentinfo" className="app-footer">
      <p>&copy; {new Date().getFullYear()} {APP_CONSTANTS.APP_NAME}</p>
    </footer>
  );
}

export function AppLayout({ children }: AppLayoutProps): React.JSX.Element {
  return (
    <div className="app-container">
      <a className="skip-link" href="#app-main">Skip to content</a>
      <AppHeader />
      <main role="main" id="app-main" className="app-main" tabIndex={-1}>
        {children}
      </main>
      <AppFooter />
    </div>
  );
}
