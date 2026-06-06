import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ResetPasswordPage } from '../ResetPasswordPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';

function renderWithRouter(initialEntry: string) {
	return render(
		withProviders(
			<MemoryRouter initialEntries={[initialEntry]}>
				<Routes>
					<Route path="/reset-password" element={<ResetPasswordPage />} />
					<Route path="/login" element={<div>Login page</div>} />
					<Route path="/forgot-password" element={<div>Forgot password page</div>} />
				</Routes>
			</MemoryRouter>,
		),
	);
}

function fillResetForm(password: string, confirmPassword: string = password) {
	const passwords = document.querySelectorAll('input[type="password"]');
	fireEvent.change(passwords[0], { target: { value: password } });
	fireEvent.change(passwords[1], { target: { value: confirmPassword } });
}

function submitForm() {
	fireEvent.submit(screen.getByRole('button', { name: /reset password/i }).closest('form')!);
}

describe('ResetPasswordPage', () => {
	it('shows invalid link message when token is missing', () => {
		renderWithRouter('/reset-password');
		expect(screen.getByText('Invalid or missing reset link.')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: /request a new link/i })).toHaveAttribute(
			'href',
			'/forgot-password',
		);
	});

	it('resets password and navigates to login', async () => {
		renderWithRouter('/reset-password?token=valid-token');
		fillResetForm('Secret123!');
		submitForm();
		await screen.findByText('Login page');
	});

	it('shows validation error for weak password', async () => {
		renderWithRouter('/reset-password?token=valid-token');
		fillResetForm('short1');
		submitForm();
		await waitFor(() => {
			expect(screen.getByText(/Password must include at least 8 characters/i)).toBeInTheDocument();
		});
	});

	it('shows validation error when passwords do not match', async () => {
		renderWithRouter('/reset-password?token=valid-token');
		fillResetForm('Secret123!', 'Secret456!');
		submitForm();
		await waitFor(() => {
			expect(screen.getAllByText('Passwords do not match').length).toBeGreaterThan(0);
		});
	});

	it('shows API error when reset fails', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/reset-password', () =>
				HttpResponse.json({ detail: 'Reset link expired' }, { status: 400 }),
			),
		);
		renderWithRouter('/reset-password?token=expired-token');
		fillResetForm('Secret123!');
		submitForm();
		await waitFor(() => {
			expect(screen.getByText('Reset link expired')).toBeInTheDocument();
		});
	});
});
