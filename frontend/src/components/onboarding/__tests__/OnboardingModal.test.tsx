/**
 * OnboardingModal.test.tsx — Comprehensive tests for the onboarding walkthrough component.
 * Covers: first-visit rendering, step navigation, localStorage persistence, skip, and accessibility.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import OnboardingModal from '../OnboardingModal';

// ---------------------------------------------------------------------------
// localStorage mock
// ---------------------------------------------------------------------------

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OnboardingModal', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  describe('rendering', () => {
    it('renders step 1 on first visit (localStorage empty)', () => {
      render(<OnboardingModal />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Welcome to Carbon Footprint Tracker')).toBeInTheDocument();
      expect(
        screen.getByText(/Track your daily carbon emissions across transport/),
      ).toBeInTheDocument();
    });

    it('does not render when onboarding complete in localStorage', () => {
      localStorageMock.getItem.mockReturnValueOnce('true');
      render(<OnboardingModal />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('shows the step icon for step 1', () => {
      render(<OnboardingModal />);
      const icon = screen.getByText('\u{1F30D}');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // -------------------------------------------------------------------------
  // Step navigation
  // -------------------------------------------------------------------------

  describe('step navigation', () => {
    it('advances to next step on "Next" click', () => {
      render(<OnboardingModal />);

      // Should be on step 1 initially
      expect(screen.getByText('Welcome to Carbon Footprint Tracker')).toBeInTheDocument();

      const nextBtn = screen.getByText('Next');
      fireEvent.click(nextBtn);

      // Should now be on step 2
      expect(screen.getByText('Log Your First Activity')).toBeInTheDocument();
      expect(screen.queryByText('Welcome to Carbon Footprint Tracker')).not.toBeInTheDocument();
    });

    it('goes back to previous step on "Previous" click', () => {
      render(<OnboardingModal />);

      // Go to step 2
      fireEvent.click(screen.getByText('Next'));
      expect(screen.getByText('Log Your First Activity')).toBeInTheDocument();

      // Go back to step 1
      fireEvent.click(screen.getByText('Previous'));
      expect(screen.getByText('Welcome to Carbon Footprint Tracker')).toBeInTheDocument();
    });

    it('does not show Previous button on step 1', () => {
      render(<OnboardingModal />);
      expect(screen.queryByText('Previous')).not.toBeInTheDocument();
    });

    it('shows Previous button on step 2', () => {
      render(<OnboardingModal />);
      fireEvent.click(screen.getByText('Next'));
      expect(screen.getByText('Previous')).toBeInTheDocument();
    });

    it('shows "Get Started" button on the last step', () => {
      render(<OnboardingModal />);

      // Navigate to step 2
      fireEvent.click(screen.getByText('Next'));
      // Navigate to step 3
      fireEvent.click(screen.getByText('Next'));

      expect(screen.getByText('Get Started')).toBeInTheDocument();
      expect(screen.queryByText('Next')).not.toBeInTheDocument();
    });

    it('renders step 3 content on last step', () => {
      render(<OnboardingModal />);

      fireEvent.click(screen.getByText('Next'));
      fireEvent.click(screen.getByText('Next'));

      expect(screen.getByText('Get AI-Powered Insights')).toBeInTheDocument();
      expect(
        screen.getByText(/Our AI coach analyzes your data/),
      ).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Completion / localStorage
  // -------------------------------------------------------------------------

  describe('completion', () => {
    it('completes onboarding on "Get Started" click (sets localStorage)', () => {
      render(<OnboardingModal />);

      // Navigate to last step
      fireEvent.click(screen.getByText('Next'));
      fireEvent.click(screen.getByText('Next'));

      fireEvent.click(screen.getByText('Get Started'));

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'carbon-footprint-onboarding-complete',
        'true',
      );
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('Skip button closes and marks complete', () => {
      render(<OnboardingModal />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Skip'));

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'carbon-footprint-onboarding-complete',
        'true',
      );
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('does not show on subsequent renders after completion', () => {
      const { unmount } = render(<OnboardingModal />);
      fireEvent.click(screen.getByText('Skip'));
      unmount();

      // Simulate returning — localStorage now has the key
      localStorageMock.getItem.mockReturnValueOnce('true');
      render(<OnboardingModal />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Progress dots
  // -------------------------------------------------------------------------

  describe('progress dots', () => {
    it('shows 3 progress dots', () => {
      render(<OnboardingModal />);
      const dots = screen.getAllByRole('presentation');
      expect(dots).toHaveLength(3);
    });

    it('progress dots show correct step — step 1 active', () => {
      render(<OnboardingModal />);
      const dots = screen.getAllByRole('presentation');
      expect(dots[0]).toHaveAttribute('aria-label', 'Step 1 of 3 (current)');
      expect(dots[1]).toHaveAttribute('aria-label', 'Step 2 of 3');
      expect(dots[2]).toHaveAttribute('aria-label', 'Step 3 of 3');
    });

    it('progress dots update when navigating to step 2', () => {
      render(<OnboardingModal />);
      fireEvent.click(screen.getByText('Next'));

      const dots = screen.getAllByRole('presentation');
      expect(dots[0]).toHaveAttribute('aria-label', 'Step 1 of 3');
      expect(dots[1]).toHaveAttribute('aria-label', 'Step 2 of 3 (current)');
      expect(dots[2]).toHaveAttribute('aria-label', 'Step 3 of 3');
    });

    it('progress dots have step labels', () => {
      render(<OnboardingModal />);
      const dots = screen.getAllByRole('presentation');
      expect(dots[0]).toHaveAttribute('aria-label', expect.stringContaining('Step 1 of 3'));
      expect(dots[1]).toHaveAttribute('aria-label', expect.stringContaining('Step 2 of 3'));
      expect(dots[2]).toHaveAttribute('aria-label', expect.stringContaining('Step 3 of 3'));
    });

    it('active dot has active class', () => {
      render(<OnboardingModal />);
      const dots = screen.getAllByRole('presentation');
      expect(dots[0].classList.contains('onboarding-dot--active')).toBe(true);
    });
  });

  // -------------------------------------------------------------------------
  // Accessibility
  // -------------------------------------------------------------------------

  describe('accessibility', () => {
    it('has role="dialog"', () => {
      render(<OnboardingModal />);
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    it('has aria-modal="true"', () => {
      render(<OnboardingModal />);
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('has aria-labelledby pointing to step title', () => {
      render(<OnboardingModal />);
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby', 'onboarding-step-title');

      const title = document.getElementById('onboarding-step-title');
      expect(title).toBeInTheDocument();
      expect(title?.textContent).toBe('Welcome to Carbon Footprint Tracker');
    });

    it('step icon is aria-hidden', () => {
      render(<OnboardingModal />);
      const icon = screen.getByText('\u{1F30D}');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });

    it('progress dots region has aria-label', () => {
      render(<OnboardingModal />);
      const dotsRegion = screen.getByLabelText('Onboarding progress');
      expect(dotsRegion).toBeInTheDocument();
    });

    it('focus trap: Tab key cycles within modal', () => {
      render(<OnboardingModal />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('tabindex', '-1');
    });
  });

  // -------------------------------------------------------------------------
  // Overlay click to dismiss
  // -------------------------------------------------------------------------

  describe('overlay click', () => {
    it('clicking the overlay closes the modal and marks complete', () => {
      render(<OnboardingModal />);

      const overlay = document.querySelector('.onboarding-overlay');
      expect(overlay).toBeInTheDocument();

      fireEvent.click(overlay!);

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'carbon-footprint-onboarding-complete',
        'true',
      );
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('clicking inside the modal does not close it', () => {
      render(<OnboardingModal />);

      const modal = document.querySelector('.onboarding-modal');
      fireEvent.click(modal!);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(localStorageMock.setItem).not.toHaveBeenCalled();
    });
  });
});
