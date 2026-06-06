import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { VerifyEmailPage } from '../VerifyEmailPage';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';

function renderWithRouter(initialEntry: string) {
	return render(
		withProviders(
			<MemoryRouter initialEntries={[initialEntry]}>
				<Routes>
					<Route path="/verify-email" element={<VerifyEmailPage />} />
					<Route path="/dashboard" element={<div>Dashboard</div>} />
					<Route path="/resend-verification" element={<div>Resend page</div>} />
				</Routes>
			</MemoryRouter>,
		),
	);
}

describe('VerifyEmailPage', () => {
	it('shows error when token is missing', async () => {
		renderWithRouter('/verify-email');
		await screen.findByText('Invalid or missing verification link.');
		expect(screen.getByRole('link', { name: /resend verification email/i })).toHaveAttribute(
			'href',
			'/resend-verification',
		);
	});

	it('verifies email and navigates to dashboard', async () => {
		renderWithRouter('/verify-email?token=valid-token');
		await screen.findByText('Dashboard');
	});

	it('ignores verification result after unmount', async () => {
		let resolveVerify: () => void = () => {};
		const verifyDeferred = new Promise<void>((resolve) => {
			resolveVerify = resolve;
		});

		server.use(
			http.post('http://localhost:8000/api/v1/auth/verify-email', async () => {
				await verifyDeferred;
				return HttpResponse.json({
					access_token: 'test-token',
					refresh_token: 'refresh-token',
					token_type: 'bearer',
				});
			}),
		);

		const { unmount } = renderWithRouter('/verify-email?token=slow-token');
		expect(screen.getByText(/Verifying your email/i)).toBeInTheDocument();
		unmount();
		resolveVerify();
		await new Promise((resolve) => setTimeout(resolve, 0));
	});

	it('shows error when verification fails', async () => {
		server.use(
			http.post('http://localhost:8000/api/v1/auth/verify-email', () =>
				HttpResponse.json({ detail: 'Verification link expired' }, { status: 400 }),
			),
		);
		renderWithRouter('/verify-email?token=expired-token');
		await waitFor(() => {
			expect(screen.getByText('Verification link expired')).toBeInTheDocument();
		});
		expect(screen.getByRole('link', { name: /resend verification email/i })).toBeInTheDocument();
	});
});
