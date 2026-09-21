/**
 * HealthStatus component.
 *
 * Calls the backend health endpoint and renders a status badge.
 * Automatically polls on mount — no manual refresh needed.
 */

import { useEffect, useState } from 'react';
import { fetchHealth } from '@/services/api';
import type { FetchStatus, HealthResponse } from '@/types/api';

// ------------------------------------------------------------------ //
// Status dot
// ------------------------------------------------------------------ //
function StatusDot({ status }: { status: FetchStatus }) {
  if (status === 'loading') {
    return (
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-400" />
      </span>
    );
  }
  if (status === 'success') {
    return <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-emerald-400/50 shadow-sm" />;
  }
  if (status === 'error') {
    return <span className="h-2.5 w-2.5 rounded-full bg-red-400 shadow-red-400/50 shadow-sm" />;
  }
  return <span className="h-2.5 w-2.5 rounded-full bg-slate-400" />;
}

// ------------------------------------------------------------------ //
// Main component
// ------------------------------------------------------------------ //
export function HealthStatus() {
  const [status, setStatus] = useState<FetchStatus>('idle');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const check = async () => {
    setStatus('loading');
    setError(null);
    try {
      const data = await fetchHealth();
      setHealth(data);
      setStatus('success');
    } catch (err) {
      setError('Backend unreachable');
      setStatus('error');
    }
  };

  useEffect(() => {
    check();
  }, []);

  return (
    <div className="card-glass p-5 animate-slide-up">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Backend Status
        </h3>
        <button
          id="health-refresh-btn"
          onClick={check}
          disabled={status === 'loading'}
          className="text-xs text-brand-400 hover:text-brand-300 transition-colors disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      <div className="flex items-center gap-2.5">
        <StatusDot status={status} />
        {status === 'idle' && (
          <span className="text-slate-400 text-sm">Not checked yet</span>
        )}
        {status === 'loading' && (
          <span className="text-amber-400 text-sm">Checking…</span>
        )}
        {status === 'success' && health && (
          <span className="badge-success">
            {health.status.toUpperCase()} — {health.app_name} v{health.version}
          </span>
        )}
        {status === 'error' && (
          <span className="badge-error">{error}</span>
        )}
      </div>

      {status === 'success' && health && (
        <div className="mt-4 pt-4 divider grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <span className="text-slate-500">Environment</span>
          <span className="text-slate-300 font-mono">{health.environment}</span>
          <span className="text-slate-500">Version</span>
          <span className="text-slate-300 font-mono">{health.version}</span>
          <span className="text-slate-500">Checked at</span>
          <span className="text-slate-300 font-mono">
            {new Date(health.timestamp).toLocaleTimeString()}
          </span>
        </div>
      )}
    </div>
  );
}
