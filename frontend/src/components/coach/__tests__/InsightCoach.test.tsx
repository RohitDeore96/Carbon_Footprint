/**
 * InsightCoach.test.tsx — Comprehensive tests for the InsightCoach component.
 * Covers empty state, request button, loading state, insights display, error state,
 * forwardRef/requestInsights method, and accessibility.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InsightCoach, type InsightCoachHandle } from '../InsightCoach';
import type { InsightsResponse, ApiResult, EmissionSummaryEntry } from '../../../services/apiClient';

// ---------------------------------------------------------------------------
// Mock apiClient
// ---------------------------------------------------------------------------

type PostInsightsRequestFn = (payload: unknown) => Promise<ApiResult<InsightsResponse>>;

const { mockPostInsightsRequest } = vi.hoisted(() => ({
  mockPostInsightsRequest: vi.fn<PostInsightsRequestFn>(),
}));

vi.mock('../../../services/apiClient', () => ({
  apiClient: {
    postInsightsRequest: (...args: Parameters<PostInsightsRequestFn>) =>
      mockPostInsightsRequest(...args),
    postFootprintLog: vi.fn(),
    postChatRequest: vi.fn(),
    getFootprintHistory: vi.fn(),
    getFootprintSummary: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const emptyBreakdown: readonly EmissionSummaryEntry[] = [];

const sampleBreakdown: readonly EmissionSummaryEntry[] = [
  { category: 'transport', total_co2e_kg: 10.5, entry_count: 1, description: 'Car commute' },
  { category: 'energy', total_co2e_kg: 5.0, entry_count: 1, description: 'Electricity' },
];

const defaultProps = {
  userId: 'test-user-001',
  totalCo2eKg: 15.5,
  periodDays: 7,
  emissionBreakdown: sampleBreakdown,
};

const noDataProps = {
  userId: 'test-user-001',
  totalCo2eKg: 0,
  periodDays: 0,
  emissionBreakdown: emptyBreakdown,
};

const mockInsightsResponse: InsightsResponse = {
  user_id: 'test-user-001',
  insight: 'Your transport emissions make up the majority of your carbon footprint.',
  equivalent_impact: 'Equivalent to driving 65 km in a standard car.',
  actionable_steps: [
    'Switch to public transit for daily commutes',
    'Consider carpooling twice a week',
    'Try cycling for trips under 5 km',
  ],
  model_used: 'gemini-2.5-flash',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('InsightCoach', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPostInsightsRequest.mockReset();
  });

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  describe('rendering', () => {
    it('renders the insight coach article with correct aria-label', () => {
      render(<InsightCoach {...defaultProps} />);
      expect(screen.getByLabelText('AI Sustainability Coach')).toBeInTheDocument();
    });

    it('renders the coach title', () => {
      render(<InsightCoach {...defaultProps} />);
      expect(screen.getByText('Sustainability Coach')).toBeInTheDocument();
    });

    it('renders the coach subtitle', () => {
      render(<InsightCoach {...defaultProps} />);
      expect(screen.getByText(/Powered by Gemini/)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Empty state (no data)
  // -------------------------------------------------------------------------

  describe('empty state', () => {
    it('shows empty state when no emission data', () => {
      render(<InsightCoach {...noDataProps} />);
      expect(screen.getByText(/Log your first activity to unlock AI-powered sustainability coaching/)).toBeInTheDocument();
    });

    it('empty state has correct id', () => {
      render(<InsightCoach {...noDataProps} />);
      expect(screen.getByText(/Log your first activity/).closest('#coach-empty-state')).not.toBeNull();
    });

    it('does not show request insights button when no data', () => {
      render(<InsightCoach {...noDataProps} />);
      expect(screen.queryByLabelText(/Request personalised sustainability insights/)).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Request insights button
  // -------------------------------------------------------------------------

  describe('request insights button', () => {
    it('shows request insights button when data exists', () => {
      render(<InsightCoach {...defaultProps} />);
      expect(screen.getByLabelText(/Request personalised sustainability insights/)).toBeInTheDocument();
    });

    it('request insights button has correct text', () => {
      render(<InsightCoach {...defaultProps} />);
      expect(screen.getByText(/Get AI Insights/)).toBeInTheDocument();
    });

    it('clicking request insights button triggers API call', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      expect(mockPostInsightsRequest).toHaveBeenCalledTimes(1);
    });

    it('request insights button is not shown after insights are loaded', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.queryByLabelText(/Request personalised sustainability insights/)).not.toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  describe('loading state', () => {
    it('shows loading state while fetching insights', async () => {
      mockPostInsightsRequest.mockReturnValue(new Promise(() => {}));
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText(/Analysing your footprint with Gemini/)).toBeInTheDocument();
      });
    });

    it('loading state has role=status and aria-busy=true', async () => {
      mockPostInsightsRequest.mockReturnValue(new Promise(() => {}));
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        const loadingEl = screen.getByRole('status');
        expect(loadingEl).toHaveAttribute('aria-busy', 'true');
      });
    });

    it('loading state has aria-label for screen readers', async () => {
      mockPostInsightsRequest.mockReturnValue(new Promise(() => {}));
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        const loadingEl = screen.getByRole('status');
        expect(loadingEl).toHaveAttribute('aria-label', 'Generating sustainability insights from Gemini AI');
      });
    });
  });

  // -------------------------------------------------------------------------
  // Insights content display
  // -------------------------------------------------------------------------

  describe('insights content display', () => {
    it('displays the insight text after successful response', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText(mockInsightsResponse.insight)).toBeInTheDocument();
      });
    });

    it('displays the equivalent impact after successful response', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText(/Equivalent to driving 65 km/)).toBeInTheDocument();
      });
    });

    it('displays actionable steps after successful response', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText('Switch to public transit for daily commutes')).toBeInTheDocument();
        expect(screen.getByText('Consider carpooling twice a week')).toBeInTheDocument();
        expect(screen.getByText('Try cycling for trips under 5 km')).toBeInTheDocument();
      });
    });

    it('displays model used after successful response', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText('gemini-2.5-flash')).toBeInTheDocument();
      });
    });

    it('displays section headings', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText('Your Carbon Assessment')).toBeInTheDocument();
        expect(screen.getByText('Real-World Impact')).toBeInTheDocument();
        expect(screen.getByText('Your Action Plan')).toBeInTheDocument();
      });
    });

    it('shows refresh button after insights are loaded', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByLabelText(/Refresh AI sustainability insights/)).toBeInTheDocument();
      });
    });

    it('clicking refresh button triggers a new API call', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByLabelText(/Refresh AI sustainability insights/)).toBeInTheDocument();
      });

      const refreshBtn = screen.getByLabelText(/Refresh AI sustainability insights/);
      await userEvent.click(refreshBtn);

      expect(mockPostInsightsRequest).toHaveBeenCalledTimes(2);
    });
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  describe('error state', () => {
    it('shows error message when API call fails', async () => {
      mockPostInsightsRequest.mockResolvedValue({
        success: false,
        error: { code: 'network', message: 'Network error — backend unreachable' },
      });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText(/Insight generation failed/)).toBeInTheDocument();
      });
    });

    it('shows error code in error message', async () => {
      mockPostInsightsRequest.mockResolvedValue({
        success: false,
        error: { code: 500, message: 'HTTP 500' },
      });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText(/Insight generation failed \(500\)/)).toBeInTheDocument();
      });
    });

    it('shows error detail when available', async () => {
      mockPostInsightsRequest.mockResolvedValue({
        success: false,
        error: { code: 429, message: 'HTTP 429', detail: 'Rate limit exceeded' },
      });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText(/Rate limit exceeded/)).toBeInTheDocument();
      });
    });

    it('shows retry hint in error state', async () => {
      mockPostInsightsRequest.mockResolvedValue({
        success: false,
        error: { code: 'network', message: 'Network error' },
      });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByText(/Please try again in a moment/)).toBeInTheDocument();
      });
    });

    it('error region has role=alert and aria-live=assertive', async () => {
      mockPostInsightsRequest.mockResolvedValue({
        success: false,
        error: { code: 'network', message: 'Network error' },
      });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        const errorEl = screen.getByRole('alert');
        expect(errorEl).toHaveAttribute('aria-live', 'assertive');
      });
    });
  });

  // -------------------------------------------------------------------------
  // ForwardRef / requestInsights method
  // -------------------------------------------------------------------------

  describe('forwardRef / requestInsights method', () => {
    it('exposes requestInsights via ref', () => {
      const ref = React.createRef<InsightCoachHandle>();
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach ref={ref} {...defaultProps} />);

      expect(ref.current).not.toBeNull();
      expect(ref.current?.requestInsights).toBeDefined();
      expect(typeof ref.current?.requestInsights).toBe('function');
    });

    it('calling requestInsights via ref triggers API call', async () => {
      const ref = React.createRef<InsightCoachHandle>();
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach ref={ref} {...defaultProps} />);

      await act(async () => {
        ref.current?.requestInsights();
      });

      expect(mockPostInsightsRequest).toHaveBeenCalledTimes(1);
    });

    it('calling requestInsights via ref displays insights', async () => {
      const ref = React.createRef<InsightCoachHandle>();
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach ref={ref} {...defaultProps} />);

      await act(async () => {
        ref.current?.requestInsights();
      });

      await waitFor(() => {
        expect(screen.getByText(mockInsightsResponse.insight)).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Accessibility
  // -------------------------------------------------------------------------

  describe('accessibility', () => {
    it('response region has aria-live=polite', () => {
      render(<InsightCoach {...defaultProps} />);
      const region = screen.getByLabelText('AI coach response');
      expect(region).toHaveAttribute('aria-live', 'polite');
    });

    it('response region has role=region', () => {
      render(<InsightCoach {...defaultProps} />);
      const region = screen.getByLabelText('AI coach response');
      expect(region).toHaveAttribute('role', 'region');
    });

    it('response region has aria-atomic=true', () => {
      render(<InsightCoach {...defaultProps} />);
      const region = screen.getByLabelText('AI coach response');
      expect(region).toHaveAttribute('aria-atomic', 'true');
    });

    it('action steps list has correct aria-label', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        expect(screen.getByLabelText('Personalised action steps')).toBeInTheDocument();
      });
    });

    it('action steps list is an ordered list', async () => {
      mockPostInsightsRequest.mockResolvedValue({ success: true, data: mockInsightsResponse });
      render(<InsightCoach {...defaultProps} />);

      const btn = screen.getByLabelText(/Request personalised sustainability insights/);
      await userEvent.click(btn);

      await waitFor(() => {
        const stepsList = screen.getByLabelText('Personalised action steps');
        expect(stepsList.tagName).toBe('OL');
      });
    });

    it('request insights button has descriptive aria-label', () => {
      render(<InsightCoach {...defaultProps} />);
      const btn = screen.getByLabelText(/Request personalised sustainability insights from AI coach/);
      expect(btn).toBeInTheDocument();
    });
  });
});
