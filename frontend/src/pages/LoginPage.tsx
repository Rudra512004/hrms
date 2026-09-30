import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authService } from '../services/auth';
import { useAuth } from '../contexts/AuthContext';
import { Eye, EyeOff, Shield, Users, BarChart3, Clock } from 'lucide-react';

/**
 * Premium Login Page — Two-Panel Composition
 *
 * Left  (≈54%) : Brand panel with mouse-following ambient orb
 * Right (≈46%) : Matte-glass auth form
 *
 * Mouse-follow is implemented via:
 *   - pointer event listener on the brand panel (ref)
 *   - CSS custom properties (--orb-x, --orb-y) updated via rAF
 *   - Spring-like interpolation (lerp) for smooth following
 *   - No React state updates on mouse move (GPU-friendly)
 *   - Fully disabled when prefers-reduced-motion is set
 *   - Gracefully returns to center when pointer leaves panel
 */

/* ─── Static style objects ─────────────────────────────────── */
const S: Record<string, React.CSSProperties> = {
  /* Outermost shell — fills viewport, transparent */
  shell: {
    display: 'flex',
    minHeight: '100vh',
    width: '100%',
    position: 'relative',
    zIndex: 1,
  },

  /* ── LEFT BRAND PANEL ── */
  brandPanel: {
    /* ~54% on desktop */
    flex: '54 54 0',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '56px 64px',
    /* Deep BeyondSure green atmosphere */
    background: 'linear-gradient(155deg, rgba(18,62,36,0.97) 0%, rgba(10,34,20,0.99) 55%, rgba(8,24,38,0.98) 100%)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    position: 'relative',
    overflow: 'hidden',
    isolation: 'isolate',
  },

  /* The mouse-following ambient orb layer (sits behind content) */
  orbLayer: {
    position: 'absolute',
    inset: 0,
    pointerEvents: 'none',
    zIndex: 0,
    /* orb position driven by CSS vars updated in rAF */
    overflow: 'hidden',
  },

  /* Content wrapper — sits above the orb */
  brandContent: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    width: '100%',
    maxWidth: '640px',
  },

  /* BeyondSure logo — large, white (inverted), prominent */
  brandLogo: {
    width: 'clamp(180px, 22vw, 240px)',
    height: 'auto',
    objectFit: 'contain',
    display: 'block',
    marginBottom: '44px',
    filter: 'brightness(0) invert(1)',
    opacity: 0.97,
  },

  /* Primary headline */
  brandTagline: {
    fontSize: 'clamp(1.75rem, 2.5vw, 2.25rem)',
    fontWeight: 700,
    color: 'rgba(255,255,255,0.97)',
    letterSpacing: '-0.028em',
    lineHeight: 1.2,
    marginBottom: '20px',
    textAlign: 'left',
  },

  /* Supporting paragraph */
  brandSub: {
    fontSize: 'clamp(1rem, 1.2vw, 1.15rem)',
    color: 'rgba(255,255,255,0.7)',
    lineHeight: 1.6,
    textAlign: 'left',
    maxWidth: '440px',
    marginBottom: '48px',
  },

  /* Capability list */
  featureList: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '16px',
    width: '100%',
    marginBottom: '0',
    paddingLeft: '0',
  },

  brandFooter: {
    marginTop: '60px',
    fontSize: '0.85rem',
    color: 'rgba(255,255,255,0.4)',
    textAlign: 'left',
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
  },

  /* Thin separator line between panels */
  panelSeparator: {
    width: '1px',
    background: 'linear-gradient(to bottom, transparent 0%, rgba(255,255,255,0.08) 25%, rgba(255,255,255,0.10) 50%, rgba(255,255,255,0.08) 75%, transparent 100%)',
    flexShrink: 0,
    alignSelf: 'stretch',
  },

  /* ── RIGHT FORM PANEL ── */
  formPanel: {
    /* ~46% on desktop */
    flex: '46 46 0',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '56px 48px',
    /* Solid background to hide global watermark */
    background: 'var(--color-bg-card)',
    position: 'relative',
    zIndex: 2,
    minWidth: 0,
  },

  /* Inner form container — constrained width */
  formInner: {
    width: '100%',
    maxWidth: '460px',
  },

  /* Logo at the top of the form */
  formLogo: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '40px',
  },

  formLogoImg: {
    width: '180px',
    height: 'auto',
    objectFit: 'contain',
  },

  /* Form headings */
  title: {
    fontSize: '1.65rem',
    fontWeight: 700,
    color: 'var(--color-text-main)',
    letterSpacing: '-0.028em',
    marginBottom: '6px',
    textAlign: 'center',
  },

  subtitle: {
    fontSize: 'var(--font-size-sm)',
    color: 'var(--color-text-muted)',
    textAlign: 'center',
    marginBottom: '32px',
    lineHeight: 1.55,
  },

  formGroup: {
    marginBottom: '20px',
  },

  label: {
    display: 'block',
    marginBottom: '7px',
    fontSize: 'var(--font-size-sm)',
    fontWeight: 500,
    color: 'var(--color-text-sub)',
  },

  /* Inputs stay solid — never translucent */
  input: {
    width: '100%',
    padding: '11px 16px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--color-border)',
    fontSize: 'var(--font-size-sm)',
    color: 'var(--color-text-main)',
    backgroundColor: 'var(--surface-control-bg)',
    outline: 'none',
    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
  },

  passwordWrapper: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  },

  passwordInput: {
    width: '100%',
    padding: '11px 42px 11px 16px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--color-border)',
    fontSize: 'var(--font-size-sm)',
    color: 'var(--color-text-main)',
    backgroundColor: 'var(--surface-control-bg)',
    outline: 'none',
    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
  },

  eyeButton: {
    position: 'absolute',
    right: '12px',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: 'var(--color-text-muted)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4px',
    lineHeight: 0,
  },

  options: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginBottom: '24px',
    fontSize: 'var(--font-size-xs)',
  },

  link: {
    color: 'var(--color-primary)',
    textDecoration: 'none',
    fontWeight: 500,
  },

  button: {
    width: '100%',
    padding: '13px 16px',
    background: 'var(--color-primary)',
    color: 'white',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: 'var(--font-size-base)',
    fontWeight: 600,
    cursor: 'pointer',
    boxShadow: '0 4px 16px var(--color-primary-glow)',
    transition: 'all 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
    letterSpacing: '0.01em',
    fontFamily: 'inherit',
  },

  errorBox: {
    backgroundColor: 'var(--color-status-danger-bg)',
    color: 'var(--color-status-danger)',
    border: '1px solid var(--color-status-danger-border)',
    padding: '11px 16px',
    borderRadius: 'var(--radius-md)',
    marginBottom: '20px',
    fontSize: 'var(--font-size-xs)',
    textAlign: 'center',
    fontWeight: 500,
  },

  formFooter: {
    marginTop: '28px',
    textAlign: 'center',
    fontSize: '0.78rem',
    color: 'var(--color-text-muted)',
    letterSpacing: '0.01em',
  },
};

const FEATURES = [
  { Icon: Users,     label: 'Complete Employee Lifecycle Management' },
  { Icon: BarChart3, label: 'Real-time Payroll & Attendance Analytics' },
  { Icon: Clock,     label: 'Leave & Absence Management' },
  { Icon: Shield,    label: 'Role-based Access Control & Audit Trails' },
];

/* ─── Mouse-following orb implementation ──────────────────────
   Uses CSS custom properties + rAF for GPU-friendly smooth movement.
   No React state updates on pointer events.
   Disabled via prefers-reduced-motion media query.
─────────────────────────────────────────────────────────────── */

function useOrbFollow(panelRef: React.RefObject<HTMLDivElement | null>) {
  const orbRef = useRef<HTMLDivElement | null>(null);
  const rafRef = useRef<number>(0);
  /* Current interpolated position */
  const pos = useRef({ x: 50, y: 50 });
  /* Target position (where mouse actually is) */
  const target = useRef({ x: 50, y: 50 });
  const isInsidePanel = useRef(false);
  /* Check for reduced-motion preference once */
  const prefersReduced = useRef(
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  const applyPos = useCallback(() => {
    if (!orbRef.current) return;
    orbRef.current.style.setProperty('--orb-x', `${pos.current.x}%`);
    orbRef.current.style.setProperty('--orb-y', `${pos.current.y}%`);
  }, []);

  const tick = useCallback(() => {
    /* Spring-like lerp: ~7% per frame → ~120ms settle time at 60fps */
    const SPRING = 0.072;
    pos.current.x += (target.current.x - pos.current.x) * SPRING;
    pos.current.y += (target.current.y - pos.current.y) * SPRING;

    applyPos();

    /* Keep animating until very close to target */
    const dx = Math.abs(target.current.x - pos.current.x);
    const dy = Math.abs(target.current.y - pos.current.y);
    if (dx > 0.05 || dy > 0.05) {
      rafRef.current = requestAnimationFrame(tick);
    }
  }, [applyPos]);

  const startTick = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(tick);
  }, [tick]);

  useEffect(() => {
    if (prefersReduced.current) return;

    const panel = panelRef.current;
    if (!panel) return;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = panel.getBoundingClientRect();
      /* Convert to percentage within the panel */
      target.current.x = ((e.clientX - rect.left) / rect.width) * 100;
      target.current.y = ((e.clientY - rect.top) / rect.height) * 100;
      if (!isInsidePanel.current) {
        isInsidePanel.current = true;
      }
      startTick();
    };

    const handleMouseLeave = () => {
      isInsidePanel.current = false;
      /* Smoothly return to default center position */
      target.current = { x: 50, y: 50 };
      startTick();
    };

    panel.addEventListener('mousemove', handleMouseMove, { passive: true });
    panel.addEventListener('mouseleave', handleMouseLeave, { passive: true });

    /* Set initial CSS vars immediately */
    applyPos();

    return () => {
      panel.removeEventListener('mousemove', handleMouseMove);
      panel.removeEventListener('mouseleave', handleMouseLeave);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [panelRef, startTick, applyPos]);

  return orbRef;
}

/* ─── Component ────────────────────────────────────────────── */

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { refreshAuth } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const brandPanelRef = useRef<HTMLDivElement | null>(null);
  const orbRef = useOrbFollow(brandPanelRef);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await authService.login(email.toLowerCase().trim(), password);
      await refreshAuth();
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={S.shell}>

      {/* ══════════════════════════════════════════════
          LEFT BRAND PANEL
          Mouse-following ambient orb + brand content
      ══════════════════════════════════════════════ */}
      <div
        className="login-brand-panel"
        style={S.brandPanel}
        ref={brandPanelRef}
      >
        {/* Ambient orb layer — moves with mouse via CSS vars */}
        <div style={S.orbLayer} ref={orbRef}>
          <div className="login-orb" />
        </div>

        {/* Static subtle top-right corner highlight */}
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: '-60px',
            right: '-60px',
            width: '340px',
            height: '340px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(59,130,246,0.07) 0%, transparent 65%)',
            pointerEvents: 'none',
            zIndex: 0,
          }}
        />

        {/* Brand content — above orb */}
        <div style={S.brandContent}>
          <img
            src="/beyondsure-PNG-Logo2.png"
            alt="BeyondSure HRMS"
            style={S.brandLogo}
          />

          <h1 style={S.brandTagline}>
            Enterprise HR&nbsp;Management,&nbsp;Reimagined.
          </h1>

          <p style={S.brandSub}>
            Streamline your workforce operations with a unified platform
            built for modern organisations.
          </p>

          <ul style={S.featureList}>
            {FEATURES.map(({ Icon, label }) => (
              <li key={label} className="login-feature-card">
                <span className="icon-wrapper">
                  <Icon size={20} strokeWidth={1.8} />
                </span>
                {label}
              </li>
            ))}
          </ul>

          <p style={S.brandFooter}>BeyondSure HRMS &nbsp;·&nbsp; v2.0</p>
        </div>
      </div>

      {/* Soft panel separator */}
      <div aria-hidden="true" style={S.panelSeparator} />

      {/* ══════════════════════════════════════════════
          RIGHT AUTH FORM PANEL
          Matte glass surface — watermark faintly visible
      ══════════════════════════════════════════════ */}
      <div className="login-form-panel" style={S.formPanel}>
        <div style={S.formInner}>

          {/* Original logo shown always above the form */}
          <div className="login-form-logo" style={S.formLogo}>
            <img
              src="/logo.webp"
              alt="BeyondSure HRMS"
              style={S.formLogoImg}
            />
          </div>

          <h2 style={S.title}>Welcome&nbsp;Back</h2>
          <p style={S.subtitle}>Sign in to your organisation workspace</p>

          {error && <div style={S.errorBox}>{error}</div>}

          <form onSubmit={handleLogin} noValidate>
            <div style={S.formGroup}>
              <label htmlFor="login-email" style={S.label}>Company Email</label>
              <input
                id="login-email"
                type="email"
                style={S.input}
                placeholder="email@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoCapitalize="none"
                autoCorrect="off"
                autoComplete="username email"
                required
              />
            </div>

            <div style={S.formGroup}>
              <label htmlFor="login-password" style={S.label}>Password</label>
              <div style={S.passwordWrapper}>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  style={S.passwordInput}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  style={S.eyeButton}
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div style={S.options}>
              <Link to="/forgot-password" style={S.link}>
                Forgot password?
              </Link>
            </div>

            <button
              type="submit"
              id="login-submit-btn"
              style={{
                ...S.button,
                opacity: isLoading ? 0.75 : 1,
                cursor: isLoading ? 'not-allowed' : 'pointer',
              }}
              disabled={isLoading}
            >
              {isLoading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <div style={S.formFooter}>
            Enterprise Grade HR Management System
          </div>
        </div>
      </div>
    </div>
  );
};
