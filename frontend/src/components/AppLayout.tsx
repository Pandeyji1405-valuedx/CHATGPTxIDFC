import { useState, useEffect, type ReactNode } from 'react';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { useAuth } from '@/context/AuthContext';
import { getAuditLogs } from '@/services/api';
import type { AuditLogEntry } from '@/types/api';

interface AppLayoutProps {
  children: ReactNode;
}

function formatAuditDate(log: AuditLogEntry): string {
  const rawDate = log.timestamp || log.created_at;
  if (!rawDate) return 'Just now';
  const d = new Date(rawDate);
  return isNaN(d.getTime()) ? 'Recent Event' : d.toLocaleString();
}

export function AppLayout({ children }: AppLayoutProps) {
  const { user } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [logError, setLogError] = useState<string | null>(null);

  useEffect(() => {
    if (showAuditModal && user?.role === 'ADMIN') {
      loadAuditLogs();
    }
  }, [showAuditModal, user]);

  async function loadAuditLogs() {
    try {
      setLoadingLogs(true);
      setLogError(null);
      const data = await getAuditLogs({ limit: 50 });
      setAuditLogs(data.items);
    } catch (err: any) {
      setLogError(err?.response?.data?.detail || 'Failed to load audit logs');
    } finally {
      setLoadingLogs(false);
    }
  }

  return (
    <div className="h-screen w-screen bg-slate-950 text-slate-100 flex font-sans antialiased overflow-hidden">
      {/* Full-Height Modern Left Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        onOpenAuditModal={() => setShowAuditModal(true)}
      />

      {/* Main Content Pane with Dynamic Padding */}
      <div className={`flex-1 flex flex-col h-full min-w-0 transition-all duration-300 overflow-hidden ${
        sidebarCollapsed ? 'pl-16' : 'pl-64'
      }`}>
        {/* Top Header Bar */}
        <Navbar
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Dynamic Page Component View */}
        <main className="flex-1 overflow-y-auto bg-slate-950 relative flex flex-col min-h-0">
          {children}
        </main>
      </div>

      {/* ADMIN AUDIT LOGS MODAL */}
      {showAuditModal && user?.role === 'ADMIN' && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-slate-900 rounded-2xl shadow-2xl border border-slate-800 max-w-4xl w-full max-h-[85vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2 font-heading">
                  <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 shadow-glow"></span>
                  Enterprise Audit Trail Logs
                </h2>
                <p className="text-xs text-slate-400">
                  Immutable security and compliance event records (ADMIN view)
                </p>
              </div>
              <button
                onClick={() => setShowAuditModal(false)}
                className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto flex-1">
              {loadingLogs ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-3">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-xs">Loading audit event log...</span>
                </div>
              ) : logError ? (
                <div className="p-4 bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-xl text-xs">
                  {logError}
                </div>
              ) : auditLogs.length === 0 ? (
                <div className="py-12 text-center text-slate-400 text-xs">
                  No audit log events recorded yet.
                </div>
              ) : (
                <div className="overflow-x-auto border border-slate-800 rounded-xl">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                      <tr>
                        <th className="px-3 py-2.5">Timestamp</th>
                        <th className="px-3 py-2.5">Action</th>
                        <th className="px-3 py-2.5">Outcome</th>
                        <th className="px-3 py-2.5">Resource</th>
                        <th className="px-3 py-2.5">Actor</th>
                        <th className="px-3 py-2.5">Details (Sanitized)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80 text-slate-200 font-mono text-[11px]">
                      {auditLogs.map((log) => (
                        <tr key={log.id} className="hover:bg-slate-800/50 transition-colors">
                          <td className="px-3 py-2 whitespace-nowrap text-slate-400 font-sans">
                            {formatAuditDate(log)}
                          </td>
                          <td className="px-3 py-2 font-semibold text-white">{log.action}</td>
                          <td className="px-3 py-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              log.outcome === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            }`}>
                              {log.outcome}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-slate-300">
                            {log.resource_type} {log.resource_id ? `#${log.resource_id.substring(0, 8)}` : ''}
                          </td>
                          <td className="px-3 py-2 text-slate-400 truncate max-w-[100px]">
                            {log.actor_id ? log.actor_id.substring(0, 8) : 'SYSTEM'}
                          </td>
                          <td className="px-3 py-2 text-slate-400 max-w-[200px] truncate" title={JSON.stringify(log.details)}>
                            {log.details ? JSON.stringify(log.details) : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-between text-xs">
              <span className="text-slate-400">Showing latest {auditLogs.length} audit records</span>
              <button
                onClick={() => setShowAuditModal(false)}
                className="btn-secondary py-1.5 text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
