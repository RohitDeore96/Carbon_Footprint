/**
 * CarbonDashboard — Semantic HTML dashboard composing the log form and AI coach.
 * Uses <section aria-labelledby>, and <aside> — zero generic layout divs.
 * Includes Recharts-powered emission visualization, trend chart, benchmark comparison,
 * toast notifications, auto-generated insights, and conversational AI chat.
 */

import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LineChart, Line } from 'recharts';
import { LogActivityForm } from '../footprint/LogActivityForm';
import { InsightCoach } from '../coach/InsightCoach';
import type { InsightCoachHandle } from '../coach/InsightCoach';
import { ChatCoach } from '../coach/ChatCoach';
import { EmissionGoals } from '../goals/EmissionGoals';
import { DataExport } from '../export/DataExport';
import { useToast } from '../ui/Toast';
import {
  apiClient,
} from '../../services/apiClient';
import type {
  CarbonCalculationResponse,
  EmissionSummaryEntry,
} from '../../services/apiClient';
import { APP_CONSTANTS } from '../../constants/app.constants';

// ---------------------------------------------------------------------------
// Prop interfaces
// ---------------------------------------------------------------------------

interface CarbonDashboardProps {
  readonly userId: string;
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function roundCo2e(value: number): number {
  return Math.round(value * 10000) / 10000;
}

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
    total_co2e_kg: roundCo2e(data.total),
    entry_count: data.count,
    description: data.desc,
  }));
}

function computeTotalCo2e(logs: readonly CarbonCalculationResponse[]): number {
  return roundCo2e(logs.reduce((sum, log) => sum + log.total_co2e_kg, 0));
}

function computePeriodDays(logs: readonly CarbonCalculationResponse[]): number {
  if (logs.length === 0) return 1;
  const dates = logs
    .map((log) => log.results[0]?.date?.slice(0, 10))
    .filter((d): d is string => d !== undefined);
  if (dates.length === 0) return 1;
  const minDate = dates.reduce((a, b) => (a < b ? a : b));
  const maxDate = dates.reduce((a, b) => (a > b ? a : b));
  const diffMs = new Date(maxDate).getTime() - new Date(minDate).getTime();
  return Math.max(1, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));
}

// ---------------------------------------------------------------------------
// Sub-components (memoized for performance)
// ---------------------------------------------------------------------------

const DashboardStat = React.memo(function DashboardStat({
  label,
  value,
  unit,
  id,
}: {
  readonly label: string;
  readonly value: string;
  readonly unit: string;
  readonly id: string;
}): React.JSX.Element {
  return (
    <article
      className="stat-card"
      aria-label={`${label}: ${value} ${unit}`}
      id={id}
    >
      <span className="stat-value" aria-hidden="true">{value}</span>
      <span className="stat-unit" aria-hidden="true">{unit}</span>
      <span className="stat-label">{label}</span>
    </article>
  );
});

function EmptyLogState(): React.JSX.Element {
  return (
    <div className="empty-log-state" id="empty-log-state" role="status">
      <span className="empty-log-icon" aria-hidden="true">📋</span>
      <p className="empty-log-text">No activities logged yet. Use the form above to get started.</p>
    </div>
  );
}

const ActivityLogList = React.memo(function ActivityLogList({
  logs,
}: {
  readonly logs: readonly CarbonCalculationResponse[];
}): React.JSX.Element {
  if (logs.length === 0) return <EmptyLogState />;
  return (
    <ol className="activity-log-list" aria-label="Logged carbon footprint activities">
      {logs.map((log) => (
        <li key={log.document_id} className="activity-log-item" id={`log-item-${log.document_id}`}>
          <header className="log-item-header">
            <span className="log-item-total" aria-label={`${log.total_co2e_kg} kg CO₂e`}>
              {log.total_co2e_kg} kg CO₂e
            </span>
            <span className="log-item-count">
              {log.entry_count} {log.entry_count === 1 ? 'entry' : 'entries'}
            </span>
          </header>
          <ul className="log-item-results" aria-label="Emission breakdown">
            {log.results.map((result, i) => (
              <li key={`${log.document_id}-result-${i}`} className="log-result-item">
                <span className="log-result-category">{result.category}</span>
                <span className="log-result-desc">{result.description}</span>
                <span className="log-result-value" aria-label={`${result.co2e_kg} kg CO₂e`}>
                  {result.co2e_kg} kg
                </span>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
});

const SummaryStats = React.memo(function SummaryStats({
  logs,
}: {
  readonly logs: readonly CarbonCalculationResponse[];
}): React.JSX.Element {
  const total = computeTotalCo2e(logs);
  const entryCount = logs.reduce((sum, l) => sum + l.entry_count, 0);
  return (
    <div className="stats-row" role="region" aria-label="Carbon footprint summary statistics">
      <DashboardStat
        id="stat-total-co2e"
        label="Total CO₂e"
        value={total.toFixed(2)}
        unit="kg"
      />
      <DashboardStat
        id="stat-entries"
        label="Activities Logged"
        value={String(entryCount)}
        unit="entries"
      />
      <DashboardStat
        id="stat-categories"
        label="Categories"
        value={String(buildEmissionBreakdown(logs).length)}
        unit="types"
      />
    </div>
  );
});

// ---------------------------------------------------------------------------
// Emission Chart Component
// ---------------------------------------------------------------------------

const BENCHMARK_LINE = APP_CONSTANTS.BENCHMARK_GLOBAL_DAILY_AVG_KG;
const PARIS_TARGET = APP_CONSTANTS.BENCHMARK_PARIS_TARGET_KG;

const CATEGORY_COLORS: Record<string, string> = { ...APP_CONSTANTS.CATEGORY_COLORS };

const EmissionChart = React.memo(function EmissionChart({
  breakdown,
}: {
  readonly breakdown: EmissionSummaryEntry[];
}): React.JSX.Element {
  const chartData = breakdown.map((entry) => ({
    category: entry.category.charAt(0).toUpperCase() + entry.category.slice(1),
    co2e: roundCo2e(entry.total_co2e_kg),
    color: CATEGORY_COLORS[entry.category] ?? '#818cf8',
  }));

  return (
    <div className="emission-chart-container" role="img" aria-label="Emission breakdown chart showing CO2e by category">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
          <XAxis
            dataKey="category"
            stroke="#94a3b8"
            tick={{ fill: '#94a3b8', fontSize: 13 }}
            axisLine={{ stroke: 'rgba(99,102,241,0.2)' }}
          />
          <YAxis
            stroke="#94a3b8"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            axisLine={{ stroke: 'rgba(99,102,241,0.2)' }}
            label={{ value: 'kg CO₂e', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 12 }}
          />
          <Tooltip
            contentStyle={{
              background: '#1e293b',
              border: '1px solid rgba(99,102,241,0.3)',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '0.875rem',
            }}
            formatter={(value) => [`${value} kg CO₂e`, 'Emissions']}
          />
          <Bar dataKey="co2e" radius={[6, 6, 0, 0]} barSize={48}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Trend Chart Component
// ---------------------------------------------------------------------------

const TrendChart = React.memo(function TrendChart({
  logs,
}: {
  readonly logs: readonly CarbonCalculationResponse[];
}): React.JSX.Element {
  const dailyMap = new Map<string, number>();
  for (const log of logs) {
    const dateKey = log.results[0]?.date?.slice(0, 10) ?? 'unknown';
    dailyMap.set(dateKey, (dailyMap.get(dateKey) ?? 0) + log.total_co2e_kg);
  }
  const chartData = Array.from(dailyMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, co2e]) => ({
      date: date.slice(5),
      co2e: roundCo2e(co2e),
      benchmark: BENCHMARK_LINE,
      target: PARIS_TARGET,
    }));

  if (chartData.length < 2) return <></>;

  return (
    <div className="emission-chart-container" role="img" aria-label="Daily emission trend chart with benchmark comparison">
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
          <XAxis
            dataKey="date"
            stroke="#94a3b8"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            axisLine={{ stroke: 'rgba(99,102,241,0.2)' }}
          />
          <YAxis
            stroke="#94a3b8"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            axisLine={{ stroke: 'rgba(99,102,241,0.2)' }}
            label={{ value: 'kg CO₂e', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 12 }}
          />
          <Tooltip
            contentStyle={{
              background: '#1e293b',
              border: '1px solid rgba(99,102,241,0.3)',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '0.875rem',
            }}
          />
          <Line type="monotone" dataKey="co2e" stroke="#818cf8" strokeWidth={2} dot={{ fill: '#818cf8', r: 4 }} name="Your Emissions" />
          <Line type="monotone" dataKey="benchmark" stroke="#fbbf24" strokeWidth={1.5} strokeDasharray="8 4" dot={false} name="Global Avg" />
          <Line type="monotone" dataKey="target" stroke="#34d399" strokeWidth={1.5} strokeDasharray="4 4" dot={false} name="Paris Target" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Benchmark Comparison Component
// ---------------------------------------------------------------------------

const BenchmarkComparison = React.memo(function BenchmarkComparison({
  totalCo2eKg,
  periodDays,
}: {
  readonly totalCo2eKg: number;
  readonly periodDays: number;
}): React.JSX.Element {
  const dailyAvg = periodDays > 0 ? totalCo2eKg / periodDays : 0;
  const globalDailyAvg = BENCHMARK_LINE;
  const parisDailyTarget = PARIS_TARGET;
  const percentVsGlobal = globalDailyAvg > 0 ? Math.round((dailyAvg / globalDailyAvg) * 100) : 0;
  const percentVsParis = parisDailyTarget > 0 ? Math.round((dailyAvg / parisDailyTarget) * 100) : 0;

  return (
    <div className="benchmark-comparison" role="region" aria-label="Emission benchmark comparison">
      <div className="benchmark-item">
        <span className="benchmark-label">Your Daily Avg</span>
        <span className="benchmark-value" aria-label={`${dailyAvg.toFixed(2)} kg CO2e per day`}>
          {dailyAvg.toFixed(2)} kg
        </span>
      </div>
      <div className="benchmark-item">
        <span className="benchmark-label">vs Global Avg ({globalDailyAvg} kg/day)</span>
        <span className={`benchmark-percent ${dailyAvg <= globalDailyAvg ? 'benchmark-good' : 'benchmark-bad'}`}>
          {percentVsGlobal}%
        </span>
      </div>
      <div className="benchmark-item">
        <span className="benchmark-label">vs Paris Target ({parisDailyTarget} kg/day)</span>
        <span className={`benchmark-percent ${dailyAvg <= parisDailyTarget ? 'benchmark-good' : 'benchmark-bad'}`}>
          {percentVsParis}%
        </span>
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export function CarbonDashboard({ userId }: CarbonDashboardProps): React.JSX.Element {
  const [logs, setLogs] = useState<CarbonCalculationResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const autoInsightTriggeredRef = useRef(false);
  const insightCoachRef = useRef<InsightCoachHandle>(null);
  const { addToast } = useToast();

  // Fetch history on mount so page refresh doesn't lose data
  useEffect(() => {
    let cancelled = false;
    apiClient.getFootprintHistory(userId, APP_CONSTANTS.DEFAULT_HISTORY_PERIOD_DAYS).then((result) => {
      if (!cancelled && result.success) {
        setLogs([...result.data.logs]);
      }
    }).catch((err: unknown) => {
      console.error('Failed to load footprint history:', err);
    }).finally(() => {
      if (!cancelled) setHistoryLoading(false);
    });
    return () => { cancelled = true; };
  }, [userId]);

  const handleLogSuccess = useCallback((result: CarbonCalculationResponse): void => {
    setLogs((prev) => [result, ...prev]);
    addToast(
      `Activity logged successfully! ${result.total_co2e_kg} kg CO₂e`,
      'success',
    );
  }, [addToast]);

  // Auto-generate AI insights after the first activity log
  useEffect(() => {
    if (logs.length === 1 && !autoInsightTriggeredRef.current) {
      autoInsightTriggeredRef.current = true;
      const timer = setTimeout(() => {
        insightCoachRef.current?.requestInsights();
      }, APP_CONSTANTS.AUTO_INSIGHT_DELAY_MS);
      return () => clearTimeout(timer);
    }
  }, [logs.length]);

  // Memoized derived data to avoid recomputation on every render
  const breakdown = useMemo(() => buildEmissionBreakdown(logs), [logs]);
  const totalCo2e = useMemo(() => computeTotalCo2e(logs), [logs]);
  const periodDays = useMemo(() => computePeriodDays(logs), [logs]);

  return (
    <section id="main-content" className="carbon-dashboard" aria-label="Carbon Footprint Dashboard">

      {/* Summary statistics strip */}
      {logs.length > 0 && <SummaryStats logs={logs} />}

      {/* Emission breakdown chart */}
      {breakdown.length > 0 && (
        <section
          aria-labelledby="emission-chart-heading"
          className="dashboard-section"
          id="emission-chart-section"
        >
          <h2 id="emission-chart-heading" className="section-heading">
            <span aria-hidden="true" className="section-icon">📉</span>
            Emission Breakdown
          </h2>
          <EmissionChart breakdown={breakdown} />
        </section>
      )}

      {/* Daily emission trend */}
      {logs.length >= 2 && (
        <section
          aria-labelledby="trend-chart-heading"
          className="dashboard-section"
          id="trend-chart-section"
        >
          <h2 id="trend-chart-heading" className="section-heading">
            <span aria-hidden="true" className="section-icon">📈</span>
            Daily Trend & Benchmarks
          </h2>
          <TrendChart logs={logs} />
          <BenchmarkComparison totalCo2eKg={totalCo2e} periodDays={periodDays} />
        </section>
      )}

      {/* Two-column layout: primary content + AI aside */}
      <div className="dashboard-layout">

        {/* Primary content column */}
        <div className="dashboard-primary">

          {/* Log Activity section */}
          <section
            aria-labelledby="log-activity-section-heading"
            className="dashboard-section"
            id="log-activity-section"
          >
            <h2 id="log-activity-section-heading" className="section-heading">
              <span aria-hidden="true" className="section-icon">➕</span>
              Log Activity
            </h2>
            <p className="section-description" id="log-activity-section-desc">
              Record your transportation, energy usage, or dietary choices to track your
              personal carbon footprint.
            </p>
            <LogActivityForm userId={userId} onSuccess={handleLogSuccess} />
          </section>

          {/* Activity History section */}
          <section
            aria-labelledby="activity-history-section-heading"
            className="dashboard-section"
            id="activity-history-section"
          >
            <div className="section-heading-row">
              <h2 id="activity-history-section-heading" className="section-heading">
                <span aria-hidden="true" className="section-icon">📊</span>
                Activity History
              </h2>
              {logs.length > 0 && <DataExport logs={logs} />}
            </div>
            {historyLoading ? (
              <div role="status" aria-busy="true" className="loading-indicator">
                Loading activity history...
              </div>
            ) : (
              <ActivityLogList logs={logs} />
            )}
          </section>

        </div>

        {/* AI Coaching aside — secondary content column */}
        <aside
          aria-label="AI Sustainability Coaching"
          className="dashboard-aside"
          id="dashboard-aside"
        >
          <InsightCoach
            ref={insightCoachRef}
            userId={userId}
            totalCo2eKg={totalCo2e}
            periodDays={periodDays}
            emissionBreakdown={breakdown}
          />

          {/* Conversational Chat — shown after user has data */}
          {breakdown.length > 0 && (
            <div className="dashboard-section chat-section">
              <ChatCoach
                userId={userId}
                totalCo2eKg={totalCo2e}
                periodDays={periodDays}
                emissionBreakdown={breakdown}
              />
            </div>
          )}

          {/* Emission Goals — shown after user has data */}
          {breakdown.length > 0 && (
            <div className="dashboard-section goals-section">
              <EmissionGoals
                totalCo2eKg={totalCo2e}
                periodDays={periodDays}
              />
            </div>
          )}
        </aside>

      </div>
    </section>
  );
}
