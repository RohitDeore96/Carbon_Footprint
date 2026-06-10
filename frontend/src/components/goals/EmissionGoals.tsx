/**
 * EmissionGoals — Goal-setting & progress tracking component.
 * Allows users to set a monthly CO2e reduction target, visualize progress,
 * see a streak counter, and receive motivational messages at milestones.
 * Accessible: aria attributes, semantic HTML, keyboard navigable.
 */

import React, { useState, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EmissionGoalsProps {
  readonly totalCo2eKg: number;
  readonly periodDays: number;
  readonly dailyEmissions?: readonly { date: string; co2e_kg: number }[];
}

interface GoalData {
  readonly monthlyTargetKg: number;
  readonly createdAt: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'carbon-footprint-goals';
const DEFAULT_MONTHLY_TARGET = 165; // Paris Agreement target: 2.5 kg/day × 30 days

const MILESTONE_MESSAGES: Record<number, string> = {
  25: 'Great start! You\'re a quarter of the way there!',
  50: 'Halfway there! Keep up the amazing work!',
  75: 'Almost there! You\'re in the home stretch!',
  100: 'You hit your target! You\'re making a real difference for the planet!',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function loadGoal(): GoalData | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    return JSON.parse(raw) as GoalData;
  } catch {
    return null;
  }
}

function saveGoal(monthlyTargetKg: number): void {
  const data: GoalData = { monthlyTargetKg, createdAt: new Date().toISOString() };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function getMilestoneMessage(percentage: number): string | null {
  // Return message for the highest milestone achieved
  const milestones = Object.keys(MILESTONE_MESSAGES)
    .map(Number)
    .sort((a, b) => b - a);
  for (const milestone of milestones) {
    if (percentage >= milestone) {
      return MILESTONE_MESSAGES[milestone];
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EmissionGoals({
  totalCo2eKg,
  periodDays,
  dailyEmissions,
}: EmissionGoalsProps): React.JSX.Element {
  // Load goal from localStorage via lazy initializers (avoids setState-in-effect)
  const [goal, setGoal] = useState<GoalData | null>(() => loadGoal());
  const [inputValue, setInputValue] = useState(() => {
    const stored = loadGoal();
    return String(stored?.monthlyTargetKg ?? DEFAULT_MONTHLY_TARGET);
  });
  const handleSetGoal = useCallback((): void => {
    const target = parseFloat(inputValue);
    if (isNaN(target) || target <= 0) return;
    saveGoal(target);
    setGoal({ monthlyTargetKg: target, createdAt: new Date().toISOString() });
  }, [inputValue]);

  const handleResetGoal = useCallback((): void => {
    localStorage.removeItem(STORAGE_KEY);
    setGoal(null);
    setInputValue(String(DEFAULT_MONTHLY_TARGET));
  }, []);

  // No goal set — show the "Set Goal" form
  if (goal === null) {
    return (
      <div className="emission-goals" role="region" aria-label="Set emission reduction goal">
        <h3 className="goals-heading">
          <span aria-hidden="true">🎯</span> Set Your Goal
        </h3>
        <p className="goals-description">
          Set a monthly CO2e reduction target to track your progress toward a sustainable lifestyle.
        </p>
        <form
          className="goals-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSetGoal();
          }}
        >
          <label htmlFor="monthly-target-input" className="form-label">
            Monthly target (kg CO2e)
          </label>
          <input
            id="monthly-target-input"
            type="number"
            className="form-input"
            min={1}
            step={1}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            aria-describedby="target-hint"
          />
          <span id="target-hint" className="form-hint">
            Paris Agreement target: 165 kg/month (2.5 kg/day)
          </span>
          <button
            type="submit"
            className="form-submit-btn goals-submit-btn"
            aria-label="Set emission reduction goal"
          >
            Set Goal
          </button>
        </form>
      </div>
    );
  }

  // Goal exists — show progress
  const dailyAvg = periodDays > 0 ? totalCo2eKg / periodDays : 0;
  const projectedMonthly = dailyAvg * 30;
  const monthlyTarget = goal.monthlyTargetKg;

  // Progress: how close projected monthly is to the target (lower is better)
  // If projectedMonthly <= monthlyTarget, user is under target (100% progress)
  // If projectedMonthly > 0: progress = how much they've reduced vs. no-reduction scenario
  let progressPercentage: number;
  if (projectedMonthly <= monthlyTarget) {
    progressPercentage = 100;
  } else if (projectedMonthly <= 0) {
    progressPercentage = 100;
  } else {
    progressPercentage = Math.min(
      100,
      Math.round((1 - (projectedMonthly - monthlyTarget) / projectedMonthly) * 100),
    );
  }

  const isUnderTarget = projectedMonthly <= monthlyTarget;

  // Streak: count consecutive days (from most recent) where daily emission is under target
  let streakDays = 0;
  if (dailyEmissions && dailyEmissions.length > 0) {
    const dailyTarget = monthlyTarget / 30;
    const sortedDays = [...dailyEmissions].sort((a, b) => b.date.localeCompare(a.date));
    for (const day of sortedDays) {
      if (day.co2e_kg <= dailyTarget) {
        streakDays++;
      } else {
        break; // Streak broken
      }
    }
  } else {
    // Fallback: use average-based approximation when per-day data not available
    const dailyTarget = monthlyTarget / 30;
    streakDays = dailyAvg <= dailyTarget ? periodDays : 0;
  }

  const milestoneMessage = getMilestoneMessage(progressPercentage);

  return (
    <div className="emission-goals" role="region" aria-label="Emission goals and progress">
      <h3 className="goals-heading">
        <span aria-hidden="true">🎯</span> Your Goal
      </h3>

      <div className="goals-stats-row">
        <div className="goals-stat">
          <span className="goals-stat-value" aria-label={`${monthlyTarget} kg monthly target`}>
            {monthlyTarget}
          </span>
          <span className="goals-stat-unit">kg/mo target</span>
        </div>
        <div className="goals-stat">
          <span className="goals-stat-value" aria-label={`${projectedMonthly.toFixed(1)} kg projected monthly`}>
            {projectedMonthly.toFixed(1)}
          </span>
          <span className="goals-stat-unit">kg/mo projected</span>
        </div>
        <div className="goals-stat">
          <span className="goals-stat-value" aria-label={`${dailyAvg.toFixed(2)} kg daily average`}>
            {dailyAvg.toFixed(2)}
          </span>
          <span className="goals-stat-unit">kg/day avg</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="goals-progress-container" role="progressbar" aria-valuenow={progressPercentage} aria-valuemin={0} aria-valuemax={100} aria-label={`Goal progress: ${progressPercentage}%`}>
        <div
          className={`goals-progress-bar ${isUnderTarget ? 'goals-progress-bar--success' : 'goals-progress-bar--warning'}`}
          style={{ width: `${progressPercentage}%` }}
        />
      </div>
      <p className="goals-progress-label">
        {progressPercentage}% of target reached
      </p>

      {/* Streak counter */}
      {streakDays > 0 && (
        <div className="goals-streak" aria-label={`Streak: ${streakDays} day${streakDays !== 1 ? 's' : ''} under target`}>
          <span aria-hidden="true">🔥</span>
          <span className="goals-streak-count">{streakDays}</span>
          <span className="goals-streak-label">day{streakDays !== 1 ? 's' : ''} under target</span>
        </div>
      )}

      {/* Motivational message */}
      {isUnderTarget && (
        <div className="goals-message goals-message--success" role="status" aria-live="polite">
          <span aria-hidden="true">🎉</span> You&apos;re under your target! Keep it up!
        </div>
      )}

      {milestoneMessage && !isUnderTarget && (
        <div className="goals-message goals-message--milestone" role="status" aria-live="polite">
          <span aria-hidden="true">⭐</span> {milestoneMessage}
        </div>
      )}

      {/* Reset goal */}
      <button
        type="button"
        className="goals-reset-btn"
        onClick={handleResetGoal}
        aria-label="Reset emission reduction goal"
      >
        Reset Goal
      </button>
    </div>
  );
}
