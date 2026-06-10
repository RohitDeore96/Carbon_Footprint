/**
 * EmissionCharts — Extracted chart sub-components for the Carbon Dashboard.
 * Includes EmissionChart (bar), TrendChart (line), BenchmarkComparison,
 * ChartPlaceholder, and shared constants/helpers.
 */

import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LineChart, Line } from 'recharts';
import type { EmissionSummaryEntry } from '../../services/apiClient';
import { BENCHMARK_LINE, PARIS_TARGET, CATEGORY_COLORS, roundCo2e } from './chartHelpers';

// EmissionChart component exported for use in CarbonDashboard

export const EmissionChart = React.memo(function EmissionChart({
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
// Trend Chart Component (Line chart)
// ---------------------------------------------------------------------------

export const TrendChart = React.memo(function TrendChart({
  logs,
}: {
  readonly logs: readonly { total_co2e_kg: number; results: readonly { date?: string }[] }[];
}): React.JSX.Element {
  const chartData = useMemo(() => {
    const dailyMap = new Map<string, number>();
    for (const log of logs) {
      const dateKey = log.results[0]?.date?.slice(0, 10) ?? 'unknown';
      dailyMap.set(dateKey, (dailyMap.get(dateKey) ?? 0) + log.total_co2e_kg);
    }
    return Array.from(dailyMap.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, co2e]) => ({
        date: date.slice(5),
        co2e: roundCo2e(co2e),
        benchmark: BENCHMARK_LINE,
        target: PARIS_TARGET,
      }));
  }, [logs]);

  if (chartData.length < 2) {
    return (
      <p className="trend-chart-insufficient" role="status">
        Log at least 2 days of activities to see your emission trend.
      </p>
    );
  }

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

export const BenchmarkComparison = React.memo(function BenchmarkComparison({
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
// Placeholder chart for empty state
// ---------------------------------------------------------------------------

export function ChartPlaceholder({ title, icon, description }: {
  readonly title: string;
  readonly icon: string;
  readonly description: string;
}): React.JSX.Element {
  return (
    <div className="chart-placeholder" role="img" aria-label={`${title} placeholder — ${description}`}>
      <span className="chart-placeholder-icon" aria-hidden="true">{icon}</span>
      <p className="chart-placeholder-text">{description}</p>
    </div>
  );
}
