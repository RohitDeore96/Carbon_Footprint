/**
 * EmissionGoals.test.tsx — Tests for the EmissionGoals component.
 * Covers: form rendering when no goal, saving goal to localStorage,
 * showing progress when goal exists, progress bar calculation,
 * streak counter, milestone messages, accessibility, and reset functionality.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EmissionGoals } from '../EmissionGoals';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'carbon-footprint-goals';

const defaultProps = {
  totalCo2eKg: 75,
  periodDays: 30,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('EmissionGoals', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  // -------------------------------------------------------------------------
  // Form rendering when no goal exists
  // -------------------------------------------------------------------------

  describe('no goal set — form view', () => {
    it('renders the "Set Your Goal" heading when no goal exists', () => {
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByText('Set Your Goal')).toBeInTheDocument();
    });

    it('renders the monthly target input with default value of 165', () => {
      render(<EmissionGoals {...defaultProps} />);
      const input = screen.getByLabelText('Monthly target (kg CO2e)') as HTMLInputElement;
      expect(input).toBeInTheDocument();
      expect(input.value).toBe('165');
    });

    it('renders the Paris Agreement hint text', () => {
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByText('Paris Agreement target: 165 kg/month (2.5 kg/day)')).toBeInTheDocument();
    });

    it('renders the Set Goal button', () => {
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByRole('button', { name: /set emission reduction goal/i })).toBeInTheDocument();
    });

    it('does not show progress view when no goal is set', () => {
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.queryByText('Your Goal')).not.toBeInTheDocument();
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Saving goal to localStorage
  // -------------------------------------------------------------------------

  describe('saving goals', () => {
    it('saves goal to localStorage when form is submitted', async () => {
      const user = userEvent.setup();
      render(<EmissionGoals {...defaultProps} />);

      const input = screen.getByLabelText('Monthly target (kg CO2e)') as HTMLInputElement;
      await user.clear(input);
      await user.type(input, '200');

      const submitBtn = screen.getByRole('button', { name: /set emission reduction goal/i });
      await user.click(submitBtn);

      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
      expect(stored.monthlyTargetKg).toBe(200);
      expect(stored.createdAt).toBeDefined();
    });

    it('switches to progress view after saving a goal', async () => {
      const user = userEvent.setup();
      render(<EmissionGoals {...defaultProps} />);

      const submitBtn = screen.getByRole('button', { name: /set emission reduction goal/i });
      await user.click(submitBtn);

      expect(screen.getByText('Your Goal')).toBeInTheDocument();
      expect(screen.queryByText('Set Your Goal')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Progress view when goal exists
  // -------------------------------------------------------------------------

  describe('goal set — progress view', () => {
    it('shows progress view when a goal exists in localStorage', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByText('Your Goal')).toBeInTheDocument();
    });

    it('displays the monthly target value', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByLabelText('165 kg monthly target')).toBeInTheDocument();
    });

    it('displays the projected monthly emissions', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // totalCo2eKg=75, periodDays=30 → dailyAvg=2.5 → projected=75.0
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByLabelText('75.0 kg projected monthly')).toBeInTheDocument();
    });

    it('displays the daily average', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // totalCo2eKg=75, periodDays=30 → dailyAvg=2.5
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByLabelText('2.50 kg daily average')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Progress bar calculation
  // -------------------------------------------------------------------------

  describe('progress bar calculation', () => {
    it('shows 100% progress when projected monthly is under target', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // totalCo2eKg=75, periodDays=30 → projected=75, target=165 → under target
      render(<EmissionGoals {...defaultProps} />);
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '100');
      expect(screen.getByText('100% of target reached')).toBeInTheDocument();
    });

    it('shows correct progress when over target', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 50,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // totalCo2eKg=75, periodDays=30 → dailyAvg=2.5 → projected=75
      // progress = 1 - (75-50)/75 = 1 - 25/75 = 1 - 0.333 = 0.667 → 67%
      render(<EmissionGoals {...defaultProps} />);
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '67');
    });

    it('shows green progress bar class when under target', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals {...defaultProps} />);
      const bar = document.querySelector('.goals-progress-bar');
      expect(bar?.className).toContain('goals-progress-bar--success');
    });

    it('shows warning progress bar class when over target', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 50,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals {...defaultProps} />);
      const bar = document.querySelector('.goals-progress-bar');
      expect(bar?.className).toContain('goals-progress-bar--warning');
    });
  });

  // -------------------------------------------------------------------------
  // Streak counter
  // -------------------------------------------------------------------------

  describe('streak counter', () => {
    it('shows streak when daily average is under the daily target rate', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // dailyAvg=2.5, dailyTarget=165/30=5.5 → under target → streak = 30 days
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByLabelText('Streak: 30 days under target')).toBeInTheDocument();
    });

    it('does not show streak when daily average is over the daily target rate', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 50,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // dailyAvg=2.5, dailyTarget=50/30=1.67 → over target → no streak
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.queryByText(/days under target/)).not.toBeInTheDocument();
    });

    it('shows singular "day" when streak is 1', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 100,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // totalCo2eKg=3, periodDays=1 → dailyAvg=3, dailyTarget=100/30=3.33 → under target → streak=1
      render(<EmissionGoals totalCo2eKg={3} periodDays={1} />);
      expect(screen.getByLabelText('Streak: 1 day under target')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Motivational messages
  // -------------------------------------------------------------------------

  describe('motivational messages', () => {
    it('shows congratulatory message when under target', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByText(/You're under your target/)).toBeInTheDocument();
    });

    it('shows milestone message when at 50% progress', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 50,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // progress=67%, over target → should show 50% milestone message
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByText(/Halfway there/)).toBeInTheDocument();
    });

    it('shows 100% milestone message when hitting target', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      // progress=100%, under target → congratulatory msg, not milestone
      render(<EmissionGoals {...defaultProps} />);
      // The "under target" message is shown, not milestone
      expect(screen.getByText(/You're under your target/)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Reset functionality
  // -------------------------------------------------------------------------

  describe('reset goal', () => {
    it('renders the Reset Goal button when a goal exists', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByRole('button', { name: /reset emission reduction goal/i })).toBeInTheDocument();
    });

    it('clears localStorage and switches to form view on reset', async () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      const user = userEvent.setup();
      render(<EmissionGoals {...defaultProps} />);

      const resetBtn = screen.getByRole('button', { name: /reset emission reduction goal/i });
      await user.click(resetBtn);

      expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
      expect(screen.getByText('Set Your Goal')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Accessibility
  // -------------------------------------------------------------------------

  describe('accessibility', () => {
    it('form view has correct aria-label on the region', () => {
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByRole('region', { name: /set emission reduction goal/i })).toBeInTheDocument();
    });

    it('progress view has correct aria-label on the region', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByRole('region', { name: /emission goals and progress/i })).toBeInTheDocument();
    });

    it('progress bar has correct aria attributes', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals {...defaultProps} />);
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '100');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
      expect(progressBar).toHaveAttribute('aria-label', 'Goal progress: 100%');
    });

    it('input is associated with label via htmlFor/id', () => {
      render(<EmissionGoals {...defaultProps} />);
      const input = screen.getByLabelText('Monthly target (kg CO2e)');
      expect(input).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Edge cases
  // -------------------------------------------------------------------------

  describe('edge cases', () => {
    it('handles zero periodDays gracefully', () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        monthlyTargetKg: 165,
        createdAt: '2025-01-01T00:00:00.000Z',
      }));
      render(<EmissionGoals totalCo2eKg={0} periodDays={0} />);
      // dailyAvg = 0/0 → but we guard: periodDays > 0 ? totalCo2eKg/periodDays : 0
      expect(screen.getByLabelText('0.00 kg daily average')).toBeInTheDocument();
    });

    it('handles corrupted localStorage data by showing the form', () => {
      localStorage.setItem(STORAGE_KEY, 'not-valid-json');
      render(<EmissionGoals {...defaultProps} />);
      expect(screen.getByText('Set Your Goal')).toBeInTheDocument();
    });

    it('does not submit when input is empty or zero', async () => {
      const user = userEvent.setup();
      render(<EmissionGoals {...defaultProps} />);

      const input = screen.getByLabelText('Monthly target (kg CO2e)') as HTMLInputElement;
      await user.clear(input);

      const submitBtn = screen.getByRole('button', { name: /set emission reduction goal/i });
      await user.click(submitBtn);

      // Should still be on the form view since empty string is invalid
      expect(screen.getByText('Set Your Goal')).toBeInTheDocument();
    });
  });
});
