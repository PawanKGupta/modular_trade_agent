import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { verifyEmail } from '@/api/auth';
import { BrandMark } from '@/components/BrandMark';
import { useSessionStore } from '@/state/sessionStore';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';

export function VerifyEmailPage() {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();
	const token = useMemo(() => searchParams.get('token') ?? '', [searchParams]);
	const setSession = useSessionStore((s) => s.setSession);
	const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
	const [message, setMessage] = useState<string | null>(null);

	useEffect(() => {
		if (!token) {
			setStatus('error');
			setMessage('Invalid or missing verification link.');
			return;
		}
		let cancelled = false;
		verifyEmail(token)
			.then(async () => {
				if (cancelled) {
					return;
				}
				await useSessionStore.getState().refresh();
				setSession(useSessionStore.getState().user);
				setStatus('success');
				setMessage('Your email has been verified. Redirecting to dashboard...');
				navigate('/dashboard');
			})
			.catch((err: unknown) => {
				if (!cancelled) {
					setStatus('error');
					setMessage(getApiErrorMessage(err, 'Verification failed'));
				}
			});
		return () => {
			cancelled = true;
		};
	}, [token, navigate, setSession]);

	return (
		<div className="min-h-screen flex items-center justify-center p-2 sm:p-4">
			<div className="w-full max-w-sm bg-[var(--panel)] p-4 sm:p-6 rounded-md shadow">
				<header className="mb-4 sm:mb-5 pb-4 sm:pb-5 border-b border-[#1e293b]/50">
					<BrandMark />
				</header>
				<h1 className="text-lg sm:text-xl font-semibold mb-3 sm:mb-4">Email verification</h1>
				{status === 'loading' && <p className="text-sm text-[var(--muted)]">Verifying your email...</p>}
				{status === 'success' && (
					<div className="text-sm">
						<p className="text-green-400 mb-4">{message}</p>
						<Link to="/dashboard" className="text-[var(--accent)]">
							Continue to dashboard
						</Link>
					</div>
				)}
				{status === 'error' && (
					<div className="text-sm">
						<p className="text-red-400 mb-4">{message}</p>
						<Link to="/resend-verification" className="text-[var(--accent)]">
							Resend verification email
						</Link>
					</div>
				)}
			</div>
		</div>
	);
}
