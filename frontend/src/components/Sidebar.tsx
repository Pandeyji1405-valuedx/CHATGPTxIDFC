import { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { listConversations, deleteConversation } from '@/services/chatService';
import type { ConversationSummary } from '@/types/chat';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onOpenAuditModal?: () => void;
}

export function Sidebar({ collapsed = false, onToggleCollapse, onOpenAuditModal }: SidebarProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);

  const isChatRoute = location.pathname === '/chat';
  const currentConvId = searchParams.get('c');

  const loadConversations = async () => {
    try {
      const data = await listConversations();
      setConversations(data);
    } catch {
      // Background silent fallback
    }
  };

  useEffect(() => {
    if (isChatRoute) {
      loadConversations();
    }
  }, [isChatRoute, currentConvId]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) {
        setShowProfileMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  function handleNewChat() {
    navigate('/chat');
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentConvId === id) {
        navigate('/chat');
      }
    } catch {
      // Silent error fallback
    }
  }

  return (
    <aside
      className={`fixed top-0 left-0 bottom-0 h-screen bg-slate-950 text-slate-300 border-r border-slate-800/80 flex flex-col transition-all duration-300 z-40 shrink-0 ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* BRAND HEADER */}
      <div className="h-14 px-3 border-b border-slate-800/80 flex items-center justify-between shrink-0">
        {!collapsed ? (
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-purple-600 text-white flex items-center justify-center font-bold text-xs shadow-glow shrink-0">
              IDFC
            </div>
            <div className="flex flex-col min-w-0">
              <span className="font-heading font-bold text-white text-sm tracking-tight truncate">
                Advisory Assistant
              </span>
              <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                Grounded Engine
              </span>
            </div>
          </div>
        ) : (
          <button
            onClick={onToggleCollapse}
            className="group relative w-10 h-10 mx-auto rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center font-bold text-xs shadow-glow hover:scale-105 transition-all"
            title="Expand Sidebar"
          >
            <span>IDFC</span>
            <span className="absolute left-16 bg-slate-900 border border-slate-800 text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-all whitespace-nowrap pointer-events-none z-50 flex items-center gap-1.5">
              <span>Expand Sidebar</span>
            </span>
          </button>
        )}

        {!collapsed && onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
            title="Collapse sidebar"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        )}
      </div>

      {/* NEW CHAT CTA BUTTON */}
      {isChatRoute && (
        <div className="p-3 shrink-0">
          <button
            onClick={handleNewChat}
            className={`group relative btn-primary py-2.5 shadow-glow hover:shadow-glow-lg text-xs font-semibold flex items-center justify-center ${
              collapsed ? 'w-10 h-10 mx-auto p-0 rounded-xl' : 'w-full gap-2'
            }`}
            title="Start New Conversation"
          >
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {!collapsed && <span>New Chat</span>}
            {collapsed && (
              <span className="absolute left-16 bg-slate-900 border border-slate-800 text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-all whitespace-nowrap pointer-events-none z-50">
                New Conversation
              </span>
            )}
          </button>
        </div>
      )}

      {/* MAIN NAVIGATION ITEMS */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-4 text-xs">
        {/* WORKSPACE SECTION */}
        <div>
          {!collapsed ? (
            <h3 className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">
              Workspace
            </h3>
          ) : (
            <div className="w-8 h-[1px] bg-slate-800/80 my-2 mx-auto" />
          )}
          <nav className="space-y-1">
            <NavLink
              to="/chat"
              className={({ isActive }) =>
                `group relative flex items-center rounded-xl transition-all duration-150 ${
                  collapsed ? 'w-10 h-10 mx-auto justify-center' : 'px-3 py-2.5 gap-3'
                } ${
                  isActive && !currentConvId
                    ? 'bg-indigo-600/20 text-indigo-300 font-semibold border border-indigo-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900'
                }`
              }
            >
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              {!collapsed && <span>Regulatory Chat</span>}
              {collapsed && (
                <span className="absolute left-16 bg-slate-900 border border-slate-800 text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-all whitespace-nowrap pointer-events-none z-50">
                  Regulatory Chat
                </span>
              )}
            </NavLink>

            {user?.role === 'ADMIN' && (
              <NavLink
                to="/admin/documents"
                id="nav-knowledge-base"
                className={({ isActive }) =>
                  `group relative flex items-center rounded-xl transition-all duration-150 ${
                    collapsed ? 'w-10 h-10 mx-auto justify-center' : 'px-3 py-2.5 gap-3'
                  } ${
                    isActive
                      ? 'bg-indigo-600/20 text-indigo-300 font-semibold border border-indigo-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900'
                  }`
                }
              >
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                {!collapsed && <span>Knowledge Base</span>}
                {collapsed && (
                  <span className="absolute left-16 bg-slate-900 border border-slate-800 text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-all whitespace-nowrap pointer-events-none z-50">
                    Knowledge Base (Admin)
                  </span>
                )}
              </NavLink>
            )}
          </nav>
        </div>

        {/* GOVERNANCE SECTION */}
        <div>
          {!collapsed ? (
            <h3 className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">
              Governance
            </h3>
          ) : (
            <div className="w-8 h-[1px] bg-slate-800/80 my-2 mx-auto" />
          )}
          <nav className="space-y-1">
            {user?.role === 'ADMIN' && (
              <button
                onClick={onOpenAuditModal}
                className={`group relative flex items-center rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-900 transition-colors text-left ${
                  collapsed ? 'w-10 h-10 mx-auto justify-center' : 'w-full px-3 py-2.5 gap-3'
                }`}
              >
                <svg className="w-4 h-4 shrink-0 text-slate-400 group-hover:text-indigo-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {!collapsed && <span>Audit Trail Logs</span>}
                {collapsed && (
                  <span className="absolute left-16 bg-slate-900 border border-slate-800 text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-all whitespace-nowrap pointer-events-none z-50">
                    Audit Trail Logs
                  </span>
                )}
              </button>
            )}

            <div className={`group relative flex items-center rounded-xl bg-slate-900/60 border border-slate-800/50 text-slate-400 transition-all ${
              collapsed ? 'w-10 h-10 mx-auto justify-center cursor-pointer hover:bg-slate-800/80' : 'justify-between px-3 py-2.5'
            }`}>
              <div className="flex items-center gap-2.5">
                <div className="relative flex items-center justify-center shrink-0">
                  <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                </div>
                {!collapsed && <span>System Status</span>}
              </div>
              {!collapsed && <span className="text-[10px] text-emerald-400 font-semibold uppercase tracking-wider">Operational</span>}
              {collapsed && (
                <span className="absolute left-16 bg-slate-900 border border-slate-800 text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-all whitespace-nowrap pointer-events-none z-50">
                  System Status: Operational
                </span>
              )}
            </div>
          </nav>
        </div>

        {/* RECENT CONVERSATIONS LIST */}
        {isChatRoute && conversations.length > 0 && (
          <div>
            {!collapsed ? (
              <>
                <h3 className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center justify-between">
                  <span>Recent Threads</span>
                  <span className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded-full font-mono">{conversations.length}</span>
                </h3>
                <div className="space-y-1 max-h-52 overflow-y-auto pr-1">
                  {conversations.map((conv) => {
                    const isSelected = conv.id === currentConvId;
                    return (
                      <NavLink
                        key={conv.id}
                        to={`/chat?c=${conv.id}`}
                        className={`group flex items-center justify-between px-3 py-2 rounded-xl transition-all duration-150 text-xs ${
                          isSelected
                            ? 'bg-indigo-600/30 text-white font-medium border border-indigo-500/40 shadow-sm'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/80'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                          <svg className={`w-3.5 h-3.5 shrink-0 ${isSelected ? 'text-indigo-400' : 'text-slate-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                          </svg>
                          <span className="truncate">{conv.title || "Untitled Conversation"}</span>
                        </div>

                        <button
                          onClick={(e) => handleDelete(conv.id, e)}
                          className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 hover:bg-slate-800 rounded transition-all ml-1 shrink-0"
                          title="Delete Thread"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </NavLink>
                    );
                  })}
                </div>
              </>
            ) : (
              <div>
                <div className="w-8 h-[1px] bg-slate-800/80 my-2 mx-auto" />
                <div className="space-y-1.5">
                  {conversations.slice(0, 4).map((conv) => {
                    const isSelected = conv.id === currentConvId;
                    return (
                      <NavLink
                        key={conv.id}
                        to={`/chat?c=${conv.id}`}
                        className={`group relative flex items-center justify-center w-10 h-10 mx-auto rounded-xl transition-all ${
                          isSelected
                            ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm'
                            : 'text-slate-500 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                        <span className="absolute left-16 bg-slate-900 border border-slate-800 text-white text-xs font-medium px-2.5 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-all whitespace-nowrap pointer-events-none z-50 max-w-xs truncate">
                          {conv.title || "Untitled Conversation"}
                        </span>
                      </NavLink>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* USER PROFILE FOOTER */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950 relative shrink-0" ref={profileMenuRef}>
        {/* Profile Popover Popup */}
        {showProfileMenu && (
          <div className={`absolute bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-2 z-50 animate-fade-in text-xs space-y-1 ${
            collapsed ? 'left-16 bottom-3 w-56' : 'bottom-16 left-3 right-3'
          }`}>
            <div className="px-3 py-2 border-b border-slate-800">
              <p className="font-bold text-white truncate">{user?.name || 'IDFC User'}</p>
              <p className="text-slate-400 text-[11px] truncate">{user?.email}</p>
              <span className="inline-block mt-1 text-[9px] font-bold px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase">
                Role: {user?.role}
              </span>
            </div>

            {user?.role === 'ADMIN' && onOpenAuditModal && (
              <button
                onClick={() => { setShowProfileMenu(false); onOpenAuditModal(); }}
                className="w-full text-left px-3 py-2 rounded-xl text-slate-300 hover:text-white hover:bg-slate-800 flex items-center gap-2.5 transition-colors font-medium"
              >
                <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span>Audit Trail Logs</span>
              </button>
            )}

            <button
              onClick={handleLogout}
              className="w-full text-left px-3 py-2 rounded-xl text-rose-400 hover:bg-rose-500/10 flex items-center gap-2.5 transition-colors font-medium"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span>Sign Out</span>
            </button>
          </div>
        )}

        {/* User Pill Button */}
        <button
          onClick={() => setShowProfileMenu(!showProfileMenu)}
          className={`group relative w-full flex items-center rounded-xl hover:bg-slate-900 transition-all text-left ${
            collapsed ? 'p-1 justify-center' : 'p-1.5 gap-3'
          }`}
          title="Account Menu"
        >
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-sm">
            {user?.name ? user.name.charAt(0).toUpperCase() : user?.email?.charAt(0).toUpperCase() || 'U'}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-white truncate">{user?.name || 'IDFC User'}</p>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-400 truncate max-w-[90px]">{user?.email}</span>
                <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase">
                  {user?.role}
                </span>
              </div>
            </div>
          )}
          {!collapsed && (
            <svg className={`w-3.5 h-3.5 text-slate-400 transition-transform ${showProfileMenu ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          )}
          {collapsed && (
            <span className="absolute left-16 bg-slate-900 border border-slate-800 text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-all whitespace-nowrap pointer-events-none z-50">
              {user?.name || 'User Profile'} ({user?.role})
            </span>
          )}
        </button>
      </div>
    </aside>
  );
}
