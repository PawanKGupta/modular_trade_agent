import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage } from '../LoginPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';
import { APP_VERSION } from '@/appVersion';

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
});
