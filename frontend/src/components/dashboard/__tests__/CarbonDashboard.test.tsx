/**
 * CarbonDashboard.test.tsx — Comprehensive tests for the CarbonDashboard component.
 * Covers rendering, data fetching, empty states, summary stats, demo data,
 * chart placeholders, and activity log items.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { CarbonDashboard } from '../CarbonDashboard';
import type {
  CarbonCalculationResponse,
  EmissionSummaryEntry,
  ApiResult,
  FootprintHistoryResponse,
} from '../../../services/apiClient';

// ---------------------------------------------------------------------------
// Mock apiClient — prevent real HTTP calls
// ---------------------------------------------------------------------------

const { mockGetFootprintHistory } = vi.hoisted(() => ({
  mockGetFootprintHistory: vi.fn<
    (userId: string, periodDays?: number) => Promise<ApiResult<FootprintHistoryResponse>>
  >(),
}));

vi.mock('../../../services/apiClient', () => ({
  apiClient: {
    getFootprintHistory: (...args: Parameters<typeof mockGetFootprintHistory>) =>
      mockGetFootprintHistory(...args),
    postFootprintLog: vi.fn(),
    postInsightsRequest: vi.fn(),
    postChatRequest: vi.fn(),
    getFootprintSummary: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Mock child components
// ---------------------------------------------------------------------------

vi.mock('../../footprint/LogActivityForm', () => ({
  LogActivityForm: () => (
    <div data-testid="log-activity-form">LogActivityForm Mock</div>
  ),
}));

vi.mock('../../coach/InsightCoach', () => ({
  InsightCoach: React.forwardRef(() => <div data-testid="insight-coach">InsightCoach Mock</div>),
}));

vi.mock('../../coach/ChatCoach', () => ({
  ChatCoach: () => <div data-testid="chat-coach">ChatCoach Mock</div>,
}));

vi.mock('../../ui/Toast', () => ({
  useToast: () => ({ addToast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// Mock recharts to avoid jsdom rendering issues
vi.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: () => null,
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
}));

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function makeLog(overrides: Partial<CarbonCalculationResponse> = {}): CarbonCalculationResponse {
  return {
    user_id: 'demo-user-001',
    total_co2e_kg: 10.5,
    entry_count: 1,
    document_id: 'doc-1',
    results: [
      { category: 'transport', description: 'Car commute', co2e_kg: 10.5, date: '2025-06-01' },
    ],
    ...overrides,
  };
}

function makeLogWithMultipleResults(): CarbonCalculationResponse {
  return {
    user_id: 'demo-user-001',
    total_co2e_kg: 15.5,
    entry_count: 2,
    document_id: 'doc-multi',
    results: [
      { category: 'transport', description: 'Car commute', co2e_kg: 10.5, date: '2025-06-01' },
      { category: 'energy', description: 'Electricity usage', co2e_kg: 5.0, date: '2025-06-01' },
    ],
  };
}

const successHistoryResponse: FootprintHistoryResponse = {
  user_id: 'demo-user-001',
  logs: [makeLog()],
  count: 1,
  period_days: 30,
  page: 1,
  page_size: 20,
  total_pages: 1,
  has_next: false,
};

const emptyHistoryResponse: FootprintHistoryResponse = {
  user_id: 'demo-user-001',
  logs: [],
  count: 0,
  period_days: 30,
  page: 1,
  page_size: 20,
  total_pages: 0,
  has_next: false,
};

// ---------------------------------------------------------------------------
// Utility function tests (replicate the logic from CarbonDashboard)
// ---------------------------------------------------------------------------

function buildEmissionBreakdown(
  logs: readonly CarbonCalculationResponse[],
): EmissionSummaryEntry[] {
  const categoryMap = new Map<string, { total: number; count: number; desc: string }>();
  for (const log of logs) {
    for (const result of log.results) {
      const existing = categoryMap.get(result.category);
      if (existing !== undefined) {
        categoryMap.set(result.category, {
          total: existing.total + result.co2e_kg,
          count: existing.count + 1,
          desc: existing.desc,
        });
      } else {
        categoryMap.set(result.category, {
          total: result.co2e_kg,
          count: 1,
          desc: result.description,
        });
      }
    }
  }
  return Array.from(categoryMap.entries()).map(([category, data]) => ({
    category,
    total_co2e_kg: Math.round(data.total * 10000) / 10000,
    entry_count: data.count,
    description: data.desc,
  }));
}

function computeTotalCo2e(logs: readonly CarbonCalculationResponse[]): number {
  return Math.round(logs.reduce((sum, log) => sum + log.total_co2e_kg, 0) * 10000) / 10000;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CarbonDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetFootprintHistory.mockReset();
  });

  // -------------------------------------------------------------------------
  // Utility function tests
  // -------------------------------------------------------------------------

  describe('buildEmissionBreakdown', () => {
    it('returns empty array for no logs', () => {
      expect(buildEmissionBreakdown([])).toEqual([]);
    });

    it('aggregates a single log with one result', () => {
      const logs = [makeLog()];
      const breakdown = buildEmissionBreakdown(logs);
      expect(breakdown).toHaveLength(1);
      expect(breakdown[0].category).toBe('transport');
      expect(breakdown[0].total_co2e_kg).toBe(10.5);
      expect(breakdown[0].entry_count).toBe(1);
      expect(breakdown[0].description).toBe('Car commute');
    });

    it('aggregates multiple results in the same category', () => {
      const logs = [
        makeLog({
          total_co2e_kg: 10,
          document_id: 'doc-1',
          results: [
            { category: 'transport', description: 'Car commute', co2e_kg: 10, date: '2025-06-01' },
          ],
        }),
        makeLog({
          total_co2e_kg: 5,
          document_id: 'doc-2',
          results: [
            { category: 'transport', description: 'Bus ride', co2e_kg: 5, date: '2025-06-02' },
          ],
        }),
      ];
      const breakdown = buildEmissionBreakdown(logs);
      expect(breakdown).toHaveLength(1);
      expect(breakdown[0].category).toBe('transport');
      expect(breakdown[0].total_co2e_kg).toBe(15);
      expect(breakdown[0].entry_count).toBe(2);
    });

    it('separates different categories', () => {
      const logs = [
        makeLog({
          total_co2e_kg: 10,
          document_id: 'doc-1',
          results: [
            { category: 'transport', description: 'Car', co2e_kg: 10, date: '2025-06-01' },
            { category: 'energy', description: 'Electricity', co2e_kg: 3, date: '2025-06-01' },
          ],
        }),
      ];
      const breakdown = buildEmissionBreakdown(logs);
      expect(breakdown).toHaveLength(2);
      const categories = breakdown.map((b) => b.category);
      expect(categories).toContain('transport');
      expect(categories).toContain('energy');
    });

    it('rounds totals to 4 decimal places', () => {
      const logs = [
        makeLog({
          total_co2e_kg: 1.11111,
          document_id: 'doc-1',
          results: [
            { category: 'transport', description: 'Car', co2e_kg: 1.11111, date: '2025-06-01' },
          ],
        }),
      ];
      const breakdown = buildEmissionBreakdown(logs);
      expect(breakdown[0].total_co2e_kg).toBe(1.1111);
    });
  });

  describe('computeTotalCo2e', () => {
    it('returns 0 for no logs', () => {
      expect(computeTotalCo2e([])).toBe(0);
    });

    it('returns total_co2e_kg for a single log', () => {
      const logs = [makeLog({ total_co2e_kg: 10.5 })];
      expect(computeTotalCo2e(logs)).toBe(10.5);
    });

    it('sums multiple logs', () => {
      const logs = [
        makeLog({ total_co2e_kg: 10.5 }),
        makeLog({ total_co2e_kg: 5.25, document_id: 'doc-2' }),
      ];
      expect(computeTotalCo2e(logs)).toBe(15.75);
    });

    it('rounds to 4 decimal places', () => {
      const logs = [makeLog({ total_co2e_kg: 1.11111 })];
      expect(computeTotalCo2e(logs)).toBe(1.1111);
    });
  });

  // -------------------------------------------------------------------------
  // Component rendering tests
  // -------------------------------------------------------------------------

  describe('component rendering', () => {
    it('renders the dashboard section with correct aria-label', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      expect(screen.getByLabelText('Carbon Footprint Dashboard')).toBeInTheDocument();
    });

    it('renders the Log Activity section', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      expect(screen.getByText('Log Activity')).toBeInTheDocument();
    });

    it('renders the Activity History section', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      expect(screen.getByText('Activity History')).toBeInTheDocument();
    });

    it('renders the LogActivityForm', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      expect(screen.getByTestId('log-activity-form')).toBeInTheDocument();
    });

    it('renders the InsightCoach', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      expect(screen.getByTestId('insight-coach')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // History fetching on mount
  // -------------------------------------------------------------------------

  describe('history fetching on mount', () => {
    it('calls getFootprintHistory with userId and 30 days on mount', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      expect(mockGetFootprintHistory).toHaveBeenCalledWith('demo-user-001', 30);
    });

    it('shows loading state initially', () => {
      // Never resolve to keep loading state
      mockGetFootprintHistory.mockReturnValue(new Promise(() => {}));
      render(<CarbonDashboard userId="demo-user-001" />);
      expect(screen.getByText('Loading activity history...')).toBeInTheDocument();
    });

    it('shows empty state when no logs are returned', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText(/No activities logged yet/)).toBeInTheDocument();
      });
    });

    it('shows activity log items when logs exist', async () => {
      const logData = makeLog();
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [logData] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('10.5 kg CO₂e')).toBeInTheDocument();
      });
    });

    it('hides loading state after fetch completes', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.queryByText('Loading activity history...')).not.toBeInTheDocument();
      });
    });

    it('hides loading state even when API returns error', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: false,
        error: { code: 'network', message: 'Network error' },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.queryByText('Loading activity history...')).not.toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Summary stats rendering
  // -------------------------------------------------------------------------

  describe('SummaryStats', () => {
    it('renders summary stats even when no logs exist', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByLabelText('Carbon footprint summary statistics')).toBeInTheDocument();
      });
    });

    it('renders summary stats when logs exist', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByLabelText('Carbon footprint summary statistics')).toBeInTheDocument();
      });
    });

    it('renders total CO₂e stat when logs exist', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByLabelText(/Total CO₂e: 10.50 kg/)).toBeInTheDocument();
      });
    });

    it('renders Activities Logged stat when logs exist', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByLabelText(/Activities Logged: 1 entries/)).toBeInTheDocument();
      });
    });

    it('renders Categories stat when logs exist', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByLabelText(/Categories: 1 types/)).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Activity log list
  // -------------------------------------------------------------------------

  describe('ActivityLogList', () => {
    it('renders empty state when no logs', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByRole('status', { name: undefined })).toBeInTheDocument();
        expect(screen.getByText(/No activities logged yet/)).toBeInTheDocument();
      });
    });

    it('renders "Load Demo Data" button when no logs', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('Load Demo Data')).toBeInTheDocument();
      });
    });

    it('loads demo data when "Load Demo Data" button is clicked', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('Load Demo Data')).toBeInTheDocument();
      });
      const demoBtn = screen.getByText('Load Demo Data');
      await act(async () => {
        fireEvent.click(demoBtn);
      });
      // After clicking, demo data should be loaded — verify activity items appear
      await waitFor(() => {
        expect(screen.getByText('Daily commute by car')).toBeInTheDocument();
      });
    });

    it('renders activity log items with correct content', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('Car commute')).toBeInTheDocument();
        expect(screen.getByText('10.5 kg')).toBeInTheDocument();
      });
    });

    it('renders multiple logs', async () => {
      const logs = [
        makeLog({ document_id: 'doc-1' }),
        makeLog({ document_id: 'doc-2', total_co2e_kg: 5.0, results: [
          { category: 'energy', description: 'Solar panel', co2e_kg: 5.0, date: '2025-06-02' },
        ] }),
      ];
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('Car commute')).toBeInTheDocument();
        expect(screen.getByText('Solar panel')).toBeInTheDocument();
      });
    });

    it('renders log entry count correctly', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('1 entry')).toBeInTheDocument();
      });
    });

    it('renders "entries" plural for multiple entries in a log', async () => {
      const log = makeLogWithMultipleResults();
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [log] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('2 entries')).toBeInTheDocument();
      });
    });

    it('renders activity list with correct aria-label', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByLabelText('Logged carbon footprint activities')).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Emission chart section
  // -------------------------------------------------------------------------

  describe('Emission chart section', () => {
    it('renders chart placeholder when no breakdown data', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('Emission Breakdown')).toBeInTheDocument();
        expect(screen.getByText(/Log activities or load demo data/)).toBeInTheDocument();
      });
    });

    it('renders emission chart section when logs exist', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByText('Emission Breakdown')).toBeInTheDocument();
      });
    });

    it('renders emission chart with correct aria-label', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByLabelText('Emission breakdown chart showing CO2e by category')).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // ChatCoach visibility — always rendered
  // -------------------------------------------------------------------------

  describe('ChatCoach visibility', () => {
    it('renders ChatCoach even when no logs exist', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByTestId('chat-coach')).toBeInTheDocument();
      });
    });

    it('renders ChatCoach when breakdown data exists', async () => {
      mockGetFootprintHistory.mockResolvedValue({
        success: true,
        data: { ...successHistoryResponse, logs: [makeLog()] },
      });
      render(<CarbonDashboard userId="demo-user-001" />);
      await waitFor(() => {
        expect(screen.getByTestId('chat-coach')).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Accessibility
  // -------------------------------------------------------------------------

  describe('Accessibility', () => {
    it('main section has correct aria-label', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      expect(screen.getByLabelText('Carbon Footprint Dashboard')).toBeInTheDocument();
    });

    it('aside has correct aria-label', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      expect(screen.getByLabelText('AI Sustainability Coaching')).toBeInTheDocument();
    });

    it('log activity section has aria-labelledby', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      const section = screen.getByText('Log Activity').closest('section');
      expect(section).toHaveAttribute('aria-labelledby', 'log-activity-section-heading');
    });

    it('activity history section has aria-labelledby', async () => {
      mockGetFootprintHistory.mockResolvedValue({ success: true, data: emptyHistoryResponse });
      await act(async () => {
        render(<CarbonDashboard userId="demo-user-001" />);
      });
      const section = screen.getByText('Activity History').closest('section');
      expect(section).toHaveAttribute('aria-labelledby', 'activity-history-section-heading');
    });

    it('loading state has role=status and aria-busy=true', () => {
      mockGetFootprintHistory.mockReturnValue(new Promise(() => {}));
      render(<CarbonDashboard userId="demo-user-001" />);
      const loadingEl = screen.getByText('Loading activity history...');
      expect(loadingEl).toHaveAttribute('role', 'status');
      expect(loadingEl).toHaveAttribute('aria-busy', 'true');
    });
  });
});
