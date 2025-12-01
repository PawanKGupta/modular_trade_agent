import { FormEvent, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { signup } from '@/api/auth';
import { useSessionStore } from '@/state/sessionStore';

export function SignupPage() {
	const navigate = useNavigate();
	const setSession = useSessionStore((s) => s.setSession);
	const [email, setEmail] = useState('');
	const [name, setName] = useState('');
	const [password, setPassword] = useState('');
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	async function onSubmit(e: FormEvent) {
		e.preventDefault();
		setError(null);
		setLoading(true);
		try {
			await signup(email, password, name);
			await useSessionStore.getState().refresh();
			setSession(useSessionStore.getState().user);
			navigate('/dashboard');
		} catch (err: any) {
			setError(err?.response?.data?.detail ?? 'Signup failed');
		} finally {
			setLoading(false);
		}
	}

	return (
		<div className="min-h-screen flex items-center justify-center p-4">
			<form onSubmit={onSubmit} className="w-full max-w-sm bg-[var(--panel)] p-6 rounded-md shadow">
				<h1 className="text-xl font-semibold mb-4">Create account</h1>
				<label className="block text-sm mb-1" htmlFor="email">Email</label>
				<input id="email" name="email" className="w-full mb-3 p-2 rounded bg-[#0f1720] border border-[#1e293b]" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
				<label className="block text-sm mb-1" htmlFor="name">Name</label>
				<input id="name" name="name" className="w-full mb-3 p-2 rounded bg-[#0f1720] border border-[#1e293b]" value={name} onChange={(e) => setName(e.target.value)} type="text" />
				<label className="block text-sm mb-1" htmlFor="password">Password</label>
				<input id="password" name="password" className="w-full mb-4 p-2 rounded bg-[#0f1720] border border-[#1e293b]" value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
				{error && <div className="text-red-400 text-sm mb-3">{error}</div>}
				<button disabled={loading} className="w-full bg-[var(--accent)] text-black py-2 rounded disabled:opacity-60">{loading ? 'Creating...' : 'Sign up'}</button>
				<div className="mt-3 text-sm text-[var(--muted)]">
					Have an account? <Link to="/login" className="text-[var(--accent)]">Login</Link>
				</div>
			</form>
		</div>
	);
}
