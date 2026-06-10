/**
 * Chart constants and shared helpers for EmissionCharts.
 * Separated from components to satisfy react-refresh/only-export-components.
 */

import { APP_CONSTANTS } from '../../constants/app.constants';

// ---------------------------------------------------------------------------
// Shared constants
// ---------------------------------------------------------------------------

export const BENCHMARK_LINE = APP_CONSTANTS.BENCHMARK_GLOBAL_DAILY_AVG_KG;
export const PARIS_TARGET = APP_CONSTANTS.BENCHMARK_PARIS_TARGET_KG;

export const CATEGORY_COLORS: Record<string, string> = { ...APP_CONSTANTS.CATEGORY_COLORS };

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

export function roundCo2e(value: number): number {
  return Math.round(value * 10000) / 10000;
}
