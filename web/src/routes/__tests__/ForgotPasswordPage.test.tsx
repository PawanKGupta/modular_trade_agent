import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ForgotPasswordPage } from '../ForgotPasswordPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';

function renderWithRouter() {
	return render(
		withProviders(
			<MemoryRouter initialEntries={['/forgot-password']}>
				<Routes>
					<Route path="/forgot-password" element={<ForgotPasswordPage />} />
					<Route path="/login" element={<div>Login page</div>} />
				</Routes>
			</MemoryRouter>,
		),
	);
}

function submitForm() {
	fireEvent.submit(screen.getByRole('button', { name: /send reset link/i }).closest('form')!);
}

describe('ForgotPasswordPage', () => {
	it('shows success message after submitting a valid email', async () => {
		renderWithRouter();
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'user@example.com' },
		});
		submitForm();
		await screen.findByText(/If an account exists for that email/i);
		expect(screen.getByRole('link', { name: /back to login/i })).toHaveAttribute('href', '/login');
	});

	it('shows validation error when email is empty', async () => {
		renderWithRouter();
		submitForm();
		await waitFor(() => {
			expect(screen.getByText('Email is required')).toBeInTheDocument();
		});
	});

	it('shows validation error for invalid email', async () => {
		renderWithRouter();
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'not-an-email' },
		});
		submitForm();
		await waitFor(() => {
			expect(screen.getByText('Enter a valid email address')).toBeInTheDocument();
		});
	});

	it('shows API error when request fails', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/forgot-password', () =>
				HttpResponse.json({ detail: 'Service unavailable' }, { status: 503 }),
			),
		);
		renderWithRouter();
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'user@example.com' },
		});
		submitForm();
		await waitFor(() => {
			expect(screen.getByText('Service unavailable')).toBeInTheDocument();
		});
	});
});
