import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

function validateForm(email: string, password: string) {
  const errors: { email?: string; password?: string } = {};
  if (!email.trim()) errors.email = 'Email is required.';
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = 'Enter a valid email address.';
  if (!password) errors.password = 'Password is required.';
  return errors;
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [errors, setErrors]     = useState<{ email?: string; password?: string }>({});
  const [apiError, setApiError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setApiError('');

    const validation = validateForm(email, password);
    if (Object.keys(validation).length) {
      setErrors(validation);
      return;
    }
    setErrors({});

    setIsLoading(true);
    try {
      await login({ email: email.trim().toLowerCase(), password });
      navigate('/chat', { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Login failed. Please verify your credentials.';
      setApiError(msg);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 sm:p-6 lg:p-8 font-sans antialiased text-slate-100 relative overflow-hidden">
      {/* Background Ambient Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[500px] bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>

      {/* Container */}
      <div className="w-full max-w-5xl bg-slate-900/90 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-12 min-h-[580px] backdrop-blur-xl relative z-10">
        
        {/* LEFT BRANDING COLUMN */}
        <div className="lg:col-span-6 bg-slate-950 p-8 lg:p-12 text-white flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-slate-800/80 relative">
          <div>
            <div className="flex items-center gap-3 mb-8">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-purple-600 text-white flex items-center justify-center font-bold text-base shadow-glow">
                IDFC
              </div>
              <div className="flex flex-col">
                <span className="font-heading font-bold text-lg text-white tracking-tight">IDFC Advisory Assistant</span>
                <span className="text-xs text-indigo-400 font-medium">Compliance & Regulatory Technology</span>
              </div>
            </div>

            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-300 font-semibold mb-6">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Internal Enterprise Platform
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold font-heading text-white leading-tight mb-3">
              Grounded RBI Regulatory Intelligence
            </h1>
            <p className="text-slate-400 text-xs sm:text-sm leading-relaxed mb-8">
              Navigate approved RBI Master Directions, Circulars, and Statutory Guidelines with deterministic precision.
            </p>
          </div>

          <div className="space-y-3 border-t border-slate-800/80 pt-6 my-4 text-xs text-slate-300">
            <div className="flex items-center gap-2.5">
              <span className="text-emerald-400 font-bold">✓</span>
              <span>100% Verifiable Document Provenance & Page Citations</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="text-emerald-400 font-bold">✓</span>
              <span>4-Tier Cache Cascade & Real-Time Redis Session Context</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="text-emerald-400 font-bold">✓</span>
              <span>Role-Based Access Control & PII Masking Security</span>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>SECURITY LEVEL: RESTRICTED</span>
            <span>v1.0 PRODUCTION</span>
          </div>
        </div>

        {/* RIGHT LOGIN FORM COLUMN */}
        <div className="lg:col-span-6 p-8 lg:p-12 flex flex-col justify-center bg-slate-900/60">
          <div className="max-w-md w-full mx-auto space-y-6">
            
            <div>
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-2xl font-bold font-heading text-white">Enterprise Sign In</h2>
                <span className="badge-slate text-[10px]">INTERNAL ONLY</span>
              </div>
              <p className="text-xs text-slate-400">
                Authenticate with your IDFC employee credentials to access compliance tools.
              </p>
            </div>

            <form onSubmit={handleSubmit} noValidate id="login-form" className="space-y-4">
              <div>
                <label htmlFor="login-email" className="label-saas">
                  Email Address
                </label>
                <input
                  id="login-email"
                  type="email"
                  placeholder="name@idfcbank.com"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setErrors(p => ({...p, email: undefined})); }}
                  className={`input-saas ${errors.email ? 'border-rose-500 ring-rose-500/20' : ''}`}
                  disabled={isLoading}
                />
                {errors.email && (
                  <p id="login-email-error" className="text-xs text-rose-400 mt-1">{errors.email}</p>
                )}
              </div>

              <div>
                <label htmlFor="login-password" className="label-saas">
                  Password
                </label>
                <div className="relative flex items-center">
                  <input
                    id="login-password"
                    type={showPass ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setErrors(p => ({...p, password: undefined})); }}
                    className={`input-saas pr-10 ${errors.password ? 'border-rose-500 ring-rose-500/20' : ''}`}
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    className="absolute right-3 text-slate-400 hover:text-white focus:outline-none"
                    onClick={() => setShowPass(s => !s)}
                  >
                    {showPass ? '🙈' : '👁️'}
                  </button>
                </div>
                {errors.password && (
                  <p id="login-password-error" className="text-xs text-rose-400 mt-1">{errors.password}</p>
                )}
              </div>

              {apiError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-xl text-xs">
                  {apiError}
                </div>
              )}

              <button
                id="login-submit"
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full py-3 text-sm font-semibold shadow-glow mt-2"
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <span>Sign In to Advisory Assistant</span>
                )}
              </button>
            </form>

            <div className="pt-4 border-t border-slate-800 text-center text-xs text-slate-400">
              Need account access?{' '}
              <Link to="/register" className="text-indigo-400 hover:text-indigo-300 font-bold">
                Register new account
              </Link>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
