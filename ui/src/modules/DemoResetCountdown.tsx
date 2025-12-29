/**
 * DemoResetCountdown - Countdown timer for demo environment auto-reset
 *
 * This component displays a countdown timer showing when the demo environment
 * will be automatically reset. It's designed for "first-run" public demos.
 *
 * Features:
 * - Real-time countdown display (HH:MM:SS)
 * - Color-coded urgency (green → yellow → red)
 * - Polling to sync with server time
 * - Graceful handling of disabled/unavailable states
 */

import React, { useState, useEffect, useCallback } from "react";

interface DemoStatus {
  enabled: boolean;
  interval_hours: number | null;
  next_reset_utc: string | null;
  seconds_until_reset: number | null;
  last_reset_utc: string | null;
  reset_count: number;
  server_time_utc: string;
}

interface DemoResetCountdownProps {
  /** API base URL (default: empty for same origin) */
  apiBaseUrl?: string;
  /** Poll interval in milliseconds (default: 60000 = 1 minute) */
  pollInterval?: number;
  /** Show in compact mode (just timer) */
  compact?: boolean;
  /** Custom class name */
  className?: string;
}

/**
 * Format seconds into HH:MM:SS display
 */
function formatCountdown(seconds: number): string {
  if (seconds <= 0) return "00:00:00";

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  return [
    hours.toString().padStart(2, "0"),
    minutes.toString().padStart(2, "0"),
    secs.toString().padStart(2, "0"),
  ].join(":");
}

/**
 * Get urgency level based on remaining time
 */
function getUrgencyLevel(
  seconds: number,
  intervalHours: number
): "low" | "medium" | "high" {
  const totalSeconds = intervalHours * 3600;
  const percentage = (seconds / totalSeconds) * 100;

  if (percentage > 25) return "low";
  if (percentage > 10) return "medium";
  return "high";
}

export const DemoResetCountdown: React.FC<DemoResetCountdownProps> = ({
  apiBaseUrl = "",
  pollInterval = 60000,
  compact = false,
  className = "",
}) => {
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  /**
   * Fetch demo status from the API
   */
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/demo/status`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: DemoStatus = await response.json();
      setStatus(data);
      setSecondsRemaining(data.seconds_until_reset);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  // Initial fetch and polling
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, pollInterval);
    return () => clearInterval(interval);
  }, [fetchStatus, pollInterval]);

  // Local countdown tick (every second)
  useEffect(() => {
    if (secondsRemaining === null || secondsRemaining <= 0) return;

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev === null || prev <= 0) return 0;
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [secondsRemaining]);

  // Don't render if disabled or loading
  if (loading) {
    return null;
  }

  if (error || !status?.enabled) {
    return null;
  }

  const urgency = status.interval_hours
    ? getUrgencyLevel(secondsRemaining || 0, status.interval_hours)
    : "low";

  const urgencyClass = `demo-countdown-${urgency}`;

  if (compact) {
    return (
      <div className={`demo-countdown-compact ${urgencyClass} ${className}`}>
        <span className="demo-countdown-icon">[T]</span>
        <span className="demo-countdown-time">
          {formatCountdown(secondsRemaining || 0)}
        </span>
      </div>
    );
  }

  return (
    <div className={`demo-countdown-panel ${urgencyClass} ${className}`}>
      <div className="demo-countdown-header">
        <span className="demo-countdown-icon">[R]</span>
        <span className="demo-countdown-title">Próximo reinicio del demo</span>
      </div>

      <div className="demo-countdown-timer">
        {formatCountdown(secondsRemaining || 0)}
      </div>

      <div className="demo-countdown-info">
        <p>
          El entorno se reinicia automáticamente cada {status.interval_hours}{" "}
          horas para garantizar una experiencia limpia.
        </p>
        {status.reset_count > 0 && (
          <p className="demo-countdown-stats">
            Reinicios realizados: {status.reset_count}
          </p>
        )}
      </div>
    </div>
  );
};

export default DemoResetCountdown;
