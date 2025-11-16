import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AppShell } from '../AppShell';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';

function renderAppShell() {
	return render(
		withProviders(
			<MemoryRouter initialEntries={['/dashboard']}>
				<Routes>
					<Route path="/login" element={<div>LoginForm</div>} />
					<Route path="/dashboard" element={<AppShell />}>
						<Route index element={<div>Home</div>} />
					</Route>
				</Routes>
			</MemoryRouter>,
		),
	);
}

describe('AppShell', () => {
	it('shows user email and logs out to login route', async () => {
		renderAppShell();
		// email from MSW /auth/me
		const email = await screen.findByText('test@example.com');
		expect(email).toBeInTheDocument();
		const logout = screen.getByText(/logout/i);
		fireEvent.click(logout);
		await screen.findByText('LoginForm');
	});
});


