import { FormEvent, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { signup } from '@/api/auth';
import { BrandMark } from '@/components/BrandMark';
import { useSessionStore } from '@/state/sessionStore';
import { fieldErrorFor, validateSignupForm } from '@/utils/authValidation';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';

export function SignupPage() {
	const navigate = useNavigate();
	const setSession = useSessionStore((s) => s.setSession);
	const [email, setEmail] = useState('');
	const [name, setName] = useState('');
	const [password, setPassword] = useState('');
	const [confirmPassword, setConfirmPassword] = useState('');
	const [fieldErrors, setFieldErrors] = useState<ReturnType<typeof validateSignupForm>>([]);
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		const validationErrors = validateSignupForm({ email, password, confirmPassword });
		setFieldErrors(validationErrors);
		if (validationErrors.length > 0) {
			return;
		}
		setLoading(true);
		try {
			await signup(email.trim(), password, name.trim() || undefined);
			await useSessionStore.getState().refresh();
			setSession(useSessionStore.getState().user);
			navigate('/dashboard');
		} catch (err: unknown) {
			setError(getApiErrorMessage(err, 'Signup failed'));
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
				<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Create account</h1>
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
				<label className="block text-xs sm:text-sm mb-1 mt-2" htmlFor="name">Name</label>
				<input
					id="name"
					name="name"
					className={`${inputClass} mb-3`}
					value={name}
					onChange={(e) => setName(e.target.value)}
					type="text"
					autoComplete="name"
				/>
				<label className="block text-xs sm:text-sm mb-1" htmlFor="password">Password</label>
				<input
					id="password"
					name="password"
					className={inputClass}
					value={password}
					onChange={(e) => setPassword(e.target.value)}
					type="password"
					autoComplete="new-password"
					required
				/>
				{fieldErrorFor(fieldErrors, 'password') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'password')}</div>
				)}
				<p className="text-xs text-[var(--muted)] mb-2 mt-1">At least 8 characters with a letter and a number.</p>
				<label className="block text-xs sm:text-sm mb-1" htmlFor="confirmPassword">Confirm password</label>
				<input
					id="confirmPassword"
					name="confirmPassword"
					className={inputClass}
					value={confirmPassword}
					onChange={(e) => setConfirmPassword(e.target.value)}
					type="password"
					autoComplete="new-password"
					required
				/>
				{fieldErrorFor(fieldErrors, 'confirmPassword') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'confirmPassword')}</div>
				)}
				{error && <div className="text-red-400 text-xs sm:text-sm mb-3 mt-2">{error}</div>}
				<button
					disabled={loading}
					className="w-full bg-[var(--accent)] text-black py-3 sm:py-2 rounded disabled:opacity-60 min-h-[44px] sm:min-h-0 text-sm sm:text-base mt-2"
				>
					{loading ? 'Creating...' : 'Sign up'}
				</button>
				<div className="mt-3 text-xs sm:text-sm text-[var(--muted)]">
					Have an account? <Link to="/login" className="text-[var(--accent)]">Login</Link>
				</div>
			</form>
		</div>
	);
}
