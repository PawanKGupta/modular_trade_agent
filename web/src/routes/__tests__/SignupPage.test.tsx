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

describe('SignupPage', () => {
	it('shows product branding and version', () => {
		renderWithRouter(<SignupPage />);
		expect(screen.getByText('Rebound')).toBeInTheDocument();
		expect(screen.getByText('Modular Trade Agent')).toBeInTheDocument();
		expect(screen.getByText(`v${APP_VERSION}`)).toBeInTheDocument();
	});

	it('signs up successfully and navigates to dashboard', async () => {
		renderWithRouter(<SignupPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const name = document.querySelector('input[type="text"]') as HTMLInputElement;
		const passwords = document.querySelectorAll('input[type="password"]');
		fireEvent.change(email, { target: { value: 'new@example.com' } });
		fireEvent.change(name, { target: { value: 'New User' } });
		fireEvent.change(passwords[0], { target: { value: 'Secret123' } });
		fireEvent.change(passwords[1], { target: { value: 'Secret123' } });
		fireEvent.click(screen.getByRole('button', { name: /sign up/i }));
		await screen.findByText('Dashboard');
	});

	it('shows validation error for weak password', async () => {
		renderWithRouter(<SignupPage />);
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'new@example.com' },
		});
		const passwords = document.querySelectorAll('input[type="password"]');
		fireEvent.change(passwords[0], { target: { value: 'short1' } });
		fireEvent.change(passwords[1], { target: { value: 'short1' } });
		fireEvent.click(screen.getByRole('button', { name: /sign up/i }));
		await waitFor(() => {
			expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
		});
	});

	it('shows signup error when API rejects', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/signup', () =>
				HttpResponse.json({ detail: 'Email already registered' }, { status: 400 })
			)
		);

		renderWithRouter(<SignupPage />);
		fireEvent.change(document.querySelector('input[type="email"]')!, {
			target: { value: 'dup@example.com' },
		});
		const passwords = document.querySelectorAll('input[type="password"]');
		fireEvent.change(passwords[0], { target: { value: 'Secret123' } });
		fireEvent.change(passwords[1], { target: { value: 'Secret123' } });
		fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

		await waitFor(() => {
			expect(screen.getByText('Email already registered')).toBeInTheDocument();
		});
	});
});
