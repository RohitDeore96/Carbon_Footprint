export const APP_CONSTANTS = {
  APP_NAME: 'Carbon Footprint Awareness Platform',
  APP_VERSION: '1.0.0',
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  GEMINI_MODEL_NAME: 'gemini-2.5-flash',
  LOADING_ARIA_LABEL: 'Content is loading',
  ERROR_ARIA_LABEL: 'An error occurred',
  COACH_RESPONSE_ARIA_LABEL: 'AI coach response',
  COACH_LOADING_ARIA_LABEL: 'Generating sustainability insights from Gemini AI',
  FORM_ARIA_LABEL: 'Log a carbon footprint activity',
} as const;

export type AppConstants = typeof APP_CONSTANTS;
