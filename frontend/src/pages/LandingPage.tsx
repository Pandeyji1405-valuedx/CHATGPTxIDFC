import { Link } from 'react-router-dom';
import { HealthStatus } from '@/components/HealthStatus';

interface CapabilityCardProps {
  icon: string;
  title: string;
  description: string;
  badge: string;
}

function CapabilityCard({ icon, title, description, badge }: CapabilityCardProps) {
  return (
    <div className="card-saas-hover p-6 flex flex-col justify-between border border-slate-800">
      <div>
        <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center text-2xl mb-4 font-bold shadow-sm">
          {icon}
        </div>
        <h3 className="text-base font-bold font-heading text-white mb-2">{title}</h3>
        <p className="text-xs text-slate-400 leading-relaxed">{description}</p>
      </div>
      <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-between">
        <span className="badge-indigo text-[10px]">
          {badge}
        </span>
      </div>
    </div>
  );
}

const CAPABILITIES: CapabilityCardProps[] = [
  {
    icon: '📜',
    title: 'Approved RBI Sources',
    description: 'Indexed directly against official Reserve Bank of India Master Directions, Circulars, and Guidelines for 100% compliance accuracy.',
    badge: 'Statutory Coverage',
  },
  {
    icon: '🎯',
    title: 'Grounded Verifiable Provenance',
    description: 'Backend-assembled citations with verifiable document title, circular number, version, and exact page provenance.',
    badge: '100% Traceable',
  },
  {
    icon: '🛡️',
    title: 'Governed Architecture',
    description: 'Single-tenant namespace isolation, PII masking, 4-tier cost-saving cache cascade, and immutable audit logging.',
    badge: 'Enterprise Governance',
  },
];

export function LandingPage() {
  return (
    <main className="min-h-screen flex flex-col bg-slate-950 font-sans antialiased text-slate-100" id="landing-page">
      {/* ── Top Header Bar ── */}
      <header className="glass-header px-6 py-4 flex items-center justify-between border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-purple-600 text-white flex items-center justify-center font-bold text-xs shadow-glow">
            IDFC
          </div>
          <div className="flex flex-col">
            <span className="font-heading font-bold text-white text-sm tracking-tight flex items-center gap-2">
              IDFC Advisory Assistant
              <span className="badge-slate text-[10px]">RESTRICTED</span>
            </span>
            <span className="text-[11px] text-slate-400 font-normal hidden sm:inline">
              Internal Regulatory Compliance Intelligence Platform
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            id="get-started-btn"
            to="/login"
            className="btn-primary text-xs font-semibold px-4 py-2 shadow-glow"
          >
            Sign In to Assistant →
          </Link>
        </div>
      </header>

      {/* ── Hero Section ── */}
      <section className="px-6 py-20 text-center relative overflow-hidden bg-slate-950">
        <div className="absolute top-10 left-1/2 -translate-x-1/2 w-[700px] h-[350px] bg-indigo-500/15 rounded-full blur-3xl pointer-events-none" />
        
        <div className="max-w-4xl mx-auto relative z-10 animate-fade-in space-y-6">
          <div className="inline-flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-full px-4 py-1.5 text-xs text-indigo-300 font-medium shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            IDFC FIRST Bank · Regulatory Technology
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold font-heading tracking-tight leading-tight text-white">
            IDFC Advisory Assistant
          </h1>

          <p className="text-slate-300 text-lg sm:text-xl max-w-2xl mx-auto font-normal leading-relaxed">
            Trusted regulatory guidance, grounded in approved RBI sources.
          </p>

          <p className="text-slate-400 text-xs sm:text-sm max-w-xl mx-auto leading-relaxed">
            Navigate complex banking guidelines, circulars, and compliance requirements with deterministic AI grounded in verified RBI documents.
          </p>

          <div className="pt-4 flex flex-col sm:flex-row gap-4 items-center justify-center">
            <Link
              to="/login"
              className="btn-primary text-sm font-semibold px-8 py-3.5 shadow-glow"
            >
              Open Advisory Assistant →
            </Link>
            <a
              id="docs-link"
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
              className="btn-secondary text-sm font-medium px-6 py-3.5"
            >
              API OpenAPI Specs ↗
            </a>
          </div>
        </div>
      </section>

      {/* ── Core Capabilities Grid ── */}
      <section className="px-6 py-16 max-w-6xl mx-auto w-full space-y-10">
        <div className="text-center">
          <h2 className="text-2xl sm:text-3xl font-bold font-heading text-white">Governed Architecture & Capabilities</h2>
          <p className="text-xs text-slate-400 mt-2 max-w-md mx-auto">
            Engineered specifically for banking compliance, accuracy, and auditability.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {CAPABILITIES.map((c) => (
            <CapabilityCard key={c.title} {...c} />
          ))}
        </div>
      </section>

      {/* ── Security & System Status ── */}
      <section className="px-6 pb-16 max-w-6xl mx-auto w-full">
        <div className="grid md:grid-cols-12 gap-6 items-start">
          {/* Security Features */}
          <div className="md:col-span-8 card-saas p-6 sm:p-8 space-y-6 border border-slate-800">
            <h3 className="text-sm font-bold font-heading text-white uppercase tracking-wider flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 shadow-glow"></span>
              Enterprise Governance & Security Architecture
            </h3>

            <div className="grid sm:grid-cols-2 gap-4 text-xs">
              <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800/80 space-y-1">
                <span className="font-bold text-white block">🔐 Role-Based Access Control</span>
                <span className="text-slate-400">Strict isolation between standard USER queries and ADMIN document ingestion.</span>
              </div>
              <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800/80 space-y-1">
                <span className="font-bold text-white block">🏷️ Version-Aware Invalidation</span>
                <span className="text-slate-400">Automatic cache invalidation on circular supersession ensures zero stale guidance.</span>
              </div>
              <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800/80 space-y-1">
                <span className="font-bold text-white block">🔒 PII & Secret Redaction</span>
                <span className="text-slate-400">Deterministic masking redacts PAN, Aadhaar, Phone, Email, and JWTs from logs.</span>
              </div>
              <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800/80 space-y-1">
                <span className="font-bold text-white block">📜 Immutable Audit Logging</span>
                <span className="text-slate-400">All administrative operations are recorded to PostgreSQL audit trail logs.</span>
              </div>
            </div>
          </div>

          {/* Infrastructure Health */}
          <div className="md:col-span-4 space-y-3">
            <p className="text-xs font-bold font-heading text-slate-400 uppercase tracking-wider px-1">
              Live Infrastructure
            </p>
            <HealthStatus />
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-slate-950 text-slate-400 px-6 py-6 border-t border-slate-800/80 text-center text-xs mt-auto">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 font-medium text-slate-300">
            <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
            IDFC Advisory Assistant · Internal Enterprise Application
          </div>
          <p className="text-slate-500 text-[11px]">
            Strictly RESTRICTED for IDFC FIRST Bank Personnel · Grounded in Approved RBI Documents
          </p>
        </div>
      </footer>
    </main>
  );
}
