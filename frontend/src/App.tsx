import React, { useState, useEffect, Component, type ErrorInfo, type ReactNode, lazy, Suspense } from 'react';
import { AppLayout } from './components/layout/AppLayout';
import { ToastProvider } from './components/ui/Toast';
import { signInAnonymouslyAndGetUser, onAuthChange } from './services/firebase';
import OnboardingModal from './components/onboarding/OnboardingModal';
import './styles/variables.css';
import './styles/base.css';
import './styles/layout.css';
import './styles/dashboard.css';
import './styles/charts.css';
import './styles/form.css';
import './styles/coach.css';
import './styles/goals.css';
import './styles/onboarding.css';
import './styles/export.css';
import './styles/toast.css';
import './styles/empty-state.css';

// Route-based code splitting: lazy-load heavy components
// Recharts (~150KB) and AI coach components are loaded only when needed
const CarbonDashboard = lazy(() =>
  import('./components/dashboard/CarbonDashboard').then((m) => ({ default: m.CarbonDashboard }))
);

// ---------------------------------------------------------------------------
// Error Boundary — prevents unhandled runtime errors from crashing the whole app
// ---------------------------------------------------------------------------

interface ErrorBoundaryProps {
  readonly children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ErrorBoundary caught an unhandled error:', error, info);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div role="alert" className="error-boundary-fallback">
          <h2>Something went wrong</h2>
          <p>{this.state.error?.message ?? 'An unexpected error occurred.'}</p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Root Application Component
// ---------------------------------------------------------------------------

/**
 * Root application component.
 * Uses Firebase Anonymous Authentication to assign each user a unique identity.
 * Falls back to a unique generated ID if Firebase auth fails.
 * Single ToastProvider wraps entire app to avoid duplicate context instances.
 */
export default function App(): React.JSX.Element {
  const [userId, setUserId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthChange((uid) => {
      if (uid) {
        setUserId(uid);
        setLoading(false);
      } else {
        signInAnonymouslyAndGetUser()
          .then(({ uid }) => {
            setUserId(uid);
            setLoading(false);
          })
          .catch((err: unknown) => {
            console.error('Firebase anonymous auth failed, using fallback:', err);
            // Generate unique fallback ID instead of shared sentinel
            setUserId(`fallback-${crypto.randomUUID().slice(0, 12)}`);
            setLoading(false);
          });
      }
    });
    return () => unsubscribe();
  }, []);

  return (
    <ToastProvider>
      <ErrorBoundary>
        <AppLayout>
          {loading ? (
            <div role="status" aria-live="polite" aria-label="Loading application">
              <span className="loading-spinner" aria-hidden="true" />
              <p>Initializing Carbon Footprint Platform...</p>
            </div>
          ) : (
            <>
              <OnboardingModal />
              <h1 className="sr-only">Carbon Footprint Awareness Platform</h1>
              <Suspense fallback={
                <div role="status" aria-live="polite" aria-label="Loading dashboard">
                  <span className="loading-spinner" aria-hidden="true" />
                  <p>Loading dashboard...</p>
                </div>
              }>
                <CarbonDashboard userId={userId ?? `fallback-${crypto.randomUUID().slice(0, 12)}`} />
              </Suspense>
            </>
          )}
        </AppLayout>
      </ErrorBoundary>
    </ToastProvider>
  );
}
