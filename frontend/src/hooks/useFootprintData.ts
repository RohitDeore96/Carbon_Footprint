/**
 * Custom hook for managing footprint data (logs, loading state, history fetch).
 * Extracted from CarbonDashboard to reduce component complexity.
 */

import { useState, useEffect } from 'react';
import { apiClient, type CarbonCalculationResponse } from '../services/apiClient';
import { APP_CONSTANTS } from '../constants/app.constants';

export function useFootprintData(userId: string): {
  logs: CarbonCalculationResponse[];
  setLogs: React.Dispatch<React.SetStateAction<CarbonCalculationResponse[]>>;
  historyLoading: boolean;
  historyError: string | null;
} {
  const [logs, setLogs] = useState<CarbonCalculationResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient.getFootprintHistory(userId, APP_CONSTANTS.DEFAULT_HISTORY_PERIOD_DAYS).then((result) => {
      if (!cancelled && result.success) {
        setLogs([...result.data.logs]);
        setHistoryError(null);
      } else if (!cancelled && !result.success) {
        // Distinguish auth errors (user should refresh) from server errors
        const errorCode = result.error.code;
        if (errorCode === 401) {
          setHistoryError('Session expired. Please refresh the page to re-authenticate.');
        } else if (errorCode === 403) {
          setHistoryError('Access denied. You can only view your own activity history.');
        } else if (errorCode === 429) {
          setHistoryError('Too many requests. Please wait a moment and try again.');
        } else {
          // 500, 503, network, and other errors — server-side issue, not auth
          setHistoryError('Failed to load activity history. Please refresh the page.');
        }
      }
    }).catch(() => {
      if (!cancelled) {
        setHistoryError('Failed to load activity history. Please refresh the page.');
      }
    }).finally(() => {
      if (!cancelled) setHistoryLoading(false);
    });
    return () => { cancelled = true; };
  }, [userId]);

  return { logs, setLogs, historyLoading, historyError };
}
