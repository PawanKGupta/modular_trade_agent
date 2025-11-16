import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage } from '../LoginPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';

function renderWithRouter(ui: React.ReactElement) {
	return render(
		withProviders(
			<MemoryRouter initialEntries={['/login']}>
				<Routes>
					<Route path="/login" element={ui} />
					<Route path="/dashboard" element={<div>Dashboard</div>} />
				</Routes>
			</MemoryRouter>,
		),
	);
}

describe('LoginPage', () => {
	it('logs in successfully and navigates to dashboard', async () => {
		// default MSW handlers return 200 and token + me
		renderWithRouter(<LoginPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'test@example.com' } });
		fireEvent.change(password, { target: { value: 'Secret123' } });
		fireEvent.click(screen.getByRole('button', { name: /login/i }));
		await screen.findByText('Dashboard');
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
	});
});


