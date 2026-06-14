import { FormEvent, useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { login, mfaLogin } from '@/api/auth';
import { BrandMark } from '@/components/BrandMark';
import { PasswordInput } from '@/components/PasswordInput';
import { EmailInput } from '@/components/EmailInput';
import { FormLabel } from '@/components/FormLabel';
import { useSessionStore } from '@/state/sessionStore';
import { fieldErrorFor, validateLoginForm } from '@/utils/authValidation';
import {
	getApiErrorMessage,
	getApiErrorWarning,
	getAuthRetryAfterSeconds,
	isAuthRateLimitError,
	isUnverifiedEmailLoginError,
} from '@/utils/getApiErrorMessage';
import {
	clearLoginLockout,
	formatLockoutCountdown,
	LOGIN_LOCKOUT_HEADLINE,
	readLoginLockoutSeconds,
	saveLoginLockout,
} from '@/utils/loginLockout';

export function LoginPage() {
	const navigate = useNavigate();
	const setSession = useSessionStore((s) => s.setSession);
	const [email, setEmail] = useState('');
	const [password, setPassword] = useState('');
	const [fieldErrors, setFieldErrors] = useState<ReturnType<typeof validateLoginForm>>([]);
	const [error, setError] = useState<string | null>(null);
	const [warning, setWarning] = useState<string | null>(null);
	const [rateLimited, setRateLimited] = useState(false);
	const [lockoutSecondsRemaining, setLockoutSecondsRemaining] = useState(0);
	const [showResendVerification, setShowResendVerification] = useState(false);
	const [loading, setLoading] = useState(false);
	// MFA challenge state
	const [mfaRequired, setMfaRequired] = useState(false);
	const [mfaToken, setMfaToken] = useState<string | null>(null);
	const [mfaCode, setMfaCode] = useState('');
	const [mfaError, setMfaError] = useState<string | null>(null);
	const [mfaLoading, setMfaLoading] = useState(false);

	function applyLockout(seconds: number) {
		if (seconds <= 0) {
			setLockoutSecondsRemaining(0);
			setRateLimited(false);
			return;
		}
		setLockoutSecondsRemaining(seconds);
		setRateLimited(true);
		setError(LOGIN_LOCKOUT_HEADLINE);
		setWarning(null);
	}

	function clearLockoutState() {
		setLockoutSecondsRemaining(0);
		setRateLimited(false);
		clearLoginLockout();
	}

	useEffect(() => {
		const remaining = readLoginLockoutSeconds(email);
		if (remaining > 0) {
			applyLockout(remaining);
		} else if (rateLimited && lockoutSecondsRemaining <= 0) {
			setRateLimited(false);
		}

	}, [email]);

	useEffect(() => {
		if (lockoutSecondsRemaining <= 0) {
			return;
		}
		const timer = window.setInterval(() => {
			const remaining = readLoginLockoutSeconds(email);
			if (remaining <= 0) {
				setLockoutSecondsRemaining(0);
				setRateLimited(false);
				setError(null);
				clearLoginLockout();
				return;
			}
			setLockoutSecondsRemaining(remaining);
		}, 1000);
		return () => window.clearInterval(timer);
	}, [email, lockoutSecondsRemaining]);

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		if (lockoutSecondsRemaining > 0) {
			return;
		}
		setError(null);
		setWarning(null);
		setRateLimited(false);
		setShowResendVerification(false);
		const validationErrors = validateLoginForm({ email, password });
		setFieldErrors(validationErrors);
		if (validationErrors.length > 0) {
			return;
		}
		setLoading(true);
		try {
			const res = await login(email.trim(), password);
			if (res.mfa_required && res.mfa_token) {
				// Password OK — need MFA code to complete login
				setMfaToken(res.mfa_token);
				setMfaRequired(true);
				return;
			}
			clearLockoutState();
			await useSessionStore.getState().refresh();
			setSession(useSessionStore.getState().user);
			navigate('/dashboard');
		} catch (err: unknown) {
			if (isAuthRateLimitError(err)) {
				const retryAfter = getAuthRetryAfterSeconds(err) ?? 0;
				if (retryAfter > 0) {
					saveLoginLockout(email, retryAfter);
					applyLockout(retryAfter);
				} else {
					setError(getApiErrorMessage(err, LOGIN_LOCKOUT_HEADLINE));
					setRateLimited(true);
				}
			} else {
				setError(getApiErrorMessage(err, 'Login failed'));
				setRateLimited(false);
				setWarning(getApiErrorWarning(err));
				setShowResendVerification(isUnverifiedEmailLoginError(err));
			}
		} finally {
			setLoading(false);
		}
	}

	async function onMfaSubmit(e: FormEvent) {
		e.preventDefault();
		if (!mfaToken) return;
		setMfaError(null);
		setMfaLoading(true);
		try {
			await mfaLogin(mfaToken, mfaCode);
			clearLockoutState();
			await useSessionStore.getState().refresh();
			setSession(useSessionStore.getState().user);
			navigate('/dashboard');
		} catch (err: unknown) {
			setMfaError(getApiErrorMessage(err, 'Invalid MFA code'));
		} finally {
			setMfaLoading(false);
		}
	}

	const inputClass =
		'w-full mb-1 px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0';
	const loginDisabled = loading || lockoutSecondsRemaining > 0;

	// ── MFA challenge screen ──────────────────────────────────────────────────
	if (mfaRequired) {
		return (
			<div className="min-h-screen flex items-center justify-center p-2 sm:p-4">
				<form
					onSubmit={onMfaSubmit}
					className="w-full max-w-sm bg-[var(--panel)] p-4 sm:p-6 rounded-md shadow space-y-4"
				>
					<header className="pb-4 border-b border-[#1e293b]/50">
						<BrandMark />
					</header>
					<h1 className="text-lg sm:text-xl font-semibold">Two-factor authentication</h1>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Open your authenticator app and enter the 6-digit code for Rebound.
					</p>
					<div>
						<label className="block text-xs sm:text-sm mb-1" htmlFor="mfaLoginCode">
							Authenticator code
						</label>
						<input
							id="mfaLoginCode"
							type="text"
							inputMode="numeric"
							autoComplete="one-time-code"
							maxLength={16}
							className={`${inputClass} font-mono tracking-widest`}
							placeholder="000000"
							value={mfaCode}
							onChange={(e) => setMfaCode(e.target.value.trim())}
							autoFocus
							required
						/>
					</div>
					{mfaError && (
						<div role="alert" className="text-red-400 text-xs sm:text-sm">
							{mfaError}
						</div>
					)}
					<button
						type="submit"
						disabled={mfaLoading || mfaCode.length < 6}
						className="w-full bg-[var(--accent)] text-black py-3 sm:py-2 rounded disabled:opacity-60 min-h-[44px] sm:min-h-0 text-sm sm:text-base"
					>
						{mfaLoading ? 'Verifying...' : 'Verify'}
					</button>
					<button
						type="button"
						className="w-full text-xs sm:text-sm text-[var(--muted)] hover:text-[var(--fg)] transition-colors"
						onClick={() => {
							setMfaRequired(false);
							setMfaToken(null);
							setMfaCode('');
							setMfaError(null);
						}}
					>
						← Back to login
					</button>
				</form>
			</div>
		);
	}

	return (
		<div className="min-h-screen flex items-center justify-center p-2 sm:p-4">
			<form onSubmit={onSubmit} className="w-full max-w-sm bg-[var(--panel)] p-4 sm:p-6 rounded-md shadow">
				<header className="mb-4 sm:mb-5 pb-4 sm:pb-5 border-b border-[#1e293b]/50">
					<BrandMark />
				</header>
				<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Login</h1>
				<FormLabel htmlFor="email" required>
					Email
				</FormLabel>
				<EmailInput
					id="email"
					name="email"
					className={inputClass}
					value={email}
					onChange={(e) => {
						setEmail(e.target.value);
						setShowResendVerification(false);
						setWarning(null);
						if (!readLoginLockoutSeconds(e.target.value)) {
							clearLockoutState();
							setError(null);
						}
					}}
					autoComplete="email"
					required
				/>
				{fieldErrorFor(fieldErrors, 'email') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'email')}</div>
				)}
				<FormLabel htmlFor="password" required className="mt-2">
					Password
				</FormLabel>
				<PasswordInput
					id="password"
					name="password"
					className={inputClass}
					value={password}
					onChange={(e) => {
						setPassword(e.target.value);
						setShowResendVerification(false);
						setWarning(null);
						if (!rateLimited) {
							setError(null);
						}
					}}
					autoComplete="current-password"
					required
				/>
				{fieldErrorFor(fieldErrors, 'password') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'password')}</div>
				)}
				<div className="text-right mb-3 mt-1">
					<Link to="/forgot-password" className="text-xs sm:text-sm text-[var(--accent)]">
						Forgot password?
					</Link>
				</div>
				{error ? (
					<div
						role="alert"
						className={
							rateLimited
								? 'text-amber-400 text-xs sm:text-sm mb-3 border border-amber-500/40 rounded px-3 py-2 bg-amber-500/10'
								: 'text-red-400 text-xs sm:text-sm mb-3'
						}
					>
						{error}
						{rateLimited && lockoutSecondsRemaining > 0 ? (
							<p className="mt-2 font-medium tabular-nums">
								You can try again in {formatLockoutCountdown(lockoutSecondsRemaining)}
							</p>
						) : null}
					</div>
				) : null}
				{warning && !rateLimited ? (
					<div
						role="status"
						className="text-amber-400 text-xs sm:text-sm mb-3 border border-amber-500/40 rounded px-3 py-2 bg-amber-500/10"
					>
						{warning}
					</div>
				) : null}
				<button
					disabled={loginDisabled}
					className="w-full bg-[var(--accent)] text-black py-3 sm:py-2 rounded disabled:opacity-60 min-h-[44px] sm:min-h-0 text-sm sm:text-base"
				>
					{loading ? 'Signing in...' : lockoutSecondsRemaining > 0 ? 'Login temporarily locked' : 'Login'}
				</button>
				<div className="mt-3 text-xs sm:text-sm text-[var(--muted)]">
					No account? <Link to="/signup" className="text-[var(--accent)]">Sign up</Link>
				</div>
				<div className="mt-2 text-xs sm:text-sm text-[var(--muted)]">
					<Link to="/help" className="text-[var(--accent)]">
						Help &amp; setup guide
					</Link>
				</div>
				{showResendVerification ? (
					<div className="mt-2 text-xs sm:text-sm text-[var(--muted)]">
						Need to verify?{' '}
						<Link
							to={`/resend-verification?email=${encodeURIComponent(email.trim())}`}
							className="text-[var(--accent)]"
						>
							Resend verification email
						</Link>
					</div>
				) : null}
			</form>
		</div>
	);
}
