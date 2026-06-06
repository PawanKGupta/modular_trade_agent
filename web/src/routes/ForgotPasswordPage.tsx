import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { forgotPassword } from '@/api/auth';
import { BrandMark } from '@/components/BrandMark';
import { EmailInput } from '@/components/EmailInput';
import { FormLabel } from '@/components/FormLabel';
import { fieldErrorFor, validateEmail } from '@/utils/authValidation';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';

export function ForgotPasswordPage() {
	const [email, setEmail] = useState('');
	const [fieldErrors, setFieldErrors] = useState<{ field: string; message: string }[]>([]);
	const [error, setError] = useState<string | null>(null);
	const [success, setSuccess] = useState(false);
	const [loading, setLoading] = useState(false);

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		const emailError = validateEmail(email);
		const errors = emailError ? [{ field: 'email', message: emailError }] : [];
		setFieldErrors(errors);
		if (errors.length > 0) {
			return;
		}
		setLoading(true);
		try {
			await forgotPassword(email.trim());
			setSuccess(true);
		} catch (err: unknown) {
			setError(getApiErrorMessage(err, 'Request failed'));
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
				<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Forgot password</h1>
				{success ? (
					<div className="text-sm text-[var(--text)]">
						If an account exists for that email, we sent password reset instructions. Check your inbox.
						<div className="mt-4">
							<Link to="/login" className="text-[var(--accent)]">
								Back to login
							</Link>
						</div>
					</div>
				) : (
					<>
						<p className="text-xs sm:text-sm text-[var(--muted)] mb-4">
							Enter your email and we will send you a reset link.
						</p>
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
						{error && <div className="text-red-400 text-xs sm:text-sm mb-3 mt-2">{error}</div>}
						<button
							disabled={loading}
							className="w-full bg-[var(--accent)] text-black py-3 sm:py-2 rounded disabled:opacity-60 min-h-[44px] sm:min-h-0 text-sm sm:text-base mt-2"
						>
							{loading ? 'Sending...' : 'Send reset link'}
						</button>
						<div className="mt-3 text-xs sm:text-sm text-[var(--muted)]">
							<Link to="/login" className="text-[var(--accent)]">
								Back to login
							</Link>
						</div>
					</>
				)}
			</form>
		</div>
	);
}
