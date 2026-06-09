import React, { useState, useEffect } from 'react';
import { AppLayout } from './components/layout/AppLayout';
import { CarbonDashboard } from './components/dashboard/CarbonDashboard';
import { ToastProvider } from './components/ui/Toast';
import { signInAnonymouslyAndGetUser, onAuthChange } from './services/firebase';
import OnboardingModal from './components/onboarding/OnboardingModal';
import './App.css';

/**
 * Root application component.
 * Uses Firebase Anonymous Authentication to assign each user a unique identity.
 * Falls back to 'anonymous-fallback' if Firebase auth fails.
 * Wrapped with ToastProvider for global notification support.
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
          .catch(() => {
            setUserId('anonymous-fallback');
            setLoading(false);
          });
      }
    });
    return () => unsubscribe();
  }, []);

  if (loading) {
    return (
      <ToastProvider>
        <AppLayout>
          <div role="status" aria-live="polite" aria-label="Loading application">
            <span className="loading-spinner" aria-hidden="true" />
            <p>Initializing Carbon Footprint Platform...</p>
          </div>
        </AppLayout>
      </ToastProvider>
    );
  }

  return (
    <ToastProvider>
      <OnboardingModal />
      <AppLayout>
        <h1 className="sr-only">Carbon Footprint Awareness Platform</h1>
        <CarbonDashboard userId={userId ?? 'anonymous-fallback'} />
      </AppLayout>
    </ToastProvider>
  );
}
