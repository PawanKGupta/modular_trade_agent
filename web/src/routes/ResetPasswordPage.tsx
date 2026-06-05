import { FormEvent, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { resetPassword } from '@/api/auth';
import { BrandMark } from '@/components/BrandMark';
import { PasswordInput } from '@/components/PasswordInput';
import { FormLabel } from '@/components/FormLabel';
import { fieldErrorFor, validateResetPasswordForm } from '@/utils/authValidation';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';
import { PasswordConfirmHint, PasswordRequirementsChecklist } from '@/components/PasswordRequirementsChecklist';

export function ResetPasswordPage() {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();
	const token = useMemo(() => searchParams.get('token') ?? '', [searchParams]);
	const [password, setPassword] = useState('');
	const [confirmPassword, setConfirmPassword] = useState('');
	const [fieldErrors, setFieldErrors] = useState<ReturnType<typeof validateResetPasswordForm>>([]);
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	const inputClass =
		'w-full mb-1 px-3 py-2.5 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0';

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		if (!token) {
			setError('Invalid or missing reset link');
			return;
		}
		const validationErrors = validateResetPasswordForm({ password, confirmPassword });
		setFieldErrors(validationErrors);
		if (validationErrors.length > 0) {
			return;
		}
		setLoading(true);
		try {
			await resetPassword(token, password);
			navigate('/login');
		} catch (err: unknown) {
			setError(getApiErrorMessage(err, 'Password reset failed'));
		} finally {
			setLoading(false);
		}
	}

	if (!token) {
		return (
			<div className="min-h-screen flex items-center justify-center p-2 sm:p-4">
				<div className="w-full max-w-sm bg-[var(--panel)] p-4 sm:p-6 rounded-md shadow text-sm">
					<p className="text-red-400 mb-4">Invalid or missing reset link.</p>
					<Link to="/forgot-password" className="text-[var(--accent)]">
						Request a new link
					</Link>
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
				<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Reset password</h1>
				<p className="text-xs text-[var(--muted)] mb-3">
					<span className="text-red-400">*</span> Required fields
				</p>
				<FormLabel htmlFor="password" required>
					New password
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
				<FormLabel htmlFor="confirmPassword" required className="mt-2">
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
					{loading ? 'Saving...' : 'Reset password'}
				</button>
			</form>
		</div>
	);
}
