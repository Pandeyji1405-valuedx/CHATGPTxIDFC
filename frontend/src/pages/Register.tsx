import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

function validateForm(name: string, email: string, password: string, confirm: string) {
  const errors: Record<string, string> = {};
  if (!name.trim()) errors.name = 'Full name is required.';
  if (!email.trim()) errors.email = 'Email is required.';
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = 'Enter a valid email address.';
  if (!password) errors.password = 'Password is required.';
  else if (password.length < 8) errors.password = 'Password must be at least 8 characters.';
  else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(password))
    errors.password = 'Password must contain uppercase, lowercase, and a number.';
  if (!confirm) errors.confirm = 'Please confirm your password.';
  else if (password !== confirm) errors.confirm = 'Passwords do not match.';
  return errors;
}

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [name, setName]         = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [showPass, setShowPass] = useState(false);
  const [errors, setErrors]     = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setApiError('');

    const validation = validateForm(name, email, password, confirm);
    if (Object.keys(validation).length) {
      setErrors(validation);
      return;
    }
    setErrors({});

    setIsLoading(true);
    try {
      await register({ name: name.trim(), email: email.trim().toLowerCase(), password });
      navigate('/chat', { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Registration failed. Please try again.';
      setApiError(msg);
    } finally {
      setIsLoading(false);
    }
  }

  const clearError = (field: string) => setErrors(p => { const n = {...p}; delete n[field]; return n; });

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 sm:p-6 lg:p-8 font-sans antialiased text-slate-100 relative overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[500px] bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>

      <div className="w-full max-w-5xl bg-slate-900/90 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-12 min-h-[640px] backdrop-blur-xl relative z-10">
        
        {/* LEFT BRANDING COLUMN */}
        <div className="lg:col-span-6 bg-slate-950 p-8 lg:p-12 text-white flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-slate-800/80">
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
              Account Onboarding
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold font-heading text-white leading-tight mb-3">
              Join Advisory Assistant Platform
            </h1>
            <p className="text-slate-400 text-xs sm:text-sm leading-relaxed mb-6">
              Create an internal compliance account to access grounded RBI regulatory intelligence.
            </p>
          </div>

          <div className="space-y-2 border-t border-slate-800/80 pt-6 my-4 text-xs text-slate-400">
            <p className="font-bold text-white mb-2">Password Policy Requirements:</p>
            <div className="flex items-center gap-2"><span className="text-emerald-400">✓</span> Minimum 8 characters</div>
            <div className="flex items-center gap-2"><span className="text-emerald-400">✓</span> Must include uppercase & lowercase letters</div>
            <div className="flex items-center gap-2"><span className="text-emerald-400">✓</span> Must contain at least one numeric digit</div>
          </div>

          <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>SECURITY: RESTRICTED</span>
            <span>IDFC BANK GOVERNANCE</span>
          </div>
        </div>

        {/* RIGHT REGISTER FORM COLUMN */}
        <div className="lg:col-span-6 p-8 lg:p-12 flex flex-col justify-center bg-slate-900/60">
          <div className="max-w-md w-full mx-auto space-y-5">
            
            <div>
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-2xl font-bold font-heading text-white">Create Account</h2>
                <span className="badge-slate text-[10px]">INTERNAL USE</span>
              </div>
              <p className="text-xs text-slate-400">
                Enter your details to request internal account authorization.
              </p>
            </div>

            <form onSubmit={handleSubmit} noValidate id="register-form" className="space-y-4">
              
              <div>
                <label htmlFor="register-name" className="label-saas">Full Name</label>
                <input
                  id="register-name"
                  type="text"
                  placeholder="e.g. Rahul Sharma"
                  value={name}
                  onChange={(e) => { setName(e.target.value); clearError('name'); }}
                  className={`input-saas ${errors.name ? 'border-rose-500 ring-rose-500/20' : ''}`}
                  disabled={isLoading}
                />
                {errors.name && <p id="register-name-error" className="text-xs text-rose-400 mt-1">{errors.name}</p>}
              </div>

              <div>
                <label htmlFor="register-email" className="label-saas">Work Email</label>
                <input
                  id="register-email"
                  type="email"
                  placeholder="rahul.sharma@idfcbank.com"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); clearError('email'); }}
                  className={`input-saas ${errors.email ? 'border-rose-500 ring-rose-500/20' : ''}`}
                  disabled={isLoading}
                />
                {errors.email && <p id="register-email-error" className="text-xs text-rose-400 mt-1">{errors.email}</p>}
              </div>

              <div>
                <label htmlFor="register-password" className="label-saas">Password</label>
                <div className="relative flex items-center">
                  <input
                    id="register-password"
                    type={showPass ? 'text' : 'password'}
                    placeholder="Min 8 chars, 1 uppercase, 1 digit"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); clearError('password'); }}
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
                {errors.password && <p id="register-password-error" className="text-xs text-rose-400 mt-1">{errors.password}</p>}
              </div>

              <div>
                <label htmlFor="register-confirm" className="label-saas">Confirm Password</label>
                <input
                  id="register-confirm"
                  type={showPass ? 'text' : 'password'}
                  placeholder="Re-enter password"
                  value={confirm}
                  onChange={(e) => { setConfirm(e.target.value); clearError('confirm'); }}
                  className={`input-saas ${errors.confirm ? 'border-rose-500 ring-rose-500/20' : ''}`}
                  disabled={isLoading}
                />
                {errors.confirm && <p id="register-confirm-error" className="text-xs text-rose-400 mt-1">{errors.confirm}</p>}
              </div>

              {apiError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-xl text-xs">
                  {apiError}
                </div>
              )}

              <button
                id="register-submit"
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full py-3 text-sm font-semibold shadow-glow mt-2"
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <span>Create Account & Request Access</span>
                )}
              </button>
            </form>

            <div className="pt-4 border-t border-slate-800 text-center text-xs text-slate-400">
              Already registered?{' '}
              <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-bold">
                Sign in here
              </Link>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
