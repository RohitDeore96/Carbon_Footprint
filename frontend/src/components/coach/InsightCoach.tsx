/**
 * InsightCoach — Conversational AI interface displaying Gemini 2.5 Flash sustainability insights.
 * Accessibility: aria-live="polite" on the response region, role="status" on loading state.
 * Exposes requestInsights via React.forwardRef for auto-triggering from parent.
 */

import React, { useState, useCallback, useImperativeHandle, forwardRef, useRef, useEffect } from 'react';
import { apiClient, type InsightsResponse, type ApiError, type EmissionSummaryEntry } from '../../services/apiClient';
import { APP_CONSTANTS } from '../../constants/app.constants';

// ---------------------------------------------------------------------------
// Prop interfaces
// ---------------------------------------------------------------------------

export interface InsightCoachProps {
  readonly userId: string;
  readonly totalCo2eKg: number;
  readonly periodDays: number;
  readonly emissionBreakdown: readonly EmissionSummaryEntry[];
}

export interface InsightCoachHandle {
  requestInsights: () => void;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CoachLoadingState(): React.JSX.Element {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Generating sustainability insights from Gemini AI"
      className="coach-loading"
    >
      <span className="loading-spinner coach-spinner" aria-hidden="true" />
      <p className="coach-loading-text">
        Analysing your footprint with Gemini {APP_CONSTANTS.GEMINI_MODEL_NAME}…
      </p>
    </div>
  );
}

function CoachErrorState({ error }: { readonly error: ApiError }): React.JSX.Element {
  return (
    <div role="alert" aria-live="assertive" className="coach-error" id="coach-error-msg">
      <span className="coach-error-icon" aria-hidden="true">⚠</span>
      <p>
        <strong>Insight generation failed ({error.code}):</strong>{' '}
        {error.detail ?? error.message}
      </p>
      <p className="coach-error-hint">Please try again in a moment.</p>
    </div>
  );
}

function ActionableStep({
  step,
  index,
}: {
  readonly step: string;
  readonly index: number;
}): React.JSX.Element {
  return (
    <li className="coach-step" id={`coach-step-${index + 1}`}>
      <span className="coach-step-number" aria-hidden="true">{index + 1}</span>
      <span className="coach-step-text">{step}</span>
    </li>
  );
}

function InsightContent({ insights }: { readonly insights: InsightsResponse }): React.JSX.Element {
  return (
    <div className="coach-content" id="coach-insights-content">
      <div className="coach-insight-block" id="coach-insight-block">
        <h4 className="coach-block-heading" id="coach-insight-heading">
          Your Carbon Assessment
        </h4>
        <p className="coach-insight-text">{insights.insight}</p>
      </div>

      <div className="coach-equivalent-block" id="coach-equivalent-block">
        <h4 className="coach-block-heading" id="coach-equivalent-heading">
          Real-World Impact
        </h4>
        <p className="coach-equivalent-text coach-highlight">
          <span aria-hidden="true" className="coach-icon">🌍</span>
          {insights.equivalent_impact}
        </p>
      </div>

      <div className="coach-steps-block" id="coach-steps-block">
        <h4 className="coach-block-heading" id="coach-steps-heading">
          Your Action Plan
        </h4>
        <ol
          className="coach-steps-list"
          aria-labelledby="coach-steps-heading"
          aria-label="Personalised action steps"
        >
          {insights.actionable_steps.map((step, i) => (
            <ActionableStep key={`step-${i}`} step={step} index={i} />
          ))}
        </ol>
      </div>

      <footer className="coach-footer" id="coach-footer">
        <p className="coach-model-label">
          <span aria-hidden="true">✦</span> Powered by{' '}
          <span className="coach-model-name">{insights.model_used}</span>
        </p>
      </footer>
    </div>
  );
}

function CoachEmptyState(): React.JSX.Element {
  return (
    <div className="coach-empty" id="coach-empty-state">
      <span className="coach-empty-icon" aria-hidden="true">🌱</span>
      <p className="coach-empty-text">
        Log your first activity to unlock AI-powered sustainability coaching.
      </p>
    </div>
  );
}

function RequestInsightsButton({
  onClick,
  disabled,
}: {
  readonly onClick: () => void;
  readonly disabled: boolean;
}): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="coach-request-btn"
      id="coach-request-btn"
      aria-label="Request personalised sustainability insights from AI coach"
    >
      <span aria-hidden="true">✦</span> Get AI Insights
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main InsightCoach component (with forwardRef for auto-trigger)
// ---------------------------------------------------------------------------

export const InsightCoach = forwardRef<InsightCoachHandle, InsightCoachProps>(
  function InsightCoach({
    userId,
    totalCo2eKg,
    periodDays,
    emissionBreakdown,
  }, ref) {
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [insights, setInsights] = useState<InsightsResponse | null>(null);
    const [error, setError] = useState<ApiError | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);

    const hasData: boolean = emissionBreakdown.length > 0;

    const requestInsights = useCallback(async (): Promise<void> => {
      // Abort any previous in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsLoading(true);
      setError(null);
      const result = await apiClient.postInsightsRequest({
        user_id: userId,
        total_co2e_kg: totalCo2eKg,
        period_days: periodDays,
        emission_breakdown: emissionBreakdown,
      });

      // Ignore result if request was aborted
      if (controller.signal.aborted) return;

      setIsLoading(false);
      if (result.success) {
        setInsights(result.data);
      } else {
        setError(result.error);
      }
    }, [userId, totalCo2eKg, periodDays, emissionBreakdown]);

    // Cleanup on unmount
    useEffect(() => {
      return () => {
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
        }
      };
    }, []);

    // Expose requestInsights to parent via ref
    useImperativeHandle(ref, () => ({ requestInsights }), [requestInsights]);

    return (
      <article
        className="insight-coach"
        aria-label="AI Sustainability Coach"
        id="insight-coach"
      >
        <header className="coach-header" id="coach-header">
          <h3 className="coach-title" id="coach-title">
            <span aria-hidden="true" className="coach-title-icon">✦</span>
            Sustainability Coach
          </h3>
          <p className="coach-subtitle">
            Powered by Gemini — personalised advice for your carbon footprint.
          </p>
        </header>

        {hasData && insights === null && !isLoading && (
          <RequestInsightsButton onClick={requestInsights} disabled={!hasData} />
        )}

        {/*
          aria-live="polite" ensures screen readers announce updates
          when new AI content appears without disrupting current reading flow.
          role="region" identifies this as a significant landmark.
        */}
        <div
          role="region"
          aria-live="polite"
          aria-atomic="true"
          aria-label="AI coach response"
          aria-relevant="additions text"
          className="coach-response-region"
          id="coach-response-region"
        >
          {isLoading && <CoachLoadingState />}
          {!isLoading && error !== null && <CoachErrorState error={error} />}
          {!isLoading && insights !== null && <InsightContent insights={insights} />}
          {!isLoading && insights === null && error === null && !hasData && <CoachEmptyState />}
        </div>

        {insights !== null && (
          <div className="coach-actions" id="coach-actions">
            <button
              type="button"
              onClick={requestInsights}
              disabled={isLoading}
              className="coach-refresh-btn"
              id="coach-refresh-btn"
              aria-label="Refresh AI sustainability insights"
            >
              Refresh Insights
            </button>
          </div>
        )}
      </article>
    );
  },
);
