/**
 * DataExport.test.tsx — Tests for the DataExport component.
 * Covers: renders button, disabled when no logs, generates CSV on click,
 * CSV format verification, and accessibility.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DataExport } from '../DataExport';
import type { CarbonCalculationResponse } from '../../../services/apiClient';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function makeLog(overrides: Partial<CarbonCalculationResponse> = {}): CarbonCalculationResponse {
  return {
    user_id: 'test-user-001',
    total_co2e_kg: 10.5,
    entry_count: 1,
    document_id: 'doc-1',
    results: [
      { category: 'transport', description: 'Car commute', co2e_kg: 10.5, date: '2025-06-01' },
    ],
    ...overrides,
  };
}

const logs: CarbonCalculationResponse[] = [
  makeLog(),
  makeLog({
    total_co2e_kg: 5.0,
    entry_count: 2,
    document_id: 'doc-2',
    results: [
      { category: 'energy', description: 'Electricity usage', co2e_kg: 3.0, date: '2025-06-02' },
      { category: 'food', description: 'Vegetarian meal', co2e_kg: 2.0, date: '2025-06-02' },
    ],
  }),
];

// ---------------------------------------------------------------------------
// CSV generation logic (replicated from component for unit testing)
// ---------------------------------------------------------------------------

function generateCSV(logs: readonly CarbonCalculationResponse[]): string {
  const BOM = '\uFEFF';
  const header = 'Date,Category,Description,CO2e (kg)';
  const rows: string[] = [];

  for (const log of logs) {
    for (const result of log.results) {
      const escapedDesc = escapeCSVField(result.description);
      const date = result.date?.slice(0, 10) ?? 'unknown';
      rows.push(`${date},${result.category},${escapedDesc},${result.co2e_kg}`);
    }
  }

  return BOM + header + '\n' + rows.join('\n');
}

function escapeCSVField(field: string): string {
  if (field.includes(',') || field.includes('"') || field.includes('\n')) {
    return '"' + field.replace(/"/g, '""') + '"';
  }
  return field;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DataExport', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  describe('rendering', () => {
    it('renders the Export Data button', () => {
      render(<DataExport logs={logs} />);
      expect(screen.getByRole('button', { name: /export carbon footprint data as csv/i })).toBeInTheDocument();
    });

    it('renders the button with correct text', () => {
      render(<DataExport logs={logs} />);
      expect(screen.getByText('Export Data')).toBeInTheDocument();
    });

    it('renders the download icon', () => {
      render(<DataExport logs={logs} />);
      expect(screen.getByText('📥')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Disabled state
  // -------------------------------------------------------------------------

  describe('disabled state', () => {
    it('disables the button when no logs exist', () => {
      render(<DataExport logs={[]} />);
      const button = screen.getByRole('button', { name: /export carbon footprint data as csv/i });
      expect(button).toBeDisabled();
    });

    it('enables the button when logs exist', () => {
      render(<DataExport logs={logs} />);
      const button = screen.getByRole('button', { name: /export carbon footprint data as csv/i });
      expect(button).not.toBeDisabled();
    });
  });

  // -------------------------------------------------------------------------
  // CSV generation and download
  // -------------------------------------------------------------------------

  describe('CSV generation and download', () => {
    it('creates a Blob and triggers download when button is clicked', async () => {
      const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-url');
      const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

      const user = userEvent.setup();
      render(<DataExport logs={logs} />);

      const button = screen.getByRole('button', { name: /export carbon footprint data as csv/i });
      await user.click(button);

      expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
      expect(clickSpy).toHaveBeenCalledTimes(1);

      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
      clickSpy.mockRestore();
    });

    it('does not trigger download when button is disabled', async () => {
      const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-url');

      const user = userEvent.setup();
      render(<DataExport logs={[]} />);

      const button = screen.getByRole('button', { name: /export carbon footprint data as csv/i });
      await user.click(button);

      expect(createObjectURLSpy).not.toHaveBeenCalled();

      createObjectURLSpy.mockRestore();
    });
  });

  // -------------------------------------------------------------------------
  // CSV format verification (pure function tests — no DOM needed)
  // -------------------------------------------------------------------------

  describe('CSV format', () => {
    it('generates CSV with correct header row', () => {
      const csv = generateCSV(logs);
      const lines = csv.split('\n');
      expect(lines[0]).toContain('Date,Category,Description,CO2e (kg)');
    });

    it('generates CSV with one row per EmissionResult', () => {
      const csv = generateCSV(logs);
      const lines = csv.split('\n').filter((line) => line.trim().length > 0);

      // Header + 3 data rows (1 from first log + 2 from second log)
      expect(lines).toHaveLength(4);

      // Verify content of first data row
      expect(lines[1]).toContain('2025-06-01');
      expect(lines[1]).toContain('transport');
      expect(lines[1]).toContain('Car commute');
      expect(lines[1]).toContain('10.5');

      // Verify content of second log rows
      expect(lines[2]).toContain('2025-06-02');
      expect(lines[2]).toContain('energy');
      expect(lines[3]).toContain('food');
    });

    it('starts CSV with BOM character for Excel compatibility', () => {
      const csv = generateCSV(logs);
      // BOM is \uFEFF
      expect(csv.charCodeAt(0)).toBe(0xFEFF);
    });

    it('escapes descriptions containing commas in CSV', () => {
      const logsWithCommas: CarbonCalculationResponse[] = [
        makeLog({
          total_co2e_kg: 5.0,
          document_id: 'doc-comma',
          results: [
            { category: 'transport', description: 'Car, bus and train', co2e_kg: 5.0, date: '2025-06-03' },
          ],
        }),
      ];

      const csv = generateCSV(logsWithCommas);
      const dataLine = csv.split('\n')[1];
      // The description with comma should be quoted
      expect(dataLine).toContain('"Car, bus and train"');
    });

    it('escapes descriptions containing double quotes', () => {
      const logsWithQuotes: CarbonCalculationResponse[] = [
        makeLog({
          total_co2e_kg: 3.0,
          document_id: 'doc-quote',
          results: [
            { category: 'food', description: 'A "healthy" meal', co2e_kg: 3.0, date: '2025-06-04' },
          ],
        }),
      ];

      const csv = generateCSV(logsWithQuotes);
      const dataLine = csv.split('\n')[1];
      // Double quotes should be escaped by doubling them
      expect(dataLine).toContain('"A ""healthy"" meal"');
    });

    it('handles empty logs array', () => {
      const csv = generateCSV([]);
      const lines = csv.split('\n');
      // Header line + empty trailing line from the split
      expect(lines[0]).toContain('Date,Category,Description,CO2e (kg)');
      // No data rows — only header content
      expect(lines.filter((line) => line.trim().length > 0)).toHaveLength(1);
    });
  });

  // -------------------------------------------------------------------------
  // Accessibility
  // -------------------------------------------------------------------------

  describe('accessibility', () => {
    it('button has aria-label', () => {
      render(<DataExport logs={logs} />);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Export carbon footprint data as CSV');
    });

    it('aria-label is present even when disabled', () => {
      render(<DataExport logs={[]} />);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Export carbon footprint data as CSV');
      expect(button).toBeDisabled();
    });
  });
});
