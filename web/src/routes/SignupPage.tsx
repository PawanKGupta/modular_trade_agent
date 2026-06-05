import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { signup } from '@/api/auth';
import { BrandMark } from '@/components/BrandMark';
import { PasswordInput } from '@/components/PasswordInput';
import { EmailInput } from '@/components/EmailInput';
import { FormLabel } from '@/components/FormLabel';
import { fieldErrorFor, validateSignupForm } from '@/utils/authValidation';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';
import { PasswordConfirmHint, PasswordRequirementsChecklist } from '@/components/PasswordRequirementsChecklist';

export function SignupPage() {
	const [email, setEmail] = useState('');
	const [name, setName] = useState('');
	const [password, setPassword] = useState('');
	const [confirmPassword, setConfirmPassword] = useState('');
	const [fieldErrors, setFieldErrors] = useState<ReturnType<typeof validateSignupForm>>([]);
	const [error, setError] = useState<string | null>(null);
	const [successMessage, setSuccessMessage] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		setSuccessMessage(null);
		const validationErrors = validateSignupForm({ name, email, password, confirmPassword });
		setFieldErrors(validationErrors);
		if (validationErrors.length > 0) {
			return;
		}
		setLoading(true);
		try {
			const result = await signup(email.trim(), password, name.trim());
			setSuccessMessage(result.message);
		} catch (err: unknown) {
			setError(getApiErrorMessage(err, 'Signup failed'));
		} finally {
			setLoading(false);
		}
	}

	const inputClass =
		'w-full mb-1 px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0';

	if (successMessage) {
		return (
			<div className="min-h-screen flex items-center justify-center p-2 sm:p-4">
				<div className="w-full max-w-sm bg-[var(--panel)] p-4 sm:p-6 rounded-md shadow">
					<header className="mb-4 sm:mb-5 pb-4 sm:pb-5 border-b border-[#1e293b]/50">
						<BrandMark />
					</header>
					<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Check your email</h1>
					<p className="text-sm text-[var(--text)] mb-2">{successMessage}</p>
					<p className="text-xs sm:text-sm text-[var(--muted)] mb-4">
						We sent a verification link to <strong>{email.trim()}</strong>. You must verify before you can log in.
					</p>
					<div className="flex flex-col gap-2 text-xs sm:text-sm">
						<Link to="/login" className="text-[var(--accent)]">
							Back to login
						</Link>
						<Link to={`/resend-verification?email=${encodeURIComponent(email.trim())}`} className="text-[var(--accent)]">
							Resend verification email
						</Link>
					</div>
				</div>
			</div>
		);
	}

	return (
		<div className="min-h-screen flex items-center justify-center p-2 sm:p-4">
			<form onSubmit={onSubmit} className="w-full max-w-sm bg-[var(--panel)] p-4 sm:p-6 rounded-md shadow">
				<header className="mb-4 sm:mb-5 pb-4 sm:pb-5 border-b border-[#1e293b]/50">
					<BrandMark />
				</header>
				<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Create account</h1>
				<p className="text-xs text-[var(--muted)] mb-3">
					<span className="text-red-400">*</span> Required fields
				</p>
				<FormLabel htmlFor="email" required>
					Email
				</FormLabel>
				<EmailInput
					id="email"
					name="email"
					className={inputClass}
					value={email}
					onChange={(e) => setEmail(e.target.value)}
					autoComplete="email"
					required
				/>
				{fieldErrorFor(fieldErrors, 'email') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'email')}</div>
				)}
				<FormLabel htmlFor="name" required className="mt-2">
					Name
				</FormLabel>
				<input
					id="name"
					name="name"
					className={`${inputClass} mb-3`}
					value={name}
					onChange={(e) => setName(e.target.value)}
					type="text"
					autoComplete="name"
					required
				/>
				{fieldErrorFor(fieldErrors, 'name') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'name')}</div>
				)}
				<FormLabel htmlFor="password" required>
					Password
				</FormLabel>
				<PasswordInput
					id="password"
					name="password"
					className={inputClass}
					value={password}
					onChange={(e) => setPassword(e.target.value)}
					autoComplete="new-password"
					required
				/>
				{fieldErrorFor(fieldErrors, 'password') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'password')}</div>
				)}
				<PasswordRequirementsChecklist password={password} />
				<FormLabel htmlFor="confirmPassword" required>
					Confirm password
				</FormLabel>
				<PasswordInput
					id="confirmPassword"
					name="confirmPassword"
					className={inputClass}
					value={confirmPassword}
					onChange={(e) => setConfirmPassword(e.target.value)}
					autoComplete="new-password"
					required
				/>
				{fieldErrorFor(fieldErrors, 'confirmPassword') && (
					<div className="text-red-400 text-xs sm:text-sm mb-2">{fieldErrorFor(fieldErrors, 'confirmPassword')}</div>
				)}
				<PasswordConfirmHint password={password} confirmPassword={confirmPassword} />
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
