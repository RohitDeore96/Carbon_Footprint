/**
 * Toast.test.tsx — Comprehensive tests for the Toast notification component.
 * Covers ToastProvider, useToast hook, addToast, auto-dismiss, and accessibility.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { ToastProvider, useToast, type ToastVariant } from '../Toast';

// ---------------------------------------------------------------------------
// Test component that uses useToast inside the provider
// ---------------------------------------------------------------------------

function TestConsumer({ message, variant }: { message: string; variant: ToastVariant }): React.JSX.Element {
  const { addToast } = useToast();
  return (
    <button type="button" onClick={() => addToast(message, variant)}>
      Add Toast
    </button>
  );
}

function TestApp({
  message = 'Test notification',
  variant = 'success' as ToastVariant,
}: {
  message?: string;
  variant?: ToastVariant;
}): React.JSX.Element {
  return (
    <ToastProvider>
      <TestConsumer message={message} variant={variant} />
    </ToastProvider>
  );
}

// ---------------------------------------------------------------------------
// Test component that tries to use useToast outside the provider
// ---------------------------------------------------------------------------

function OutsideProviderConsumer(): React.JSX.Element {
  useToast();
  return <div>Should not render</div>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Toast', () => {
  // -------------------------------------------------------------------------
  // ToastProvider rendering (no fake timers needed)
  // -------------------------------------------------------------------------

  describe('ToastProvider', () => {
    it('renders children', () => {
      render(
        <ToastProvider>
          <div data-testid="child">Hello World</div>
        </ToastProvider>,
      );
      expect(screen.getByTestId('child')).toBeInTheDocument();
    });

    it('renders toast container region', () => {
      render(<TestApp />);
      expect(screen.getByLabelText('Notifications')).toBeInTheDocument();
    });

    it('toast container has role=region', () => {
      render(<TestApp />);
      const container = screen.getByLabelText('Notifications');
      expect(container).toHaveAttribute('role', 'region');
    });

    it('toast container has aria-live=polite', () => {
      render(<TestApp />);
      const container = screen.getByLabelText('Notifications');
      expect(container).toHaveAttribute('aria-live', 'polite');
    });
  });

  // -------------------------------------------------------------------------
  // useToast hook
  // -------------------------------------------------------------------------

  describe('useToast', () => {
    it('throws error when used outside ToastProvider', () => {
      // Suppress console.error for this expected error
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      expect(() => render(<OutsideProviderConsumer />)).toThrow(
        'useToast must be used within a ToastProvider',
      );
      spy.mockRestore();
    });

    it('returns addToast function when inside provider', () => {
      let addToastFn: ((msg: string, variant: ToastVariant) => void) | null = null;
      function CaptureRef(): React.JSX.Element {
        const { addToast } = useToast();
        React.useEffect(() => {
          addToastFn = addToast;
        }, [addToast]);
        return <div>Capture</div>;
      }
      render(
        <ToastProvider>
          <CaptureRef />
        </ToastProvider>,
      );
      expect(addToastFn).toBeDefined();
      expect(typeof addToastFn).toBe('function');
    });
  });

  // -------------------------------------------------------------------------
  // addToast and notification display (no fake timers needed)
  // -------------------------------------------------------------------------

  describe('addToast', () => {
    it('shows notification when addToast is called', () => {
      render(<TestApp message="Activity logged successfully!" />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      expect(screen.getByText('Activity logged successfully!')).toBeInTheDocument();
    });

    it('shows success icon for success variant', () => {
      render(<TestApp variant="success" />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      expect(screen.getByText('✓')).toBeInTheDocument();
    });

    it('shows error icon for error variant', () => {
      render(<TestApp variant="error" />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      expect(screen.getByText('⚠')).toBeInTheDocument();
    });

    it('shows info icon for info variant', () => {
      render(<TestApp variant="info" />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      expect(screen.getByText('ℹ')).toBeInTheDocument();
    });

    it('displays multiple toasts', () => {
      render(<TestApp />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      fireEvent.click(btn);
      fireEvent.click(btn);
      const messages = screen.getAllByText('Test notification');
      expect(messages).toHaveLength(3);
    });
  });

  // -------------------------------------------------------------------------
  // Auto-dismiss (uses fake timers)
  // -------------------------------------------------------------------------

  describe('auto-dismiss', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('toast auto-dismisses after timeout', () => {
      render(<TestApp message="Will disappear" />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);

      expect(screen.getByText('Will disappear')).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(4000);
      });

      expect(screen.queryByText('Will disappear')).not.toBeInTheDocument();
    });

    it('toast does not dismiss before timeout', () => {
      render(<TestApp message="Still here" />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);

      act(() => {
        vi.advanceTimersByTime(3999);
      });

      expect(screen.getByText('Still here')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Manual dismiss (no fake timers needed)
  // -------------------------------------------------------------------------

  describe('manual dismiss', () => {
    it('toast can be dismissed with dismiss button', async () => {
      render(<TestApp message="Dismiss me" />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);

      const dismissBtn = screen.getByLabelText('Dismiss notification');
      fireEvent.click(dismissBtn);

      await waitFor(() => {
        expect(screen.queryByText('Dismiss me')).not.toBeInTheDocument();
      });
    });

    it('dismiss button removes only the target toast', () => {
      let callCount = 0;
      function MultiToastApp(): React.JSX.Element {
        const { addToast } = useToast();
        return (
          <div>
            <button
              type="button"
              onClick={() => {
                callCount++;
                addToast(`Toast ${callCount}`, 'success');
              }}
            >
              Add
            </button>
          </div>
        );
      }
      render(
        <ToastProvider>
          <MultiToastApp />
        </ToastProvider>,
      );

      const btn = screen.getByText('Add');
      fireEvent.click(btn);
      fireEvent.click(btn);

      expect(screen.getByText('Toast 1')).toBeInTheDocument();
      expect(screen.getByText('Toast 2')).toBeInTheDocument();

      // Dismiss the first toast
      const dismissBtns = screen.getAllByLabelText('Dismiss notification');
      fireEvent.click(dismissBtns[0]);

      // The second toast should still be visible
      expect(screen.getByText('Toast 2')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Accessibility (no fake timers needed)
  // -------------------------------------------------------------------------

  describe('accessibility', () => {
    it('toast item has role=status', () => {
      render(<TestApp />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      const toast = screen.getByText('Test notification').closest('[role="status"]');
      expect(toast).not.toBeNull();
    });

    it('toast item has aria-live=polite', () => {
      render(<TestApp />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      const toast = screen.getByText('Test notification').closest('[aria-live="polite"]');
      expect(toast).not.toBeNull();
    });

    it('dismiss button has descriptive aria-label', () => {
      render(<TestApp />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      expect(screen.getByLabelText('Dismiss notification')).toBeInTheDocument();
    });

    it('toast icon is aria-hidden', () => {
      render(<TestApp variant="success" />);
      const btn = screen.getByText('Add Toast');
      fireEvent.click(btn);
      const icon = screen.getByText('✓');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });
});
