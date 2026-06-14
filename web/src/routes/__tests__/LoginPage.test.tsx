import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage } from '../LoginPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';
import { APP_VERSION } from '@/appVersion';
import { saveLoginLockout } from '@/utils/loginLockout';

function renderWithRouter(ui: React.ReactElement) {
	return render(
		withProviders(
			<MemoryRouter initialEntries={['/login']}>
				<Routes>
					<Route path="/login" element={ui} />
					<Route path="/forgot-password" element={<div>Forgot password page</div>} />
					<Route path="/dashboard" element={<div>Dashboard</div>} />
				</Routes>
			</MemoryRouter>,
		),
	);
}

describe('LoginPage', () => {
	afterEach(() => {
		vi.useRealTimers();
		sessionStorage.clear();
	});

	it('shows product branding and version', () => {
		renderWithRouter(<LoginPage />);
		expect(screen.getByText('Rebound')).toBeInTheDocument();
		expect(screen.getByText('Modular Trade Agent')).toBeInTheDocument();
		expect(screen.getByText(`v${APP_VERSION}`)).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: /resend verification email/i })).not.toBeInTheDocument();
	});

	it('shows forgot password link', () => {
		renderWithRouter(<LoginPage />);
		expect(screen.getByRole('link', { name: /forgot password/i })).toHaveAttribute(
			'href',
			'/forgot-password',
		);
	});

	it('shows help center link', () => {
		renderWithRouter(<LoginPage />);
		expect(screen.getByRole('link', { name: /help & setup guide/i })).toHaveAttribute('href', '/help');
	});

	it('toggles password visibility with Show/Hide', () => {
		renderWithRouter(<LoginPage />);
		const password = document.getElementById('password') as HTMLInputElement;
		expect(password.type).toBe('password');
		fireEvent.click(screen.getByRole('button', { name: /show password/i }));
		expect(password.type).toBe('text');
		fireEvent.click(screen.getByRole('button', { name: /hide password/i }));
		expect(password.type).toBe('password');
	});

	it('logs in successfully and navigates to dashboard', async () => {
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'test@example.com' } });
		fireEvent.change(password, { target: { value: 'Secret123' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));
		await screen.findByText('Dashboard');
	});

	it('shows validation errors when required fields are empty on submit', async () => {
		renderWithRouter(<LoginPage />);
		fireEvent.submit(screen.getByRole('button', { name: /login/i }).closest('form')!);
		await waitFor(() => {
			expect(screen.getByText('Email is required')).toBeInTheDocument();
		});
	});

	it('shows error on invalid credentials', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/login', async () =>
				new HttpResponse(JSON.stringify({ detail: 'Invalid credentials' }), {
					status: 401,
					headers: { 'Content-Type': 'application/json' },
				}),
			),
		);
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'bad@example.com' } });
		fireEvent.change(password, { target: { value: 'wrong' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));
		await waitFor(() => expect(screen.getByText(/invalid credentials|login failed/i)).toBeInTheDocument());
		expect(screen.queryByRole('link', { name: /resend verification email/i })).not.toBeInTheDocument();
	});

	it('shows pre-lockout warning with invalid credentials after repeated failures', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/login', async () =>
				new HttpResponse(
					JSON.stringify({
						detail: {
							message: 'Invalid credentials',
							warning:
								'Multiple failed login attempts. Your account may be temporarily locked if this continues.',
						},
					}),
					{
						status: 401,
						headers: { 'Content-Type': 'application/json' },
					},
				),
			),
		);
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'user@example.com' } });
		fireEvent.change(password, { target: { value: 'wrong' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));

		await waitFor(() => {
			expect(screen.getByRole('alert')).toHaveTextContent(/invalid credentials/i);
			expect(screen.getByText(/temporarily locked/i)).toBeInTheDocument();
		});
	});

	it('shows lockout countdown and disables login when rate limited', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/login', async () =>
				new HttpResponse(
					JSON.stringify({
						detail: {
							message: 'Too many login attempts. Please wait before trying again.',
							retry_after_seconds: 305,
						},
					}),
					{
						status: 429,
						headers: { 'Content-Type': 'application/json', 'Retry-After': '305' },
					},
				),
			),
		);
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'locked@example.com' } });
		fireEvent.change(password, { target: { value: 'Secret123!' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));

		await waitFor(() => {
			expect(screen.getByRole('alert')).toHaveTextContent(/please wait before trying again/i);
			expect(screen.getByRole('alert')).toHaveTextContent(/5:05/);
		});
		expect(screen.getByRole('button', { name: /login temporarily locked/i })).toBeDisabled();
		expect(screen.queryByRole('link', { name: /resend verification email/i })).not.toBeInTheDocument();
	});

	it('restores lockout from session storage when email matches', async () => {
		saveLoginLockout('held@example.com', 90);
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'held@example.com' } });

		await waitFor(() => {
			expect(screen.getByRole('button', { name: /login temporarily locked/i })).toBeDisabled();
			expect(screen.getByRole('alert')).toHaveTextContent(/please wait before trying again/i);
		});
	});

	it('shows rate limit error without countdown when retry_after is missing', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/login', async () =>
				new HttpResponse(
					JSON.stringify({
						detail: {
							message: 'Too many login attempts. Please wait before trying again.',
						},
					}),
					{
						status: 429,
						headers: { 'Content-Type': 'application/json' },
					},
				),
			),
		);
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'limited@example.com' } });
		fireEvent.change(password, { target: { value: 'Secret123!' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));

		await waitFor(() => {
			expect(screen.getByRole('alert')).toHaveTextContent(/please wait before trying again/i);
		});
		expect(screen.getByRole('button', { name: /^login$/i })).toBeEnabled();
	});

	it('clears lockout countdown when stored lockout expires', async () => {
		vi.useFakeTimers();
		saveLoginLockout('held@example.com', 2);
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;

		await act(async () => {
			fireEvent.change(email, { target: { value: 'held@example.com' } });
		});

		expect(screen.getByRole('button', { name: /login temporarily locked/i })).toBeDisabled();

		await act(async () => {
			await vi.advanceTimersByTimeAsync(2500);
		});

		expect(screen.getByRole('button', { name: /^login$/i })).toBeEnabled();
	});

	it('shows resend verification link after unverified email login error', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/login', async () =>
				new HttpResponse(
					JSON.stringify({
						detail:
							'Please verify your email before logging in. Check your inbox or request a new verification link.',
					}),
					{
						status: 403,
						headers: { 'Content-Type': 'application/json' },
					},
				),
			),
		);
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'pending@example.com' } });
		fireEvent.change(password, { target: { value: 'Secret123!' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));

		await waitFor(() => {
			expect(screen.getByRole('link', { name: /resend verification email/i })).toBeInTheDocument();
		});
		expect(screen.getByRole('link', { name: /resend verification email/i })).toHaveAttribute(
			'href',
			'/resend-verification?email=pending%40example.com',
		);
	});

	it('handles MFA challenge requirement during login and logs in successfully', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/login', async () =>
				new HttpResponse(
					JSON.stringify({
						mfa_required: true,
						mfa_token: 'mfa-test-token',
					}),
					{
						status: 200,
						headers: { 'Content-Type': 'application/json' },
					},
				),
			),
			http.post('http://localhost:8000/api/v1/auth/mfa/login', async () =>
				new HttpResponse(
					JSON.stringify({
						access_token: 'test-mfa-access-token',
						refresh_token: 'test-mfa-refresh-token',
						token_type: 'bearer',
					}),
					{
						status: 200,
						headers: { 'Content-Type': 'application/json' },
					},
				),
			),
		);

		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'mfa@example.com' } });
		fireEvent.change(password, { target: { value: 'Secret123!' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));

		// It should switch to MFA screen
		await screen.findByText('Two-factor authentication');
		expect(screen.getByLabelText(/Authenticator code/i)).toBeInTheDocument();

		const codeInput = screen.getByPlaceholderText('000000') as HTMLInputElement;
		fireEvent.change(codeInput, { target: { value: '123456' } });
		fireEvent.click(screen.getByRole('button', { name: /verify/i }));

		await screen.findByText('Dashboard');
	});

	it('shows error on invalid MFA code during verification', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/login', async () =>
				new HttpResponse(
					JSON.stringify({
						mfa_required: true,
						mfa_token: 'mfa-test-token',
					}),
					{
						status: 200,
						headers: { 'Content-Type': 'application/json' },
					},
				),
			),
			http.post('http://localhost:8000/api/v1/auth/mfa/login', async () =>
				new HttpResponse(
					JSON.stringify({
						detail: 'Invalid MFA code',
					}),
					{
						status: 400,
						headers: { 'Content-Type': 'application/json' },
					},
				),
			),
		);

		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'mfa-fail@example.com' } });
		fireEvent.change(password, { target: { value: 'Secret123!' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));

		await screen.findByText('Two-factor authentication');
		const codeInput = screen.getByPlaceholderText('000000') as HTMLInputElement;
		fireEvent.change(codeInput, { target: { value: '111111' } });
		fireEvent.click(screen.getByRole('button', { name: /verify/i }));

		await screen.findByText(/invalid mfa code/i);
	});

	it('allows going back to login screen from MFA prompt', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/login', async () =>
				new HttpResponse(
					JSON.stringify({
						mfa_required: true,
						mfa_token: 'mfa-test-token',
					}),
					{
						status: 200,
						headers: { 'Content-Type': 'application/json' },
					},
				),
			),
		);

		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'mfa-back@example.com' } });
		fireEvent.change(password, { target: { value: 'Secret123!' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));

		await screen.findByText('Two-factor authentication');
		fireEvent.click(screen.getByRole('button', { name: /back to login/i }));

		// Should be back to login screen
		expect(screen.getByRole('button', { name: /^login$/i })).toBeInTheDocument();
	});
});
