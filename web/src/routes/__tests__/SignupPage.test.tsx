import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SignupPage } from '../SignupPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';
import { APP_VERSION } from '@/appVersion';

function renderWithRouter(ui: React.ReactElement) {
	return render(
		withProviders(
			<MemoryRouter initialEntries={['/signup']}>
				<Routes>
					<Route path="/signup" element={ui} />
					<Route path="/dashboard" element={<div>Dashboard</div>} />
				</Routes>
			</MemoryRouter>,
		),
	);
}

function getSignupForm() {
	return screen.getByRole('button', { name: /sign up/i }).closest('form')!;
}

function submitSignupForm() {
	fireEvent.submit(getSignupForm());
}

function fillSignupForm(options: {
	email?: string;
	name?: string;
	mobile?: string;
	password?: string;
	confirmPassword?: string;
} = {}) {
	const email = options.email ?? 'new@example.com';
	const name = options.name ?? 'New User';
	const mobile = options.mobile ?? '';
	const password = options.password ?? 'Secret123!';
	const confirmPassword = options.confirmPassword ?? password;

	fireEvent.change(document.querySelector('input[type="email"]')!, {
		target: { value: email },
	});
	fireEvent.change(document.getElementById('name')!, {
		target: { value: name },
	});
	if (mobile) {
		fireEvent.change(document.getElementById('mobile')!, {
			target: { value: mobile },
		});
	}
	const passwords = document.querySelectorAll('input[type="password"]');
	fireEvent.change(passwords[0], { target: { value: password } });
	fireEvent.change(passwords[1], { target: { value: confirmPassword } });
}

describe('SignupPage', () => {
	it('shows product branding and version', () => {
		renderWithRouter(<SignupPage />);
		expect(screen.getByText('Rebound')).toBeInTheDocument();
		expect(screen.getByText('Modular Trade Agent')).toBeInTheDocument();
		expect(screen.getByText(`v${APP_VERSION}`)).toBeInTheDocument();
	});

	it('shows check your email after successful signup', async () => {
		renderWithRouter(<SignupPage />);
		fillSignupForm();
		submitSignupForm();
		await screen.findByRole('heading', { name: /check your email/i });
		expect(screen.getByText(/We sent a verification link to/i)).toBeInTheDocument();
	});

	it('shows validation error for invalid email on submit', async () => {
		renderWithRouter(<SignupPage />);
		fillSignupForm({ email: 'not-an-email', name: 'New User' });
		submitSignupForm();
		await waitFor(() => {
			expect(screen.getByText('Enter a valid email address')).toBeInTheDocument();
		});
	});

	it('shows green tick when email is valid', async () => {
		renderWithRouter(<SignupPage />);
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'user@example.com' },
		});
		await waitFor(() => {
			expect(screen.getByLabelText('Valid email address')).toBeInTheDocument();
		});
	});

	it('shows validation error when name is empty', async () => {
		renderWithRouter(<SignupPage />);
		fillSignupForm({ name: '' });
		submitSignupForm();
		await waitFor(() => {
			expect(screen.getByText('Name is required')).toBeInTheDocument();
		});
	});

	it('shows validation error for weak password', async () => {
		renderWithRouter(<SignupPage />);
		fillSignupForm({ password: 'short1', confirmPassword: 'short1' });
		submitSignupForm();
		await waitFor(() => {
			expect(screen.getByText(/Password must include at least 8 characters/i)).toBeInTheDocument();
		});
	});

	it('shows signup error when API rejects', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/signup', () =>
				HttpResponse.json({ detail: 'Email already registered' }, { status: 400 }),
			),
		);

		renderWithRouter(<SignupPage />);
		fillSignupForm({ email: 'dup@example.com' });
		submitSignupForm();

		await waitFor(() => {
			expect(screen.getByText('Email already registered')).toBeInTheDocument();
		});
	});

	it('includes optional mobile in signup request', async () => {
		let capturedBody: Record<string, string> | null = null;
		server.use(
			http.post('http://localhost:8000/api/v1/auth/signup', async ({ request }) => {
				capturedBody = (await request.json()) as Record<string, string>;
				return HttpResponse.json({
					message: 'Account created. Check your email and click the verification link before logging in.',
				});
			}),
		);

		renderWithRouter(<SignupPage />);
		fillSignupForm({ mobile: '9876543210' });
		submitSignupForm();

		await screen.findByRole('heading', { name: /check your email/i });
		expect(capturedBody?.mobile_number).toBe('9876543210');
	});

	it('shows validation error for invalid mobile', async () => {
		renderWithRouter(<SignupPage />);
		fillSignupForm({ mobile: '12345' });
		submitSignupForm();
		await waitFor(() => {
			expect(screen.getByText(/10-digit Indian mobile/i)).toBeInTheDocument();
		});
	});
});
