/**
 * Centralised application constants for the Carbon Footprint Awareness Platform.
 *
 * All magic values (API URLs, model names, ARIA labels, etc.) are defined here
 * to ensure a single source of truth and easy maintainability.
 * Import as `APP_CONSTANTS` — never hard-code these values in components.
 */

export const APP_CONSTANTS = {
  APP_NAME: 'Carbon Footprint Awareness Platform',
  APP_VERSION: '1.0.0',
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  GEMINI_MODEL_NAME: 'gemini-2.5-flash',

  // ARIA labels (centralised for consistency)
  LOADING_ARIA_LABEL: 'Content is loading',
  ERROR_ARIA_LABEL: 'An error occurred',
  COACH_RESPONSE_ARIA_LABEL: 'AI coach response',
  COACH_LOADING_ARIA_LABEL: 'Generating sustainability insights from Gemini AI',
  FORM_ARIA_LABEL: 'Log a carbon footprint activity',

  // Emission benchmark reference values (kg CO2e per day)
  BENCHMARK_GLOBAL_DAILY_AVG_KG: 5.5,
  BENCHMARK_PARIS_TARGET_KG: 2.5,

  // Chat conversation context window
  MAX_CHAT_CONTEXT_MESSAGES: 10,

  // Default lookback period for history fetches (days)
  DEFAULT_HISTORY_PERIOD_DAYS: 30,

  // Auto-insight trigger delay (ms) — wait for component mount
  AUTO_INSIGHT_DELAY_MS: 500,

  // Chart category colours
  CATEGORY_COLORS: {
    transport: '#818cf8',
    energy: '#34d399',
    food: '#fbbf24',
    consumption: '#f87171',
  } as const,
} as const;

export type AppConstants = typeof APP_CONSTANTS;
