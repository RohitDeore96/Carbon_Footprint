/**
 * apiClient.test.ts — Comprehensive tests for the API client module.
 * Covers all API methods, success/error responses, discriminated union return types,
 * and error mapping for various HTTP status codes and network errors.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '../apiClient';
import type {
  CarbonCalculationRequest,
  InsightsRequest,
  ChatRequest,
  CarbonCalculationResponse,
  InsightsResponse,
  ChatResponse,
  FootprintHistoryResponse,
  FootprintSummaryResponse,
} from '../apiClient';

// ---------------------------------------------------------------------------
// Mock axios — use vi.hoisted so mock functions are available when vi.mock runs
// ---------------------------------------------------------------------------

const { mockPost, mockGet } = vi.hoisted(() => ({
  mockPost: vi.fn(),
  mockGet: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    create: () => ({
      post: mockPost,
      get: mockGet,
      defaults: {},
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    }),
  },
}));

// ---------------------------------------------------------------------------
// Mock firebase/auth — getAuth returns an object with no currentUser by default
// ---------------------------------------------------------------------------

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
}));

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const mockCalculationResponse: CarbonCalculationResponse = {
  user_id: 'test-user',
  total_co2e_kg: 5.25,
  entry_count: 1,
  results: [
    { category: 'transport', description: 'Car commute', co2e_kg: 5.25, date: '2026-06-09T10:00:00' },
  ],
  document_id: 'abc123',
};

const mockInsightsResponse: InsightsResponse = {
  user_id: 'test-user',
  insight: 'Your transport emissions are high.',
  equivalent_impact: 'Equivalent to driving 25 km.',
  actionable_steps: ['Use public transit', 'Carpool'],
  model_used: 'gemini-2.5-flash',
};

const mockChatResponse: ChatResponse = {
  user_id: 'test-user',
  response: 'Consider reducing your car usage.',
  suggestions: ['Try cycling', 'Use public transit'],
  model_used: 'gemini-2.5-flash',
};

const mockHistoryResponse: FootprintHistoryResponse = {
  user_id: 'test-user',
  logs: [mockCalculationResponse],
  count: 1,
  period_days: 30,
};

const mockSummaryResponse: FootprintSummaryResponse = {
  user_id: 'test-user',
  period_days: 30,
  total_co2e_kg: 5.25,
  entry_count: 1,
  category_breakdown: [{ category: 'transport', total_co2e_kg: 5.25 }],
};

const samplePayload: CarbonCalculationRequest = {
  user_id: 'test-user',
  entries: [
    {
      category: 'transport',
      description: 'Car commute',
      date: '2026-06-09T10:00:00',
      transport: { mode: 'car', distance_km: 25 },
    },
  ],
  calculation_date: '2026-06-09T10:00:00',
};

const sampleInsightsPayload: InsightsRequest = {
  user_id: 'test-user',
  total_co2e_kg: 5.25,
  period_days: 30,
  emission_breakdown: [
    { category: 'transport', total_co2e_kg: 5.25, entry_count: 1, description: 'Car commute' },
  ],
};

// ---------------------------------------------------------------------------
// Helper to create AxiosError-like objects
// ---------------------------------------------------------------------------

function createAxiosError(
  status?: number,
  data?: unknown,
  hasRequest = false,
): Record<string, unknown> {
  const err: Record<string, unknown> = {
    isAxiosError: true,
    message: status ? `Request failed with status code ${status}` : 'Network Error',
  };
  if (status !== undefined) {
    err.response = { status, data: data ?? {} };
  } else if (hasRequest) {
    err.request = {};
  }
  return err;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPost.mockReset();
    mockGet.mockReset();
  });

  // -------------------------------------------------------------------------
  // Module structure
  // -------------------------------------------------------------------------

  describe('module structure', () => {
    it('should have all required methods', () => {
      expect(apiClient.postFootprintLog).toBeDefined();
      expect(apiClient.postInsightsRequest).toBeDefined();
      expect(apiClient.postChatRequest).toBeDefined();
      expect(apiClient.getFootprintHistory).toBeDefined();
      expect(apiClient.getFootprintSummary).toBeDefined();
    });

    it('all methods are functions', () => {
      expect(typeof apiClient.postFootprintLog).toBe('function');
      expect(typeof apiClient.postInsightsRequest).toBe('function');
      expect(typeof apiClient.postChatRequest).toBe('function');
      expect(typeof apiClient.getFootprintHistory).toBe('function');
      expect(typeof apiClient.getFootprintSummary).toBe('function');
    });
  });

  // -------------------------------------------------------------------------
  // postFootprintLog
  // -------------------------------------------------------------------------

  describe('postFootprintLog', () => {
    it('returns success result on valid payload', async () => {
      mockPost.mockResolvedValue({ data: mockCalculationResponse });

      const result = await apiClient.postFootprintLog(samplePayload);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockCalculationResponse);
        expect(result.data.user_id).toBe('test-user');
        expect(result.data.total_co2e_kg).toBe(5.25);
        expect(result.data.document_id).toBe('abc123');
      }
    });

    it('calls POST with correct endpoint and payload', async () => {
      mockPost.mockResolvedValue({ data: mockCalculationResponse });

      await apiClient.postFootprintLog(samplePayload);

      expect(mockPost).toHaveBeenCalledWith('/api/v1/footprint/log', samplePayload, { signal: undefined });
    });

    it('returns error result on HTTP error with response', async () => {
      mockPost.mockRejectedValue(createAxiosError(422, { detail: 'Invalid input' }));

      const result = await apiClient.postFootprintLog(samplePayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe(422);
        expect(result.error.message).toBe('HTTP 422');
        expect(result.error.detail).toBe('Invalid input');
      }
    });

    it('returns network error when no response received', async () => {
      mockPost.mockRejectedValue(createAxiosError(undefined, undefined, true));

      const result = await apiClient.postFootprintLog(samplePayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe('network');
        expect(result.error.message).toContain('Network error');
      }
    });

    it('returns unknown error for unexpected errors', async () => {
      mockPost.mockRejectedValue(new Error('Something unexpected'));

      const result = await apiClient.postFootprintLog(samplePayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe('unknown');
        expect(result.error.message).toBe('Something unexpected');
      }
    });

    it('returns 429 error for rate limit', async () => {
      mockPost.mockRejectedValue(createAxiosError(429, { detail: 'Too many requests' }));

      const result = await apiClient.postFootprintLog(samplePayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe(429);
        expect(result.error.detail).toBe('Too many requests');
      }
    });

    it('returns 500 error for server error', async () => {
      mockPost.mockRejectedValue(createAxiosError(500));

      const result = await apiClient.postFootprintLog(samplePayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe(500);
      }
    });

    it('returns 403 code for forbidden HTTP status', async () => {
      mockPost.mockRejectedValue(createAxiosError(403));

      const result = await apiClient.postFootprintLog(samplePayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe(403);
      }
    });
  });

  // -------------------------------------------------------------------------
  // postInsightsRequest
  // -------------------------------------------------------------------------

  describe('postInsightsRequest', () => {
    it('returns success result on valid payload', async () => {
      mockPost.mockResolvedValue({ data: mockInsightsResponse });

      const result = await apiClient.postInsightsRequest(sampleInsightsPayload);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockInsightsResponse);
        expect(result.data.insight).toBe('Your transport emissions are high.');
        expect(result.data.actionable_steps).toHaveLength(2);
      }
    });

    it('calls POST with correct endpoint and payload', async () => {
      mockPost.mockResolvedValue({ data: mockInsightsResponse });

      await apiClient.postInsightsRequest(sampleInsightsPayload);

      expect(mockPost).toHaveBeenCalledWith('/api/v1/ai/insights', sampleInsightsPayload, { signal: undefined, timeout: 60000 });
    });

    it('returns error result on HTTP error', async () => {
      mockPost.mockRejectedValue(createAxiosError(500));

      const result = await apiClient.postInsightsRequest(sampleInsightsPayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe(500);
      }
    });

    it('returns network error when no response received', async () => {
      mockPost.mockRejectedValue(createAxiosError(undefined, undefined, true));

      const result = await apiClient.postInsightsRequest(sampleInsightsPayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe('network');
      }
    });
  });

  // -------------------------------------------------------------------------
  // postChatRequest
  // -------------------------------------------------------------------------

  describe('postChatRequest', () => {
    const chatPayload: ChatRequest = {
      user_id: 'test-user',
      message: 'How can I reduce my emissions?',
      total_co2e_kg: 5.25,
      period_days: 30,
      emission_breakdown: sampleInsightsPayload.emission_breakdown,
      conversation_history: [],
    };

    it('returns success result on valid payload', async () => {
      mockPost.mockResolvedValue({ data: mockChatResponse });

      const result = await apiClient.postChatRequest(chatPayload);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockChatResponse);
        expect(result.data.response).toBe('Consider reducing your car usage.');
        expect(result.data.suggestions).toHaveLength(2);
      }
    });

    it('calls POST with correct endpoint and payload', async () => {
      mockPost.mockResolvedValue({ data: mockChatResponse });

      await apiClient.postChatRequest(chatPayload);

      expect(mockPost).toHaveBeenCalledWith('/api/v1/ai/chat', chatPayload, { signal: undefined, timeout: 60000 });
    });

    it('returns error result on HTTP error', async () => {
      mockPost.mockRejectedValue(createAxiosError(429, { detail: 'Rate limit exceeded' }));

      const result = await apiClient.postChatRequest(chatPayload);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe(429);
        expect(result.error.detail).toBe('Rate limit exceeded');
      }
    });
  });

  // -------------------------------------------------------------------------
  // getFootprintHistory
  // -------------------------------------------------------------------------

  describe('getFootprintHistory', () => {
    it('returns success result with history data', async () => {
      mockGet.mockResolvedValue({ data: mockHistoryResponse });

      const result = await apiClient.getFootprintHistory('test-user', 30);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockHistoryResponse);
        expect(result.data.logs).toHaveLength(1);
        expect(result.data.count).toBe(1);
        expect(result.data.period_days).toBe(30);
      }
    });

    it('calls GET with correct endpoint and params', async () => {
      mockGet.mockResolvedValue({ data: mockHistoryResponse });

      await apiClient.getFootprintHistory('test-user', 30);

      expect(mockGet).toHaveBeenCalledWith('/api/v1/footprint/history/test-user', {
        params: { period_days: 30 },
      });
    });

    it('uses default period_days of 30', async () => {
      mockGet.mockResolvedValue({ data: mockHistoryResponse });

      await apiClient.getFootprintHistory('test-user');

      expect(mockGet).toHaveBeenCalledWith('/api/v1/footprint/history/test-user', {
        params: { period_days: 30 },
      });
    });

    it('returns error result on HTTP error', async () => {
      mockGet.mockRejectedValue(createAxiosError(500));

      const result = await apiClient.getFootprintHistory('test-user', 30);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe(500);
      }
    });

    it('returns network error when no response received', async () => {
      mockGet.mockRejectedValue(createAxiosError(undefined, undefined, true));

      const result = await apiClient.getFootprintHistory('test-user', 30);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe('network');
      }
    });
  });

  // -------------------------------------------------------------------------
  // getFootprintSummary
  // -------------------------------------------------------------------------

  describe('getFootprintSummary', () => {
    it('returns success result with summary data', async () => {
      mockGet.mockResolvedValue({ data: mockSummaryResponse });

      const result = await apiClient.getFootprintSummary('test-user', 30);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockSummaryResponse);
        expect(result.data.total_co2e_kg).toBe(5.25);
        expect(result.data.entry_count).toBe(1);
        expect(result.data.category_breakdown).toHaveLength(1);
      }
    });

    it('calls GET with correct endpoint and params', async () => {
      mockGet.mockResolvedValue({ data: mockSummaryResponse });

      await apiClient.getFootprintSummary('test-user', 30);

      expect(mockGet).toHaveBeenCalledWith('/api/v1/footprint/summary/test-user', {
        params: { period_days: 30 },
      });
    });

    it('returns error result on HTTP error', async () => {
      mockGet.mockRejectedValue(createAxiosError(500));

      const result = await apiClient.getFootprintSummary('test-user', 30);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe(500);
      }
    });
  });

  // -------------------------------------------------------------------------
  // Discriminated union type safety
  // -------------------------------------------------------------------------

  describe('ApiResult discriminated union', () => {
    it('success result has success=true and data property', async () => {
      mockPost.mockResolvedValue({ data: mockCalculationResponse });

      const result = await apiClient.postFootprintLog(samplePayload);

      if (result.success) {
        // TypeScript narrows to the success variant
        expect(result.data).toBeDefined();
        expect(result.data.user_id).toBe('test-user');
      }
    });

    it('error result has success=false and error property', async () => {
      mockPost.mockRejectedValue(createAxiosError(422));

      const result = await apiClient.postFootprintLog(samplePayload);

      if (!result.success) {
        // TypeScript narrows to the error variant
        expect(result.error).toBeDefined();
        expect(result.error.code).toBeDefined();
        expect(result.error.message).toBeDefined();
      }
    });

    it('error result includes optional detail field', async () => {
      mockPost.mockRejectedValue(createAxiosError(422, { detail: 'Validation failed' }));

      const result = await apiClient.postFootprintLog(samplePayload);

      if (!result.success) {
        expect(result.error.detail).toBe('Validation failed');
      }
    });

    it('error result detail is undefined when not provided in response', async () => {
      mockPost.mockRejectedValue(createAxiosError(500));

      const result = await apiClient.postFootprintLog(samplePayload);

      if (!result.success) {
        expect(result.error.detail).toBeUndefined();
      }
    });

    it('error result detail is undefined when response data is not an object', async () => {
      mockPost.mockRejectedValue(createAxiosError(500, 'string response'));

      const result = await apiClient.postFootprintLog(samplePayload);

      if (!result.success) {
        expect(result.error.detail).toBeUndefined();
      }
    });
  });

  // -------------------------------------------------------------------------
  // Error code mapping
  // -------------------------------------------------------------------------

  describe('error code mapping', () => {
    it('maps 422 status to code 422', async () => {
      mockPost.mockRejectedValue(createAxiosError(422));
      const result = await apiClient.postFootprintLog(samplePayload);
      if (!result.success) expect(result.error.code).toBe(422);
    });

    it('maps 429 status to code 429', async () => {
      mockPost.mockRejectedValue(createAxiosError(429));
      const result = await apiClient.postFootprintLog(samplePayload);
      if (!result.success) expect(result.error.code).toBe(429);
    });

    it('maps 500 status to code 500', async () => {
      mockPost.mockRejectedValue(createAxiosError(500));
      const result = await apiClient.postFootprintLog(samplePayload);
      if (!result.success) expect(result.error.code).toBe(500);
    });

    it('maps no-response to code "network"', async () => {
      mockPost.mockRejectedValue(createAxiosError(undefined, undefined, true));
      const result = await apiClient.postFootprintLog(samplePayload);
      if (!result.success) expect(result.error.code).toBe('network');
    });

    it('maps unknown status to code "unknown"', async () => {
      mockPost.mockRejectedValue(createAxiosError(418)); // I'm a teapot — truly unknown
      const result = await apiClient.postFootprintLog(samplePayload);
      if (!result.success) expect(result.error.code).toBe('unknown');
    });
  });
});
