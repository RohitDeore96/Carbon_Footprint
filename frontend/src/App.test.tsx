/**
 * App.test.tsx — Tests for the root App component.
 * Verifies Firebase auth flow: loading state, authenticated rendering, and fallback behavior.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import App from './App';

// ---------------------------------------------------------------------------
// Mock firebase auth service
// ---------------------------------------------------------------------------

let authCallback: ((uid: string | null) => void) | null = null;
const mockSignInAnonymouslyAndGetUser = vi.fn();

vi.mock('./services/firebase', () => ({
  signInAnonymouslyAndGetUser: (...args: unknown[]) => mockSignInAnonymouslyAndGetUser(...args),
  onAuthChange: (callback: (uid: string | null) => void) => {
    authCallback = callback;
    return () => {
      authCallback = null;
    };
  },
}));

// ---------------------------------------------------------------------------
// Mock child components to isolate App logic
// ---------------------------------------------------------------------------

vi.mock('./components/layout/AppLayout', () => ({
  AppLayout: ({ children }: { readonly children: React.ReactNode }) => (
    <div data-testid="app-layout">{children}</div>
  ),
}));

vi.mock('./components/dashboard/CarbonDashboard', () => ({
  CarbonDashboard: ({ userId }: { readonly userId: string }) => (
    <div data-testid="carbon-dashboard" data-userid={userId} />
  ),
}));

// Mock CSS import
vi.mock('./App.css', () => ({}));

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authCallback = null;
    mockSignInAnonymouslyAndGetUser.mockReset();
  });

  it('shows loading spinner while auth is initializing', () => {
    render(<App />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/Initializing Carbon Footprint/i)).toBeInTheDocument();
  });

  it('renders CarbonDashboard after successful anonymous sign-in', async () => {
    mockSignInAnonymouslyAndGetUser.mockResolvedValue({ uid: 'test-uid-123' });

    render(<App />);

    // Simulate onAuthStateChanged firing with null user (triggers signInAnonymously)
    await act(async () => {
      authCallback?.(null);
    });

    await waitFor(() => {
      expect(screen.getByTestId('carbon-dashboard')).toBeInTheDocument();
    });

    expect(screen.getByTestId('carbon-dashboard').dataset.userid).toBe('test-uid-123');
  });

  it('renders CarbonDashboard when user is already authenticated', async () => {
    render(<App />);

    // Simulate onAuthStateChanged firing with an existing user
    await act(async () => {
      authCallback?.('existing-uid-456');
    });

    await waitFor(() => {
      expect(screen.getByTestId('carbon-dashboard')).toBeInTheDocument();
    });

    expect(screen.getByTestId('carbon-dashboard').dataset.userid).toBe('existing-uid-456');
    expect(mockSignInAnonymouslyAndGetUser).not.toHaveBeenCalled();
  });

  it('falls back to a unique fallback ID when Firebase auth fails', async () => {
    mockSignInAnonymouslyAndGetUser.mockRejectedValue(new Error('Firebase unavailable'));

    render(<App />);

    // Trigger sign-in attempt by reporting null user
    await act(async () => {
      authCallback?.(null);
    });

    await waitFor(() => {
      expect(screen.getByTestId('carbon-dashboard')).toBeInTheDocument();
    });

    const userId = screen.getByTestId('carbon-dashboard').dataset.userid;
    expect(userId).toMatch(/^fallback-[a-f0-9-]+$/);
    expect(userId?.startsWith('fallback-')).toBe(true);
  });

  it('unsubscribes from auth changes on unmount', () => {
    const { unmount } = render(<App />);

    // The auth callback should be set
    expect(authCallback).not.toBeNull();

    unmount();

    // After unmount, the callback should be cleared (unsubscribe was called)
    expect(authCallback).toBeNull();
  });

  it('renders within AppLayout', () => {
    render(<App />);
    expect(screen.getByTestId('app-layout')).toBeInTheDocument();
  });

  it('shows a loading spinner with correct aria attributes', () => {
    render(<App />);
    const statusEl = screen.getByRole('status');
    expect(statusEl).toHaveAttribute('aria-live', 'polite');
    expect(statusEl).toHaveAttribute('aria-label', 'Loading application');
  });
});
