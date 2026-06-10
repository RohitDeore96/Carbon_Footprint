/**
 * DataExport — CSV export component for carbon footprint activity logs.
 * Generates a downloadable CSV file with columns: Date, Category, Description, CO2e (kg).
 * Accessible: aria-label on button, disabled state when no logs exist.
 */

import React, { useCallback } from 'react';
import type { CarbonCalculationResponse } from '../../services/apiClient';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DataExportProps {
  readonly logs: readonly CarbonCalculationResponse[];
}

// ---------------------------------------------------------------------------
// CSV generation
// ---------------------------------------------------------------------------

function generateCSV(logs: readonly CarbonCalculationResponse[]): string {
  const BOM = '\uFEFF';
  const header = 'Date,Category,Description,CO2e (kg)';
  const rows: string[] = [];

  for (const log of logs) {
    for (const result of log.results) {
      // Escape description in case it contains commas or quotes
      const escapedDesc = escapeCSVField(result.description);
      const date = result.date?.slice(0, 10) ?? 'unknown';
      rows.push(`${date},${result.category},${escapedDesc},${result.co2e_kg}`);
    }
  }

  return BOM + header + '\n' + rows.join('\n');
}

function escapeCSVField(field: string): string {
  if (field.includes(',') || field.includes('"') || field.includes('\n')) {
    return '"' + field.replace(/"/g, '""') + '"';
  }
  return field;
}

function getExportFilename(): string {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  return `carbon-footprint-export-${yyyy}-${mm}-${dd}.csv`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataExport({ logs }: DataExportProps): React.JSX.Element {
  const hasLogs = logs.length > 0;

  const handleExport = useCallback((): void => {
    if (!hasLogs) return;

    const csvContent = generateCSV(logs);
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = getExportFilename();
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    // Delay revocation to ensure the browser has initiated the download
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, [logs, hasLogs]);

  return (
    <button
      type="button"
      className="data-export-btn"
      onClick={handleExport}
      disabled={!hasLogs}
      aria-label="Export carbon footprint data as CSV"
    >
      <span aria-hidden="true">📥</span> Export Data
    </button>
  );
}
