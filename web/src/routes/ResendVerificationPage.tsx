import { FormEvent, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { resendVerification } from '@/api/auth';
import { BrandMark } from '@/components/BrandMark';
import { EmailInput } from '@/components/EmailInput';
import { FormLabel } from '@/components/FormLabel';
import { validateEmail } from '@/utils/authValidation';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';

export function ResendVerificationPage() {
	const [searchParams] = useSearchParams();
	const initialEmail = useMemo(() => searchParams.get('email') ?? '', [searchParams]);
	const [email, setEmail] = useState(initialEmail);
	const [error, setError] = useState<string | null>(null);
	const [success, setSuccess] = useState(false);
	const [loading, setLoading] = useState(false);

	const inputClass =
		'w-full mb-1 px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0';

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		const emailError = validateEmail(email);
		if (emailError) {
			setError(emailError);
			return;
		}
		setLoading(true);
		try {
			await resendVerification(email.trim());
			setSuccess(true);
		} catch (err: unknown) {
			setError(getApiErrorMessage(err, 'Request failed'));
		} finally {
			setLoading(false);
		}
	}

	return (
		<div className="min-h-screen flex items-center justify-center p-2 sm:p-4">
			<form onSubmit={onSubmit} className="w-full max-w-sm bg-[var(--panel)] p-4 sm:p-6 rounded-md shadow">
				<header className="mb-4 sm:mb-5 pb-4 sm:pb-5 border-b border-[#1e293b]/50">
					<BrandMark />
				</header>
				<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Resend verification</h1>
				{success ? (
					<div className="text-sm">
						<p className="text-[var(--text)] mb-4">
							If an account exists and is not yet verified, we sent a new verification link.
						</p>
						<Link to="/login" className="text-[var(--accent)]">
							Back to login
						</Link>
					</div>
				) : (
					<>
						<p className="text-xs sm:text-sm text-[var(--muted)] mb-4">
							Enter your email to receive a new verification link. You must verify before logging in.
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
						{error && <div className="text-red-400 text-xs sm:text-sm mb-3 mt-2">{error}</div>}
						<button
							disabled={loading}
							className="w-full bg-[var(--accent)] text-black py-3 sm:py-2 rounded disabled:opacity-60 min-h-[44px] sm:min-h-0 text-sm sm:text-base mt-2"
						>
							{loading ? 'Sending...' : 'Send verification email'}
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
