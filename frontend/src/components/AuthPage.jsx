import { useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, History, KeyRound, Shield, UserRound } from 'lucide-react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function AuthPage() {
  const { isAuthenticated, login, register, enterDemo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const initialMode = useMemo(() => new URLSearchParams(location.search).get('mode') === 'register' ? 'register' : 'login', [location.search]);
  const [mode, setMode] = useState(initialMode);
  const [form, setForm] = useState({ full_name: '', email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  if (isAuthenticated) return <Navigate to="/app" replace />;

  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  const finish = () => navigate('/app', { replace: true });
  const submit = async (event) => {
    event.preventDefault();
    setBusy(mode);
    setError('');
    try {
      if (mode === 'register') await register(form);
      else await login({ email: form.email, password: form.password });
      finish();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy('');
    }
  };

  const openDemo = async (role) => {
    setBusy(role);
    setError('');
    try {
      await enterDemo(role);
      finish();
    } catch (requestError) {
      setError(requestError.status === 404 ? 'Demo access is disabled on this backend. Set DEMO_MODE=true for the portfolio sandbox.' : requestError.message);
    } finally {
      setBusy('');
    }
  };

  return (
    <main className="auth-page">
      <Link className="auth-back" to="/"><ArrowLeft size={16} /> Back to Sentinel Guard</Link>
      <section className="auth-story" aria-label="Authentication context">
        
        <h1>Enter with a role.<br />Leave every action traceable.</h1>
        <p className="auth-story-copy">Analysts investigate model decisions. Administrators coordinate people, integrity, and model health. Both work from the same evidence.</p>
        <ol className="auth-role-trace">
          <li><span>01</span><div><strong>Analyst</strong><small>Investigate, recommend, await approval</small></div></li>
          <li><span>02</span><div><strong>Administrator</strong><small>Assign, approve or return, monitor</small></div></li>
        </ol>
        <div className="auth-history-note"><History size={16} /><span><strong>Append-only history</strong><small>Every transition remains attributable</small></span></div>
      </section>

      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-mode" role="tablist" aria-label="Account access">
          <button role="tab" aria-selected={mode === 'login'} onClick={() => { setMode('login'); setError(''); }}>Sign in</button>
          <button role="tab" aria-selected={mode === 'register'} onClick={() => { setMode('register'); setError(''); }}>Create analyst account</button>
        </div>
        <div className="auth-heading">
          <span><KeyRound size={15} /> Protected workspace</span>
          <h2 id="auth-title">{mode === 'login' ? 'Welcome back.' : 'Join as an analyst.'}</h2>
          <p>{mode === 'login' ? 'Use your institutional identity or enter the disposable portfolio demo.' : 'Public registration creates an analyst role only. Administrator access is provisioned separately.'}</p>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === 'register' && <label><span>Full name</span><input name="full_name" autoComplete="name" minLength="2" required value={form.full_name} onChange={update} placeholder="Your full name" /></label>}
          <label><span>Email address</span><input name="email" type="email" autoComplete="email" required value={form.email} onChange={update} placeholder="name@institution.com" /></label>
          <label><span>Password</span><div className="password-field"><input name="password" type={showPassword ? 'text' : 'password'} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 8 : 1} required value={form.password} onChange={update} placeholder={mode === 'register' ? 'At least 8 characters' : 'Your password'} /><button type="button" onClick={() => setShowPassword((shown) => !shown)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" disabled={Boolean(busy)}>{busy === mode ? 'Verifying…' : mode === 'login' ? 'Enter workspace' : 'Create account'} <ArrowRight size={16} /></button>
        </form>

        <div className="demo-divider"><span>Portfolio sandbox</span></div>
        <div className="demo-actions">
          <button onClick={() => openDemo('analyst')} disabled={Boolean(busy)}><UserRound size={18} /><span><strong>{busy === 'analyst' ? 'Preparing demo…' : 'Continue as analyst'}</strong><small>Investigate and recommend</small></span><ArrowRight size={15} /></button>
          <button onClick={() => openDemo('admin')} disabled={Boolean(busy)}><Shield size={18} /><span><strong>{busy === 'admin' ? 'Preparing demo…' : 'Continue as administrator'}</strong><small>Coordinate and monitor</small></span><ArrowRight size={15} /></button>
        </div>
        <p className="demo-note"><Check size={13} /> Disposable identities · deterministic sample data · no credentials required</p>
      </section>
    </main>
  );
}
