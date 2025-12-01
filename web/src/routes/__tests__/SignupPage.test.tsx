import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SignupPage } from '../SignupPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';

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
	it('signs up successfully and navigates to dashboard', async () => {
		renderWithRouter(<SignupPage />);
		const email = document.querySelector('input[type="email"]') as HTMLInputElement;
		const name = document.querySelector('input[type="text"]') as HTMLInputElement;
		const password = document.querySelector('input[type="password"]') as HTMLInputElement;
		fireEvent.change(email, { target: { value: 'new@example.com' } });
		fireEvent.change(name, { target: { value: 'New User' } });
		fireEvent.change(password, { target: { value: 'Secret123' } });
		fireEvent.click(screen.getByRole('button', { name: /sign up/i }));
		await screen.findByText('Dashboard');
	});

	// Additional error path tests can be added by asserting non-navigation or error banners if UI changes
});
