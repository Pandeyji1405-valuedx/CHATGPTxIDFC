interface NavbarProps {
  title?: string;
  sidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
}

export function Navbar({ title = "IDFC Advisory Assistant", sidebarCollapsed, onToggleSidebar }: NavbarProps) {
  return (
    <header className="glass-header px-6 py-3.5 flex items-center justify-between border-b border-slate-800/80">
      {/* LEFT TITLE, SIDEBAR TOGGLE & GROUNDING PILL */}
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors"
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
            </svg>
          </button>
        )}

        <h1 className="text-sm sm:text-base font-bold text-white tracking-tight flex items-center gap-3">
          {title}
          <span className="badge-emerald hidden sm:inline-flex">
            <svg className="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Grounded in RBI Master Directions
          </span>
        </h1>
      </div>

      {/* RIGHT CONTROLS */}
      <div className="flex items-center gap-3">
        {/* Quick Search Shortcut */}
        <div className="flex items-center gap-2 bg-slate-900/90 text-slate-400 text-xs px-3.5 py-1.5 rounded-xl border border-slate-800 cursor-pointer hover:border-slate-700 transition-colors w-64">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span className="flex-1">Search regulations...</span>
          <kbd className="bg-slate-800 text-slate-400 text-[10px] font-mono px-1.5 py-0.5 rounded border border-slate-700">⌘K</kbd>
        </div>
      </div>
    </header>
  );
}
