/**
 * Strongly typed API client for the Carbon Footprint Awareness Platform backend.
 * Uses Axios with explicit request/response interfaces mirroring backend Pydantic schemas.
 * All error states are typed — zero implicit `any`.
 *
 * **Error Handling Contract**: Every method returns `ApiResult<T>` — a discriminated union.
 * - Success: `{ success: true, data: T }` — use the data directly
 * - Failure: `{ success: false, error: ApiError }` — never throws
 *
 * **Authentication**: Firebase ID tokens are automatically attached via an Axios
 * request interceptor. The backend falls back to anonymous access when no token
 * is provided.
 */

import axios, { AxiosError, type AxiosInstance, type AxiosResponse } from 'axios';
import { getAuth } from 'firebase/auth';
import { APP_CONSTANTS } from '../constants/app.constants';

// ---------------------------------------------------------------------------
// Request / Response Interfaces (mirror backend Pydantic schemas exactly)
// ---------------------------------------------------------------------------

export interface TransportMetrics {
  readonly mode: 'car' | 'bus' | 'train' | 'bicycle' | 'walking' | 'flight';
  readonly distance_km: number;
}

export interface EnergyMetrics {
  readonly source: 'electricity' | 'natural_gas' | 'solar' | 'wind';
  readonly consumption_kwh: number;
}

export interface DietMetrics {
  readonly diet_type: 'meat_heavy' | 'average' | 'vegetarian' | 'vegan';
  readonly days: number;
}

export interface ConsumptionMetrics {
  readonly item_type: 'clothing' | 'electronics' | 'furniture' | 'general';
  readonly quantity: number;
}

export type ActivityCategory = 'transport' | 'energy' | 'food' | 'consumption';

export interface ActivityEntry {
  readonly category: ActivityCategory;
  readonly description: string;
  readonly date: string;
  readonly transport?: TransportMetrics;
  readonly energy?: EnergyMetrics;
  readonly diet?: DietMetrics;
  readonly consumption?: ConsumptionMetrics;
}

export interface CarbonCalculationRequest {
  readonly user_id: string;
  readonly entries: readonly ActivityEntry[];
  readonly calculation_date: string;
}

export interface EmissionResult {
  readonly category: string;
  readonly description: string;
  readonly co2e_kg: number;
  readonly date: string;
}

export interface CarbonCalculationResponse {
  readonly user_id: string;
  readonly total_co2e_kg: number;
  readonly entry_count: number;
  readonly results: readonly EmissionResult[];
  readonly document_id: string;
}

export interface EmissionSummaryEntry {
  readonly category: string;
  readonly total_co2e_kg: number;
  readonly entry_count: number;
  readonly description: string;
}

export interface InsightsRequest {
  readonly user_id: string;
  readonly total_co2e_kg: number;
  readonly period_days: number;
  readonly emission_breakdown: readonly EmissionSummaryEntry[];
}

export interface InsightsResponse {
  readonly user_id: string;
  readonly insight: string;
  readonly equivalent_impact: string;
  readonly actionable_steps: readonly string[];
  readonly model_used: string;
}

// ---------------------------------------------------------------------------
// Typed Error State
// ---------------------------------------------------------------------------

export type ApiErrorCode = 422 | 429 | 500 | 'network' | 'unknown';

export interface ApiError {
  readonly code: ApiErrorCode;
  readonly message: string;
  readonly detail?: string;
}

export type ApiResult<T> =
  | { readonly success: true; readonly data: T }
  | { readonly success: false; readonly error: ApiError };

// ---------------------------------------------------------------------------
// Error Mapping
// ---------------------------------------------------------------------------

function mapStatusToCode(status: number): ApiErrorCode {
  const knownCodes: Record<number, ApiErrorCode> = { 422: 422, 429: 429, 500: 500 };
  return knownCodes[status] ?? 'unknown';
}

function buildApiError(err: AxiosError): ApiError {
  if (err.response !== undefined) {
    const status = err.response.status;
    const detail =
      typeof err.response.data === 'object' &&
      err.response.data !== null &&
      'detail' in err.response.data
        ? String((err.response.data as Record<string, unknown>)['detail'])
        : undefined;
    return { code: mapStatusToCode(status), message: `HTTP ${status}`, detail };
  }
  if (err.request !== undefined) {
    return { code: 'network', message: 'Network error — backend unreachable' };
  }
  return { code: 'unknown', message: err.message };
}

// ---------------------------------------------------------------------------
// Axios Instance with Auth Interceptor
// ---------------------------------------------------------------------------

function createAxiosInstance(): AxiosInstance {
  const instance = axios.create({
    baseURL: APP_CONSTANTS.API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
    timeout: 30000,
  });

  // Automatically attach Firebase ID token to every request
  instance.interceptors.request.use(async (config) => {
    try {
      const auth = getAuth();
      const user = auth.currentUser;
      if (user) {
        const token = await user.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {
      // If token retrieval fails, proceed without auth — backend will use anonymous
    }
    return config;
  });

  return instance;
}

const httpClient: AxiosInstance = createAxiosInstance();

// ---------------------------------------------------------------------------
// Typed API Methods
// ---------------------------------------------------------------------------

async function postFootprintLog(
  payload: CarbonCalculationRequest,
): Promise<ApiResult<CarbonCalculationResponse>> {
  try {
    const response: AxiosResponse<CarbonCalculationResponse> = await httpClient.post(
      '/api/v1/footprint/log',
      payload,
    );
    return { success: true, data: response.data };
  } catch (err) {
    return { success: false, error: buildApiError(err as AxiosError) };
  }
}

async function postInsightsRequest(
  payload: InsightsRequest,
): Promise<ApiResult<InsightsResponse>> {
  try {
    const response: AxiosResponse<InsightsResponse> = await httpClient.post(
      '/api/v1/ai/insights',
      payload,
    );
    return { success: true, data: response.data };
  } catch (err) {
    return { success: false, error: buildApiError(err as AxiosError) };
  }
}

export interface ChatRequestMessage {
  readonly role: 'user' | 'model';
  readonly content: string;
}

export interface ChatRequest {
  readonly user_id: string;
  readonly message: string;
  readonly total_co2e_kg: number;
  readonly period_days: number;
  readonly emission_breakdown: readonly EmissionSummaryEntry[];
  readonly conversation_history: readonly ChatRequestMessage[];
}

export interface ChatResponse {
  readonly user_id: string;
  readonly response: string;
  readonly suggestions: readonly string[];
  readonly model_used: string;
}

export interface FootprintHistoryResponse {
  readonly user_id: string;
  readonly logs: readonly CarbonCalculationResponse[];
  readonly count: number;
  readonly period_days: number;
}

export interface CategoryBreakdownEntry {
  readonly category: string;
  readonly total_co2e_kg: number;
}

export interface FootprintSummaryResponse {
  readonly user_id: string;
  readonly period_days: number;
  readonly total_co2e_kg: number;
  readonly entry_count: number;
  readonly category_breakdown: readonly CategoryBreakdownEntry[];
}

async function getFootprintHistory(
  userId: string,
  periodDays: number = 30,
): Promise<ApiResult<FootprintHistoryResponse>> {
  try {
    const response: AxiosResponse<FootprintHistoryResponse> = await httpClient.get(
      `/api/v1/footprint/history/${userId}`,
      { params: { period_days: periodDays } },
    );
    return { success: true, data: response.data };
  } catch (err) {
    return { success: false, error: buildApiError(err as AxiosError) };
  }
}

async function postChatRequest(
  payload: ChatRequest,
): Promise<ApiResult<ChatResponse>> {
  try {
    const response: AxiosResponse<ChatResponse> = await httpClient.post(
      '/api/v1/ai/chat',
      payload,
    );
    return { success: true, data: response.data };
  } catch (err) {
    return { success: false, error: buildApiError(err as AxiosError) };
  }
}

async function getFootprintSummary(
  userId: string,
  periodDays: number = 30,
): Promise<ApiResult<FootprintSummaryResponse>> {
  try {
    const response: AxiosResponse<FootprintSummaryResponse> = await httpClient.get(
      `/api/v1/footprint/summary/${userId}`,
      { params: { period_days: periodDays } },
    );
    return { success: true, data: response.data };
  } catch (err) {
    return { success: false, error: buildApiError(err as AxiosError) };
  }
}

export const apiClient = {
  postFootprintLog,
  postInsightsRequest,
  postChatRequest,
  getFootprintHistory,
  getFootprintSummary,
} as const;
