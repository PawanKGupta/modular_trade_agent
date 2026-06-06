import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ResendVerificationPage } from '../ResendVerificationPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';

function renderWithRouter(initialEntry = '/resend-verification') {
	return render(
		withProviders(
			<MemoryRouter initialEntries={[initialEntry]}>
				<Routes>
					<Route path="/resend-verification" element={<ResendVerificationPage />} />
					<Route path="/login" element={<div>Login page</div>} />
				</Routes>
			</MemoryRouter>,
		),
	);
}

function submitForm() {
	fireEvent.submit(screen.getByRole('button', { name: /send verification email/i }).closest('form')!);
}

describe('ResendVerificationPage', () => {
	it('prefills email from query string', () => {
		renderWithRouter('/resend-verification?email=pending%40example.com');
		expect(document.querySelector('input[type="email"]')).toHaveValue('pending@example.com');
	});

	it('shows success message after submitting a valid email', async () => {
		renderWithRouter();
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'pending@example.com' },
		});
		submitForm();
		await screen.findByText(/If an account exists and is not yet verified/i);
		expect(screen.getByRole('link', { name: /back to login/i })).toHaveAttribute('href', '/login');
	});

	it('shows validation error for invalid email', async () => {
		renderWithRouter();
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'bad-email' },
		});
		submitForm();
		await waitFor(() => {
			expect(screen.getByText('Enter a valid email address')).toBeInTheDocument();
		});
	});

	it('shows API error when request fails', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/resend-verification', () =>
				HttpResponse.json({ detail: 'Too many requests' }, { status: 429 }),
			),
		);
		renderWithRouter();
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'pending@example.com' },
		});
		submitForm();
		await waitFor(() => {
			expect(screen.getByText('Too many requests')).toBeInTheDocument();
		});
	});
});
