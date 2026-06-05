import { FormEvent, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { login } from '@/api/auth';
import { BrandMark } from '@/components/BrandMark';
import { useSessionStore } from '@/state/sessionStore';
import { fieldErrorFor, validateLoginForm } from '@/utils/authValidation';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';

export function LoginPage() {
	const navigate = useNavigate();
	const setSession = useSessionStore((s) => s.setSession);
	const [email, setEmail] = useState('');
	const [password, setPassword] = useState('');
	const [fieldErrors, setFieldErrors] = useState<ReturnType<typeof validateLoginForm>>([]);
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		const validationErrors = validateLoginForm({ email, password });
		setFieldErrors(validationErrors);
		if (validationErrors.length > 0) {
			return;
		}
		setLoading(true);
		try {
			await login(email.trim(), password);
			await useSessionStore.getState().refresh();
			setSession(useSessionStore.getState().user);
			navigate('/dashboard');
		} catch (err: unknown) {
			setError(getApiErrorMessage(err, 'Login failed'));
		} finally {
			setLoading(false);
		}
	}

	const inputClass =
		'w-full mb-1 px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0';

	return (
		<div className="min-h-screen flex items-center justify-center p-2 sm:p-4">
			<form onSubmit={onSubmit} className="w-full max-w-sm bg-[var(--panel)] p-4 sm:p-6 rounded-md shadow">
				<header className="mb-4 sm:mb-5 pb-4 sm:pb-5 border-b border-[#1e293b]/50">
					<BrandMark />
				</header>
				<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Login</h1>
				<label className="block text-xs sm:text-sm mb-1" htmlFor="email">Email</label>
				<input
					id="email"
					name="email"
					className={inputClass}
					value={email}
					onChange={(e) => setEmail(e.target.value)}
					type="email"
					autoComplete="email"
					required
				/>
				{fieldErrorFor(fieldErrors, 'email') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'email')}</div>
				)}
				<label className="block text-xs sm:text-sm mb-1 mt-2" htmlFor="password">Password</label>
				<input
					id="password"
					name="password"
					className={inputClass}
					value={password}
					onChange={(e) => setPassword(e.target.value)}
					type="password"
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
				{error && <div className="text-red-400 text-xs sm:text-sm mb-3">{error}</div>}
				<button
					disabled={loading}
					className="w-full bg-[var(--accent)] text-black py-3 sm:py-2 rounded disabled:opacity-60 min-h-[44px] sm:min-h-0 text-sm sm:text-base"
				>
					{loading ? 'Signing in...' : 'Login'}
				</button>
				<div className="mt-3 text-xs sm:text-sm text-[var(--muted)]">
					No account? <Link to="/signup" className="text-[var(--accent)]">Sign up</Link>
				</div>
			</form>
		</div>
	);
}
