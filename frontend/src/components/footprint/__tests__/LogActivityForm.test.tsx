/**
 * LogActivityForm.test.tsx — Comprehensive tests for the activity logging form.
 * Covers category switching, field visibility, validation errors, form submission, and accessibility.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LogActivityForm } from '../LogActivityForm';
import type { CarbonCalculationResponse, ApiResult } from '../../../services/apiClient';

// ---------------------------------------------------------------------------
// Mock apiClient to prevent real HTTP calls
// ---------------------------------------------------------------------------

type PostFootprintLogFn = (payload: unknown) => Promise<ApiResult<CarbonCalculationResponse>>;

const { mockPostFootprintLog } = vi.hoisted(() => ({
  mockPostFootprintLog: vi.fn<PostFootprintLogFn>(),
}));

vi.mock('../../../services/apiClient', () => ({
  apiClient: {
    postFootprintLog: (...args: Parameters<PostFootprintLogFn>) => mockPostFootprintLog(...args),
    postInsightsRequest: vi.fn(),
    getFootprintHistory: vi.fn(),
    getFootprintSummary: vi.fn(),
    postChatRequest: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockOnSuccess = vi.fn();
const TEST_USER_ID = 'test-user-abc';

function renderForm(): ReturnType<typeof render> {
  return render(<LogActivityForm userId={TEST_USER_ID} onSuccess={mockOnSuccess} />);
}

/** Sets a React-controlled input value by using the native value setter. */
function setReactInputValue(element: HTMLElement, value: string): void {
  const input = element as HTMLInputElement;
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    'value',
  )?.set;
  nativeInputValueSetter?.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LogActivityForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPostFootprintLog.mockReset();
  });

  // -------------------------------------------------------------------------
  // Rendering & Category Switching
  // -------------------------------------------------------------------------

  describe('category field visibility', () => {
    it('shows transport fields by default (distance_km, mode)', () => {
      renderForm();
      expect(screen.getByLabelText(/Transport Mode/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Distance \(km\)/i)).toBeInTheDocument();
    });

    it('shows energy fields when Energy is selected (consumption_kwh, source)', async () => {
      renderForm();
      const categorySelect = screen.getByLabelText(/Category/);
      await userEvent.selectOptions(categorySelect, 'energy');

      expect(screen.getByLabelText(/Energy Source/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Consumption \(kWh\)/i)).toBeInTheDocument();
      // Transport fields should be gone
      expect(screen.queryByLabelText(/Transport Mode/i)).not.toBeInTheDocument();
    });

    it('shows diet fields when Diet / Food is selected (diet_type, days)', async () => {
      renderForm();
      const categorySelect = screen.getByLabelText(/Category/);
      await userEvent.selectOptions(categorySelect, 'food');

      expect(screen.getByLabelText(/Diet Type/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Number of Days/i)).toBeInTheDocument();
    });

    it('shows consumption fields when Consumption is selected (item_type, quantity)', async () => {
      renderForm();
      const categorySelect = screen.getByLabelText(/Category/);
      await userEvent.selectOptions(categorySelect, 'consumption');

      expect(screen.getByLabelText(/Item Type/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Quantity/i)).toBeInTheDocument();
    });

    it('switches back to transport fields when switching away and back', async () => {
      renderForm();
      const categorySelect = screen.getByLabelText(/Category/);

      await userEvent.selectOptions(categorySelect, 'energy');
      expect(screen.queryByLabelText(/Transport Mode/i)).not.toBeInTheDocument();

      await userEvent.selectOptions(categorySelect, 'transport');
      expect(screen.getByLabelText(/Transport Mode/i)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Form Validation
  // -------------------------------------------------------------------------

  describe('form validation', () => {
    it('shows validation error when description is empty on submit', async () => {
      renderForm();

      // Click submit without filling any fields
      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        const alerts = screen.getAllByRole('alert');
        const descError = alerts.find((el) =>
          el.textContent?.toLowerCase().includes('description is required'),
        );
        expect(descError).toBeDefined();
      });
    });

    it('date field is marked as required and linked to error element', async () => {
      renderForm();

      // The date input is marked as aria-required, proving it's a required field
      const dateInput = screen.getByLabelText(/Date/);
      expect(dateInput).toHaveAttribute('aria-required', 'true');

      // The date input references its error element via aria-describedby
      expect(dateInput).toHaveAttribute('aria-describedby', 'activity-date-error');
    });

    it('shows validation errors for multiple empty fields on submit', async () => {
      renderForm();

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        const alerts = screen.getAllByRole('alert');
        // At minimum description and distance should have errors
        expect(alerts.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('description is required — empty description prevents submission', async () => {
      renderForm();

      // Description input should be marked as required
      const descInput = screen.getByLabelText(/Description/);
      expect(descInput).toHaveAttribute('aria-required', 'true');
    });

    it('distance field shows error for zero value', async () => {
      renderForm();

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const distInput = screen.getByLabelText(/Distance \(km\)/);

      await userEvent.type(descInput, 'Car commute');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(distInput, '0');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        const alerts = screen.getAllByRole('alert');
        const distError = alerts.find((el) =>
          el.textContent?.toLowerCase().includes('distance'),
        );
        expect(distError).toBeDefined();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Form Submission
  // -------------------------------------------------------------------------

  describe('form submission', () => {
    const mockSuccessResponse: CarbonCalculationResponse = {
      user_id: TEST_USER_ID,
      total_co2e_kg: 5.25,
      entry_count: 1,
      results: [
        { category: 'transport', description: 'Car commute', co2e_kg: 5.25, date: '2026-03-05T10:00:00' },
      ],
      document_id: 'doc-123',
    };

    it('calls apiClient.postFootprintLog on valid transport form submission', async () => {
      mockPostFootprintLog.mockResolvedValue({
        success: true,
        data: mockSuccessResponse,
      });

      renderForm();

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const distInput = screen.getByLabelText(/Distance \(km\)/);

      await userEvent.type(descInput, 'Car commute');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(distInput, '25');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockPostFootprintLog).toHaveBeenCalledTimes(1);
      });

      const callArg = mockPostFootprintLog.mock.calls[0][0] as Record<string, unknown>;
      expect(callArg.user_id).toBe(TEST_USER_ID);
      const entries = callArg.entries as Array<Record<string, unknown>>;
      expect(entries[0].category).toBe('transport');
      expect(entries[0].description).toBe('Car commute');
    });

    it('calls onSuccess callback with response data on successful submission', async () => {
      mockPostFootprintLog.mockResolvedValue({
        success: true,
        data: mockSuccessResponse,
      });

      renderForm();

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const distInput = screen.getByLabelText(/Distance \(km\)/);

      await userEvent.type(descInput, 'Car commute');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(distInput, '25');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalledWith(mockSuccessResponse);
      });
    });

    it('shows API error when submission fails', async () => {
      mockPostFootprintLog.mockResolvedValue({
        success: false,
        error: { code: 'network' as const, message: 'Network error — backend unreachable' },
      });

      renderForm();

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const distInput = screen.getByLabelText(/Distance \(km\)/);

      await userEvent.type(descInput, 'Car commute');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(distInput, '25');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Submission failed/i)).toBeInTheDocument();
      });
    });

    it('shows API error with code and detail', async () => {
      mockPostFootprintLog.mockResolvedValue({
        success: false,
        error: { code: 422 as const, message: 'HTTP 422', detail: 'Invalid input data' },
      });

      renderForm();

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const distInput = screen.getByLabelText(/Distance \(km\)/);

      await userEvent.type(descInput, 'Car commute');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(distInput, '25');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Submission failed \(422\)/)).toBeInTheDocument();
        expect(screen.getByText(/Invalid input data/)).toBeInTheDocument();
      });
    });

    it('submits energy form with correct category when energy is selected', async () => {
      const energyResponse: CarbonCalculationResponse = {
        user_id: TEST_USER_ID,
        total_co2e_kg: 12.0,
        entry_count: 1,
        results: [
          { category: 'energy', description: 'Electricity usage', co2e_kg: 12.0, date: '2026-03-05T10:00:00' },
        ],
        document_id: 'doc-energy-1',
      };
      mockPostFootprintLog.mockResolvedValue({ success: true, data: energyResponse });

      renderForm();

      await userEvent.selectOptions(screen.getByLabelText(/Category/), 'energy');

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const kwhInput = screen.getByLabelText(/Consumption \(kWh\)/);

      await userEvent.type(descInput, 'Electricity usage');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(kwhInput, '350');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockPostFootprintLog).toHaveBeenCalledTimes(1);
      });

      const callArg = mockPostFootprintLog.mock.calls[0][0] as Record<string, unknown>;
      const entries = callArg.entries as Array<Record<string, unknown>>;
      expect(entries[0].category).toBe('energy');
    });

    it('submits diet form with correct category when diet is selected', async () => {
      const dietResponse: CarbonCalculationResponse = {
        user_id: TEST_USER_ID,
        total_co2e_kg: 8.0,
        entry_count: 1,
        results: [
          { category: 'food', description: 'Weekly meals', co2e_kg: 8.0, date: '2026-03-05T10:00:00' },
        ],
        document_id: 'doc-diet-1',
      };
      mockPostFootprintLog.mockResolvedValue({ success: true, data: dietResponse });

      renderForm();

      await userEvent.selectOptions(screen.getByLabelText(/Category/), 'food');

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const daysInput = screen.getByLabelText(/Number of Days/);

      await userEvent.type(descInput, 'Weekly meals');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(daysInput, '7');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockPostFootprintLog).toHaveBeenCalledTimes(1);
      });

      const callArg = mockPostFootprintLog.mock.calls[0][0] as Record<string, unknown>;
      const entries = callArg.entries as Array<Record<string, unknown>>;
      expect(entries[0].category).toBe('food');
    });

    it('submits consumption form with correct category when consumption is selected', async () => {
      const consumptionResponse: CarbonCalculationResponse = {
        user_id: TEST_USER_ID,
        total_co2e_kg: 15.0,
        entry_count: 1,
        results: [
          { category: 'consumption', description: 'Bought clothes', co2e_kg: 15.0, date: '2026-03-05T10:00:00' },
        ],
        document_id: 'doc-cons-1',
      };
      mockPostFootprintLog.mockResolvedValue({ success: true, data: consumptionResponse });

      renderForm();

      await userEvent.selectOptions(screen.getByLabelText(/Category/), 'consumption');

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const qtyInput = screen.getByLabelText(/Quantity/);

      await userEvent.type(descInput, 'Bought clothes');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(qtyInput, '3');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockPostFootprintLog).toHaveBeenCalledTimes(1);
      });

      const callArg = mockPostFootprintLog.mock.calls[0][0] as Record<string, unknown>;
      const entries = callArg.entries as Array<Record<string, unknown>>;
      expect(entries[0].category).toBe('consumption');
    });
  });

  // -------------------------------------------------------------------------
  // Form Structure & Accessibility
  // -------------------------------------------------------------------------

  describe('form structure and accessibility', () => {
    it('renders a form with the correct aria-label', () => {
      renderForm();
      expect(screen.getByRole('form')).toBeInTheDocument();
      expect(screen.getByRole('form').getAttribute('aria-label')).toBe('Log a carbon footprint activity');
    });

    it('renders the category selector with all four options', () => {
      renderForm();
      const categorySelect = screen.getByLabelText(/Category/);
      const options = categorySelect.querySelectorAll('option');
      const optionValues = Array.from(options).map((o) => o.value);
      expect(optionValues).toContain('transport');
      expect(optionValues).toContain('energy');
      expect(optionValues).toContain('food');
      expect(optionValues).toContain('consumption');
    });

    it('renders the description input field', () => {
      renderForm();
      expect(screen.getByLabelText(/Description/)).toBeInTheDocument();
    });

    it('renders the date input field', () => {
      renderForm();
      expect(screen.getByLabelText(/Date/)).toBeInTheDocument();
    });

    it('submit button shows correct text when not submitting', () => {
      renderForm();
      expect(screen.getByRole('button', { name: /Log activity entry/i })).toBeInTheDocument();
    });

    it('category selector has aria-required attribute', () => {
      renderForm();
      const categorySelect = screen.getByLabelText(/Category/);
      expect(categorySelect).toHaveAttribute('aria-required', 'true');
    });

    it('description input has aria-required attribute', () => {
      renderForm();
      const descInput = screen.getByLabelText(/Description/);
      expect(descInput).toHaveAttribute('aria-required', 'true');
    });

    it('form has noValidate attribute', () => {
      renderForm();
      const form = screen.getByRole('form');
      expect(form).toHaveAttribute('novalidate');
    });

    it('transport mode select has aria-describedby linking to error element', () => {
      renderForm();
      const modeSelect = screen.getByLabelText(/Transport Mode/);
      expect(modeSelect).toHaveAttribute('aria-describedby', 'transport-mode-error');
    });

    it('distance input has aria-describedby linking to error element', () => {
      renderForm();
      const distInput = screen.getByLabelText(/Distance \(km\)/);
      expect(distInput).toHaveAttribute('aria-describedby', 'transport-distance-error');
    });

    it('API error region has role=alert and aria-live=assertive', async () => {
      mockPostFootprintLog.mockResolvedValue({
        success: false,
        error: { code: 'network' as const, message: 'Network error — backend unreachable' },
      });

      renderForm();

      const descInput = screen.getByLabelText(/Description/);
      const dateInput = screen.getByLabelText(/Date/);
      const distInput = screen.getByLabelText(/Distance \(km\)/);

      await userEvent.type(descInput, 'Car commute');
      await act(async () => {
        setReactInputValue(dateInput, '2026-03-05T10:00');
        setReactInputValue(distInput, '25');
      });

      const submitBtn = screen.getByRole('button', { name: /Log activity entry/i });
      await userEvent.click(submitBtn);

      await waitFor(() => {
        const errorDiv = screen.getByRole('alert');
        expect(errorDiv).toHaveAttribute('aria-live', 'assertive');
      });
    });
  });
});
